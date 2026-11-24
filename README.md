# Books API (FastAPI demo)

A small REST API demonstrating CRUD, filtering, sorting, pagination, validation
and auto-generated Swagger docs, backed by a CSV file.

## Quick start

```bash
cd /Users/tejuexo/Desktop/playground
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs
ReDoc:      http://127.0.0.1:8000/redoc
OpenAPI:    http://127.0.0.1:8000/openapi.json

Run tests: `pytest -v`

## Endpoints

| Method | Path                | Description                         |
|--------|---------------------|-------------------------------------|
| GET    | /health             | Liveness check                      |
| GET    | /api/v1/books       | List (filter, search, sort, paginate) |
| GET    | /api/v1/books/{id}  | Get one                             |
| POST   | /api/v1/books       | Create (201 + Location header)      |
| PUT    | /api/v1/books/{id}  | Full replace                        |
| PATCH  | /api/v1/books/{id}  | Partial update                      |
| DELETE | /api/v1/books/{id}  | Delete (204)                        |
| POST   | /api/v1/assistant/ask | Ask an AI (OpenAI) questions about the catalogue |

## AI assistant (OpenAI)

`POST /api/v1/assistant/ask` sends the catalogue plus the question to OpenAI and
returns an answer grounded in the CSV data.

1. Create an API key at https://platform.openai.com/api-keys
2. `cp .env.example .env` and set `APP_OPENAI_API_KEY=sk-...`
   (or `export APP_OPENAI_API_KEY=sk-...` in your shell). Never commit `.env`.
3. Restart the server. The startup log shows "AI assistant enabled".

Optional: `APP_OPENAI_MODEL` (default `gpt-6-luna`), `APP_OPENAI_TIMEOUT_SECONDS`,
`APP_AI_MAX_BOOKS_IN_CONTEXT`. Without a key the rest of the API still works and
this endpoint returns 503. Tests use a fake LLM, so they never call OpenAI.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/assistant/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which in-stock science fiction books cost less than $12?"}'
```

## AI safeguards: guardrails, drift, rate limiting

**Rate limiting** (`app/core/rate_limit.py`, wired in `app/api/deps.py`): sliding-window limits on
`POST /assistant/ask`: per client IP (default 10 requests/60s) and a global cap (default 200/day).
Over-limit calls get `429` with a `Retry-After` header and never reach OpenAI. Successful responses carry
`X-RateLimit-Limit` / `X-RateLimit-Remaining`. State is in-memory (per process); use Redis for multi-worker setups.

**Guardrails** (`app/guardrails/`):
- *Input rails*: reject obvious prompt-injection / control characters (400 `input_blocked`) before any model call.
- *Output rails*: the model must return JSON; answers that leak prompt text or key-like strings, are out of scope,
  or cite book ids that don't exist in the data are replaced by a standard refusal (`refused: true`).
  Responses include `sources` (book ids) so answers are verifiable.

**Drift** (`app/services/drift_monitor.py`, `app/evals/`, `evals/`):
- Every response reports the exact `model` and `prompt_version`; a warning is logged if the serving model changes.
- Golden-set evals: `python -m scripts.run_evals` runs fixed questions against the real model and compares
  with `evals/baseline.json`. Save a baseline once with `--update-baseline`, then re-run periodically
  (e.g. weekly, and after any prompt/model change). Costs a few cents per run. Bump `PROMPT_VERSION` when editing the prompt.

## Structure

```
app/
  main.py              app factory, exception handlers, router wiring
  core/                config (env-driven settings), logging
  api/deps.py          dependency injection: chooses the data source
  api/v1/endpoints/    HTTP layer only (routes)
  schemas/             Pydantic request/response models
  services/            business logic
  repositories/        data access (abstract base + CSV implementation)
  clients/             external service clients (LLMClient interface + OpenAI)
  guardrails/          input and output rails for the AI endpoint
  evals/               golden-set evaluation logic (drift detection)
data/books.csv         seed data (modified by POST/PUT/PATCH/DELETE)
evals/                 golden questions, fixed fixture CSV, baseline + results
scripts/               run_evals.py
tests/                 pytest suite (temp CSV copy, fake LLM)
```

## Where to extend

- Real database: implement `BookRepository` (e.g. SQLAlchemy) and change one line in `app/api/deps.py`.
- Middlewares (CORS, request IDs, rate limits): register in `create_app()` in `app/main.py`.
- Auth: add a dependency (e.g. JWT/OAuth2) and attach it to `api_router` or individual routes.
- Larger datasets for the AI endpoint: the catalogue is sent as prompt context (capped by `APP_AI_MAX_BOOKS_IN_CONTEXT`); beyond a few hundred rows use retrieval, function calling, or text-to-SQL.
- Other LLM providers: implement `LLMClient` in `app/clients/` and switch it in `app/api/deps.py`.
- New resources: add schemas, repository, service, and an endpoints module, then include it in `api/v1/router.py`.
- API versioning: add `api/v2/` and mount it with a new prefix.
