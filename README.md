# Books API

A production-minded REST API built with **FastAPI**, with an **OpenAI-powered Q&A endpoint** that answers questions about a book catalogue. It started as a CRUD demo and is being built up, step by step, into a service that is secure, tested, observable and deployable. This README is honest about what is done today and what is planned next.

**Stack:** Python · FastAPI · Pydantic · SQLAlchemy · PostgreSQL · Alembic · OpenAI API · Pytest

---

## What it does today

**Books REST API**
- CRUD with filtering, search, sorting and pagination (`/api/v1/books`)
- Pydantic validation, consistent JSON error format, auto-generated OpenAPI docs (Swagger UI and ReDoc)
- Storage switchable by configuration: a CSV file for quick local use, or **PostgreSQL** via SQLAlchemy with **Alembic migrations**
- API-key authentication on write endpoints (`X-API-Key` header), fail-closed with constant-time key comparison
- Request-ID middleware (`X-Request-ID`) and structured **JSON logging** option

**AI assistant (`POST /api/v1/assistant/ask`)**
- Sends the catalogue and the question to OpenAI and returns an answer grounded in the data, with the `sources` (book ids) it used, plus the `model` and `prompt_version`
- **Input guardrails:** blocks obvious prompt-injection attempts and control characters before any model call
- **Output guardrails:** the model must return JSON; answers that leak prompt text or key-like strings, are out of scope, or cite book ids that do not exist are replaced with a standard refusal
- **Rate limiting:** per-client and global sliding-window limits, with `429` and `Retry-After`. Over-limit calls never reach OpenAI
- **Drift monitoring and evals:** a golden-set evaluation script compares answers against a saved baseline, and a warning is logged if the serving model changes

**Quality**
- 60+ Pytest tests covering books, auth, the assistant, guardrails, rate limiting, request IDs and the eval runner. The tests use a **fake LLM**, so they never call OpenAI

---

## Quick start

```bash
git clone https://github.com/tejaswi1510/books-api.git
cd books-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then edit .env (see Configuration)
uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Run the tests: `pytest -v`

### Configuration

All settings are environment variables with the `APP_` prefix, loaded from `.env` (never committed).

| Variable | Purpose |
|---|---|
| `APP_API_KEYS` | Comma-separated API keys for protected endpoints (several keys allow rotation) |
| `APP_OPENAI_API_KEY` | Enables the AI assistant. Without it the rest of the API works and the assistant returns `503` |
| `APP_OPENAI_MODEL` | Model name for the assistant |
| `APP_DATABASE_URL` | PostgreSQL URL. When empty, the app uses the CSV file |
| `APP_LOG_FORMAT` | `text` (default) or `json` |

See `.env.example` for the full list, including the rate-limit settings.

### Using PostgreSQL

```bash
# in .env:  APP_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/books
alembic upgrade head          # create / update the schema
python -m scripts.seed_db     # load the seed CSV once
```

---

## API overview

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | none | Liveness check |
| GET | `/api/v1/books` | none | List (filter, search, sort, paginate) |
| GET | `/api/v1/books/{id}` | none | Get one |
| POST | `/api/v1/books` | API key | Create (`201` + `Location` header) |
| PUT | `/api/v1/books/{id}` | API key | Full replace |
| PATCH | `/api/v1/books/{id}` | API key | Partial update |
| DELETE | `/api/v1/books/{id}` | API key | Delete (`204`) |
| POST | `/api/v1/assistant/ask` | API key + rate limit | Ask the AI about the catalogue |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/assistant/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"question": "Which in-stock science fiction books cost less than $12?"}'
```

Errors use one format everywhere: `{"error": {"code": "...", "message": "..."}}`.

---

## Evals

```bash
python -m scripts.run_evals --update-baseline   # save a baseline once
python -m scripts.run_evals                     # compare later runs against it
```

Fixed questions in `evals/golden_set.json` run against the real model using a fixed fixture catalogue. Re-run after any prompt or model change, and bump `PROMPT_VERSION` when the prompt is edited. Each run costs a few cents.

---

## Project structure

```
app/
  main.py              app factory, exception handlers, middleware
  core/                config, logging, auth, rate limiting, request IDs
  api/                 dependency injection and the v1 routes (HTTP layer only)
  schemas/             Pydantic request/response models
  services/            business logic (books, assistant, drift monitor)
  repositories/        data access: abstract base, CSV and SQL implementations
  clients/             external service clients (LLM interface + OpenAI)
  guardrails/          input and output rails for the AI endpoint
  evals/               golden-set evaluation logic
migrations/            Alembic migrations
evals/                 golden questions, fixture catalogue, baseline
scripts/               seed_db.py, run_evals.py
tests/                 Pytest suite (fake LLM)
```

### Design decisions
- **Layered design** (routes → services → repositories). Swapping CSV for PostgreSQL was one change in the dependency wiring, with no changes to the routes or services.
- **LLM behind an interface**, so the tests use a fake model and never spend money or depend on the network, and another provider can be added without touching the services.
- **Guardrails on both sides of the model**, because model output is untrusted until it is checked against the data.
- **Auth fails closed**: with no keys configured, protected endpoints stay shut.
- **Known limitation:** rate-limit state is in memory, per process. It moves to Redis in the roadmap below.

---

## Roadmap (planned, not yet built)

This is the order I am working through. Nothing below is claimed as done until it has a checked box.

**Phase 1: Harden**
- [ ] JWT authentication (alongside or replacing API keys)
- [ ] Environment-based config profiles and CORS
- [ ] Tests running in CI on every push (GitHub Actions), with a status badge

**Phase 2: Containerise**
- [ ] Dockerfile
- [ ] docker-compose: API + PostgreSQL + Redis
- [ ] Redis-backed rate limiter, so limits hold across several workers

**Phase 3: Deploy on AWS**
- [ ] Image in ECR, container running on ECS
- [ ] RDS PostgreSQL and ElastiCache Redis
- [ ] Secrets in AWS Secrets Manager, HTTPS, logs in CloudWatch
- [ ] A small Lambda + API Gateway + DynamoDB variant of the API
- [ ] Infrastructure as code (Terraform or CDK)

**Phase 4: Operate**
- [ ] Alerts on errors and latency
- [ ] Database backups and a tested restore
- [ ] Load test of the rate limits
- [ ] Cost review

**AI engineering**
- [ ] Agent with tool / function calling (search books, get by id, check stock) replacing the "send the whole catalogue" approach
- [ ] RAG: embeddings with pgvector in PostgreSQL
- [ ] A small MCP server exposing the book tools
- [ ] Deeper evals: LLM-as-judge checks, tracing, and per-request latency and cost tracking
- [ ] Responsible-AI checks: a prompt-injection test suite and PII handling

**Front end and testing**
- [ ] Small React + TypeScript front end for the API
- [ ] Playwright end-to-end tests and coverage reporting

---

## Related work

A separate **Text-to-SQL** project (natural-language question → schema retrieval → validated SQL → execution) is in progress as its own project.
