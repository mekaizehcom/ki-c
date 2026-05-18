FROM node:22-bookworm-slim AS base
WORKDIR /srv
COPY package.json ./
RUN npm install
COPY svelte.config.js vite.config.ts tsconfig.json ./
COPY src ./src
COPY static ./static

# ---- dev: vite dev server (src/static bind-mounted by compose) ----
FROM base AS dev
ENV NODE_ENV=development
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

# ---- build ----
FROM base AS build
RUN npm run build

# ---- prod: run adapter-node output ----
FROM node:22-bookworm-slim AS prod
WORKDIR /srv
ENV NODE_ENV=production PORT=3000
COPY package.json ./
RUN npm install --omit=dev
COPY --from=build /srv/build ./build
EXPOSE 3000
CMD ["node", "build/index.js"]
