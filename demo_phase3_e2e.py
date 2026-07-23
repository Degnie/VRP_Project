#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo End-to-End Phase 3: Solve + Persist (PostgreSQL + MongoDB) + Retrieve

Pipeline completo:
1. Crear instancia VRP
2. Persistir en PostgreSQL
3. Resolver con NN → SA → 3-opt
4. Persistir solución en MongoDB
5. Recuperar instancia desde PostgreSQL
6. Recuperar solución desde MongoDB
7. Validar consistencia
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend_python.models import Coordinate, Cliente, Deposito, Flota, Instancia
from backend_python.service.solver_orchestrator import solve_instance
from backend_python.config import get_config
from backend_python.persistence.postgres_adapter import PostgreSQLAdapter
from backend_python.persistence.mongodb_adapter import MongoDBAdapter


def main():
    print("=" * 80)
    print("VRP SOLVER DEMO - Phase 3 - End-to-End (Solve + Persist + Retrieve)")
    print("=" * 80)

    # Initialize adapters
    config = get_config()
    pg_adapter = None
    mongo_adapter = None

    try:
        pg_adapter = PostgreSQLAdapter(config.DATABASE_URL)
        print("\n[✓] PostgreSQL adapter initialized")
    except Exception as e:
        print(f"\n[✗] PostgreSQL connection failed: {e}")
        print("    Continuing with Python fallback (no persistence)")

    try:
        mongo_adapter = MongoDBAdapter(config.MONGO_URL)
        print("[✓] MongoDB adapter initialized")
    except Exception as e:
        print(f"[✗] MongoDB connection failed: {e}")
        print("    Continuing without solution persistence")

    # Step 1: Create instance
    print("\n" + "=" * 80)
    print("[1/5] Creating VRP Instance")
    print("=" * 80)

    depot = Deposito(Coordinate(0.0, 0.0), "Central Depot")
    flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=400)
    clientes = [
        Cliente(1, Coordinate(10.0, 5.0), 100),
        Cliente(2, Coordinate(15.0, 15.0), 120),
        Cliente(3, Coordinate(5.0, 20.0), 80),
        Cliente(4, Coordinate(20.0, 25.0), 110),
        Cliente(5, Coordinate(25.0, 10.0), 90),
    ]

    instance = Instancia(
        id="phase3_e2e_demo",
        deposito=depot,
        flota=flota,
        clientes=clientes
    )

    print(f"Instance ID: {instance.id}")
    print(f"Clients: {len(instance.clientes)}")
    print(f"Vehicles: {instance.flota.num_vehiculos}")
    print(f"Vehicle Capacity: {instance.flota.capacidad_por_vehiculo}")
    print(f"Total Demand: {sum(c.demanda for c in instance.clientes)}")

    # Step 2: Persist instance (PostgreSQL)
    print("\n" + "=" * 80)
    print("[2/5] Persisting Instance to PostgreSQL")
    print("=" * 80)

    if pg_adapter:
        try:
            pg_adapter.save_instance(instance)
            print(f"[✓] Instance saved to PostgreSQL")
        except Exception as e:
            print(f"[✗] Failed to save instance: {e}")
    else:
        print("[⊘] PostgreSQL not available, skipping")

    # Step 3: Solve instance
    print("\n" + "=" * 80)
    print("[3/5] Solving Instance (NN → SA → 3-opt)")
    print("=" * 80)

    try:
        solution = solve_instance(instance)
        print(f"[✓] Solution found")
        print(f"    Total Cost: {solution.costo_total:.2f}")
        print(f"    Routes: {len(solution.rutas)}")

        for i, ruta in enumerate(solution.rutas):
            route_demand = sum(
                c.demanda
                for c in instance.clientes
                if c.id in ruta.secuencia
            )
            print(f"    Route {i} (Vehicle {ruta.vehicle_id}): "
                  f"sequence={ruta.secuencia}, cost={ruta.costo:.2f}, load={route_demand}")

    except Exception as e:
        print(f"[✗] Solve failed: {e}")
        return 1

    # Step 4: Persist solution (MongoDB)
    print("\n" + "=" * 80)
    print("[4/5] Persisting Solution to MongoDB")
    print("=" * 80)

    if mongo_adapter:
        try:
            mongo_adapter.save_solution(
                solution,
                metadata={"phase": "Phase 3", "solver": "NN_SA_3opt"}
            )
            print(f"[✓] Solution saved to MongoDB")
        except Exception as e:
            print(f"[✗] Failed to save solution: {e}")
    else:
        print("[⊘] MongoDB not available, skipping")

    # Step 5: Retrieve and validate
    print("\n" + "=" * 80)
    print("[5/5] Retrieving and Validating")
    print("=" * 80)

    # Retrieve instance from PostgreSQL
    if pg_adapter:
        try:
            retrieved_inst = pg_adapter.load_instance(instance.id)
            if retrieved_inst:
                print(f"[✓] Instance retrieved from PostgreSQL")
                print(f"    Loaded {len(retrieved_inst.clientes)} clients")
                assert len(retrieved_inst.clientes) == len(instance.clientes)
                print(f"    ✓ Client count matches")
            else:
                print(f"[✗] Instance not found in PostgreSQL")
        except Exception as e:
            print(f"[✗] Failed to retrieve instance: {e}")
    else:
        print("[⊘] PostgreSQL not available, skipping instance retrieval")

    # Retrieve solution from MongoDB
    if mongo_adapter:
        try:
            retrieved_sol = mongo_adapter.load_solution(instance.id)
            if retrieved_sol:
                print(f"[✓] Solution retrieved from MongoDB")
                print(f"    Cost: {retrieved_sol.costo_total:.2f}")
                assert abs(retrieved_sol.costo_total - solution.costo_total) < 1e-6
                print(f"    ✓ Cost matches")
            else:
                print(f"[✗] Solution not found in MongoDB")
        except Exception as e:
            print(f"[✗] Failed to retrieve solution: {e}")
    else:
        print("[⊘] MongoDB not available, skipping solution retrieval")

    # Final validation
    print("\n" + "=" * 80)
    print("Final Validation")
    print("=" * 80)

    all_visited = set()
    for ruta in solution.rutas:
        all_visited.update(ruta.secuencia)

    if len(all_visited) == len(instance.clientes):
        print(f"[✓] All clients visited ({len(all_visited)} clients)")
    else:
        print(f"[✗] Some clients not visited: {set(c.id for c in instance.clientes) - all_visited}")

    for ruta in solution.rutas:
        route_demand = sum(
            c.demanda
            for c in instance.clientes
            if c.id in ruta.secuencia
        )
        if route_demand <= instance.flota.capacidad_por_vehiculo:
            print(f"[✓] Route {ruta.vehicle_id} respects capacity ({route_demand}/{instance.flota.capacidad_por_vehiculo})")
        else:
            print(f"[✗] Route {ruta.vehicle_id} exceeds capacity")

    if abs(solution.costo_total - sum(r.costo for r in solution.rutas)) < 1e-6:
        print(f"[✓] Cost calculation verified")
    else:
        print(f"[✗] Cost mismatch")

    print("\n" + "=" * 80)
    print("END-TO-END DEMO COMPLETE")
    print("=" * 80)

    # Cleanup
    if pg_adapter:
        pg_adapter.close()
    if mongo_adapter:
        mongo_adapter.close()

    return 0


if __name__ == "__main__":
    exit(main())
