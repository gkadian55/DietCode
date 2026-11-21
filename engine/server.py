import asyncio
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Ensure both workspace root and engine directory are in sys.path
ENGINE_DIR = Path(__file__).resolve().parent
ROOT_DIR = ENGINE_DIR.parent
for p in [str(ENGINE_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
import stripe
from stripe._util import convert_to_dict
from clerk_backend_api import Clerk
from clerk_backend_api.security import TokenVerificationError, VerifyTokenOptions, verify_token

try:
    from database import SessionLocal, initialize_database
    from executor import (
        DAGExecutor,
        ExecutionSettings,
        LOCAL_MODEL,
        OLLAMA_API_BASE,
        PRIMARY_MODEL,
    )
    from exporter import ProjectExporter
    from models.billing import (
        ExecutionLog,
        PaymentTransaction,
        User,
        allocate_charged_costs,
        calculate_credit_amount,
        calculate_task_cost,
        reserve_balance,
        settle_reserved_balance,
    )
    from models.planner import DAGPlanner
    from models.token_forecaster import MODEL_PROFILES, TokenForecaster
    from openrouter_catalog import CATALOG_REFRESH_SECONDS, APPROVED_OPENROUTER_MODELS, catalog
except ImportError:
    from engine.database import SessionLocal, initialize_database
    from engine.executor import (
        DAGExecutor,
        ExecutionSettings,
        LOCAL_MODEL,
        OLLAMA_API_BASE,
        PRIMARY_MODEL,
    )
    from engine.exporter import ProjectExporter
    from engine.models.billing import (
        ExecutionLog,
        PaymentTransaction,
        User,
        allocate_charged_costs,
        calculate_credit_amount,
        calculate_task_cost,
        reserve_balance,
        settle_reserved_balance,
    )
    from engine.models.planner import DAGPlanner
    from engine.models.token_forecaster import MODEL_PROFILES, TokenForecaster
    from engine.openrouter_catalog import (
        CATALOG_REFRESH_SECONDS,
        APPROVED_OPENROUTER_MODELS,
        catalog,
    )

app = FastAPI(title="DietCode ML Engine", version="1.0.0")

# Only the local Vite/Electron development origins may call the API.
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "DIETCODE_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_clerk_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Verify a Clerk session token and return its claims."""
    secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(
            status_code=503,
            detail="Clerk authentication is not configured",
        )
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        claims = verify_token(
            token.strip(),
            VerifyTokenOptions(secret_key=secret_key),
        )
    except TokenVerificationError as err:
        print(f"[Auth] Clerk token rejected: {err.reason.value[0]}")
        raise HTTPException(status_code=401, detail="Invalid authentication token") from err

    clerk_user_id = claims.get("sub")
    if not isinstance(clerk_user_id, str) or not clerk_user_id:
        raise HTTPException(status_code=401, detail="Authentication token has no user")
    return claims


def _clerk_user_email(clerk_user: Any, clerk_user_id: str) -> str:
    email_addresses = getattr(clerk_user, "email_addresses", []) or []
    primary_id = getattr(clerk_user, "primary_email_address_id", None)
    for address in email_addresses:
        address_id = getattr(address, "id", None)
        email = getattr(address, "email_address", None)
        if email and (primary_id is None or address_id == primary_id):
            return email.strip().lower()
    for address in email_addresses:
        email = getattr(address, "email_address", None)
        if email:
            return email.strip().lower()
    return f"{clerk_user_id}@clerk.local"


def get_current_user(
    claims: dict[str, Any] = Depends(get_current_clerk_user),
) -> dict[str, Any]:
    """Resolve the verified Clerk identity to a Neon billing account."""
    clerk_user_id = claims["sub"]
    with SessionLocal() as session:
        user = (
            session.query(User)
            .filter(User.clerk_user_id == clerk_user_id)
            .one_or_none()
        )
        if user is None:
            try:
                clerk_user = Clerk(
                    bearer_auth=os.getenv("CLERK_SECRET_KEY", "").strip()
                ).users.get(user_id=clerk_user_id)
            except Exception as err:
                raise HTTPException(
                    status_code=502,
                    detail="Could not retrieve the authenticated Clerk user",
                ) from err

            email = _clerk_user_email(clerk_user, clerk_user_id)
            user = session.query(User).filter(User.email == email).one_or_none()
            if user is not None:
                if user.clerk_user_id and user.clerk_user_id != clerk_user_id:
                    raise HTTPException(
                        status_code=409,
                        detail="This email is already linked to another account",
                    )
                user.clerk_user_id = clerk_user_id
            else:
                user = User(
                    email=email,
                    clerk_user_id=clerk_user_id,
                    credit_balance=Decimal("0"),
                )
                session.add(user)
            try:
                session.commit()
            except IntegrityError as err:
                session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="Could not link the Clerk account",
                ) from err
            session.refresh(user)
        return {
            "id": user.id,
            "clerk_user_id": user.clerk_user_id,
            "email": user.email,
        }


# Initialize ML models
print("[Server] Initializing DietCode ML Engine & Self-Trained Regressors...")
forecaster = TokenForecaster()
planner = DAGPlanner(forecaster)
initialize_database()
print("[Server] ML Engine ready!")


async def _refresh_openrouter_catalog() -> None:
    """Refresh pricing in a worker thread so the event loop stays responsive."""
    while True:
        await asyncio.to_thread(catalog.refresh)
        await asyncio.sleep(CATALOG_REFRESH_SECONDS)


@app.on_event("startup")
async def start_openrouter_catalog() -> None:
    app.state.openrouter_catalog_task = asyncio.create_task(_refresh_openrouter_catalog())


@app.on_event("shutdown")
async def stop_openrouter_catalog() -> None:
    task = getattr(app.state, "openrouter_catalog_task", None)
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


class DecomposeRequest(BaseModel):
    goal: str


class PredictNodeRequest(BaseModel):
    title: str
    description: str = ""
    upstream_count: int | None = 0
    depth: int | None = 1


class ReplanRequest(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    credit_balance: float = Field(default=10.0, ge=0)


class ExecuteRequest(BaseModel):
    graph: dict[str, dict[str, Any]]
    max_concurrency: int = Field(default=8, ge=1, le=32)
    request_timeout: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=1, ge=0, le=5)
    mode: str = "hybrid"
    primary_model: str = PRIMARY_MODEL
    local_model: str = LOCAL_MODEL
    allow_fallback: bool = True
    max_context_chars: int = 12000


class ExportRequest(BaseModel):
    goal: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]] | None = []
    aggregates: dict[str, Any] | None = {}


