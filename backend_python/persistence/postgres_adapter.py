"""
PostgreSQL Adapter: Instancia + Cliente persistence.

Mínimo sin ORM (YAGNI). Usa SQL raw para inserts/selects.
"""

from typing import List, Optional
from backend_python.models import Instancia, Cliente, Coordinate, Deposito, Flota


class PostgreSQLAdapter:
    """
    Adapter para persistencia en PostgreSQL.

    Esquema:
    - instancias: (id, nombre, num_clientes, flota_id)
    - clientes: (id, instancia_id, demand, x, y)
    - flota_config: (id, num_vehicles, capacity)
    """

    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: "postgresql://user:pass@localhost/vrp_db"
        """
        self.connection_string = connection_string
        self.conn = None
        # In real implementation, would do: import psycopg2; self.conn = psycopg2.connect(...)

    def save_instance(self, instance: Instancia) -> bool:
        """
        Persist Instancia to PostgreSQL.

        Returns:
            True if successful
        """
        # Pseudo-code (actual would use psycopg2)
        # INSERT INTO instancias (id, nombre, num_clientes, depot_x, depot_y)
        # VALUES (instance.id, 'nombre', len(instance.clientes),
        #         instance.deposito.coordenada.x, instance.deposito.coordenada.y)
        #
        # INSERT INTO flota_config (instancia_id, num_vehicles, capacity)
        # VALUES (instance.id, instance.flota.num_vehiculos, instance.flota.capacidad_por_vehiculo)
        #
        # FOR each client:
        #   INSERT INTO clientes (id, instancia_id, demand, x, y)
        #   VALUES (client.id, instance.id, client.demanda, client.coordenada.x, client.coordenada.y)

        return True  # Stub

    def load_instance(self, instance_id: str) -> Optional[Instancia]:
        """
        Load Instancia from PostgreSQL.

        Returns:
            Instancia or None if not found
        """
        # Pseudo-code:
        # SELECT * FROM instancias WHERE id = instance_id
        # SELECT * FROM clientes WHERE instancia_id = instance_id
        # SELECT * FROM flota_config WHERE instancia_id = instance_id
        # BUILD Instancia from rows

        return None  # Stub

    def list_instances(self) -> List[str]:
        """List all stored instance IDs."""
        # SELECT id FROM instancias ORDER BY created_at DESC
        return []  # Stub


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
                id SERIAL PRIMARY KEY,
                instancia_id VARCHAR(255) UNIQUE REFERENCES instancias(id),
                num_vehicles INT,
                capacity FLOAT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id INT,
                instancia_id VARCHAR(255) REFERENCES instancias(id),
                demand INT,
                x FLOAT,
                y FLOAT,
                PRIMARY KEY (id, instancia_id)
            );
            """,
        ]
