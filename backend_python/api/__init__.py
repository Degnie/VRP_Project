"""FastAPI application factory with persistence integration."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple
import logging

from backend_python.config import get_config
from backend_python.models import Coordinate, Cliente, Deposito, Flota, Instancia
from backend_python.service.solver_orchestrator import solve_instance
from backend_python.persistence.postgres_adapter import PostgreSQLAdapter
from backend_python.persistence.mongodb_adapter import MongoDBAdapter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models
class InstanceRequest(BaseModel):
    """Request para resolver una instancia."""
    instancia_id: str
    coordinates: List[Tuple[float, float]]  # [(x1, y1), (x2, y2), ...]
    demands: List[float]
    num_vehicles: int
    vehicle_capacity: float
    depot_coordinates: Tuple[float, float] = (0.0, 0.0)


class SolutionResponse(BaseModel):
    """Response con solución."""
    instancia_id: str
    total_cost: float
    num_routes: int
    routes: List[Dict[str, Any]]


class InstanceSummary(BaseModel):
    """Resumen de instancia persistida."""
    id: str
    num_clients: int
    num_vehicles: int
    capacity: float


def create_app() -> FastAPI:
    """Factory para crear app FastAPI con persistencia."""
    app = FastAPI(
        title="VRP Solver API",
        version="0.3.0-beta",
        description="Hybrid Python/C++ VRP Solver with Persistence"
    )

    # Initialize adapters
    config = get_config()
    pg_adapter = None
    mongo_adapter = None

    try:
        pg_adapter = PostgreSQLAdapter(config.DATABASE_URL)
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed: {e}")

    try:
        mongo_adapter = MongoDBAdapter(config.MONGO_URL)
        logger.info("MongoDB connected")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")

    @app.get("/health")
    def health():
        """Health check endpoint."""
        pg_status = "ok" if pg_adapter else "unavailable"
        mongo_status = "ok" if mongo_adapter else "unavailable"

        return {
            "status": "ok" if (pg_adapter and mongo_adapter) else "degraded",
            "version": "0.3.0-beta",
            "postgresql": pg_status,
            "mongodb": mongo_status
        }

    @app.post("/solve", response_model=SolutionResponse)
    def solve(request: InstanceRequest):
        """
        Resuelve una instancia VRP.

        Pipeline: NN → SA → 3-opt
        Persiste instancia en PostgreSQL, solución en MongoDB.
        """
        try:
            # Build Instancia from request
            depot = Deposito(Coordinate(*request.depot_coordinates), "Depot")
            flota = Flota(request.num_vehicles, request.vehicle_capacity)
            clientes = [
                # id arranca en 1: el pipeline C++ reserva id=0 para el depósito
                Cliente(
                    id=i + 1,
                    coordenada=Coordinate(request.coordinates[i][0], request.coordinates[i][1]),
                    demanda=request.demands[i]
                )
                for i in range(len(request.coordinates))
            ]

            instance = Instancia(
                id=request.instancia_id,
                deposito=depot,
                flota=flota,
                clientes=clientes
            )

            # Persist instance (PostgreSQL)
            if pg_adapter:
                if pg_adapter.save_instance(instance):
                    logger.info(f"Saved instance {request.instancia_id} to PostgreSQL")
                else:
                    logger.warning(f"Failed to save instance {request.instancia_id} to PostgreSQL")

            # Solve
            logger.info(f"Solving instance {request.instancia_id}")
            solution = solve_instance(instance)

            # Persist solution (MongoDB)
            if mongo_adapter:
                if mongo_adapter.save_solution(solution, {"phase": "Phase 3", "status": "completed"}):
                    logger.info(f"Saved solution for {request.instancia_id} to MongoDB")
                else:
                    logger.warning(f"Failed to save solution for {request.instancia_id} to MongoDB")

            # Format response
            routes = [
                {
                    "vehicle_id": ruta.vehicle_id,
                    "sequence": ruta.secuencia,
                    "cost": ruta.costo
                }
                for ruta in solution.rutas
            ]

            return SolutionResponse(
                instancia_id=solution.instancia_id,
                total_cost=solution.costo_total,
                num_routes=len(solution.rutas),
                routes=routes
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Solve error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/instances", response_model=List[InstanceSummary])
    def list_instances():
        """Lista instancias persistidas en PostgreSQL."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        try:
            instance_ids = pg_adapter.list_instances()
            summaries = []

            for inst_id in instance_ids:
                inst = pg_adapter.load_instance(inst_id)
                if inst:
                    summaries.append(InstanceSummary(
                        id=inst.id,
                        num_clients=len(inst.clientes),
                        num_vehicles=inst.flota.num_vehiculos,
                        capacity=inst.flota.capacidad_por_vehiculo
                    ))

            return summaries

        except Exception as e:
            logger.error(f"List instances error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/solutions/{instancia_id}", response_model=SolutionResponse)
    def get_solution(instancia_id: str):
        """Recupera solución más reciente para una instancia."""
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB unavailable")

        try:
            solution = mongo_adapter.load_solution(instancia_id)

            if not solution:
                raise HTTPException(status_code=404, detail="Solution not found")

            routes = [
                {
                    "vehicle_id": ruta.vehicle_id,
                    "sequence": ruta.secuencia,
                    "cost": ruta.costo
                }
                for ruta in solution.rutas
            ]

            return SolutionResponse(
                instancia_id=solution.instancia_id,
                total_cost=solution.costo_total,
                num_routes=len(solution.rutas),
                routes=routes
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get solution error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/")
    def root():
        """API root."""
        return {
            "message": "VRP Solver API v0.3.0-beta",
            "docs": "/docs",
            "endpoints": {
                "health": "GET /health",
                "solve": "POST /solve",
                "instances": "GET /instances",
                "solution": "GET /solutions/{instancia_id}"
            }
        }

    @app.on_event("shutdown")
    def shutdown_event():
        """Close database connections on shutdown."""
        if pg_adapter:
            pg_adapter.close()
        if mongo_adapter:
            mongo_adapter.close()

    return app


__all__ = ["create_app"]
