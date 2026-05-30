# Next.js standalone build (Decision 8/15), multi-stage, non-root.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN addgroup -g 10003 nodegrp && adduser -u 10003 -G nodegrp -S nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodegrp /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodegrp /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
