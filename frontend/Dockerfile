# Build context: esta carpeta (frontend/) — self-contained, a diferencia del
# backend. Construir con:
#   docker build -t vrp-frontend frontend/

# --- Etapa de build ---
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Etapa de runtime: solo el estático generado, servido por nginx ---
# nginxinc/nginx-unprivileged: mismo nginx, pero ya configurado para correr
# como usuario no-root de fábrica (puerto 8080, no el 80 — bindear <1024
# requiere root, que es justo lo que RNF-004 pide evitar).
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Explícito, aunque la imagen base ya lo configura por defecto — declarado
# acá para que quede a la vista sin tener que revisar el Dockerfile de la
# imagen base.
USER nginx

EXPOSE 8080
