FROM node:22-alpine AS base
WORKDIR /app
COPY apps/web/package.json /app/package.json
RUN npm install
COPY apps/web /app

FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS test
CMD ["npm", "test", "--", "--run"]

FROM base AS build
RUN npm run build
