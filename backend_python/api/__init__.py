"""
API REST - FastAPI endpoints

Expone la funcionalidad del solver a través de HTTP.
Endpoints:
  POST /solve - Resolver una instancia
  GET /solve/{job_id} - Obtener resultado
  POST /validate - Validar solución
  GET /instances - Listar instancias
"""

from fastapi import FastAPI

def create_app() -> FastAPI:
    """Factory para crear instancia de FastAPI."""
    app = FastAPI(
        title="VRP Solver API",
        description="Solver híbrido Python/C++ para Vehicle Routing Problem",
        version="0.1.0-alpha",
    )

    # TODO: Agregar rutas
    # from .routes import solver_routes
    # app.include_router(solver_routes.router)

    return app

__all__ = ["create_app"]
