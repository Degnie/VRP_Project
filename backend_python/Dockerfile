# Build context: la RAÍZ del repo, no esta carpeta — el paquete se importa
# como "backend_python.api.main" (path relativo a la raíz). Construir con:
#   docker build -f backend_python/Dockerfile -t vrp-backend .
FROM python:3.11-slim

WORKDIR /app

# Solo el subconjunto de requirements.txt que el backend necesita en runtime —
# sin cmake/pybind11 (build del core C++) ni las herramientas de desarrollo:
# core C++ no se compila acá, el sistema corre en el fallback Python (EC-003).
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    "uvicorn[standard]==0.24.0" \
    pydantic==2.5.0 \
    psycopg2-binary==2.9.9 \
    pymongo==4.6.0 \
    alembic==1.18.5 \
    "python-jose[cryptography]==3.3.0" \
    "passlib[bcrypt]==1.7.4" \
    bcrypt==4.0.1 \
    reportlab==4.5.1 \
    python-dotenv==1.0.0 \
    requests==2.31.0

COPY backend_python/ backend_python/

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend_python.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
