# Stage 1: build the static bundle
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve it with nginx, which also proxies /api to the backend
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
HEALTHCHECK --interval=5s --timeout=3s --start-period=2s --retries=5 \
  CMD wget -qO- http://127.0.0.1:3000/healthz > /dev/null || exit 1
