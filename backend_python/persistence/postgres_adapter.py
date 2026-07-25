"""
PostgreSQL Adapter: Instancia + Cliente persistence.

Conecta a PostgreSQL usando psycopg2 con connection pooling.
"""

from typing import List, Optional
import json
import logging
import os
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

        if HAS_PSYCOPG2:
            last_error = None
            for attempt in range(1, CONNECT_RETRIES + 1):
                try:
                    self.conn = psycopg2.connect(connection_string, connect_timeout=5)
                    return
                except psycopg2.Error as e:
                    last_error = e
                    logger.warning(
                        f"PostgreSQL connection attempt {attempt}/{CONNECT_RETRIES} failed: {e}"
                    )
                    if attempt < CONNECT_RETRIES:
                        time.sleep(CONNECT_RETRY_DELAY_SECONDS)
            raise ConnectionError(f"PostgreSQL connection failed after {CONNECT_RETRIES} attempts: {last_error}")

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

            # Insert clientes
            for client in instance.clientes:
                cursor.execute(
                    sql.SQL("""
                        INSERT INTO clientes (id, instancia_id, demand, x, y, customer_name, customer_phone, address)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id, instancia_id) DO UPDATE SET
                            demand = EXCLUDED.demand,
                            x = EXCLUDED.x,
                            y = EXCLUDED.y,
                            customer_name = EXCLUDED.customer_name,
                            customer_phone = EXCLUDED.customer_phone,
                            address = EXCLUDED.address
                    """),
                    [
                        client.id,
                        instance.id,
                        int(client.demanda),
                        client.coordenada.x,
                        client.coordenada.y,
                        client.customer_name,
                        client.customer_phone,
                        client.address,
                    ]
                )

            self.conn.commit()
            return True

        except psycopg2.Error as e:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

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
            if account_id is not None:
                cursor.execute(
                    "SELECT depot_x, depot_y FROM instancias WHERE id = %s AND (account_id = %s OR account_id IS NULL)",
                    [instance_id, account_id]
                )
            else:
                cursor.execute(
                    "SELECT depot_x, depot_y FROM instancias WHERE id = %s",
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
                "SELECT id, demand, x, y, customer_name, customer_phone, address "
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
                )
                for row in clientes_rows
            ]

            return Instancia(instance_id, depot, flota, clientes)

        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    def list_instances(self, account_id: Optional[str] = None) -> List[str]:
        """List stored instance IDs, optionally scoped to one account."""
        if self.conn is None:
            return []

        cursor = self.conn.cursor()
        try:
            if account_id is not None:
                cursor.execute(
                    "SELECT id FROM instancias WHERE account_id = %s OR account_id IS NULL ORDER BY created_at DESC",
                    [account_id],
                )
            else:
                cursor.execute("SELECT id FROM instancias ORDER BY created_at DESC")
            return [row[0] for row in cursor.fetchall()]
        except psycopg2.Error:
            return []
        finally:
            cursor.close()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    # --- Auth: accounts + users (Etapa 0b) ---

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

    # --- Catálogo de vehículos + zona de cobertura (Etapa 1) ---

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

    def list_vehicle_types(self, account_id: str) -> List[dict]:
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, name, weight_capacity_kg, volume_capacity_m3, tolerance_margin "
                "FROM vehicle_catalog WHERE account_id = %s ORDER BY created_at",
                [account_id],
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

    def update_client_delivery_status(
        self, instancia_id: str, cliente_id: int, status: str, updated_by_user_id: str,
    ) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    UPDATE clientes SET delivery_status = %s,
                        delivery_updated_at = CURRENT_TIMESTAMP, delivery_updated_by = %s
                    WHERE id = %s AND instancia_id = %s
                """),
                [status, updated_by_user_id, cliente_id, instancia_id],
            )
            updated = cursor.rowcount > 0
            self.conn.commit()
            return updated
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def get_client_delivery_statuses(self, instancia_id: str) -> dict:
        """Devuelve {cliente_id: delivery_status} para todos los clientes de una instancia."""
        if self.conn is None:
            return {}
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, delivery_status FROM clientes WHERE instancia_id = %s",
                [instancia_id],
            )
            return {int(row[0]): row[1] for row in cursor.fetchall()}
        except psycopg2.Error:
            return {}
        finally:
            cursor.close()

    def get_pending_clients(self, instancia_id: str) -> List[dict]:
        """Clientes no-terminales (pendiente o no_encontrado) de una instancia — insumo de reschedule."""
        if self.conn is None:
            return []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, demand, x, y, customer_name, customer_phone, address "
                "FROM clientes WHERE instancia_id = %s AND delivery_status IN ('pendiente', 'no_encontrado')",
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

    def mark_clients_rescheduled(self, instancia_id: str, cliente_ids: List[int], new_instancia_id: str) -> bool:
        if self.conn is None:
            return False
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                sql.SQL("""
                    UPDATE clientes SET delivery_status = 'reprogramado', rescheduled_to_instancia_id = %s
                    WHERE instancia_id = %s AND id = ANY(%s)
                """),
                [new_instancia_id, instancia_id, cliente_ids],
            )
            self.conn.commit()
            return True
        except psycopg2.Error:
            self.conn.rollback()
            raise
        finally:
            cursor.close()
