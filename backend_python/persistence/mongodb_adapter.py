"""
MongoDB Adapter: Solucion + Ruta + CostMatrix persistence.

Conecta a MongoDB usando pymongo.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
import os
import time
from backend_python.models import Solucion, Ruta

try:
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

logger = logging.getLogger(__name__)

CONNECT_RETRIES = 3
CONNECT_RETRY_DELAY_SECONDS = 1


class MongoDBAdapter:
    """
    Adapter para persistencia en MongoDB.

    Colecciones:
    - soluciones: { _id, instancia_id, rutas[], total_cost, timestamp, metadata }
    - cost_matrices: { _id, instancia_id, n, data_binary, timestamp }
    """

    def __init__(self, connection_string: str = None):
        """
        Args:
            connection_string: "mongodb://localhost:27017/vrp_db"
                             If None, uses MONGO_URL env var
        """
        if connection_string is None:
            connection_string = os.getenv("MONGO_URL", "mongodb://localhost:27017/vrp_db")

        self.connection_string = connection_string
        self.client = None
        self.db = None

        if HAS_PYMONGO:
            last_error = None
            for attempt in range(1, CONNECT_RETRIES + 1):
                try:
                    self.client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
                    self.client.admin.command("ping")  # Test connection
                    self.db = self.client.vrp_db
                    self._init_indexes()
                    return
                except ServerSelectionTimeoutError as e:
                    last_error = e
                    logger.warning(
                        f"MongoDB connection attempt {attempt}/{CONNECT_RETRIES} failed: {e}"
                    )
                    if attempt < CONNECT_RETRIES:
                        time.sleep(CONNECT_RETRY_DELAY_SECONDS)
            raise ConnectionError(
                f"MongoDB connection failed after {CONNECT_RETRIES} attempts: {connection_string} ({last_error})"
            )

    def _init_indexes(self):
        """Create indexes for collections."""
        if self.db is None:
            return

        # Indexes for soluciones
        self.db.soluciones.create_index([("instancia_id", 1), ("timestamp", -1)])
        self.db.soluciones.create_index([("instancia_id", 1), ("total_cost", 1)])

        # Indexes for cost_matrices
        self.db.cost_matrices.create_index([("instancia_id", 1)], unique=True)

    def save_solution(self, solution: Solucion, metadata: Dict[str, Any] = None) -> bool:
        """
        Persist Solucion to MongoDB.

        Args:
            solution: Solucion to save
            metadata: Optional metadata (solver_time, gap, etc.)

        Returns:
            True if successful
        """
        if self.db is None:
            return False

        try:
            doc = {
                "_id": f"{solution.instancia_id}_{datetime.now(timezone.utc).isoformat()}",
                "instancia_id": solution.instancia_id,
                "rutas": [
                    {
                        "vehicle_id": ruta.vehicle_id,
                        "sequence": ruta.secuencia,
                        "cost": ruta.costo
                    }
                    for ruta in solution.rutas
                ],
                "total_cost": solution.costo_total,
                "timestamp": datetime.now(timezone.utc),
                "metadata": metadata or {}
            }
            self.db.soluciones.insert_one(doc)
            return True
        except Exception as e:
            logger.error(f"save_solution failed for {solution.instancia_id}: {e}")
            return False

    def load_solution(self, instancia_id: str, timestamp: Optional[str] = None) -> Optional[Solucion]:
        """
        Load best Solucion for instancia_id.

        Args:
            instancia_id: Instance ID
            timestamp: Optional - load specific version (ISO format)

        Returns:
            Solucion or None if not found
        """
        if self.db is None:
            return None

        try:
            query = {"instancia_id": instancia_id}
            if timestamp:
                query["timestamp"] = {"$lte": datetime.fromisoformat(timestamp)}

            doc = self.db.soluciones.find_one(query, sort=[("timestamp", -1)])

            if not doc:
                return None

            # Reconstruct Solucion
            rutas = [
                Ruta(
                    vehicle_id=r["vehicle_id"],
                    secuencia=r["sequence"],
                    costo=r["cost"]
                )
                for r in doc["rutas"]
            ]

            return Solucion(
                instancia_id=doc["instancia_id"],
                rutas=rutas,
                costo_total=doc["total_cost"]
            )

        except Exception as e:
            logger.error(f"load_solution failed for {instancia_id}: {e}")
            return None

    def list_solutions(self, instancia_id: str) -> List[Dict[str, Any]]:
        """
        List all solutions for instance.

        Returns:
            List of { _id, timestamp, total_cost }
        """
        if self.db is None:
            return []

        try:
            docs = list(
                self.db.soluciones.find(
                    {"instancia_id": instancia_id},
                    {"_id": 1, "timestamp": 1, "total_cost": 1}
                ).sort("timestamp", -1)
            )
            return [
                {
                    "_id": doc["_id"],
                    "timestamp": doc["timestamp"].isoformat(),
                    "total_cost": doc["total_cost"]
                }
                for doc in docs
            ]
        except Exception as e:
            logger.error(f"list_solutions failed for {instancia_id}: {e}")
            return []

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
        if self.db is None:
            return False

        try:
            doc = {
                "_id": f"{instancia_id}_costmatrix",
                "instancia_id": instancia_id,
                "n": n,
                "data": data,
                "timestamp": datetime.utcnow()
            }
            self.db.cost_matrices.replace_one(
                {"_id": doc["_id"]},
                doc,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"save_cost_matrix failed for {instancia_id}: {e}")
            return False

    def load_cost_matrix(self, instancia_id: str) -> Optional[tuple]:
        """
        Load cost matrix.

        Returns:
            (n, data) or None if not found
        """
        if self.db is None:
            return None

        try:
            doc = self.db.cost_matrices.find_one({"instancia_id": instancia_id})
            if doc:
                return (doc["n"], doc["data"])
            return None
        except Exception as e:
            logger.error(f"load_cost_matrix failed for {instancia_id}: {e}")
            return None

    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()


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
