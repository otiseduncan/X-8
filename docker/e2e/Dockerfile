FROM mcr.microsoft.com/playwright:v1.44.1-jammy
WORKDIR /app
COPY e2e/package.json /app/package.json
RUN npm install
COPY e2e /app
CMD ["npx", "playwright", "test"]
