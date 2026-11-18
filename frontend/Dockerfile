# FaultIQ frontend images.
#   target "dev": Vite dev server with hot reload (docker-compose.yml)
#   target "web" (default): production static build served by Caddy, which also
#                           proxies /api to the API and handles HTTPS (compose.prod.yml)

# ---- dependencies (shared) ----
FROM node:26.13.0-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci && chown -R node:node /app

# ---- development server ----
FROM deps AS dev
COPY --chown=node:node . .
USER node
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- production build (runs natively on the build machine; output is platform-independent) ----
FROM --platform=$BUILDPLATFORM node:26.13.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- production web server ----
FROM caddy:2.11.8-alpine AS web
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
EXPOSE 80 443 443/udp
