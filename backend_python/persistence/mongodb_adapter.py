"""
MongoDB Adapter: Solucion + Ruta + CostMatrix persistence.

Mínimo sin ORM. Usa json serialization para documentos.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from backend_python.models import Solucion, Ruta


class MongoDBAdapter:
    """
    Adapter para persistencia en MongoDB.

    Colecciones:
    - soluciones: { instancia_id, rutas[], total_cost, timestamp, metadata }
    - cost_matrices: { instancia_id, n, data_binary, timestamp }
    """

    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: "mongodb://localhost:27017/vrp_db"
        """
        self.connection_string = connection_string
        self.db = None
        # In real implementation: from pymongo import MongoClient
        # self.db = MongoClient(connection_string)["vrp_db"]

    def save_solution(self, solution: Solucion, metadata: Dict[str, Any] = None) -> bool:
        """
        Persist Solucion to MongoDB.

        Args:
            solution: Solucion to save
            metadata: Optional metadata (solver_time, gap, etc.)

        Returns:
            True if successful
        """
        # Pseudo-code:
        # doc = {
        #     "_id": f"{solution.instancia_id}_{timestamp}",
        #     "instancia_id": solution.instancia_id,
        #     "rutas": [
        #         {
        #             "vehicle_id": ruta.vehicle_id,
        #             "sequence": ruta.secuencia,
        #             "cost": ruta.costo
        #         }
        #         for ruta in solution.rutas
        #     ],
        #     "total_cost": solution.costo_total,
        #     "timestamp": datetime.utcnow(),
        #     "metadata": metadata or {}
        # }
        # self.db.soluciones.insert_one(doc)

        return True  # Stub

    def load_solution(self, instancia_id: str, timestamp: Optional[str] = None) -> Optional[Solucion]:
        """
        Load best Solucion for instancia_id.

        Args:
            instancia_id: Instance ID
            timestamp: Optional - load specific version

        Returns:
            Solucion or None if not found
        """
        # Pseudo-code:
        # query = {"instancia_id": instancia_id}
        # if timestamp:
        #     query["timestamp"] = {"$lte": datetime.fromisoformat(timestamp)}
        # doc = self.db.soluciones.find_one(query, sort=[("timestamp", -1)])
        # IF doc FOUND:
        #     rutas = [Ruta(...) for r in doc["rutas"]]
        #     return Solucion(instancia_id=doc["instancia_id"], rutas=rutas, ...)

        return None  # Stub

    def list_solutions(self, instancia_id: str) -> List[Dict[str, Any]]:
        """
        List all solutions for instance.

        Returns:
            List of { timestamp, total_cost, gap_to_best }
        """
        # SELECT * FROM soluciones WHERE instancia_id ORDER BY timestamp DESC
        return []  # Stub

    def save_cost_matrix(self, instancia_id: str, n: int, data: bytes) -> bool:
        """
        Persist cost matrix (binary).

        Args:
            instancia_id: Instance ID
            n: Matrix size
            data: Flattened cost matrix as bytes

        Returns:
            True if successful
        """
        # doc = {
        #     "_id": f"{instancia_id}_costmatrix",
        #     "instancia_id": instancia_id,
        #     "n": n,
        #     "data": data,  # Binary data (numpy array serialized)
        #     "timestamp": datetime.utcnow()
        # }
        # self.db.cost_matrices.insert_one(doc)

        return True  # Stub

    def load_cost_matrix(self, instancia_id: str) -> Optional[tuple]:
        """
        Load cost matrix.

        Returns:
            (n, data) or None if not found
        """
        # doc = self.db.cost_matrices.find_one({"instancia_id": instancia_id})
        # IF doc: return (doc["n"], doc["data"])

        return None  # Stub


class MongoDBSchema:
    """Index and collection initialization."""

    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """Return index definitions for MongoDB."""
        return [
            {
                "collection": "soluciones",
                "index": {"instancia_id": 1, "timestamp": -1},
                "unique": False
            },
            {
                "collection": "soluciones",
                "index": {"instancia_id": 1, "total_cost": 1},
                "unique": False
            },
            {
                "collection": "cost_matrices",
                "index": {"instancia_id": 1},
                "unique": True
            },
        ]
