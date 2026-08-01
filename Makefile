.PHONY: help build test run clean install-deps osrm-prepare db-migrate db-migration verify traceability mutation

help:
	@echo "VRP Solver - Build Targets"
	@echo "  make install-deps    Install Python dependencies"
	@echo "  make build           Build C++ core + Python bindings"
	@echo "  make test            Run full test suite (Python + C++)"
	@echo "  make test-py         Run Python tests only"
	@echo "  make test-cpp        Run C++ tests only"
	@echo "  make verify          Contrato de verificación completo (build + test + trazabilidad)"
	@echo "  make traceability    Verifica que cada regla de SPEC.md tenga un test anotado"
	@echo "  make mutation        Mide el mutation score de mutmut sobre backend_python/models y service"
	@echo "  make run             Start FastAPI server (http://localhost:8000)"
	@echo "  make clean           Remove build artifacts"
	@echo "  make format          Format code (black, clang-format)"
	@echo "  make osrm-prepare    Download + pre-process Lima OSM map for OSRM (run once, offline)"
	@echo "  make db-migrate      Apply pending Alembic migrations (alembic upgrade head)"
	@echo "  make db-migration msg=\"...\"   Create a new Alembic migration (autogenerate off, DDL manual)"

install-deps:
	python -m pip install -r requirements.txt
	@echo "✓ Dependencies installed"

build:
	mkdir -p build
	cd build && cmake -DBUILD_PYTHON_BINDINGS=ON -DBUILD_TESTS=ON ..
	cd build && cmake --build . --config Release
	@echo "✓ Build complete"

test: test-py test-cpp
	@echo "✓ All tests passed"

test-py:
	pytest tests/ -v --tb=short --cov=backend_python

test-cpp:
	cd build && cmake --build . --target vrp_core_tests --config Release
	cd build && ctest --output-on-failure

run:
	uvicorn backend_python.api.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf build/ __pycache__ .pytest_cache .coverage
	find . -name "*.pyc" -delete
	find . -name "*.so" -delete
	@echo "✓ Clean complete"

format:
	black backend_python/ tests/
	find core_cpp -name "*.cpp" -o -name "*.hpp" | xargs clang-format -i
	@echo "✓ Format complete"

osrm-prepare:
	mkdir -p data/osrm
	curl -L -o data/osrm/lima-latest.osm.pbf https://download.geofabrik.de/south-america/peru-latest.osm.pbf
	docker run --rm -v "$$(pwd)/data/osrm:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/lima-latest.osm.pbf
	docker run --rm -v "$$(pwd)/data/osrm:/data" osrm/osrm-backend osrm-partition /data/lima-latest.osrm
	docker run --rm -v "$$(pwd)/data/osrm:/data" osrm/osrm-backend osrm-customize /data/lima-latest.osrm
	@echo "✓ OSRM map ready — start with: docker-compose up -d osrm"

db-migrate:
	alembic upgrade head
	@echo "✓ Migrations applied"

db-migration:
	alembic revision -m "$(msg)"
	@echo "✓ New migration created — escribí el DDL a mano en versions/ (sin autogenerate, el proyecto no usa ORM declarativo)"

traceability:
	python scripts/check_traceability.py

verify: build test traceability
	@echo "✓ verify: build + test + trazabilidad en verde"

# Umbral fijado en ETAPA 3 tras medir el score base (ADR-005, plan-adopcion.md sección 5)
mutation:
	mutmut run --paths-to-mutate backend_python/models,backend_python/service || true
	mutmut results
