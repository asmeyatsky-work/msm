# syntax=docker/dockerfile:1.7
# Stage 1 — build the React app with Vite.
FROM node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npx tsc -p tsconfig.json --noEmit && npx vite build

# Stage 2 — nginx serves static assets + reverse-proxies /api to the
# reconciliation Cloud Run service so the browser has a single origin.
FROM nginx:1.27-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

# Cloud Run sets $PORT; nginx image's envsubst entrypoint expands the template.
ENV PORT=8080
ENV RECONCILIATION_API_HOST=reconciliation-staging-794974391956.europe-west2.run.app
ENV SCORING_API_HOST=scoring-api-staging-794974391956.europe-west2.run.app
# Restrict envsubst to our vars so nginx's own $uri/$host/$upstream aren't blanked.
ENV NGINX_ENVSUBST_FILTER=^(PORT|RECONCILIATION_API_HOST|SCORING_API_HOST)$
EXPOSE 8080