class CreateCheckoutRequest(BaseModel):
    amount_inr: Decimal = Field(default=Decimal("500.00"), gt=0, le=Decimal("100000.00"))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "DietCode ML Engine",
        "modelLoaded": forecaster.model is not None,
        "supportedModels": list(MODEL_PROFILES.keys())
    }


@app.get("/api/model-profiles")
def get_model_profiles():
    return MODEL_PROFILES


@app.get("/api/providers")
def get_providers(_current_user: dict[str, Any] = Depends(get_current_clerk_user)):
    """Return provider availability and approved cloud model status."""
    cloud_models = {}
    for key, model_id in APPROVED_OPENROUTER_MODELS.items():
        model = catalog.get(key)
        cloud_models[key] = {
            "openrouterId": model_id,
            "available": model is not None,
            "inputPricePerMillion": str(model.input_price_per_million) if model else None,
            "outputPricePerMillion": str(model.output_price_per_million) if model else None,
        }
    return {
        "providers": [
            {
                "id": "ollama",
                "available": DAGExecutor._is_ollama_online(),
                "model": LOCAL_MODEL,
                "apiBase": OLLAMA_API_BASE,
            },
            {
                "id": "openrouter",
                "available": bool(os.getenv("OPENROUTER_API_KEY", "").strip())
                and any(model["available"] for model in cloud_models.values()),
                "models": cloud_models,
                "lastRefresh": catalog.last_refresh,
            },
        ]
    }


@app.post("/api/users", status_code=201)
def create_user(
    req: CreateUserRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
):
    """Create a local development user with an initial credit balance."""
    email = req.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    with SessionLocal() as session:
        user = User(email=email, credit_balance=req.credit_balance)
        session.add(user)
        try:
            session.commit()
        except IntegrityError as err:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="A user with this email already exists",
            ) from err
        session.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "credit_balance": user.credit_balance,
            "created_at": user.created_at,
        }


