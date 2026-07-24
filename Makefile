.PHONY: help build test run clean install-deps osrm-prepare

help:
	@echo "VRP Solver - Build Targets"
	@echo "  make install-deps    Install Python dependencies"
	@echo "  make build           Build C++ core + Python bindings"
	@echo "  make test            Run full test suite (Python + C++)"
	@echo "  make test-py         Run Python tests only"
	@echo "  make test-cpp        Run C++ tests only"
	@echo "  make run             Start FastAPI server (http://localhost:8000)"
	@echo "  make clean           Remove build artifacts"
	@echo "  make format          Format code (black, clang-format)"
	@echo "  make osrm-prepare    Download + pre-process Lima OSM map for OSRM (run once, offline)"

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
