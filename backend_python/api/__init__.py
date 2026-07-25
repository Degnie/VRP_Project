"""FastAPI application factory with persistence integration."""

import uuid
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple, Optional
import logging

from backend_python.config import get_config
from backend_python.models import Coordinate, Cliente, Deposito, Flota, Instancia
from backend_python.service.solver_orchestrator import solve_instance
from backend_python.persistence.postgres_adapter import PostgreSQLAdapter
from backend_python.persistence.mongodb_adapter import MongoDBAdapter
from backend_python.auth import create_access_token, hash_password, verify_password
from backend_python.auth.dependencies import CurrentUser, get_current_user, require_role
from backend_python.auth.models import (
    CreateUserRequest, LoginRequest, RegisterRequest, TokenResponse, UserOut,
)
from backend_python.api.export import build_route_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models
class ContactInfo(BaseModel):
    """Datos de contacto de un cliente — opcionales, no los usa el solver."""
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None


class InstanceRequest(BaseModel):
    """Request para resolver una instancia."""
    instancia_id: str
    coordinates: List[Tuple[float, float]]  # [(x1, y1), (x2, y2), ...]
    demands: List[float]
    num_vehicles: int
    vehicle_capacity: float
    # Capacidad por vehículo individual (en orden); si se especifica, tiene
    # prioridad sobre vehicle_capacity para soportar flota heterogénea real.
    vehicle_capacities: Optional[List[float]] = None
    depot_coordinates: Tuple[float, float] = (0.0, 0.0)
    # Mismo índice que coordinates/demands; None o lista más corta es válido
    # (contactos ausentes para ese cliente).
    contacts: Optional[List[Optional[ContactInfo]]] = None


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


class VehicleTypeRequest(BaseModel):
    """Request para crear/editar un tipo de vehículo del catálogo."""
    name: str
    weight_capacity_kg: float
    volume_capacity_m3: float
    tolerance_margin: float = 0.9


class VehicleTypeOut(BaseModel):
    """Tipo de vehículo del catálogo."""
    id: str
    name: str
    weight_capacity_kg: float
    volume_capacity_m3: float
    tolerance_margin: float


class CoverageZoneRequest(BaseModel):
    """Request para reemplazar el polígono de cobertura de la cuenta."""
    points: List[Tuple[float, float]]


class CoverageZoneOut(BaseModel):
    """Zona de cobertura de la cuenta."""
    points: List[Tuple[float, float]]


DELIVERY_STATUSES = ("pendiente", "entregado", "no_encontrado", "reprogramado")


class DeliveryStatusRequest(BaseModel):
    """Request para actualizar el estado de entrega de un cliente."""
    status: str


class AssignmentsRequest(BaseModel):
    """Request para asignar repartidores a vehículos de una instancia."""
    assignments: Dict[int, str]  # {vehicle_id: repartidor_user_id}


class RouteStop(BaseModel):
    """Parada de la ruta de un repartidor, con estado de entrega."""
    client_id: int
    sequence: int
    delivery_status: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None


class MyRouteResponse(BaseModel):
    """Ruta + estado de entrega del repartidor autenticado."""
    instancia_id: str
    vehicle_id: int
    stops: List[RouteStop]


class RescheduleResponse(BaseModel):
    """Nueva instancia creada a partir de pedidos no entregados."""
    new_instancia_id: str
    rescheduled_client_ids: List[int]


