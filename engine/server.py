import os
import sys
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
from pydantic import BaseModel

try:
    from models.planner import DAGPlanner
    from models.token_forecaster import MODEL_PROFILES, TokenForecaster
except ImportError:
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print(f"[Server] Starting Uvicorn on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
