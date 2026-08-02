"""
PostgreSQL Adapter: Instancia + Cliente persistence.

Conecta a PostgreSQL usando psycopg2 con connection pooling.
"""

from typing import List, Optional
import functools
import json
import logging
import os
import threading
import time
from backend_python.models import Instancia, Cliente, Coordinate, Deposito, Flota

try:
    import psycopg2
    from psycopg2 import sql
    HAS_PSYCOPG2 = True
except ImportError:
    try:
        import psycopg as psycopg2
        from psycopg import sql
        HAS_PSYCOPG2 = True
    except ImportError:
        HAS_PSYCOPG2 = False

logger = logging.getLogger(__name__)

CONNECT_RETRIES = 3
CONNECT_RETRY_DELAY_SECONDS = 1


def _locked(method):
    """Serializa el acceso a self.conn entre threads.

    Los endpoints de FastAPI son `def` (síncronos) — Starlette los despacha a
    un threadpool real, y varios requests concurrentes (ej. un repartidor
    tocando 5 paradas casi al mismo tiempo) terminan ejecutando cursor/
    execute/commit/rollback sobre la MISMA conexión psycopg2 en threads
    distintos. psycopg2 no es thread-safe para eso: los statements se pueden
    intercalar y un commit/rollback de un thread corta la transacción en
    curso de otro, perdiendo su UPDATE en silencio (sin ninguna excepción
    visible al cliente — bug real detectado con 5 PUT concurrentes perdiendo
    2-3 de 5 escrituras). Un pool de conexiones sería la solución de fondo,
    pero requiere gestionar conexión-por-request en cada endpoint; este lock
    por instancia es el fix mínimo que preserva la corrección sin reescribir
    el ciclo de vida de la conexión — serializa el acceso, no lo paraleliza,
    aceptable dado el volumen de escrituras de esta app (no es un caso de
    alto throughput).
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            # Bug real (Ronda 1, ciclo nuevo, dueño): CONNECT_RETRIES en
            # __init__ solo cubre la conexión inicial — si Postgres se
            # reinicia (mantenimiento, actualización de imagen Docker)
            # mientras el proceso de la API sigue vivo, self.conn queda con
            # un objeto roto (no None) y CADA acción del dueño/operario que
            # toca Postgres falla con 500 hasta reiniciar el proceso a mano,
            # aunque Postgres ya se haya recuperado solo. self.conn.closed
            # es 0 mientras la conexión sigue viva del lado del cliente —
            # psycopg2 no lo actualiza proactivamente ante un corte remoto,
            # así que este chequeo detecta el caso más común (el propio
            # proceso ya cerró la conexión tras un error previo) sin
            # pretender detectar cualquier corte de red instantáneamente.
            if self.conn is not None and self.conn.closed:
                self._reconnect()
            return method(self, *args, **kwargs)
    return wrapper


class PostgreSQLAdapter:
    """
    Adapter para persistencia en PostgreSQL.

    El schema (tablas, columnas, migraciones) vive en backend_python/migrations/
    (Alembic) — este adapter asume que `alembic upgrade head` ya corrió y solo
    conecta + hace CRUD. Ver backend_python/migrations/versions/ para el DDL.
    """

    def __init__(self, connection_string: str = None):
        """
        Args:
            connection_string: "postgresql://user:pass@localhost/vrp_db"
                             If None, uses DATABASE_URL env var
        """
        if connection_string is None:
            connection_string = os.getenv("DATABASE_URL")
            if not connection_string:
                raise ValueError("DATABASE_URL not set in environment")

        self.connection_string = connection_string
        self.conn = None
        self._lock = threading.Lock()

        if HAS_PSYCOPG2:
            self._reconnect()

    def _reconnect(self) -> None:
        """(Re)establece self.conn con reintentos — usado en __init__ y por
        @_locked cuando detecta que la conexión ya establecida se cerró."""
        last_error = None
        for attempt in range(1, CONNECT_RETRIES + 1):
            try:
                self.conn = psycopg2.connect(self.connection_string, connect_timeout=5)
                return
            except psycopg2.Error as e:
                last_error = e
                logger.warning(
                    f"PostgreSQL connection attempt {attempt}/{CONNECT_RETRIES} failed: {e}"
                )
                if attempt < CONNECT_RETRIES:
                    time.sleep(CONNECT_RETRY_DELAY_SECONDS)
        raise ConnectionError(f"PostgreSQL connection failed after {CONNECT_RETRIES} attempts: {last_error}")

    @_locked
    def save_instance(self, instance: Instancia, account_id: Optional[str] = None) -> bool:
        """
        Persist Instancia to PostgreSQL.

        Returns:
            True if successful
        """
        if self.conn is None:
            return False

        cursor = self.conn.cursor()
        try:
            # Insert instancia
            cursor.execute(
                sql.SQL("""
                    INSERT INTO instancias (id, nombre, num_clientes, depot_x, depot_y, account_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET num_clientes = EXCLUDED.num_clientes
                """),
                [
                    instance.id,
                    "instance",
                    len(instance.clientes),
                    instance.deposito.coordenada.x,
                    instance.deposito.coordenada.y,
                    account_id,
                ]
            )

            # Insert flota config
            cursor.execute(
                sql.SQL("""
                    INSERT INTO flota_config (instancia_id, num_vehicles, capacity, capacities)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (instancia_id) DO UPDATE SET
                        num_vehicles = EXCLUDED.num_vehicles,
                        capacity = EXCLUDED.capacity,
                        capacities = EXCLUDED.capacities
                """),
                [
                    instance.id,
                    instance.flota.num_vehiculos,
                    instance.flota.capacidad_por_vehiculo,
                    instance.flota.capacidades_vehiculos,
                ]
            )

            # Borra clientes que ya no están en el payload nuevo — resolver
            # la MISMA instancia con menos clientes que la corrida anterior
            # (ej. el dueño corrige el archivo y saca 2 direcciones erróneas)
            # dejaba esas filas viejas como basura permanente: el
            # ON CONFLICT DO UPDATE de abajo solo toca los ids presentes en
            # el payload actual, nunca borra los que sobran. Se excluyen los
            # ids del payload actual del DELETE (en vez de un DELETE + INSERT
            # sin condición) para no perder delivery_status/delivery_note ya
            # marcados de los clientes que SÍ siguen — un DELETE total
            # reiniciaría a 'pendiente' hasta pedidos ya entregados.
            current_ids = [client.id for client in instance.clientes]
            cursor.execute(
                sql.SQL("DELETE FROM clientes WHERE instancia_id = %s AND NOT (id = ANY(%s))"),
                [instance.id, current_ids],
            )

            # Insert clientes — executemany en vez de un execute() por fila:
            # con instancias grandes (100-300+ clientes) el loop anterior
            # hacía un roundtrip a Postgres por cliente, todo dentro de la
            # sección crítica de @_locked — bloqueaba cualquier otra
            # operación de Postgres del proceso (login, listar instancias,
            # marcar una entrega) durante varios segundos mientras se
            # guardaba una instancia grande. executemany de psycopg
            # pipelinea los statements en un solo roundtrip de red.
            if instance.clientes:
                # Bug real (Ronda 2, ciclo nuevo, operario): este upsert
                # sobreescribía incondicionalmente demand/x/y/contacto con el
                # snapshot que la instancia tenía al EMPEZAR el solve — un
                # PATCH /clients/{id} (update_client) de otro operario que
                # commiteaba mientras el pipeline NN->SA->3-opt seguía
                # corriendo (puede tardar segundos) se perdía en silencio,
                # ambos requests devolviendo 200. El WHERE de la cláusula DO
                # UPDATE solo pisa la fila si su updated_at en DB sigue
                # coincidiendo con el snapshot que trajo load_instance() —
                # si cambió (edición concurrente), la fila existente gana y
                # el cliente en memoria queda con datos ahora obsoletos, pero
                # eso es preferible a perder la edición sin ningún aviso.
                cursor.executemany(
                    sql.SQL("""
                        INSERT INTO clientes (id, instancia_id, demand, x, y, customer_name, customer_phone, address)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id, instancia_id) DO UPDATE SET
                            demand = EXCLUDED.demand,
                            x = EXCLUDED.x,
                            y = EXCLUDED.y,
                            customer_name = EXCLUDED.customer_name,
                            customer_phone = EXCLUDED.customer_phone,
                            address = EXCLUDED.address,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE clientes.updated_at IS NOT DISTINCT FROM %s
                    """),
                    [
                        (
                            client.id,
                            instance.id,
                            int(client.demanda),
                            client.coordenada.x,
                            client.coordenada.y,
                            client.customer_name,
                            client.customer_phone,
                            client.address,
                            client.updated_at,
                        )
                        for client in instance.clientes
                    ],
                )

            self.conn.commit()
            return True

        except psycopg2.Error as e:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def load_instance(self, instance_id: str, account_id: Optional[str] = None) -> Optional[Instancia]:
        """
        Load Instancia from PostgreSQL.

        Si account_id se especifica, solo devuelve la instancia si pertenece a esa
        cuenta (o no tiene dueño asignado — instancias de antes de Etapa 2).

        Returns:
            Instancia or None if not found
        """
        if self.conn is None:
            return None

        cursor = self.conn.cursor()
        try:
            # Load instancia
            #
            # account_id IS NULL ya NO se trata como accesible por cualquier
            # cuenta — ese fallback era para instancias creadas antes de que
            # existiera multi-tenancy (0002_auth.py), pero hoy toda instancia
            # nueva se crea siempre con account_id (todo pasa por endpoints
            # autenticados). Mantenerlo abría una fuga cross-tenant real:
            # cualquier cuenta nueva veía y podía abrir instancias huérfanas
            # de otras cuentas (datos de clientes reales: nombre, teléfono,
            # dirección), sin ninguna distinción visual de que no eran suyas.
            if account_id is not None:
                cursor.execute(
                    "SELECT depot_x, depot_y, created_at FROM instancias WHERE id = %s AND account_id = %s",
                    [instance_id, account_id]
                )
            else:
                cursor.execute(
                    "SELECT depot_x, depot_y, created_at FROM instancias WHERE id = %s",
                    [instance_id]
                )
            inst_row = cursor.fetchone()
            if not inst_row:
                return None

            # Load flota
            cursor.execute(
                "SELECT num_vehicles, capacity, capacities FROM flota_config WHERE instancia_id = %s",
                [instance_id]
            )
            flota_row = cursor.fetchone()
            if not flota_row:
                return None

            # Load clientes
            cursor.execute(
                "SELECT id, demand, x, y, customer_name, customer_phone, address, updated_at "
                "FROM clientes WHERE instancia_id = %s",
                [instance_id]
            )
            clientes_rows = cursor.fetchall()

            # Build objects
            depot = Deposito(
                Coordinate(inst_row[0], inst_row[1]),
                "Depot"
            )
            capacidades = list(flota_row[2]) if flota_row[2] else None
            flota = Flota(flota_row[0], flota_row[1], capacidades_vehiculos=capacidades)
            clientes = [
                Cliente(
                    int(row[0]), Coordinate(row[2], row[3]), float(row[1]),
                    customer_name=row[4], customer_phone=row[5], address=row[6],
                    updated_at=row[7].isoformat() if row[7] else None,
                )
                for row in clientes_rows
            ]

            # Bug real (Ronda 4, ciclo nuevo, repartidor): created_at es
            # TIMESTAMP (naive) — sin el sufijo "Z", el frontend interpreta
            # el string como hora LOCAL del navegador en vez de UTC,
            # desplazando la hora mostrada según el huso del repartidor.
            # Postgres siempre guarda en UTC en este proyecto (sin TimeZone
            # custom), así que el sufijo es correcto sin migrar la columna.
            created_at = (inst_row[2].isoformat() + "Z") if inst_row[2] else None
            return Instancia(instance_id, depot, flota, clientes, created_at=created_at)

        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    @_locked
    def delete_instance(self, instance_id: str, account_id: Optional[str] = None) -> bool:
        """Borra una instancia y sus filas dependientes (clientes, flota_config,
        route_assignments tienen ON DELETE CASCADE hacia instancias.id;
        clientes.rescheduled_to_instancia_id tiene ON DELETE SET NULL — ver
        migración 0008, bug real: sin esto, borrar una instancia intermedia de
        una cadena de reprogramación A->B->C violaba esa FK con un 500 sin
        manejar, porque los clientes de A seguían apuntando a B).

        Usado para limpiar el placeholder que reschedule_instance crea antes
        de marcar clientes atómicamente — si pierde la carrera de una
        reprogramación concurrente (moved_ids vacío), la instancia vacía no
        debe quedar visible en GET /instances como basura fantasma.
        """
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            if account_id is not None:
                cursor.execute(
                    "DELETE FROM instancias WHERE id = %s AND account_id = %s",
                    [instance_id, account_id],
                )
            else:
                cursor.execute("DELETE FROM instancias WHERE id = %s", [instance_id])
            deleted = cursor.rowcount > 0
            self.conn.commit()
            return deleted
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def update_client(
        self, instance_id: str, client_id: int,
        x: float, y: float, demand: float,
        customer_name: Optional[str], customer_phone: Optional[str], address: Optional[str],
    ) -> bool:
        """Corrige los datos de un cliente ya persistido (ej. error de tipeo
        en la dirección/teléfono de un CSV) sin tener que re-resolver toda
        la instancia desde cero — antes la única forma de arreglar un solo
        campo era re-subir toda la instancia, perdiendo los estados de
        entrega ya marcados ese día vía el flujo de "sobreescribir"."""
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            # Bug real (Ronda 15, ciclo nuevo, operario): el endpoint chequeaba
            # "no reprogramado" con un SELECT separado ANTES de este UPDATE —
            # entre ese chequeo y el commit, un reschedule_instance concurrente
            # podía leer el snapshot viejo (sin esta edición) y marcar el
            # cliente como reprogramado, perdiendo la corrección en silencio
            # (ambos requests devolvían 200). Igual que update_client_delivery_status,
            # el guard va en el propio WHERE para que sea atómico con el UPDATE.
            # updated_at=CURRENT_TIMESTAMP (Ronda 2, ciclo nuevo, operario):
            # marca esta edición como más reciente que cualquier snapshot que
            # un solve concurrente haya cargado antes — save_instance la
            # respeta en vez de pisarla con el upsert al terminar el pipeline.
            cursor.execute(
                """
                UPDATE clientes SET x=%s, y=%s, demand=%s,
                    customer_name=%s, customer_phone=%s, address=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND instancia_id=%s AND delivery_status != 'reprogramado'
                """,
                [x, y, demand, customer_name, customer_phone, address, client_id, instance_id],
            )
            updated = cursor.rowcount > 0
            self.conn.commit()
            return updated
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def list_instances(self, account_id: Optional[str] = None) -> List[str]:
        """List stored instance IDs, optionally scoped to one account."""
        if self.conn is None:
            return []

        cursor = self.conn.cursor()
        try:
            if account_id is not None:
                cursor.execute(
                    "SELECT id FROM instancias WHERE account_id = %s ORDER BY created_at DESC",
                    [account_id],
                )
            else:
                cursor.execute("SELECT id FROM instancias ORDER BY created_at DESC")
            return [row[0] for row in cursor.fetchall()]
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    @_locked
    def list_instance_summaries(
        self, account_id: str, repartidor_user_id: Optional[str] = None,
        limit: Optional[int] = None, offset: int = 0,
    ) -> List[dict]:
        """Resumen (id, num_clients, num_vehicles, capacity, created_at) de cada
        instancia de la cuenta en un solo query agregado — evita el N+1 de
        llamar load_instance() (que trae clientes completos) por cada fila
        solo para exponer un conteo en GET /instances.

        limit/offset opcionales (Ronda 2, ciclo nuevo, dueño): sin límite
        declarado en SPEC.md, ninguna cuenta con muchas instancias históricas
        tenía forma de acotar este listado — sin limit, el comportamiento es
        idéntico al de siempre (trae todo).

        Si repartidor_user_id se pasa, filtra a solo las instancias con una
        ruta asignada a ese repartidor (mismo alcance que
        list_instances_assigned_to, sin el N+1 posterior).
        """
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            if repartidor_user_id is not None:
                # Bug real (Ronda 3, ciclo nuevo, repartidor): num_clients/
                # num_vehicles/capacity eran los de la flota/operación COMPLETA
                # (todos los repartidores), no los de la ruta propia — un
                # repartidor veía "50 clientes, 6 vehículos" cuando a él le
                # tocaban 8. ra.vehicle_id se expone para que el caller (API)
                # pueda leer la ruta específica en Mongo y acotar esos campos
                # sin reintroducir el N+1 que este query ya evita (Mongo se
                # consulta solo para las filas ya acotadas a este repartidor).
                cursor.execute(
                    """
                    SELECT i.id, COUNT(DISTINCT c.id), f.num_vehicles, f.capacity, i.created_at, ra.vehicle_id, f.capacities
                    FROM instancias i
                    JOIN route_assignments ra ON ra.instancia_id = i.id AND ra.repartidor_user_id = %s
                    JOIN flota_config f ON f.instancia_id = i.id
                    LEFT JOIN clientes c ON c.instancia_id = i.id
                    WHERE i.account_id = %s
                    GROUP BY i.id, f.num_vehicles, f.capacity, i.created_at, ra.vehicle_id, f.capacities
                    ORDER BY i.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    [repartidor_user_id, account_id, limit, offset],
                )
            else:
                cursor.execute(
                    """
                    SELECT i.id, COUNT(DISTINCT c.id), f.num_vehicles, f.capacity, i.created_at
                    FROM instancias i
                    JOIN flota_config f ON f.instancia_id = i.id
                    LEFT JOIN clientes c ON c.instancia_id = i.id
                    WHERE i.account_id = %s
                    GROUP BY i.id, f.num_vehicles, f.capacity, i.created_at
                    ORDER BY i.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    [account_id, limit, offset],
                )
            rows_out = []
            for row in cursor.fetchall():
                capacity = row[3]
                vehicle_id = None
                if repartidor_user_id is not None:
                    vehicle_id = row[5]
                    capacities = row[6]
                    if capacities and 0 <= vehicle_id < len(capacities):
                        capacity = capacities[vehicle_id]
                rows_out.append({
                    "id": row[0],
                    "num_clients": row[1],
                    "num_vehicles": row[2],
                    "capacity": capacity,
                    # Ver nota de zona horaria en load_instance() más arriba.
                    "created_at": (row[4].isoformat() + "Z") if row[4] else None,
                    "vehicle_id": vehicle_id,
                })
            return rows_out
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    # --- Auth: accounts + users (Etapa 0b) ---

    @_locked
    def create_account(self, account_id: str, name: str) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("INSERT INTO accounts (id, name) VALUES (%s, %s)"),
                [account_id, name],
            )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def create_account_with_user(
        self, account_id: str, account_name: str,
        user_id: str, email: str, password_hash: str, role: str, full_name: Optional[str] = None,
    ) -> bool:
        """Crea la cuenta y su primer usuario en una sola transacción.

        Bug real (Ronda 2, ciclo nuevo, dueño): /auth/register llamaba
        create_account() y create_user() como dos escrituras independientes,
        cada una con su propio commit — si la segunda fallaba por cualquier
        motivo que no fuera el email duplicado ya capturado (Postgres caído,
        timeout entre ambas), la cuenta quedaba huérfana sin usuario, sin
        ningún endpoint ni proceso para detectarla o recuperarla. Un solo
        cursor + un solo commit/rollback hace que ambos INSERT sean atómicos.
        """
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("INSERT INTO accounts (id, name) VALUES (%s, %s)"),
                [account_id, account_name],
            )
            cursor.execute(
                sql.SQL("""
                    INSERT INTO users (id, account_id, email, password_hash, role, full_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """),
                [user_id, account_id, email, password_hash, role, full_name],
            )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def create_user(
        self, user_id: str, account_id: str, email: str, password_hash: str,
        role: str, full_name: Optional[str] = None,
    ) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    INSERT INTO users (id, account_id, email, password_hash, role, full_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """),
                [user_id, account_id, email, password_hash, role, full_name],
            )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def get_user_by_email(self, email: str) -> Optional[dict]:
        if self.conn is None:
            return None
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, account_id, email, password_hash, role, full_name, active "
                "FROM users WHERE email = %s",
                [email],
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0], "account_id": row[1], "email": row[2],
                "password_hash": row[3], "role": row[4], "full_name": row[5],
                "active": row[6],
            }
        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    @_locked
    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        if self.conn is None:
            return None
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, account_id, email, password_hash, role, full_name, active "
                "FROM users WHERE id = %s",
                [user_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0], "account_id": row[1], "email": row[2],
                "password_hash": row[3], "role": row[4], "full_name": row[5],
                "active": row[6],
            }
        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    @_locked
    def list_users_by_account(
        self, account_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[dict]:
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, email, role, full_name, active FROM users "
                "WHERE account_id = %s ORDER BY created_at LIMIT %s OFFSET %s",
                [account_id, limit, offset],
            )
            return [
                {"id": row[0], "email": row[1], "role": row[2], "full_name": row[3], "active": row[4]}
                for row in cursor.fetchall()
            ]
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    @_locked
    def set_user_active(self, user_id: str, account_id: str, active: bool) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("UPDATE users SET active=%s WHERE id=%s AND account_id=%s"),
                [active, user_id, account_id],
            )
            updated = cursor.rowcount > 0
            self.conn.commit()
            return updated
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    # --- Catálogo de vehículos + zona de cobertura (Etapa 1) ---

    @_locked
    def create_vehicle_type(
        self, vehicle_id: str, account_id: str, name: str,
        weight_capacity_kg: float, volume_capacity_m3: float, tolerance_margin: float,
    ) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    INSERT INTO vehicle_catalog
                        (id, account_id, name, weight_capacity_kg, volume_capacity_m3, tolerance_margin)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """),
                [vehicle_id, account_id, name, weight_capacity_kg, volume_capacity_m3, tolerance_margin],
            )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def list_vehicle_types(
        self, account_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[dict]:
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, name, weight_capacity_kg, volume_capacity_m3, tolerance_margin "
                "FROM vehicle_catalog WHERE account_id = %s ORDER BY created_at LIMIT %s OFFSET %s",
                [account_id, limit, offset],
            )
            return [
                {
                    "id": row[0], "name": row[1], "weight_capacity_kg": row[2],
                    "volume_capacity_m3": row[3], "tolerance_margin": row[4],
                }
                for row in cursor.fetchall()
            ]
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    @_locked
    def update_vehicle_type(
        self, vehicle_id: str, account_id: str, name: str,
        weight_capacity_kg: float, volume_capacity_m3: float, tolerance_margin: float,
    ) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    UPDATE vehicle_catalog SET name=%s, weight_capacity_kg=%s,
                        volume_capacity_m3=%s, tolerance_margin=%s
                    WHERE id=%s AND account_id=%s
                """),
                [name, weight_capacity_kg, volume_capacity_m3, tolerance_margin, vehicle_id, account_id],
            )
            updated = cursor.rowcount > 0
            self.conn.commit()
            return updated
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def delete_vehicle_type(self, vehicle_id: str, account_id: str) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM vehicle_catalog WHERE id=%s AND account_id=%s",
                [vehicle_id, account_id],
            )
            deleted = cursor.rowcount > 0
            self.conn.commit()
            return deleted
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def get_coverage_zone(self, account_id: str) -> Optional[List[List[float]]]:
        if self.conn is None:
            return None
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT points FROM coverage_zones WHERE account_id = %s",
                [account_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            points = row[0]
            # psycopg2 devuelve JSONB ya deserializado (list); psycopg v3 a
            # veces lo entrega como str — normalizar ambos casos.
            return points if isinstance(points, list) else json.loads(points)
        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    @_locked
    def set_coverage_zone(self, account_id: str, points: List[List[float]]) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    INSERT INTO coverage_zones (account_id, points, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (account_id) DO UPDATE SET
                        points = EXCLUDED.points, updated_at = CURRENT_TIMESTAMP
                """),
                [account_id, json.dumps(points)],
            )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def delete_coverage_zone(self, account_id: str) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM coverage_zones WHERE account_id = %s", [account_id])
            deleted = cursor.rowcount > 0
            self.conn.commit()
            return deleted
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    # --- Ciclo de vida de pedido (Etapa 4) ---

    @_locked
    def set_route_assignments(self, instancia_id: str, assignments: dict) -> bool:
        """Reemplaza las asignaciones repartidor↔vehicle_id de una instancia.

        assignments: {vehicle_id: repartidor_user_id}
        """
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM route_assignments WHERE instancia_id = %s", [instancia_id])
            for vehicle_id, repartidor_user_id in assignments.items():
                cursor.execute(
                    sql.SQL("""
                        INSERT INTO route_assignments (instancia_id, vehicle_id, repartidor_user_id)
                        VALUES (%s, %s, %s)
                    """),
                    [instancia_id, int(vehicle_id), repartidor_user_id],
                )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def get_route_assignments(self, instancia_id: str) -> dict:
        """Devuelve {vehicle_id: repartidor_user_id} para una instancia."""
        if self.conn is None:
            return {}
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT vehicle_id, repartidor_user_id FROM route_assignments WHERE instancia_id = %s",
                [instancia_id],
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        except psycopg2.Error:
            return {}
        finally:
            cursor.close()

    @_locked
    def get_assigned_vehicle_for_repartidor(self, instancia_id: str, repartidor_user_id: str) -> Optional[int]:
        """vehicle_id asignado a un repartidor en una instancia, o None si no tiene ninguno."""
        if self.conn is None:
            return None
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT vehicle_id FROM route_assignments WHERE instancia_id = %s AND repartidor_user_id = %s",
                [instancia_id, repartidor_user_id],
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None
        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    @_locked
    def update_client_delivery_status(
        self, instancia_id: str, cliente_id: int, status: str, updated_by_user_id: str,
        note: Optional[str] = None,
    ) -> bool:
        # 'reprogramado' es un estado terminal real: el pedido ya vive como
        # cliente nuevo en otra instancia (rescheduled_to_instancia_id) — sin
        # este filtro, alguien con la ruta vieja todavía abierta (ej. un
        # repartidor que no refrescó) podía marcar "entregado" acá, dejando
        # un registro falso en la instancia vieja mientras el pedido real
        # sigue pendiente en la instancia nueva, sin ningún aviso.
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    UPDATE clientes SET delivery_status = %s, delivery_note = %s,
                        delivery_updated_at = CURRENT_TIMESTAMP, delivery_updated_by = %s
                    WHERE id = %s AND instancia_id = %s AND delivery_status != 'reprogramado'
                """),
                [status, note, updated_by_user_id, cliente_id, instancia_id],
            )
            updated = cursor.rowcount > 0
            self.conn.commit()
            return updated
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    @_locked
    def get_client_delivery_statuses(self, instancia_id: str) -> dict:
        """Devuelve {cliente_id: {"status": ..., "note": ...}} para los clientes de una instancia."""
        if self.conn is None:
            return {}
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, delivery_status, delivery_note FROM clientes WHERE instancia_id = %s",
                [instancia_id],
            )
            return {int(row[0]): {"status": row[1], "note": row[2]} for row in cursor.fetchall()}
        except psycopg2.Error:
            return {}
        finally:
            cursor.close()

    @_locked
    def get_pending_clients(self, instancia_id: str) -> List[dict]:
        """Clientes no-terminales (pendiente, no_encontrado o rechazado) de una instancia — insumo de reschedule."""
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, demand, x, y, customer_name, customer_phone, address "
                "FROM clientes WHERE instancia_id = %s AND delivery_status IN ('pendiente', 'no_encontrado', 'rechazado')",
                [instancia_id],
            )
            return [
                {
                    "id": row[0], "demand": row[1], "x": row[2], "y": row[3],
                    "customer_name": row[4], "customer_phone": row[5], "address": row[6],
                }
                for row in cursor.fetchall()
            ]
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    def get_clients_by_id(self, instancia_id: str, cliente_ids: List[int]) -> List[dict]:
        """Datos actuales de clientes específicos por id, sin filtro de
        delivery_status. Bug real (Ronda 17, ciclo nuevo, operario):
        reschedule_instance usaba el snapshot de get_pending_clients (leído
        ANTES de mark_clients_rescheduled) para armar la instancia nueva —
        una edición válida de PATCH /clients/{id} que llegara entre ese
        snapshot y el guard atómico del reschedule se perdía en silencio,
        porque la instancia nueva se armaba con los datos VIEJOS. Se relee
        después de marcar, para reflejar cualquier edición que haya llegado
        a tiempo."""
        if self.conn is None or not cliente_ids:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, demand, x, y, customer_name, customer_phone, address "
                "FROM clientes WHERE instancia_id = %s AND id = ANY(%s)",
                [instancia_id, cliente_ids],
            )
            return [
                {
                    "id": row[0], "demand": row[1], "x": row[2], "y": row[3],
                    "customer_name": row[4], "customer_phone": row[5], "address": row[6],
                }
                for row in cursor.fetchall()
            ]
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    @_locked
    def mark_clients_rescheduled(self, instancia_id: str, cliente_ids: List[int], new_instancia_id: str) -> List[int]:
        """Marca como 'reprogramado' solo los clientes que TODAVÍA están en un
        estado no-terminal — el filtro de estado en el WHERE (no solo en el
        SELECT previo de get_pending_clients) es lo que evita la doble
        reprogramación concurrente: si dos requests leen el mismo set de
        pendientes y corren casi al mismo tiempo, la segunda en llegar acá ya
        no encuentra 'pendiente/no_encontrado/rechazado' en esas filas (la
        primera ya las puso en 'reprogramado') y su UPDATE no las toca —
        devuelve solo los ids que esta llamada realmente movió, para que el
        caller arme la instancia nueva únicamente con esos.
        """
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    UPDATE clientes SET delivery_status = 'reprogramado', rescheduled_to_instancia_id = %s
                    WHERE instancia_id = %s AND id = ANY(%s)
                        AND delivery_status IN ('pendiente', 'no_encontrado', 'rechazado')
                    RETURNING id
                """),
                [new_instancia_id, instancia_id, cliente_ids],
            )
            moved_ids = [row[0] for row in cursor.fetchall()]
            self.conn.commit()
            return moved_ids
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()