def create_app() -> FastAPI:
    """Factory para crear app FastAPI con persistencia."""
    app = FastAPI(
        title="VRP Solver API",
        version="0.3.0-beta",
        description="Hybrid Python/C++ VRP Solver with Persistence"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_config().CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize adapters
    config = get_config()
    pg_adapter = None
    mongo_adapter = None

    if not config.JWT_SECRET:
        # Sin secret, cualquier auth firmada quedaría en un estado inseguro
        # (o directamente rompería en el primer login) — error explícito al
        # arrancar es mejor que un 500 silencioso más tarde.
        logger.error(
            "JWT_SECRET no está configurado. Setealo en .env.local/.env "
            "(python -c \"import secrets; print(secrets.token_urlsafe(32))\")."
        )

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

    @app.post("/auth/register", response_model=TokenResponse)
    def register(request: RegisterRequest):
        """Crea una cuenta (negocio) nueva + su primer usuario, con rol dueño."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        if pg_adapter.get_user_by_email(request.email):
            raise HTTPException(status_code=400, detail="Email already registered")

        account_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        try:
            pg_adapter.create_account(account_id, request.account_name)
            pg_adapter.create_user(
                user_id, account_id, request.email,
                hash_password(request.password), "dueño", request.full_name,
            )
        except Exception as e:
            logger.error(f"Register error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

        token = create_access_token(user_id, account_id, "dueño")
        return TokenResponse(access_token=token, role="dueño", account_id=account_id)

    @app.post("/auth/login", response_model=TokenResponse)
    def login(request: LoginRequest):
        """Autentica un usuario existente y devuelve un JWT."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        user = pg_adapter.get_user_by_email(request.email)
        if not user or not user["active"] or not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token(user["id"], user["account_id"], user["role"])
        return TokenResponse(access_token=token, role=user["role"], account_id=user["account_id"])

    @app.post("/auth/users", response_model=UserOut, status_code=201)
    def create_user(
        request: CreateUserRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Dueño/operario crea un usuario nuevo (operario o repartidor) en su misma cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        if request.role == "dueño" and current_user.role != "dueño":
            raise HTTPException(status_code=403, detail="Only an owner can create another owner")

        if pg_adapter.get_user_by_email(request.email):
            raise HTTPException(status_code=400, detail="Email already registered")

        user_id = str(uuid.uuid4())
        try:
            pg_adapter.create_user(
                user_id, current_user.account_id, request.email,
                hash_password(request.password), request.role, request.full_name,
            )
        except Exception as e:
            logger.error(f"Create user error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

        return UserOut(
            id=user_id, account_id=current_user.account_id, email=request.email,
            role=request.role, full_name=request.full_name,
        )

    @app.get("/auth/me", response_model=UserOut)
    def me(current_user: CurrentUser = Depends(get_current_user)):
        """Datos del usuario autenticado (decodificados del token)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        user = pg_adapter.get_user_by_id(current_user.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserOut(
            id=user["id"], account_id=user["account_id"], email=user["email"],
            role=user["role"], full_name=user["full_name"],
        )

    @app.get("/vehicle-catalog", response_model=List[VehicleTypeOut])
    def list_vehicle_catalog(current_user: CurrentUser = Depends(get_current_user)):
        """Catálogo de vehículos de la cuenta del usuario autenticado."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        types = pg_adapter.list_vehicle_types(current_user.account_id)
        return [VehicleTypeOut(**t) for t in types]

    @app.post("/vehicle-catalog", response_model=VehicleTypeOut, status_code=201)
    def create_vehicle_catalog_entry(
        request: VehicleTypeRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Crea un tipo de vehículo nuevo en el catálogo de la cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        vehicle_id = str(uuid.uuid4())
        try:
            pg_adapter.create_vehicle_type(
                vehicle_id, current_user.account_id, request.name,
                request.weight_capacity_kg, request.volume_capacity_m3, request.tolerance_margin,
            )
        except Exception as e:
            logger.error(f"Create vehicle type error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        return VehicleTypeOut(id=vehicle_id, **request.model_dump())

    @app.put("/vehicle-catalog/{vehicle_id}", response_model=VehicleTypeOut)
    def update_vehicle_catalog_entry(
        vehicle_id: str,
        request: VehicleTypeRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Edita un tipo de vehículo existente (solo si pertenece a la cuenta del usuario)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        try:
            updated = pg_adapter.update_vehicle_type(
                vehicle_id, current_user.account_id, request.name,
                request.weight_capacity_kg, request.volume_capacity_m3, request.tolerance_margin,
            )
        except Exception as e:
            logger.error(f"Update vehicle type error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        if not updated:
            raise HTTPException(status_code=404, detail="Vehicle type not found")
        return VehicleTypeOut(id=vehicle_id, **request.model_dump())

    @app.delete("/vehicle-catalog/{vehicle_id}", status_code=204)
    def delete_vehicle_catalog_entry(
        vehicle_id: str,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Elimina un tipo de vehículo del catálogo de la cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        try:
            deleted = pg_adapter.delete_vehicle_type(vehicle_id, current_user.account_id)
        except Exception as e:
            logger.error(f"Delete vehicle type error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        if not deleted:
            raise HTTPException(status_code=404, detail="Vehicle type not found")

    @app.get("/coverage-zone", response_model=Optional[CoverageZoneOut])
    def get_coverage_zone_endpoint(current_user: CurrentUser = Depends(get_current_user)):
        """Zona de cobertura de la cuenta del usuario (null si no hay ninguna guardada)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        points = pg_adapter.get_coverage_zone(current_user.account_id)
        if points is None:
            return None
        return CoverageZoneOut(points=[(p[0], p[1]) for p in points])

    @app.put("/coverage-zone", response_model=CoverageZoneOut)
    def set_coverage_zone_endpoint(
        request: CoverageZoneRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Reemplaza el polígono de cobertura de la cuenta (uno solo por cuenta)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        try:
            pg_adapter.set_coverage_zone(
                current_user.account_id, [[p[0], p[1]] for p in request.points]
            )
        except Exception as e:
            logger.error(f"Set coverage zone error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        return CoverageZoneOut(points=request.points)

    @app.delete("/coverage-zone", status_code=204)
    def delete_coverage_zone_endpoint(
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Elimina la zona de cobertura de la cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        try:
            pg_adapter.delete_coverage_zone(current_user.account_id)
        except Exception as e:
            logger.error(f"Delete coverage zone error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

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
    def solve(
        request: InstanceRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """
        Resuelve una instancia VRP.

        Pipeline: NN → SA → 3-opt
        Persiste instancia en PostgreSQL, solución en MongoDB.
        """
        try:
            # Build Instancia from request
            depot = Deposito(Coordinate(*request.depot_coordinates), "Depot")
            flota = Flota(
                request.num_vehicles,
                request.vehicle_capacity,
                capacidades_vehiculos=request.vehicle_capacities,
            )
            contacts = request.contacts or []
            clientes = [
                # id arranca en 1: el pipeline C++ reserva id=0 para el depósito
                Cliente(
                    id=i + 1,
                    coordenada=Coordinate(request.coordinates[i][0], request.coordinates[i][1]),
                    demanda=request.demands[i],
                    customer_name=(contacts[i].customer_name if i < len(contacts) and contacts[i] else None),
                    customer_phone=(contacts[i].customer_phone if i < len(contacts) and contacts[i] else None),
                    address=(contacts[i].address if i < len(contacts) and contacts[i] else None),
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
                if pg_adapter.save_instance(instance, account_id=current_user.account_id):
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
    def list_instances(current_user: CurrentUser = Depends(get_current_user)):
        """Lista instancias persistidas en PostgreSQL, de la cuenta del usuario."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        try:
            instance_ids = pg_adapter.list_instances(account_id=current_user.account_id)
            summaries = []

            for inst_id in instance_ids:
                inst = pg_adapter.load_instance(inst_id, account_id=current_user.account_id)
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
    def get_solution(instancia_id: str, current_user: CurrentUser = Depends(get_current_user)):
        """Recupera solución más reciente para una instancia de la cuenta del usuario."""
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB unavailable")

        # La solución vive en Mongo sin account_id propio — la pertenencia se
        # valida a través de la instancia en Postgres (que sí lo tiene).
        if pg_adapter and not pg_adapter.load_instance(instancia_id, account_id=current_user.account_id):
            raise HTTPException(status_code=404, detail="Solution not found")

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

    @app.get("/solutions/{instancia_id}/export.pdf")
    def export_solution_pdf(
        instancia_id: str,
        vehicle_id: Optional[int] = None,
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Hoja de ruta en PDF — una página por vehículo, o solo la de `vehicle_id`."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB unavailable")

        instance = pg_adapter.load_instance(instancia_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Solution not found")

        solution = mongo_adapter.load_solution(instancia_id)
        if not solution:
            raise HTTPException(status_code=404, detail="Solution not found")

        clientes_by_id = {c.id: c for c in instance.clientes}
        pdf_bytes = build_route_pdf(solution, clientes_by_id, vehicle_id=vehicle_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="ruta_{instancia_id}.pdf"'},
        )

    @app.put("/instances/{instancia_id}/clients/{cliente_id}/status")
    def update_delivery_status(
        instancia_id: str,
        cliente_id: int,
        request: DeliveryStatusRequest,
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Marca el estado de entrega de un pedido. Dueño/operario: cualquiera de
        su cuenta. Repartidor: solo pedidos de su propia ruta asignada."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        if request.status not in DELIVERY_STATUSES:
            raise HTTPException(status_code=422, detail=f"status debe ser uno de {DELIVERY_STATUSES}")

        instance = pg_adapter.load_instance(instancia_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")

        if current_user.role == "repartidor":
            assigned_vehicle = pg_adapter.get_assigned_vehicle_for_repartidor(instancia_id, current_user.user_id)
            if assigned_vehicle is None:
                raise HTTPException(status_code=403, detail="No tenés una ruta asignada en esta instancia")
            if mongo_adapter:
                solution = mongo_adapter.load_solution(instancia_id)
                own_ruta = next(
                    (r for r in solution.rutas if r.vehicle_id == assigned_vehicle), None
                ) if solution else None
                if not own_ruta or cliente_id not in own_ruta.secuencia:
                    raise HTTPException(status_code=403, detail="Ese pedido no está en tu ruta")
        elif current_user.role not in ("dueño", "operario"):
            raise HTTPException(status_code=403, detail="Rol sin permiso")

        updated = pg_adapter.update_client_delivery_status(
            instancia_id, cliente_id, request.status, current_user.user_id
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Client not found")
        return {"status": request.status}

    @app.put("/instances/{instancia_id}/assignments")
    def set_assignments(
        instancia_id: str,
        request: AssignmentsRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Asigna un repartidor a cada vehicle_id de la instancia (reemplaza lo anterior)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        instance = pg_adapter.load_instance(instancia_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")

        for repartidor_user_id in request.assignments.values():
            user = pg_adapter.get_user_by_id(repartidor_user_id)
            if not user or user["account_id"] != current_user.account_id:
                raise HTTPException(status_code=422, detail=f"Usuario inválido: {repartidor_user_id}")

        pg_adapter.set_route_assignments(instancia_id, request.assignments)
        return {"assignments": request.assignments}

    @app.get("/instances/{instancia_id}/my-route", response_model=MyRouteResponse)
    def get_my_route(instancia_id: str, current_user: CurrentUser = Depends(get_current_user)):
        """Ruta + estado de entrega del vehículo asignado al repartidor autenticado."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB unavailable")

        instance = pg_adapter.load_instance(instancia_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")

        vehicle_id = pg_adapter.get_assigned_vehicle_for_repartidor(instancia_id, current_user.user_id)
        if vehicle_id is None:
            raise HTTPException(status_code=404, detail="No tenés una ruta asignada en esta instancia")

        solution = mongo_adapter.load_solution(instancia_id)
        if not solution:
            raise HTTPException(status_code=404, detail="Solution not found")
        ruta = next((r for r in solution.rutas if r.vehicle_id == vehicle_id), None)
        if not ruta:
            raise HTTPException(status_code=404, detail="Route not found")

        clientes_by_id = {c.id: c for c in instance.clientes}
        statuses = pg_adapter.get_client_delivery_statuses(instancia_id)
        stops = [
            RouteStop(
                client_id=client_id,
                sequence=i + 1,
                delivery_status=statuses.get(client_id, "pendiente"),
                customer_name=clientes_by_id[client_id].customer_name if client_id in clientes_by_id else None,
                customer_phone=clientes_by_id[client_id].customer_phone if client_id in clientes_by_id else None,
                address=clientes_by_id[client_id].address if client_id in clientes_by_id else None,
            )
            for i, client_id in enumerate(ruta.secuencia)
        ]
        return MyRouteResponse(instancia_id=instancia_id, vehicle_id=vehicle_id, stops=stops)

    @app.post("/instances/{instancia_id}/reschedule", response_model=RescheduleResponse)
    def reschedule_instance(
        instancia_id: str,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Crea una instancia nueva con los pedidos no entregados (pendiente/no_encontrado).

        Reusa el pipeline de /solve con la misma flota que tenía la instancia original.
        No recalcula automáticamente — el usuario dispara la reprogramación a mano.
        """
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")

        instance = pg_adapter.load_instance(instancia_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")

        pending = pg_adapter.get_pending_clients(instancia_id)
        if not pending:
            raise HTTPException(status_code=400, detail="No hay pedidos pendientes para reprogramar")

        new_instancia_id = f"{instancia_id}-reprog-{uuid.uuid4().hex[:8]}"
        new_clientes = [
            Cliente(
                id=row["id"], coordenada=Coordinate(row["x"], row["y"]), demanda=row["demand"],
                customer_name=row["customer_name"], customer_phone=row["customer_phone"], address=row["address"],
            )
            for row in pending
        ]
        new_instance = Instancia(
            id=new_instancia_id, deposito=instance.deposito, flota=instance.flota, clientes=new_clientes,
        )
        pg_adapter.save_instance(new_instance, account_id=current_user.account_id)

        cliente_ids = [row["id"] for row in pending]
        pg_adapter.mark_clients_rescheduled(instancia_id, cliente_ids, new_instancia_id)

        return RescheduleResponse(new_instancia_id=new_instancia_id, rescheduled_client_ids=cliente_ids)

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
