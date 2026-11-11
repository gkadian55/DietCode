import os
import sys
from decimal import Decimal
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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

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
    from models.billing import ExecutionLog, User
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
    from engine.models.billing import ExecutionLog, User
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
        if req.user_id is not None:
            with SessionLocal() as session:
                if session.get(User, req.user_id) is None:
                    raise HTTPException(status_code=404, detail="User not found")

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
        if req.user_id is not None:
            with SessionLocal() as session:
                for task_id, result in results.items():
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
                            cost_deducted=Decimal("0"),
                            status=str(result.get("status") or "unknown"),
                        )
                    )
                session.commit()
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
        }
    except HTTPException:
        raise
    except (TypeError, ValueError) as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
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