@app.get("/api/billing/balance")
def get_user_balance(current_user: dict[str, Any] = Depends(get_current_user)):
    """Return the authenticated user's current credit balance."""
    user_id = current_user["id"]
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "user_id": user.id,
            "email": user.email,
            "credit_balance": user.credit_balance,
        }


@app.get("/api/billing/executions")
def get_user_executions(current_user: dict[str, Any] = Depends(get_current_user)):
    """Return execution history for the authenticated user."""
    user_id = current_user["id"]
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        logs = (
            session.query(ExecutionLog)
            .filter(ExecutionLog.user_id == user_id)
            .order_by(ExecutionLog.created_at.desc(), ExecutionLog.id.desc())
            .all()
        )
        return {
            "user_id": user_id,
            "executions": [
                {
                    "id": log.id,
                    "task_name": log.task_name,
                    "model_used": log.model_used,
                    "input_tokens": log.input_tokens,
                    "output_tokens": log.output_tokens,
                    "cost_deducted": log.cost_deducted,
                    "status": log.status,
                    "created_at": log.created_at,
                }
                for log in logs
            ],
        }


def _stripe_config() -> tuple[str, Decimal]:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
                raise HTTPException(status_code=503, detail="Stripe payments are not configured")
    try:
                inr_per_usd = Decimal(os.getenv("INR_PER_USD", "100").strip())
    except (InvalidOperation, ValueError):
                raise HTTPException(status_code=500, detail="INR_PER_USD must be a positive number")
    if inr_per_usd <= 0:
                raise HTTPException(status_code=500, detail="INR_PER_USD must be positive")
    return secret_key, inr_per_usd


@app.post("/api/billing/checkout")
def create_checkout_session(
    req: CreateCheckoutRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Create a Stripe test/live Checkout session for a credit top-up."""
    secret_key, inr_per_usd = _stripe_config()
    with SessionLocal() as session:
                user = session.get(User, current_user["id"])
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found")

    stripe.api_key = secret_key
    amount_inr = req.amount_inr.quantize(Decimal("0.01"))
    credit_usd = calculate_credit_amount(amount_inr, inr_per_usd)
    try:
                checkout = stripe.checkout.Session.create(
                    mode="payment",
                    line_items=[{
                        "price_data": {
                            "currency": "inr",
                            "unit_amount": int(amount_inr * 100),
                            "product_data": {
                                "name": "DietCode Credits",
                                "description": f"${credit_usd} execution balance",
                            },
                        },
                        "quantity": 1,
                    }],
                    metadata={
                        "user_id": str(current_user["id"]),
                        "amount_inr": str(amount_inr),
                        "credit_usd": str(credit_usd),
                        "inr_per_usd": str(inr_per_usd),
                    },
                    success_url=os.getenv(
                        "STRIPE_SUCCESS_URL",
                        "http://127.0.0.1:5173/?payment=success",
                    ),
                    cancel_url=os.getenv(
                        "STRIPE_CANCEL_URL",
                        "http://127.0.0.1:5173/?payment=cancelled",
                    ),
                )
    except stripe.error.StripeError as err:
                raise HTTPException(status_code=502, detail="Stripe checkout creation failed") from err
    return {
                "checkout_url": checkout.url,
                "session_id": checkout.id,
                "publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
                "amount_inr": amount_inr,
                "credit_usd": credit_usd,
                "inr_per_usd": inr_per_usd,
    }


@app.post("/api/billing/stripe/webhook")
async def stripe_webhook(request: Request):
    """Verify Stripe events and credit a user exactly once."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
                raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
                raise HTTPException(status_code=400, detail="Missing Stripe signature")
    try:
                event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as err:
                raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from err

    event_data = convert_to_dict(event)
    if event_data["type"] != "checkout.session.completed":
                return {"received": True, "processed": False}

    checkout = event_data["data"]["object"]
    if checkout.get("payment_status") != "paid":
                return {"received": True, "processed": False}
    metadata = checkout.get("metadata") or {}
    try:
                user_id = int(metadata["user_id"])
                amount_inr = Decimal(metadata["amount_inr"])
                credit_usd = Decimal(metadata["credit_usd"])
                inr_per_usd = Decimal(metadata["inr_per_usd"])
    except (KeyError, TypeError, ValueError, InvalidOperation) as err:
                raise HTTPException(status_code=400, detail="Invalid payment metadata") from err

    with SessionLocal() as session:
                if session.query(PaymentTransaction).filter_by(
                    provider_event_id=event_data["id"],
                ).first():
                    return {"received": True, "processed": False, "duplicate": True}
                user = session.get(User, user_id)
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found")
                user.credit_balance += credit_usd
                session.add(PaymentTransaction(
                    user_id=user_id,
                    provider_event_id=event_data["id"],
                    checkout_session_id=checkout["id"],
                    amount_inr=amount_inr,
                    credit_usd=credit_usd,
                    inr_per_usd=inr_per_usd,
                    status="paid",
                ))
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    return {"received": True, "processed": False, "duplicate": True}
    return {"received": True, "processed": True, "credit_usd": credit_usd}
def _estimate_graph_cost(req: ExecuteRequest) -> Decimal:
    """Estimate the graph cost before starting paid provider requests."""
    if req.mode == "ollama_only":
        return Decimal("0")

    estimated_cost = Decimal("0")
    for task in req.graph.values():
        prompt = str(task.get("prompt") or "")
        forecast = forecaster.forecast_node(
            title=prompt[:120],
            description=prompt,
            upstream_count=len(task.get("depends_on") or []),
            depth=1,
        )
        if req.mode in {"selected", "openrouter_only"}:
            routed_model = req.primary_model
        else:
            routed_model = DAGExecutor._route_model(
                str(task.get("model") or req.primary_model),
                prompt,
                ExecutionSettings(
                    mode=req.mode,
                    primary_model=req.primary_model,
                    local_model=req.local_model,
                    allow_fallback=req.allow_fallback,
                    max_context_chars=req.max_context_chars,
                    request_timeout=req.request_timeout,
                    max_retries=req.max_retries,
                ),
            )
        if not routed_model.startswith("ollama/") and catalog.get(routed_model) is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"OpenRouter model {routed_model} is unavailable or its pricing "
                    "catalog is stale. Ollama-only execution remains available."
                ),
            )
        estimated_cost += calculate_task_cost(
            routed_model,
            forecast["predictedTokens"]["input"],
            forecast["predictedTokens"]["output"],
        )
    return estimated_cost


