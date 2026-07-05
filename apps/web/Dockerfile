# syntax=docker/dockerfile:1
# Multi-stage, non-root image for the Next.js frontend. Build context = apps/web.

FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app

# ── Build-time public config (NEXT_PUBLIC_* is inlined into the client bundle) ──
# Defaults keep `docker compose build` working out of the box. Real values are
# injected from the root .env via docker-compose build args (see compose file).
ARG NEXT_PUBLIC_API_URL=http://localhost:2011
# Standard Clerk example publishable key — lets static generation succeed even
# without real keys. Override with your own to enable real sign-in.
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZXhhbXBsZS5jbGVyay5hY2NvdW50cy5kZXYk
# HS256 dev token (sub=web) the dev API verifies — makes /chat work without Clerk.
ARG NEXT_PUBLIC_DEV_TOKEN=
ARG NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
ARG NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
ARG NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
ARG NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
    NEXT_PUBLIC_DEV_TOKEN=$NEXT_PUBLIC_DEV_TOKEN \
    NEXT_PUBLIC_CLERK_SIGN_IN_URL=$NEXT_PUBLIC_CLERK_SIGN_IN_URL \
    NEXT_PUBLIC_CLERK_SIGN_UP_URL=$NEXT_PUBLIC_CLERK_SIGN_UP_URL \
    NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=$NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL \
    NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=$NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN node node_modules/next/dist/bin/next build

FROM node:22-slim AS runtime
WORKDIR /app
# WEB_PORT is env-driven end-to-end (see .env / docker-compose). Default 2012.
ARG WEB_PORT=2012
ENV WEB_PORT=${WEB_PORT} NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
# CLERK_SECRET_KEY is supplied at runtime (server-side middleware) via compose env.
RUN useradd -m -u 10001 webuser
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs
USER webuser
EXPOSE ${WEB_PORT}
# Shell form so ${WEB_PORT} is expanded at container start.
CMD node node_modules/next/dist/bin/next start -p ${WEB_PORT}
