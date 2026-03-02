# AgentHub SaaS (FastAPI + Telegram Mini App)

Production-ready SaaS for creating AI agents with unified access to multiple LLM providers, token billing, subscriptions, and task automation.

## Features
- Multi-tenant architecture (strict per-user isolation on all domain queries).
- Agent builder: system prompt, model, token limits, memory, tools, behavior profile.
- Unified LLM gateway for: OpenAI, Anthropic, Gemini, Mistral, Cohere, DeepSeek, YandexGPT, GigaChat.
- Internal token wallets with per-model accounting and usage logs.
- Subscription system (trial/week/month) with YooKassa integration.
- Scheduler with CRON/date execution powered by APScheduler.
- WebSockets for live token balance updates.
- Telegram Mini App compatible web frontend.
- Railway deployment-ready.

## Architecture
```
app/
  core/        # config, db, models, middleware, redis
  auth/        # JWT auth, registration/login
  agents/      # agent CRUD, runtime, memory
  providers/   # provider abstraction + implementations
  billing/     # token debit/credit, subscriptions, payments
  scheduler/   # apscheduler orchestration
  tools/       # tools executor (webhook/external api/text analysis)
  api/         # FastAPI route layer
  webapp/      # mini app frontend assets
```

## Run locally
```bash
docker compose up --build
```

Apply schema:
```bash
docker compose exec postgres psql -U agenthub -d agenthub -f /app/schema.sql
```

Open:
- API: http://localhost:8000/docs
- Mini App: http://localhost:8000/webapp

## Railway deploy
1. Create PostgreSQL + Redis plugins in Railway.
2. Set env vars from `.env.example`.
3. Start command:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
4. Run SQL migration by executing `schema.sql` against Railway PostgreSQL.
5. Configure YooKassa webhook URL:
`https://<your-domain>/api/v1/billing/webhook/yookassa`

## Security/ops notes
- JWT auth, bcrypt password hashing.
- ENV-only secret/key management.
- Global API rate limiting middleware.
- Usage logging and per-request token debit.
- Async DB and HTTP integrations for high concurrency.
