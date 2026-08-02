"""FastAPI application factory with persistence integration."""

import re
import uuid
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Tuple, Optional
import logging

from backend_python.config import get_config
from backend_python.models import Coordinate, Cliente, Deposito, Flota, Instancia
from backend_python.service.solver_orchestrator import solve_instance
from backend_python.persistence.postgres_adapter import PostgreSQLAdapter, psycopg2
from backend_python.persistence.mongodb_adapter import MongoDBAdapter
from backend_python.auth import create_access_token, hash_password, verify_password
from backend_python.auth.dependencies import CurrentUser, get_current_user, require_role, set_pg_adapter
from backend_python.auth.models import (
    CreateUserRequest, LoginRequest, RegisterRequest, SetUserActiveRequest,
    TeamMemberOut, TokenResponse, UserOut,
)
from backend_python.api.export import build_route_pdf

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Namespacing de instancia_id por cuenta ---
#
# instancia_id es elegido libremente por el usuario en el formulario (el
# default es literalmente "instancia-1" para todos). La tabla `instancias`
# lo usa como PRIMARY KEY global (no compuesta con account_id), y el mismo
# patrón `ON CONFLICT (id) DO UPDATE` se repite en flota_config/clientes —
# sin este namespacing, dos cuentas distintas que resuelven sin cambiar el
# ID por defecto se pisan silenciosamente los datos de flota/clientes entre
# sí (bug real encontrado en producción de pruebas). En vez de migrar la PK
# a compuesta (reescribir 4 tablas y sus FKs), se namespacea el ID real que
# se persiste como f"{account_id}:{instancia_id}" en el borde de cada
# endpoint — el usuario nunca ve el prefijo, todos los adapters (Postgres y
# Mongo) siguen recibiendo un string opaco sin cambiar ninguna firma.
_NAMESPACE_SEP = ":"


def _namespaced_id(account_id: str, instancia_id: str) -> str:
    return f"{account_id}{_NAMESPACE_SEP}{instancia_id}"


def _strip_namespace(account_id: str, namespaced_id: str) -> str:
    prefix = f"{account_id}{_NAMESPACE_SEP}"
    return namespaced_id[len(prefix):] if namespaced_id.startswith(prefix) else namespaced_id


# Bug real (Ronda 10, ciclo nuevo, dueño): "ID de instancia" es texto libre
# sin restricciones en el formulario, pero se interpolaba crudo en el header
# Content-Disposition del export de PDF. Un salto de línea rompe el header a
# nivel de protocolo (h11 lo rechaza, 500 sin aviso claro); una comilla lo
# deja mal formado (corta el parámetro filename a mitad). Se sanea a solo
# caracteres seguros para un nombre de archivo antes de interpolar.
def _safe_filename_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


# Pydantic models
class ContactInfo(BaseModel):
    """Datos de contacto de un cliente — opcionales, no los usa el solver.

    max_length coincide con las columnas reales (customer_name VARCHAR(255),
    address VARCHAR(500)) — sin esto, un valor demasiado largo pasaba Pydantic
    sin quejarse, el solve corría igual, y recién explotaba en save_instance
    con un psycopg2.errors.StringDataRightTruncation sin capturar, devolviendo
    un 500 genérico sin indicar qué falló ni si la solución quedó guardada.
    """
    customer_name: Optional[str] = Field(default=None, max_length=255)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)