def _refund_execution_reservation(
    user_id: int | None,
    reserved_cost: Decimal,
) -> None:
    """Release a reservation when execution fails before settlement."""
    if user_id is None or reserved_cost <= 0:
        return
    with SessionLocal() as session:
        settle_reserved_balance(session, user_id, reserved_cost, Decimal("0"))
        session.commit()


@app.post("/api/decompose")
def decompose_goal(
    req: DecomposeRequest,
    _current_user: dict[str, Any] = Depends(get_current_clerk_user),
):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    return planner.decompose_goal(req.goal)


@app.post("/api/predict-node")
def predict_node(
    req: PredictNodeRequest,
    _current_user: dict[str, Any] = Depends(get_current_clerk_user),
):
    return forecaster.forecast_node(
        title=req.title,
        description=req.description,
        upstream_count=req.upstream_count or 0,
        depth=req.depth or 1
    )


@app.post("/api/replan")
def replan_graph(
    req: ReplanRequest,
    _current_user: dict[str, Any] = Depends(get_current_clerk_user),
):
    """Recomputes aggregates, critical path, and model trade-offs when users add/edit/delete nodes or edges."""
    try:
        aggregates = planner.calculate_graph_aggregates(req.nodes)
        return {
            "status": "success",
            "aggregates": aggregates
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.post("/api/execute")
async def execute_graph(
    req: ExecuteRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Execute the frontend DAG and return generated text plus token telemetry."""
    try:
        user_id = current_user["id"]
        estimated_cost = Decimal("0")
        funds_reserved = False
        if user_id is not None:
            with SessionLocal() as session:
                user = session.get(User, user_id)
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found")
                estimated_cost = _estimate_graph_cost(req)
                funds_reserved = reserve_balance(session, user_id, estimated_cost)
                if not funds_reserved:
                    session.rollback()
                    session.refresh(user)
                    return {
                        "status": "insufficient_funds",
                        "results": {
                            task_id: {
                                "status": "insufficient_funds",
                                "execution_mode": "blocked",
                                "text": "",
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0,
                                "model": task.get("model"),
                                "routed_model": None,
                                "error_category": "insufficient_funds",
                                "error": (
                                    "Execution blocked before provider calls: "
                                    f"estimated cost ${estimated_cost} exceeds "
                                    f"available balance ${user.credit_balance}."
                                ),
                            }
                            for task_id, task in req.graph.items()
                        },
                        "billing": {
                            "cost_deducted": Decimal("0"),
                            "remaining_balance": user.credit_balance,
                            "estimated_cost": estimated_cost,
                        },
                    }
                session.commit()

        executor = DAGExecutor(
            max_concurrency=req.max_concurrency,
            request_timeout=req.request_timeout,
            max_retries=req.max_retries,
            settings=ExecutionSettings(
                mode=req.mode,
                primary_model=req.primary_model,
                local_model=req.local_model,
                allow_fallback=req.allow_fallback,
                max_context_chars=req.max_context_chars,
                request_timeout=req.request_timeout,
                max_retries=req.max_retries,
            ),
        )
        results = await executor.execute(req.graph)
        total_cost = Decimal("0")
        remaining_balance = None
        if user_id is not None:
            with SessionLocal() as session:
                user = session.get(User, user_id)
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found")
                task_costs = {}
                log_entries = []
                for task_id, result in results.items():
                    task_cost = (
                        calculate_task_cost(
                            result.get("routed_model")
                            or result.get("model")
                            or "unknown",
                            int(result.get("prompt_tokens") or 0),
                            int(result.get("completion_tokens") or 0),
                        )
                        if result.get("status") == "completed"
                        else Decimal("0")
                    )
                    task_costs[task_id] = task_cost
                    total_cost += task_cost
                    log_entries.append((task_id, result))
                fully_charged, charged_cost = settle_reserved_balance(
                    session,
                    user_id,
                    estimated_cost if funds_reserved else Decimal("0"),
                    total_cost,
                )
                total_cost = charged_cost
                logged_costs = allocate_charged_costs(task_costs, charged_cost)
                for task_id, result in log_entries:
                    session.add(
                        ExecutionLog(
                            user_id=user_id,
                            task_name=task_id,
                            model_used=(
                                result.get("routed_model")
                                or result.get("model")
                                or "unknown"
                            ),
                            input_tokens=int(result.get("prompt_tokens") or 0),
                            output_tokens=int(result.get("completion_tokens") or 0),
                            cost_deducted=logged_costs[task_id],
                            status=str(result.get("status") or "unknown"),
                        )
                    )
                session.commit()
                session.refresh(user)
                remaining_balance = user.credit_balance
        task_statuses = [result.get("status") for result in results.values()]
        if all(status == "completed" for status in task_statuses):
            execution_status = "completed"
        elif all(status == "failed" for status in task_statuses):
            execution_status = "failed"
        else:
            execution_status = "partial_failure"
        return {
            "status": execution_status,
            "results": results,
            "billing": {
                "cost_deducted": total_cost,
                "remaining_balance": remaining_balance,
                "estimated_cost": estimated_cost,
                **(
                    {
                        "billing_warning": (
                            "Actual usage exceeded the reserved estimate; "
                            "the reserved amount was charged."
                        )
                    }
                    if not fully_charged
                    else {}
                ),
            },
        }
    except HTTPException:
        _refund_execution_reservation(user_id, estimated_cost if funds_reserved else Decimal("0"))
        raise
    except (TypeError, ValueError) as err:
        _refund_execution_reservation(user_id, estimated_cost if funds_reserved else Decimal("0"))
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        _refund_execution_reservation(user_id, estimated_cost if funds_reserved else Decimal("0"))
        raise HTTPException(status_code=500, detail="DAG execution failed") from err


@app.post("/api/export")
def export_project(
    req: ExportRequest,
    _current_user: dict[str, Any] = Depends(get_current_clerk_user),
):
    """Extract code deliverables and export as local project directory + zip."""
    try:
        exporter = ProjectExporter()
        return exporter.export(
            goal=req.goal,
            nodes=req.nodes,
            edges=req.edges or [],
            aggregates=req.aggregates or {},
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print(f"[Server] Starting Uvicorn on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
