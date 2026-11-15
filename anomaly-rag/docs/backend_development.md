# ASTRA HEALTH Backend Development

## Phase 1 scope

This phase provides the FastAPI foundation, health endpoint, configuration,
Knowledge Card validation, and temporary in-memory Knowledge Card CRUD. It
does not connect to a database, vector store, embedding model, local LLM, or
anomaly model.

## Knowledge Card development storage

Knowledge Cards are currently held in process memory. They are deleted whenever
the API process restarts and are not shared between server processes. This is a
development-only repository behind a service boundary; a later SQL Server
repository can replace it without changing API routes.

Available endpoints:

- `POST /api/knowledge-cards`
- `GET /api/knowledge-cards`
- `GET /api/knowledge-cards/{card_id}`
- `PUT /api/knowledge-cards/{card_id}`
- `DELETE /api/knowledge-cards/{card_id}`

## RAG retrieval foundation

The retrieval foundation is intentionally independent from Knowledge Card CRUD.
Creating, replacing, or deleting an in-memory card does not automatically
change Qdrant. Explicit indexing is required until durable SQL Server storage
is available.

`SentenceTransformerEmbeddingProvider` uses
`intfloat/multilingual-e5-base`. It creates `passage: ` prefixed vectors for
Knowledge Card text and `query: ` prefixed vectors for searches. The provider
is created during application startup, then loads the model lazily on its first
embedding request and keeps it in memory for the rest of the process.

The model has a 768-dimensional embedding output. The implementation reads the
dimension from the loaded model before creating or validating a Qdrant
collection.

Start Qdrant for local development:

```powershell
docker compose -f docker-compose.qdrant.yml up -d
```

Qdrant is then reachable at `http://localhost:6333`. The first embedding
operation downloads `intfloat/multilingual-e5-base` into the local Hugging Face
cache if it is not already available. Later operations use the cached local
model.

Relevant environment settings are in `.env.example`:

- `ASTRA_EMBEDDING_MODEL_NAME`
- `ASTRA_QDRANT_URL`
- `ASTRA_QDRANT_COLLECTION_NAME`
- `ASTRA_RETRIEVAL_TOP_K`
- `ASTRA_RETRIEVAL_MIN_SIMILARITY_SCORE`

## SQL Server persistence preparation

`InMemoryKnowledgeCardRepository` remains the active API repository until an
explicit cutover is approved. `SqlAlchemyKnowledgeCardRepository` is a
session-scoped implementation of the same repository boundary and intentionally
does not commit transactions. It can therefore be adopted through dependency
injection without changing Knowledge Card routes or services.

Set `COLLAB_DB_PASSWORD` in a local `.env` or a deployment secret store; never
commit it. The backend builds the `mssql+pyodbc` URL in memory with SQLAlchemy
`URL.create()`, so URL-reserved password characters are handled safely and no
password-bearing connection string is stored in a file. The non-secret host,
port, database, user, and ODBC Driver 18 settings are shown in `.env.example`.
`ASTRA_DATABASE_TRUST_SERVER_CERTIFICATE=true` is rejected outside
`ASTRA_DATABASE_ENVIRONMENT=development`.

Set `ASTRA_KNOWLEDGE_CARD_REPOSITORY=memory` (the default) to use the temporary
in-process repository. Set it to `sqlserver` to activate SQL Server-backed
Knowledge Card CRUD. In SQL Server mode, application startup opens a connection
and runs `SELECT 1`; startup fails with a clear configuration/connectivity error
if this check fails. Each API request gets one SQLAlchemy session, commits only
after successful request handling, and always closes the session at the end.

The SQL Server integration test is skipped unless both `COLLAB_DB_PASSWORD` and
`ASTRA_RUN_SQLSERVER_INTEGRATION_TESTS=true` are present. It uses a UUID-based
`sql-integration-*` card ID, exercises the API CRUD and validation paths, then
deletes only that test card. Run it explicitly in a securely configured
environment with:

```powershell
.\.venv\Scripts\python.exe -m pytest -m integration
```

The prepared migration is
`alembic/versions/0007_create_knowledge_cards.py`, with
`revision = "0007"` and `down_revision = "0006"`. This repository does not currently contain the
central Alembic configuration or the `0006` revision, so it must be copied into
the authoritative migration repository before it is run. Do not create a
placeholder `0006` locally.

Before the privileged migration service runs it, verify the chain and database
principal configuration with the following read-only SQL in `AstraHealth`:

```sql
SELECT role_principal.name AS role_name, member_principal.name AS member_name
FROM sys.database_role_members AS membership
JOIN sys.database_principals AS role_principal
  ON role_principal.principal_id = membership.role_principal_id
JOIN sys.database_principals AS member_principal
  ON member_principal.principal_id = membership.member_principal_id
WHERE role_principal.name = N'astra_app_role'
  AND member_principal.name = N'astra_collaborator';
```

The migration independently performs the same verification and stops before
table DDL if the role or membership is absent. This worktree does not establish
whether that membership exists in the central database; it is a required
preflight condition for the privileged migration service. It grants only `SELECT`,
`INSERT`, `UPDATE`, and `DELETE` on `dbo.knowledge_cards` to `astra_app_role`;
it never grants permissions directly to `astra_collaborator` and never changes
role membership. The downgrade revokes only those object permissions before
dropping the table.

From the authoritative Alembic project, the privileged migration service can
review and apply the prepared revision with:

```powershell
alembic history --verbose
alembic upgrade 0007
```

## Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` when local settings are needed. All backend
environment variables use the `ASTRA_` prefix, such as `ASTRA_DEBUG` and
`ASTRA_CORS_ORIGINS`, so unrelated machine-level variables do not affect the API.

## Run the API

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir src/backend --reload
```

OpenAPI documentation is then available at `http://127.0.0.1:8000/docs`.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Accepted Knowledge Card systems

The Phase 1 controlled system registry accepts `behavioral`, `cognitive`,
`cardiovascular`, `respiratory`, `thermal`, `renal`, `vision`,
`sensorimotor`, and `symptoms`. It is a reviewed dictionary rather than a
Python Enum. A new source-system value must be reviewed and added explicitly;
the API never maps an unknown value to another system.