def _validate_lng_lat_pairs(pairs: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    for lng, lat in pairs:
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise ValueError(
                f"Coordenada fuera de rango: ({lng}, {lat}) — longitud debe estar entre "
                "-180 y 180, latitud entre -90 y 90"
            )
    return pairs


class InstanceRequest(BaseModel):
    """Request para resolver una instancia."""
    # 200: la columna real es VARCHAR(255), pero el id se namespacea como
    # f"{account_id}:{instancia_id}" antes de persistir — el margen deja
    # espacio de sobra para el prefijo de account_id (~37 chars) sin
    # acercarse al límite real de la columna. Sin esto, un instancia_id
    # largo pasaba Pydantic y explotaba en save_instance con un 500 genérico
    # (mismo patrón que ContactInfo sin max_length, Ronda 29).
    instancia_id: str = Field(max_length=200)
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

    # Sin este chequeo, una coordenada fuera de rango (typo de tecla, dato mal
    # importado) pasaba el 200 del /solve y recién explotaba en el frontend:
    # MapLibre lanza "Invalid LngLat" al intentar centrar el mapa en la
    # solución, y como no hay Error Boundary en la app, esa excepción tumbaba
    # el árbol de React entero — pantalla en blanco sin ningún mensaje.
    @field_validator("coordinates")
    @classmethod
    def _validate_coordinates(cls, v: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        return _validate_lng_lat_pairs(v)

    @field_validator("depot_coordinates")
    @classmethod
    def _validate_depot(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        return _validate_lng_lat_pairs([v])[0]


class SolutionResponse(BaseModel):
    """Response con solución."""
    instancia_id: str
    total_cost: float
    num_routes: int
    routes: List[Dict[str, Any]]
    # Bug real (Ronda 13, ciclo nuevo, dueño y operario, hallado
    # independientemente por ambos): si OSRM no está disponible, el solver ya
    # caía en silencio a distancia euclídea para TODA la matriz de costos
    # (afectando total_cost y la secuencia optimizada), sin que este campo
    # existiera — el número se veía idéntico a un cálculo con calles reales.
    used_osrm: bool = True


class InstanceSummary(BaseModel):
    """Resumen de instancia persistida."""
    id: str
    num_clients: int
    num_vehicles: int
    capacity: float
    created_at: Optional[str] = None


class VehicleTypeRequest(BaseModel):
    """Request para crear/editar un tipo de vehículo del catálogo.

    id: opcional, generado por el cliente (crypto.randomUUID() en el
    frontend). Si se manda, el backend lo usa tal cual en vez de generar uno
    propio — el frontend arma la fila optimista con este id antes de que la
    request termine (el usuario puede seguir tecleando mientras el POST está
    en vuelo), así que si el backend devolviera un id distinto, la respuesta
    stale terminaba reemplazando cualquier edición hecha en el medio.
    """
    id: Optional[str] = None
    name: str = Field(max_length=255)
    weight_capacity_kg: float
    volume_capacity_m3: float
    tolerance_margin: float = 0.9

    # Bug real (Ronda 18, ciclo nuevo, dueño): Field(gt=0) sin validador
    # propio dejaba pasar el mensaje crudo de Pydantic ("Input should be
    # greater than 0", en inglés) hasta la UI del catálogo — el único texto
    # en inglés/jerga técnica en una app con más de 60 mensajes de error ya
    # traducidos con tono consistente. Alcanzable: el input HTML min="1" es
    # solo un hint visual, no bloquea escribir "0" directamente (el sync es
    # por useEffect en cada cambio, sin submit nativo de por medio).
    @field_validator("weight_capacity_kg")
    @classmethod
    def _validate_weight(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La capacidad de peso debe ser mayor a 0 kg")
        return v

    @field_validator("volume_capacity_m3")
    @classmethod
    def _validate_volume(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("La capacidad de volumen debe ser mayor a 0 m³")
        return v


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

    # RN-COV-002: sin este chequeo, un polígono de 0-2 puntos (no cierra una
    # superficie real) o con coordenadas fuera de rango se persistía tal
    # cual — mismo patrón de bug que InstanceRequest.coordinates sin
    # _validate_lng_lat_pairs (RN-012).
    @field_validator("points")
    @classmethod
    def _validate_points(cls, v: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if len(v) < 3:
            raise ValueError("La zona de cobertura debe tener al menos 3 puntos")
        return _validate_lng_lat_pairs(v)


class CoverageZoneOut(BaseModel):
    """Zona de cobertura de la cuenta."""
    points: List[Tuple[float, float]]


DELIVERY_STATUSES = ("pendiente", "entregado", "no_encontrado", "reprogramado", "rechazado")

# "reprogramado" solo debe llegar a través de POST /instances/{id}/reschedule (que
# setea rescheduled_to_instancia_id vía mark_clients_rescheduled) — nunca por esta vía
# manual. Setearlo acá dejaba clientes huérfanos: bloqueados por el guard de 409 en
# cualquier edición futura, y excluidos de get_pending_clients, así que tampoco volvían
# a ser candidatos a una reprogramación real.
MANUALLY_SETTABLE_DELIVERY_STATUSES = ("pendiente", "entregado", "no_encontrado", "rechazado")


class DeliveryStatusRequest(BaseModel):
    """Request para actualizar el estado de entrega de un cliente."""
    status: str
    note: Optional[str] = None


class UpdateClientRequest(BaseModel):
    """Corrige los datos de un cliente ya persistido (ej. error de tipeo en
    el CSV importado) sin tener que re-resolver la instancia entera desde
    cero — eso perdía los estados de entrega ya marcados ese día."""
    x: float
    y: float
    # Opcional: editar solo contacto/ubicación no debería obligar al caller a
    # conocer/retransmitir la demanda actual del cliente — si se omite, el
    # endpoint preserva la que ya está persistida.
    demand: Optional[float] = Field(default=None)
    customer_name: Optional[str] = Field(default=None, max_length=255)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)

    # Bug real (Ronda 19, ciclo nuevo, dueño): mismo patrón que
    # VehicleTypeRequest.weight_capacity_kg/volume_capacity_m3 (Ronda 18) —
    # Field(gt=0) sin validador propio dejaba pasar el mensaje crudo de
    # Pydantic en inglés ("Input should be greater than 0") si demand llegaba
    # en 0/negativo. El único caller de UI hoy (ClientEditControl.tsx) omite
    # este campo a propósito, pero sigue siendo superficie de API pública
    # (api.updateClient acepta demand) alcanzable por cualquier caller directo.
    @field_validator("demand")
    @classmethod
    def _validate_demand(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("La demanda debe ser mayor a 0")
        return v

    @field_validator("x", "y")
    @classmethod
    def _validate_coordinate(cls, v: float, info) -> float:
        lo, hi = (-180, 180) if info.field_name == "x" else (-90, 90)
        if not (lo <= v <= hi):
            raise ValueError(f"{info.field_name} fuera de rango válido ({lo} a {hi})")
        return v


class AssignmentsRequest(BaseModel):
    """Request para asignar repartidores a vehículos de una instancia."""
    assignments: Dict[int, str]  # {vehicle_id: repartidor_user_id}


class DeliveryStatusEntry(BaseModel):
    """Estado de entrega + nota de un cliente, para hidratar la UI de dueño/operario."""
    status: str
    note: Optional[str] = None


class RouteStop(BaseModel):
    """Parada de la ruta de un repartidor, con estado de entrega."""
    client_id: int
    sequence: int
    delivery_status: str
    delivery_note: Optional[str] = None
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

    set_pg_adapter(pg_adapter)

    try:
        mongo_adapter = MongoDBAdapter(config.MONGO_URL)
        logger.info("MongoDB connected")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")

    @app.post("/auth/register", response_model=TokenResponse)
    def register(request: RegisterRequest):
        """Crea una cuenta (negocio) nueva + su primer usuario, con rol dueño."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        if pg_adapter.get_user_by_email(request.email):
            raise HTTPException(status_code=400, detail="Ese email ya está registrado")

        account_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        try:
            pg_adapter.create_account(account_id, request.account_name)
            pg_adapter.create_user(
                user_id, account_id, request.email,
                hash_password(request.password), "dueño", request.full_name,
            )
        except psycopg2.errors.UniqueViolation:
            # El chequeo de arriba (get_user_by_email) no cierra la ventana
            # de carrera: dos registros con el mismo email casi simultáneos
            # pueden pasar ambos ese chequeo antes de que cualquiera haga el
            # INSERT — el segundo choca acá contra el UNIQUE de la columna.
            # Sin este catch específico, caía al 500 genérico de abajo.
            raise HTTPException(status_code=400, detail="Ese email ya está registrado")
        except Exception as e:
            logger.error(f"Register error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

        token = create_access_token(user_id, account_id, "dueño")
        return TokenResponse(access_token=token, role="dueño", account_id=account_id)

    @app.post("/auth/login", response_model=TokenResponse)
    def login(request: LoginRequest):
        """Autentica un usuario existente y devuelve un JWT."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        user = pg_adapter.get_user_by_email(request.email)
        if not user or not user["active"] or not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Email o contraseña inválidos")

        token = create_access_token(user["id"], user["account_id"], user["role"])
        return TokenResponse(access_token=token, role=user["role"], account_id=user["account_id"])

    @app.post("/auth/users", response_model=UserOut, status_code=201)
    def create_user(
        request: CreateUserRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Dueño/operario crea un usuario nuevo (operario o repartidor) en su misma cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        if request.role == "dueño" and current_user.role != "dueño":
            raise HTTPException(status_code=403, detail="Solo un dueño puede crear a otro dueño")

        if pg_adapter.get_user_by_email(request.email):
            raise HTTPException(status_code=400, detail="Ese email ya está registrado")

        user_id = str(uuid.uuid4())
        try:
            pg_adapter.create_user(
                user_id, current_user.account_id, request.email,
                hash_password(request.password), request.role, request.full_name,
            )
        except psycopg2.errors.UniqueViolation:
            # Mismo caso que en /auth/register: dos invitaciones al mismo
            # email casi simultáneas (ej. dos operarios invitando al mismo
            # repartidor) pueden pasar el chequeo de arriba antes de que
            # cualquiera de las dos inserte.
            raise HTTPException(status_code=400, detail="Ese email ya está registrado")
        except Exception as e:
            logger.error(f"Create user error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

        return UserOut(
            id=user_id, account_id=current_user.account_id, email=request.email,
            role=request.role, full_name=request.full_name,
        )

    @app.get("/auth/me", response_model=UserOut)
    def me(current_user: CurrentUser = Depends(get_current_user)):
        """Datos del usuario autenticado (decodificados del token)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        user = pg_adapter.get_user_by_id(current_user.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return UserOut(
            id=user["id"], account_id=user["account_id"], email=user["email"],
            role=user["role"], full_name=user["full_name"],
        )

    @app.get("/auth/users", response_model=List[TeamMemberOut])
    def list_team(current_user: CurrentUser = Depends(require_role("dueño", "operario"))):
        """Equipo (usuarios) de la cuenta del usuario autenticado."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        users = pg_adapter.list_users_by_account(current_user.account_id)
        return [TeamMemberOut(**u) for u in users]

    @app.patch("/auth/users/{user_id}", response_model=TeamMemberOut)
    def set_user_active(
        user_id: str,
        request: SetUserActiveRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Activa/desactiva un usuario de la cuenta. Un usuario no puede desactivarse a sí mismo."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        if user_id == current_user.user_id:
            raise HTTPException(status_code=400, detail="No podés desactivarte a vos mismo")

        target = pg_adapter.get_user_by_id(user_id)
        if target and target["account_id"] == current_user.account_id and target["role"] == "dueño" and current_user.role != "dueño":
            raise HTTPException(status_code=403, detail="Solo un dueño puede desactivar a otro dueño")

        updated = pg_adapter.set_user_active(user_id, current_user.account_id, request.active)
        if not updated:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user = pg_adapter.get_user_by_id(user_id)
        return TeamMemberOut(
            id=user["id"], email=user["email"], role=user["role"],
            full_name=user["full_name"], active=user["active"],
        )

    @app.get("/vehicle-catalog", response_model=List[VehicleTypeOut])
    def list_vehicle_catalog(current_user: CurrentUser = Depends(get_current_user)):
        """Catálogo de vehículos de la cuenta del usuario autenticado."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        types = pg_adapter.list_vehicle_types(current_user.account_id)
        return [VehicleTypeOut(**t) for t in types]

    @app.post("/vehicle-catalog", response_model=VehicleTypeOut, status_code=201)
    def create_vehicle_catalog_entry(
        request: VehicleTypeRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Crea un tipo de vehículo nuevo en el catálogo de la cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        vehicle_id = request.id or str(uuid.uuid4())
        try:
            pg_adapter.create_vehicle_type(
                vehicle_id, current_user.account_id, request.name,
                request.weight_capacity_kg, request.volume_capacity_m3, request.tolerance_margin,
            )
        except psycopg2.errors.UniqueViolation:
            # El id es opcional y lo genera el cliente (crypto.randomUUID())
            # para UI optimista — un reintento de red normal del navegador
            # (o doble click) puede reenviar el mismo POST con el mismo id
            # antes de recibir la respuesta del primero, chocando contra la
            # PK. Mismo patrón que el TOCTOU de email en /auth/register.
            raise HTTPException(status_code=409, detail="Ya existe un vehículo con ese id")
        except Exception as e:
            logger.error(f"Create vehicle type error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")
        return VehicleTypeOut(id=vehicle_id, **request.model_dump(exclude={"id"}))

    @app.put("/vehicle-catalog/{vehicle_id}", response_model=VehicleTypeOut)
    def update_vehicle_catalog_entry(
        vehicle_id: str,
        request: VehicleTypeRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Edita un tipo de vehículo existente (solo si pertenece a la cuenta del usuario)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        try:
            updated = pg_adapter.update_vehicle_type(
                vehicle_id, current_user.account_id, request.name,
                request.weight_capacity_kg, request.volume_capacity_m3, request.tolerance_margin,
            )
        except Exception as e:
            logger.error(f"Update vehicle type error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")
        if not updated:
            raise HTTPException(status_code=404, detail="Tipo de vehículo no encontrado")
        return VehicleTypeOut(id=vehicle_id, **request.model_dump(exclude={"id"}))

    @app.delete("/vehicle-catalog/{vehicle_id}", status_code=204)
    def delete_vehicle_catalog_entry(
        vehicle_id: str,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Elimina un tipo de vehículo del catálogo de la cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        try:
            deleted = pg_adapter.delete_vehicle_type(vehicle_id, current_user.account_id)
        except Exception as e:
            logger.error(f"Delete vehicle type error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")
        if not deleted:
            raise HTTPException(status_code=404, detail="Tipo de vehículo no encontrado")

    @app.get("/coverage-zone", response_model=Optional[CoverageZoneOut])
    def get_coverage_zone_endpoint(current_user: CurrentUser = Depends(get_current_user)):
        """Zona de cobertura de la cuenta del usuario (null si no hay ninguna guardada)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
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
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        try:
            pg_adapter.set_coverage_zone(
                current_user.account_id, [[p[0], p[1]] for p in request.points]
            )
        except Exception as e:
            logger.error(f"Set coverage zone error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")
        return CoverageZoneOut(points=request.points)

    @app.delete("/coverage-zone", status_code=204)
    def delete_coverage_zone_endpoint(
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Elimina la zona de cobertura de la cuenta."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        try:
            pg_adapter.delete_coverage_zone(current_user.account_id)
        except Exception as e:
            logger.error(f"Delete coverage zone error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

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

    def _solve_and_persist(
        instance: Instancia, account_id: str, log_label: str, require_existing: bool = False
    ) -> SolutionResponse:
        """Corre el pipeline NN→SA→3-opt sobre una Instancia ya construida,
        persiste instancia+solución, y arma la respuesta. Compartido por
        /solve (instancia armada desde el body) y
        /instances/{id}/solve (instancia ya persistida, ej. tras reprogramar).

        require_existing=True para el segundo caso: el solve del pipeline
        NN→SA→3-opt puede tardar segundos con instancias grandes, y save_instance
        hace un upsert incondicional (INSERT ... ON CONFLICT DO UPDATE) — sin
        este chequeo, un DELETE /instances/{id} concurrente que corría y
        terminaba MIENTRAS este solve seguía en vuelo quedaba "resucitado" por
        el upsert al final, reapareciendo en GET /instances como si nunca se
        hubiera borrado, sin ningún error en ninguno de los dos flujos (Ronda
        17, ciclo nuevo, dueño)."""
        # Solve ANTES de persistir — save_instance ahora borra clientes
        # obsoletos de una corrida anterior con el mismo instancia_id
        # (Etapa de limpieza de huérfanos); si el solve fallara con la
        # persistencia ya hecha, un payload rechazado (ej. sin clientes
        # válidos) dejaría la ruta vieja borrada en la DB aunque la
        # respuesta HTTP fuera un error — el dueño ve un 400 y asume que
        # no pasó nada, pero la instancia ya quedó vacía. Solo se
        # persiste si el solve realmente produjo una solución.
        logger.info(f"Solving instance {log_label}")
        solution, used_osrm = solve_instance(instance)

        if pg_adapter:
            if require_existing and not pg_adapter.load_instance(instance.id, account_id=account_id):
                raise HTTPException(
                    status_code=404,
                    detail="La instancia fue eliminada mientras se resolvía — no se guardó el resultado.",
                )
            if pg_adapter.save_instance(instance, account_id=account_id):
                logger.info(f"Saved instance {log_label} to PostgreSQL")
            else:
                logger.warning(f"Failed to save instance {log_label} to PostgreSQL")

            # Bug real: NN/SA puede recomponer completamente qué clientes
            # caen en cada vehicle_id al re-resolver — las asignaciones
            # repartidor↔vehicle_id de la corrida anterior quedaban vivas
            # apuntando al mismo vehicle_id con una secuencia de paradas
            # DISTINTA, sin ningún aviso. El repartidor seguía viendo "su"
            # ruta (mismo vehicle_id) pero con clientes ajenos, pudiendo
            # entregar pedidos equivocados. Se invalidan siempre tras
            # cualquier re-solve — dueño/operario debe reasignar.
            pg_adapter.set_route_assignments(instance.id, {})

        if mongo_adapter:
            if mongo_adapter.save_solution(solution, {"phase": "Phase 3", "status": "completed"}):
                logger.info(f"Saved solution for {log_label} to MongoDB")
            else:
                # Bug real (Ronda 4, ciclo nuevo, operario): un warning logueado
                # y nada más dejaba Postgres (ya actualizado con la topología
                # nueva) y Mongo (todavía con la solución VIEJA) inconsistentes
                # sin que nadie se enterara — GET /solutions, export PDF,
                # my-route y update_delivery_status leen de Mongo y quedaban
                # mostrando/validando contra rutas obsoletas en silencio. Se
                # propaga como error real en vez de tragárselo.
                logger.error(f"Failed to save solution for {log_label} to MongoDB")
                raise HTTPException(
                    status_code=503,
                    detail="La ruta se calculó pero no se pudo guardar — probá resolver de nuevo.",
                )

        routes = [
            {"vehicle_id": ruta.vehicle_id, "sequence": ruta.secuencia, "cost": ruta.costo}
            for ruta in solution.rutas
        ]
        return SolutionResponse(
            instancia_id=_strip_namespace(account_id, solution.instancia_id),
            total_cost=solution.costo_total,
            num_routes=len(solution.rutas),
            routes=routes,
            used_osrm=used_osrm,
        )

    @app.post("/solve", response_model=SolutionResponse)
    def solve(
        request: InstanceRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """
        Resuelve una instancia VRP a partir de coordenadas/flota enviadas en el body.

        Pipeline: NN → SA → 3-opt
        Persiste instancia en PostgreSQL, solución en MongoDB.
        """
        try:
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

            # El id real que se persiste va namespaceado por cuenta — el usuario
            # nunca ve esto, pero evita que dos cuentas distintas usando el mismo
            # instancia_id (el default del form es literalmente "instancia-1"
            # para todos) se pisen los datos de flota/clientes entre sí.
            instance = Instancia(
                id=_namespaced_id(current_user.account_id, request.instancia_id),
                deposito=depot,
                flota=flota,
                clientes=clientes
            )
            return _solve_and_persist(instance, current_user.account_id, request.instancia_id)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Solve error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

    @app.post("/instances/{instancia_id}/solve", response_model=SolutionResponse)
    def solve_existing_instance(
        instancia_id: str,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Resuelve una instancia YA persistida (ej. la creada por
        /instances/{id}/reschedule), sin requerir retransmitir coordenadas y
        flota a mano — antes era imposible re-resolver una reprogramación
        desde la UI, porque /solve solo aceptaba una instancia armada
        completa en el body."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")
        if not instance.clientes:
            raise HTTPException(status_code=400, detail="La instancia no tiene clientes para resolver")

        try:
            return _solve_and_persist(instance, current_user.account_id, instancia_id, require_existing=True)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Solve error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

    @app.get("/instances", response_model=List[InstanceSummary])
    def list_instances(
        assigned_only: bool = False,
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Lista instancias de la cuenta del usuario.

        Con rol repartidor, siempre filtra a solo las instancias donde tiene
        una ruta asignada (route_assignments) — evita que vea el ID técnico
        de instancias ajenas en su selector. `assigned_only` queda aceptado
        por compatibilidad con el frontend, que ya lo manda; no cambia el
        resultado (el enforcement ya no depende de que el caller lo pase).
        """
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        try:
            # Bug real (Ronda 1, ciclo nuevo, repartidor): el filtro a "solo
            # mis instancias asignadas" dependía de que el caller pasara
            # assigned_only=true — un repartidor llamando el endpoint directo
            # (sin pasar por el frontend) veía metadata de toda la cuenta.
            del assigned_only  # ponytail: aceptado por compat, ya no se lee — ver docstring
            repartidor_user_id = (
                current_user.user_id if current_user.role == "repartidor" else None
            )
            rows = pg_adapter.list_instance_summaries(
                current_user.account_id, repartidor_user_id=repartidor_user_id
            )

            summaries = []
            for row in rows:
                num_clients = row["num_clients"]
                num_vehicles = row["num_vehicles"]

                # Bug real (Ronda 3, ciclo nuevo, repartidor): num_clients/
                # num_vehicles venían de la operación COMPLETA (todos los
                # repartidores), no de la ruta propia — capacity ya viene
                # acotada al vehículo propio desde Postgres (flota_config.
                # capacities[vehicle_id]); num_clients requiere la secuencia
                # real de la ruta, que solo vive en la solución (Mongo). Se
                # consulta solo para las filas ya filtradas a este repartidor
                # (no reintroduce el N+1 de toda la cuenta que este endpoint
                # evita a propósito).
                if repartidor_user_id is not None and mongo_adapter:
                    # row["id"] ya viene namespaced desde Postgres (mismo id
                    # que persiste save_instance) — no volver a namespacear.
                    solution = mongo_adapter.load_solution(row["id"])
                    ruta = next(
                        (r for r in solution.rutas if r.vehicle_id == row["vehicle_id"]),
                        None,
                    ) if solution else None
                    if ruta:
                        num_clients = len(ruta.secuencia)
                        num_vehicles = 1

                summaries.append(InstanceSummary(
                    id=_strip_namespace(current_user.account_id, row["id"]),
                    num_clients=num_clients,
                    num_vehicles=num_vehicles,
                    capacity=row["capacity"],
                    created_at=row["created_at"],
                ))
            return summaries

        except Exception as e:
            logger.error(f"List instances error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

    @app.get("/solutions/{instancia_id}", response_model=SolutionResponse)
    def get_solution(instancia_id: str, current_user: CurrentUser = Depends(get_current_user)):
        """Recupera solución más reciente para una instancia de la cuenta del usuario."""
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)

        # La solución vive en Mongo sin account_id propio — la pertenencia se
        # valida a través de la instancia en Postgres (que sí lo tiene).
        if pg_adapter and not pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id):
            raise HTTPException(status_code=404, detail="Solución no encontrada")

        try:
            solution = mongo_adapter.load_solution(namespaced_id)

            if not solution:
                raise HTTPException(status_code=404, detail="Solución no encontrada")

            rutas = solution.rutas
            # Bug real (Ronda 1, ciclo nuevo, repartidor): este endpoint
            # devolvía todas las rutas de la solución sin filtrar por rol —
            # un repartidor veía sequence/cost de vehículos ajenos, mismo
            # patrón de fuga ya cerrado en my-route/export.pdf/delivery-statuses.
            if current_user.role == "repartidor":
                vehicle_id = pg_adapter.get_assigned_vehicle_for_repartidor(
                    namespaced_id, current_user.user_id
                ) if pg_adapter else None
                rutas = [r for r in rutas if r.vehicle_id == vehicle_id]

            routes = [
                {
                    "vehicle_id": ruta.vehicle_id,
                    "sequence": ruta.secuencia,
                    "cost": ruta.costo
                }
                for ruta in rutas
            ]

            # used_osrm no se persiste junto a la solución (Mongo solo guarda
            # rutas/costo) — no hay forma de reconstruirlo retroactivamente
            # para una solución ya calculada, así que este endpoint no puede
            # afirmar con certeza que usó OSRM. Queda en el default (True) del
            # modelo; extenderlo requeriría persistir el flag junto al resto
            # de la solución, fuera de alcance de este fix puntual.
            return SolutionResponse(
                instancia_id=_strip_namespace(current_user.account_id, solution.instancia_id),
                total_cost=solution.costo_total,
                num_routes=len(solution.rutas),
                routes=routes
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get solution error: {e}")
            raise HTTPException(status_code=500, detail="Error interno del servidor")

    @app.get("/solutions/{instancia_id}/export.pdf")
    def export_solution_pdf(
        instancia_id: str,
        vehicle_id: Optional[int] = None,
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Hoja de ruta en PDF — una página por vehículo, o solo la de `vehicle_id`."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)

        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Solución no encontrada")

        # Un repartidor solo puede descargar la hoja de SU propia ruta — sin
        # esto, cualquiera con un token de repartidor podía pedir el PDF de
        # cualquier vehículo de la cuenta (o todos, sin vehicle_id) y ver
        # nombre/teléfono/dirección de clientes de rutas ajenas, sin tener
        # ninguna asignación. Mismo guard que ya existe en
        # update_delivery_status, aplicado acá también.
        if current_user.role == "repartidor":
            assigned_vehicle = pg_adapter.get_assigned_vehicle_for_repartidor(namespaced_id, current_user.user_id)
            if assigned_vehicle is None:
                raise HTTPException(status_code=403, detail="No tenés una ruta asignada en esta instancia")
            vehicle_id = assigned_vehicle

        solution = mongo_adapter.load_solution(namespaced_id)
        if not solution:
            raise HTTPException(status_code=404, detail="Solución no encontrada")

        # RN-EXP-002: sin este chequeo, un vehicle_id sin ninguna ruta en la
        # solución (typo, o topología de vehículos cambiada tras re-resolver)
        # devolvía 200 con un PDF de 0 páginas de contenido — se veía como
        # una descarga exitosa pero el archivo estaba vacío.
        if vehicle_id is not None and not any(r.vehicle_id == vehicle_id for r in solution.rutas):
            raise HTTPException(
                status_code=404, detail="No hay ruta para el vehículo solicitado en esta solución"
            )

        clientes_by_id = {c.id: c for c in instance.clientes}
        delivery_statuses = pg_adapter.get_client_delivery_statuses(namespaced_id)
        rescheduled_client_ids = {
            cid for cid, status in delivery_statuses.items() if status.get("status") == "reprogramado"
        }
        pdf_bytes = build_route_pdf(
            solution, clientes_by_id, vehicle_id=vehicle_id, rescheduled_client_ids=rescheduled_client_ids
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="ruta_{_safe_filename_component(instancia_id)}.pdf"'},
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
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        if request.status not in MANUALLY_SETTABLE_DELIVERY_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"status debe ser uno de {MANUALLY_SETTABLE_DELIVERY_STATUSES}",
            )

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        if current_user.role == "repartidor":
            assigned_vehicle = pg_adapter.get_assigned_vehicle_for_repartidor(namespaced_id, current_user.user_id)
            if assigned_vehicle is None:
                raise HTTPException(status_code=403, detail="No tenés una ruta asignada en esta instancia")
            if mongo_adapter:
                solution = mongo_adapter.load_solution(namespaced_id)
                own_ruta = next(
                    (r for r in solution.rutas if r.vehicle_id == assigned_vehicle), None
                ) if solution else None
                if not own_ruta or cliente_id not in own_ruta.secuencia:
                    raise HTTPException(status_code=403, detail="Ese pedido no está en tu ruta")
        elif current_user.role not in ("dueño", "operario"):
            raise HTTPException(status_code=403, detail="Rol sin permiso")

        current_statuses = pg_adapter.get_client_delivery_statuses(namespaced_id)
        current_entry = current_statuses.get(cliente_id)
        if current_entry is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        if current_entry["status"] == "reprogramado":
            raise HTTPException(
                status_code=409,
                detail="Este pedido ya fue reprogramado a otra instancia, no se puede modificar acá",
            )

        updated = pg_adapter.update_client_delivery_status(
            namespaced_id, cliente_id, request.status, current_user.user_id, request.note
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        return {"status": request.status, "note": request.note}

    @app.patch("/instances/{instancia_id}/clients/{cliente_id}")
    def update_client(
        instancia_id: str,
        cliente_id: int,
        request: UpdateClientRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Corrige nombre/teléfono/dirección/coordenadas de un cliente ya
        cargado — antes la única forma de arreglar un error de tipeo (ej. en
        el CSV importado) era re-resolver la instancia entera desde cero,
        perdiendo los estados de entrega ya marcados ese día."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        current_client = next((c for c in instance.clientes if c.id == cliente_id), None)
        if not current_client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        current_statuses = pg_adapter.get_client_delivery_statuses(namespaced_id)
        if current_statuses.get(cliente_id, {}).get("status") == "reprogramado":
            raise HTTPException(
                status_code=409,
                detail="Este pedido ya fue reprogramado a otra instancia, no se puede editar acá",
            )

        # model_fields_set distingue "el caller no mandó este campo" (preservar
        # lo persistido) de "lo mandó explícitamente vacío" (borrarlo a
        # propósito) — sin esto, editar solo la coordenada desde un formulario
        # que no tenía el contacto cargado (ej. `contacts` en null tras una
        # reprogramación) blanqueaba nombre/teléfono/dirección en silencio.
        fields_set = request.model_fields_set
        demand = request.demand if "demand" in fields_set else current_client.demanda
        customer_name = request.customer_name if "customer_name" in fields_set else current_client.customer_name
        customer_phone = request.customer_phone if "customer_phone" in fields_set else current_client.customer_phone
        address = request.address if "address" in fields_set else current_client.address

        # Bug real (Ronda 1, ciclo nuevo, dueño): editar la demanda escribía
        # directo a Postgres sin re-validar RN-005/RN-006 (que sí corren en la
        # creación, vía Instancia.__post_init__) — dejaba la instancia con
        # demanda total > capacidad de flota o un cliente > vehículo más
        # grande, corrupción invisible hasta que un load_instance posterior
        # (export PDF, reprogramación, delivery-statuses) explotaba con 500.
        if "demand" in fields_set:
            demanda_total = sum(
                demand if c.id == cliente_id else c.demanda for c in instance.clientes
            )
            if demanda_total > instance.flota.capacidad_total:
                raise HTTPException(
                    status_code=422,
                    detail="La nueva demanda total excede la capacidad de la flota",
                )
            max_capacidad_vehiculo = (
                max(instance.flota.capacidades_vehiculos)
                if instance.flota.capacidades_vehiculos
                else instance.flota.capacidad_por_vehiculo
            )
            if demand > max_capacidad_vehiculo:
                raise HTTPException(
                    status_code=422,
                    detail=f"La nueva demanda excede la capacidad de cualquier vehículo disponible ({max_capacidad_vehiculo})",
                )

        updated = pg_adapter.update_client(
            namespaced_id, cliente_id,
            request.x, request.y, demand,
            customer_name, customer_phone, address,
        )
        if not updated:
            # El chequeo de "no reprogramado" de arriba (línea 904-909) puede
            # perder una carrera contra un reschedule_instance concurrente que
            # marcó al cliente DESPUÉS de ese chequeo — el UPDATE con guard
            # atómico (WHERE ... AND delivery_status != 'reprogramado') es la
            # defensa real, y este es el 409 correcto para ese caso, no un 404
            # genérico que sugeriría erróneamente que el cliente no existe.
            raise HTTPException(
                status_code=409,
                detail="Este pedido ya fue reprogramado a otra instancia, no se puede editar acá",
            )
        return {"id": cliente_id, "x": request.x, "y": request.y, "demand": demand}

    @app.delete("/instances/{instancia_id}")
    def delete_instance_endpoint(
        instancia_id: str,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Elimina una instancia (de prueba, duplicada, o creada por error) y
        todo lo dependiente (clientes, flota, asignaciones — ON DELETE
        CASCADE). Antes no había forma de sacarla de la lista: quedaba
        visible para siempre en GET /instances."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        try:
            deleted = pg_adapter.delete_instance(namespaced_id, account_id=current_user.account_id)
        except psycopg2.Error:
            # Defensa en profundidad: la FK real que causaba esto
            # (rescheduled_to_instancia_id) ya tiene ON DELETE SET NULL
            # (migración 0008), pero cualquier otra dependencia futura hacia
            # instancias.id sin CASCADE/SET NULL debe dar un error explicativo,
            # no un 500 genérico sin manejar.
            raise HTTPException(
                status_code=409,
                detail="No se pudo eliminar la instancia — todavía tiene datos dependientes.",
            )
        if not deleted:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")
        return {"deleted": True}

    @app.get("/instances/{instancia_id}/delivery-statuses", response_model=Dict[int, DeliveryStatusEntry])
    def get_delivery_statuses(
        instancia_id: str,
        current_user: CurrentUser = Depends(get_current_user),
    ):
        """Estado de entrega + nota de cada cliente de una instancia — hidrata
        SolutionSummary con lo que ya se marcó (dueño/operario, o el repartidor
        viendo su propia ruta) en vez de arrancar siempre en "pendiente"."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        if not pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id):
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        statuses = pg_adapter.get_client_delivery_statuses(namespaced_id)

        # Bug real (Ronda 21, ciclo nuevo, repartidor): este endpoint no
        # restringía al repartidor a los clientes de SU propia ruta — a
        # diferencia de get_my_route, update_delivery_status y
        # export_solution_pdf (que ya tienen este mismo guard, con comentario
        # explícito del riesgo). Un repartidor autenticado podía pedir el
        # estado/nota de TODOS los clientes de una instancia de su cuenta,
        # incluidas rutas ajenas — las notas de texto libre suelen tener
        # datos sensibles del domicilio ("no había nadie, dejé aviso con el
        # vecino"). Se filtra a solo los client_id de su vehículo asignado.
        if current_user.role == "repartidor":
            if not mongo_adapter:
                raise HTTPException(status_code=503, detail="MongoDB no disponible")
            vehicle_id = pg_adapter.get_assigned_vehicle_for_repartidor(namespaced_id, current_user.user_id)
            if vehicle_id is None:
                raise HTTPException(status_code=403, detail="No tenés una ruta asignada en esta instancia")
            solution = mongo_adapter.load_solution(namespaced_id)
            ruta = next((r for r in solution.rutas if r.vehicle_id == vehicle_id), None) if solution else None
            allowed_ids = set(ruta.secuencia) if ruta else set()
            statuses = {cid: entry for cid, entry in statuses.items() if cid in allowed_ids}

        return {
            client_id: DeliveryStatusEntry(status=entry["status"], note=entry["note"])
            for client_id, entry in statuses.items()
        }

    @app.get("/instances/{instancia_id}/assignments", response_model=Dict[int, str])
    def get_assignments(
        instancia_id: str,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Asignaciones repartidor↔vehículo ya guardadas — hidrata el selector
        de SolutionSummary tras un reload en vez de mostrar siempre "Sin asignar"."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        if not pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id):
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        return pg_adapter.get_route_assignments(namespaced_id)

    @app.put("/instances/{instancia_id}/assignments")
    def set_assignments(
        instancia_id: str,
        request: AssignmentsRequest,
        current_user: CurrentUser = Depends(require_role("dueño", "operario")),
    ):
        """Asigna un repartidor a cada vehicle_id de la instancia (reemplaza lo anterior)."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        # Sin esto, un vehicle_id inventado (o de otra instancia) quedaba
        # asignado igual — la fila de route_assignments no tiene FK contra
        # las rutas reales de la solución, así que el repartidor asignado
        # jamás vería nada en su vista y la asignación quedaría huérfana en
        # silencio. Se valida contra las rutas de la solución ya resuelta.
        def valid_vehicle_ids_now() -> Optional[set]:
            solution = mongo_adapter.load_solution(namespaced_id) if mongo_adapter else None
            return {ruta.vehicle_id for ruta in solution.rutas} if solution else None

        valid_vehicle_ids = valid_vehicle_ids_now()
        if valid_vehicle_ids is not None:
            for vehicle_id in request.assignments:
                if vehicle_id not in valid_vehicle_ids:
                    raise HTTPException(status_code=422, detail=f"vehicle_id inválido para esta solución: {vehicle_id}")

        for repartidor_user_id in request.assignments.values():
            user = pg_adapter.get_user_by_id(repartidor_user_id)
            if not user or user["account_id"] != current_user.account_id:
                raise HTTPException(status_code=422, detail=f"Usuario inválido: {repartidor_user_id}")
            # Bug real (Ronda 2, ciclo nuevo, operario): faltaba validar el rol
            # del usuario asignado — la UI ya filtra el <select> a repartidores
            # activos, pero el endpoint aceptaba igual un dueño/operario vía
            # llamada directa, dejando una asignación con datos inconsistentes
            # (un dueño mostrado como "repartidor asignado" a una ruta).
            if user["role"] != "repartidor":
                raise HTTPException(status_code=422, detail=f"Usuario inválido: {repartidor_user_id} no es repartidor")

        # get_assigned_vehicle_for_repartidor asume que un repartidor tiene
        # A LO SUMO un vehicle_id por instancia (una sola ruta a la vez) —
        # sin este chequeo, asignar al mismo repartidor a dos vehículos
        # dejaba una de sus dos rutas invisible en "Mi ruta" (la query no
        # tiene ORDER BY y devuelve una fila arbitraria), sin ningún error
        # ni aviso ni para el dueño/operario ni para el repartidor.
        seen_repartidores = set()
        for repartidor_user_id in request.assignments.values():
            if repartidor_user_id in seen_repartidores:
                raise HTTPException(
                    status_code=422,
                    detail="Un repartidor no puede estar asignado a más de un vehículo en la misma instancia",
                )
            seen_repartidores.add(repartidor_user_id)

        # Bug real (Ronda 16, ciclo nuevo, dueño): "Resolver de nuevo" y
        # "Guardar asignaciones" no tienen ningún flag de disabled cruzado —
        # un re-solve concurrente puede recomponer la topología de vehículos
        # (y siempre invalida las asignaciones existentes, ver comentario más
        # abajo en _solve_and_persist) DESPUÉS de que este endpoint validó
        # contra la solución vieja pero ANTES de escribir. Se re-valida
        # inmediatamente antes del write para achicar la ventana de carrera
        # de "toda la duración del request" a "el tiempo entre esta lectura y
        # el write" — no elimina la carrera por completo (requeriría
        # versionar la solución), pero cierra el caso más grave: un re-solve
        # que ya terminó y ya invalidó, pisado en silencio por esta escritura
        # con datos obsoletos.
        if valid_vehicle_ids is not None:
            current_valid_vehicle_ids = valid_vehicle_ids_now()
            if current_valid_vehicle_ids != valid_vehicle_ids:
                raise HTTPException(
                    status_code=409,
                    detail="La instancia se volvió a resolver mientras guardabas — revisá las asignaciones e intentá de nuevo.",
                )

        pg_adapter.set_route_assignments(namespaced_id, request.assignments)
        return {"assignments": request.assignments}

    @app.get("/instances/{instancia_id}/my-route", response_model=MyRouteResponse)
    def get_my_route(instancia_id: str, current_user: CurrentUser = Depends(get_current_user)):
        """Ruta + estado de entrega del vehículo asignado al repartidor autenticado."""
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")
        if not mongo_adapter:
            raise HTTPException(status_code=503, detail="MongoDB no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        vehicle_id = pg_adapter.get_assigned_vehicle_for_repartidor(namespaced_id, current_user.user_id)
        if vehicle_id is None:
            raise HTTPException(status_code=404, detail="No tenés una ruta asignada en esta instancia")

        solution = mongo_adapter.load_solution(namespaced_id)
        if not solution:
            raise HTTPException(status_code=404, detail="Solución no encontrada")
        ruta = next((r for r in solution.rutas if r.vehicle_id == vehicle_id), None)
        if not ruta:
            raise HTTPException(status_code=404, detail="Ruta no encontrada")

        clientes_by_id = {c.id: c for c in instance.clientes}
        statuses = pg_adapter.get_client_delivery_statuses(namespaced_id)
        stops = [
            RouteStop(
                client_id=client_id,
                sequence=i + 1,
                delivery_status=statuses.get(client_id, {}).get("status", "pendiente"),
                delivery_note=statuses.get(client_id, {}).get("note"),
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
        """Crea una instancia nueva con los pedidos no entregados (pendiente/no_encontrado/rechazado).

        Reusa el pipeline de /solve con la misma flota que tenía la instancia original.
        No recalcula automáticamente — el usuario dispara la reprogramación a mano.
        """
        if not pg_adapter:
            raise HTTPException(status_code=503, detail="PostgreSQL no disponible")

        namespaced_id = _namespaced_id(current_user.account_id, instancia_id)
        instance = pg_adapter.load_instance(namespaced_id, account_id=current_user.account_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instancia no encontrada")

        pending = pg_adapter.get_pending_clients(namespaced_id)
        if not pending:
            raise HTTPException(status_code=400, detail="No hay pedidos pendientes para reprogramar")

        # El sufijo -reprog-{...} se genera sobre el id visible (sin namespace)
        # y luego se namespacea igual que cualquier instancia nueva — mantiene
        # el mismo prefijo por cuenta que ya tiene la instancia original.
        new_visible_id = f"{instancia_id}-reprog-{uuid.uuid4().hex[:8]}"
        new_namespaced_id = _namespaced_id(current_user.account_id, new_visible_id)

        # rescheduled_to_instancia_id tiene FK hacia instancias.id, así que la
        # fila tiene que existir antes de que mark_clients_rescheduled pueda
        # apuntarle — pero se crea VACÍA (0 clientes) a propósito: el set de
        # clientes real recién se decide después de marcar atómicamente.
        # mark_clients_rescheduled filtra por estado no-terminal en su propio
        # WHERE, así que si dos reprogramaciones de la misma instancia corren
        # casi al mismo tiempo, la segunda en llegar encuentra los clientes ya
        # en 'reprogramado' y no los vuelve a mover — moved_ids solo trae los
        # ids que ESTA llamada realmente logró apropiarse. Guardar la
        # instancia nueva con el set completo de "pending" ANTES de este
        # filtro (como se hacía antes) dejaba una instancia huérfana con
        # clientes duplicados cuando dos requests perdían/ganaban la carrera
        # — save_instance es idempotente (ON CONFLICT DO UPDATE), así que se
        # llama de nuevo abajo con el contenido final ya correcto.
        placeholder = Instancia(
            id=new_namespaced_id, deposito=instance.deposito, flota=instance.flota, clientes=[],
        )
        pg_adapter.save_instance(placeholder, account_id=current_user.account_id)

        pending_ids = [row["id"] for row in pending]
        try:
            moved_ids = pg_adapter.mark_clients_rescheduled(namespaced_id, pending_ids, new_namespaced_id)
        except psycopg2.Error:
            # Bug real (Ronda 3, ciclo nuevo, operario): si Postgres falla acá
            # (corte de conexión, timeout) DESPUÉS de persistir el placeholder
            # pero antes de marcar los clientes, el placeholder de 0 clientes
            # quedaba huérfano para siempre — a diferencia del caso de "perdió
            # la carrera" (moved_ids vacío) de abajo, que sí lo limpia. Mismo
            # tratamiento: borrar el placeholder antes de propagar el error.
            pg_adapter.delete_instance(new_namespaced_id, account_id=current_user.account_id)
            raise
        if not moved_ids:
            # Esta request perdió la carrera — el placeholder vacío ya
            # persistido no le pertenece a nadie (rescheduled_to_instancia_id
            # de ningún cliente lo referencia, porque moved_ids está vacío),
            # así que se borra para no dejarlo como instancia fantasma de 0
            # clientes visible en GET /instances.
            pg_adapter.delete_instance(new_namespaced_id, account_id=current_user.account_id)
            raise HTTPException(status_code=409, detail="Estos pedidos ya fueron reprogramados por otra solicitud")

        # Bug real (Ronda 17, ciclo nuevo, operario): usar el snapshot `pending`
        # (leído ANTES de mark_clients_rescheduled) para armar la instancia
        # nueva perdía en silencio cualquier PATCH /clients/{id} que hubiera
        # llegado a tiempo entre ese snapshot y el guard atómico de arriba —
        # ambos requests devolvían 200, pero la edición nunca se reflejaba.
        # Se relee el dato fresco de los clientes efectivamente movidos.
        fresh_rows = pg_adapter.get_clients_by_id(namespaced_id, moved_ids)
        new_clientes = [
            Cliente(
                id=row["id"], coordenada=Coordinate(row["x"], row["y"]), demanda=row["demand"],
                customer_name=row["customer_name"], customer_phone=row["customer_phone"], address=row["address"],
            )
            for row in fresh_rows
        ]
        new_instance = Instancia(
            id=new_namespaced_id, deposito=instance.deposito, flota=instance.flota, clientes=new_clientes,
        )
        pg_adapter.save_instance(new_instance, account_id=current_user.account_id)

        return RescheduleResponse(new_instancia_id=new_visible_id, rescheduled_client_ids=moved_ids)

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
