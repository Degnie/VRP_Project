#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo: Resolver una instancia VRP simple usando el solver híbrido.

Ejecutar: python demo.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia
)
from backend_python.service.solver_orchestrator import solve_instance


def main():
    print("=" * 60)
    print("VRP SOLVER DEMO - v0.1.0-alpha")
    print("=" * 60)

    # Create simple instance: 5 clients, 1 vehicle
    print("\n[1/3] Creating instance...")
    depot = Deposito(Coordinate(0.0, 0.0), "Main Warehouse")
    flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=300)

    clientes = [
        Cliente(1, Coordinate(10.0, 10.0), 100),
        Cliente(2, Coordinate(20.0, 10.0), 80),
        Cliente(3, Coordinate(10.0, 20.0), 120),
        Cliente(4, Coordinate(30.0, 30.0), 90),
    ]

    instance = Instancia(
        id="demo_instance_001",
        deposito=depot,
        flota=flota,
        clientes=clientes
    )

    print(f"✓ Instance created:")
    print(f"  - ID: {instance.id}")
    print(f"  - Clients: {len(instance.clientes)}")
    print(f"  - Vehicles: {instance.flota.num_vehiculos}")
    print(f"  - Vehicle capacity: {instance.flota.capacidad_por_vehiculo}")
    print(f"  - Total demand: {sum(c.demanda for c in instance.clientes)}")

    # Solve
    print("\n[2/3] Solving...")
    try:
        solution = solve_instance(instance)
        print(f"✓ Solution found:")
        print(f"  - Total cost: {solution.costo_total:.2f}")
        print(f"  - Routes: {len(solution.rutas)}")

        for i, ruta in enumerate(solution.rutas):
            print(f"\n  Route {i} (Vehicle {ruta.vehicle_id}):")
            print(f"    - Sequence: {ruta.secuencia}")
            print(f"    - Cost: {ruta.costo:.2f}")

            # Calculate demand in route
            route_demand = sum(
                c.demanda
                for c in instance.clientes
                if c.id in ruta.secuencia
            )
            print(f"    - Load: {route_demand}")

    except Exception as e:
        print(f"✗ Error solving: {e}")
        return 1

    # Validate
    print("\n[3/3] Validating solution...")
    try:
        # Check all clients visited
        all_visited = set()
        for ruta in solution.rutas:
            all_visited.update(ruta.secuencia)

        if len(all_visited) == len(instance.clientes):
            print(f"✓ All clients visited")
        else:
            print(f"✗ Missing clients: {set(c.id for c in instance.clientes) - all_visited}")

        # Check capacity
        for ruta in solution.rutas:
            demand = sum(c.demanda for c in instance.clientes if c.id in ruta.secuencia)
            if demand <= instance.flota.capacidad_por_vehiculo:
                print(f"✓ Route {ruta.vehicle_id} respects capacity ({demand}/{instance.flota.capacidad_por_vehiculo})")
            else:
                print(f"✗ Route {ruta.vehicle_id} exceeds capacity")

    except Exception as e:
        print(f"✗ Validation error: {e}")
        return 1

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
