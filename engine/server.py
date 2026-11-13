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
from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
import stripe
from stripe._util import convert_to_dict

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

app = FastAPI(title="DietCode ML Engine", version="1.0.0")

# Enable CORS for local Electron and Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ML models
print("[Server] Initializing DietCode ML Engine & Self-Trained Regressors...")
forecaster = TokenForecaster()
planner = DAGPlanner(forecaster)
initialize_database()
print("[Server] ML Engine ready!")


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
    user_id: int | None = Field(default=None, ge=1)
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
    user_id: int = Field(ge=1)
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
def get_providers():
    """Return configured provider availability without exposing credentials."""
    return {
        "providers": [
            {
                "id": "ollama",
                "available": DAGExecutor._is_ollama_online(),
                "model": LOCAL_MODEL,
                "apiBase": OLLAMA_API_BASE,
            },
            {
                "id": "gemini",
                "available": bool(os.getenv("GEMINI_API_KEY")),
                "model": PRIMARY_MODEL,
            },
            {
                "id": "openai",
                "available": bool(os.getenv("OPENAI_API_KEY")),
            },
            {
                "id": "anthropic",
                "available": bool(os.getenv("ANTHROPIC_API_KEY")),
            },
        ]
    }


@app.post("/api/users", status_code=201)
def create_user(req: CreateUserRequest):
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


@app.get("/api/users/{user_id}/balance")
def get_user_balance(user_id: int):
    """Return a user's current local credit balance."""
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "user_id": user.id,
            "email": user.email,
            "credit_balance": user.credit_balance,
        }


@app.get("/api/users/{user_id}/executions")
def get_user_executions(user_id: int):
    """Return execution history for a local development user."""
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
def create_checkout_session(req: CreateCheckoutRequest):
    """Create a Stripe test/live Checkout session for a credit top-up."""
    secret_key, inr_per_usd = _stripe_config()
    with SessionLocal() as session:
                user = session.get(User, req.user_id)
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
                        "user_id": str(req.user_id),
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
        if req.mode == "selected":
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
def decompose_goal(req: DecomposeRequest):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    return planner.decompose_goal(req.goal)


@app.post("/api/predict-node")
def predict_node(req: PredictNodeRequest):
    return forecaster.forecast_node(
        title=req.title,
        description=req.description,
        upstream_count=req.upstream_count or 0,
        depth=req.depth or 1
    )


@app.post("/api/replan")
def replan_graph(req: ReplanRequest):
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
async def execute_graph(req: ExecuteRequest):
    """Execute the frontend DAG and return generated text plus token telemetry."""
    try:
        estimated_cost = Decimal("0")
        funds_reserved = False
        if req.user_id is not None:
            with SessionLocal() as session:
                user = session.get(User, req.user_id)
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found")
                estimated_cost = _estimate_graph_cost(req)
                funds_reserved = reserve_balance(session, req.user_id, estimated_cost)
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
        if req.user_id is not None:
            with SessionLocal() as session:
                user = session.get(User, req.user_id)
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
                    req.user_id,
                    estimated_cost if funds_reserved else Decimal("0"),
                    total_cost,
                )
                total_cost = charged_cost
                logged_costs = allocate_charged_costs(task_costs, charged_cost)
                for task_id, result in log_entries:
                    session.add(
                        ExecutionLog(
                            user_id=req.user_id,
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
                "estimated_cost": estimated_cost if req.user_id is not None else None,
                **(
                    {
                        "billing_warning": (
                            "Actual usage exceeded the reserved estimate; "
                            "the reserved amount was charged."
                        )
                    }
                    if req.user_id is not None and not fully_charged
                    else {}
                ),
            } if req.user_id is not None else None,
        }
    except HTTPException:
        _refund_execution_reservation(req.user_id, estimated_cost if funds_reserved else Decimal("0"))
        raise
    except (TypeError, ValueError) as err:
        _refund_execution_reservation(req.user_id, estimated_cost if funds_reserved else Decimal("0"))
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        _refund_execution_reservation(req.user_id, estimated_cost if funds_reserved else Decimal("0"))
        raise HTTPException(status_code=500, detail="DAG execution failed") from err


@app.post("/api/export")
def export_project(req: ExportRequest):
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
