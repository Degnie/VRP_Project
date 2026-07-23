"""FastAPI application factory."""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional


class InstanceRequest(BaseModel):
    """Request para resolver una instancia."""
    instancia_id: str
    coordinates: List[tuple]  # [(x1, y1), (x2, y2), ...]
    demands: List[int]
    num_vehicles: int
    vehicle_capacity: int


class SolutionResponse(BaseModel):
    """Response con solución."""
    instancia_id: str
    total_cost: float
    num_routes: int
    routes: List[dict] = []


def create_app() -> FastAPI:
    """Factory para crear app FastAPI."""
    app = FastAPI(
        title="VRP Solver API",
        version="0.1.0-alpha",
        description="Hybrid Python/C++ Vehicle Routing Problem Solver"
    )

    @app.get("/health")
    def health():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0-alpha"}

    @app.post("/solve", response_model=SolutionResponse)
    def solve(request: InstanceRequest):
        """
        Resuelve una instancia VRP usando Nearest Neighbor.

        Por ahora retorna stub. Integración con C++ en progress.
        """
        return SolutionResponse(
            instancia_id=request.instancia_id,
            total_cost=0.0,
            num_routes=0,
            routes=[]
        )

    @app.get("/instances")
    def list_instances():
        """Lista instancias persistidas."""
        return {"instances": []}

    @app.get("/")
    def root():
        """API root."""
        return {
            "message": "VRP Solver API v0.1.0-alpha",
            "docs": "/docs"
        }

    return app


__all__ = ["create_app"]
