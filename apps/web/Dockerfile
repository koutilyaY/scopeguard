# Next.js standalone build. Build context is the repo root (see docker-compose.yml).
FROM node:20-slim AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
COPY apps/web/ ./
COPY --from=deps /app/node_modules ./node_modules
# Next evaluates next.config.mjs rewrites() at BUILD time and freezes the destination
# into routes-manifest.json — a runtime API_INTERNAL_URL is ignored. So the API URL must
# be supplied here. Default matches the compose service name; override with
#   docker build --build-arg API_INTERNAL_URL=https://api.example.com
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
# HOSTNAME=0.0.0.0 is required: Next's standalone server binds to $HOSTNAME, and Docker
# sets that to the container name, which would bind only to the container's eth0 IP and
# refuse localhost connections (breaking the healthcheck).
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN useradd --uid 10001 --create-home nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
