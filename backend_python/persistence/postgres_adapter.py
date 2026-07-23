"""
PostgreSQL Adapter: Instancia + Cliente persistence.

Conecta a PostgreSQL usando psycopg2 con connection pooling.
"""

from typing import List, Optional
import os
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


class PostgreSQLAdapter:
    """
    Adapter para persistencia en PostgreSQL.

    Esquema:
    - instancias: (id, nombre, num_clientes, depot_x, depot_y, created_at)
    - clientes: (id, instancia_id, demand, x, y)
    - flota_config: (instancia_id, num_vehicles, capacity)
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
            try:
                self.conn = psycopg2.connect(connection_string)
                self._init_schema()
            except psycopg2.Error as e:
                raise ConnectionError(f"PostgreSQL connection failed: {e}")

    def _init_schema(self):
        """Create tables if they don't exist."""
        if self.conn is None:
            return

        cursor = self.conn.cursor()
        try:
            for ddl in PostgreSQLSchema.get_create_tables():
                cursor.execute(ddl)
            self.conn.commit()
        except psycopg2.Error as e:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def save_instance(self, instance: Instancia) -> bool:
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
                    INSERT INTO instancias (id, nombre, num_clientes, depot_x, depot_y)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET num_clientes = EXCLUDED.num_clientes
                """),
                [
                    instance.id,
                    "instance",
                    len(instance.clientes),
                    instance.deposito.coordenada.x,
                    instance.deposito.coordenada.y,
                ]
            )

            # Insert flota config
            cursor.execute(
                sql.SQL("""
                    INSERT INTO flota_config (instancia_id, num_vehicles, capacity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (instancia_id) DO UPDATE SET
                        num_vehicles = EXCLUDED.num_vehicles,
                        capacity = EXCLUDED.capacity
                """),
                [
                    instance.id,
                    instance.flota.num_vehiculos,
                    instance.flota.capacidad_por_vehiculo,
                ]
            )

            # Insert clientes
            for client in instance.clientes:
                cursor.execute(
                    sql.SQL("""
                        INSERT INTO clientes (id, instancia_id, demand, x, y)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id, instancia_id) DO UPDATE SET
                            demand = EXCLUDED.demand,
                            x = EXCLUDED.x,
                            y = EXCLUDED.y
                    """),
                    [
                        client.id,
                        instance.id,
                        int(client.demanda),
                        client.coordenada.x,
                        client.coordenada.y,
                    ]
                )

            self.conn.commit()
            return True

        except psycopg2.Error as e:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def load_instance(self, instance_id: str) -> Optional[Instancia]:
        """
        Load Instancia from PostgreSQL.

        Returns:
            Instancia or None if not found
        """
        if self.conn is None:
            return None

        cursor = self.conn.cursor()
        try:
            # Load instancia
            cursor.execute(
                "SELECT depot_x, depot_y FROM instancias WHERE id = %s",
                [instance_id]
            )
            inst_row = cursor.fetchone()
            if not inst_row:
                return None

            # Load flota
            cursor.execute(
                "SELECT num_vehicles, capacity FROM flota_config WHERE instancia_id = %s",
                [instance_id]
            )
            flota_row = cursor.fetchone()
            if not flota_row:
                return None

            # Load clientes
            cursor.execute(
                "SELECT id, demand, x, y FROM clientes WHERE instancia_id = %s",
                [instance_id]
            )
            clientes_rows = cursor.fetchall()

            # Build objects
            depot = Deposito(
                Coordinate(inst_row[0], inst_row[1]),
                "Depot"
            )
            flota = Flota(flota_row[0], flota_row[1])
            clientes = [
                Cliente(int(row[0]), Coordinate(row[2], row[3]), float(row[1]))
                for row in clientes_rows
            ]

            return Instancia(instance_id, depot, flota, clientes)

        except psycopg2.Error:
            return None
        finally:
            cursor.close()

    def list_instances(self) -> List[str]:
        """List all stored instance IDs."""
        if self.conn is None:
            return []

        cursor = self.conn.cursor()
        try:
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


class PostgreSQLSchema:
    """DDL statements for PostgreSQL schema."""

    @staticmethod
    def get_create_tables() -> List[str]:
        """Return CREATE TABLE statements."""
        return [
            """
            CREATE TABLE IF NOT EXISTS instancias (
                id VARCHAR(255) PRIMARY KEY,
                nombre VARCHAR(255),
                num_clientes INT,
                depot_x FLOAT,
                depot_y FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS flota_config (
                instancia_id VARCHAR(255) PRIMARY KEY REFERENCES instancias(id) ON DELETE CASCADE,
                num_vehicles INT NOT NULL,
                capacity FLOAT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id INT NOT NULL,
                instancia_id VARCHAR(255) NOT NULL REFERENCES instancias(id) ON DELETE CASCADE,
                demand FLOAT NOT NULL,
                x FLOAT NOT NULL,
                y FLOAT NOT NULL,
                PRIMARY KEY (id, instancia_id)
            );
            """,
        ]
