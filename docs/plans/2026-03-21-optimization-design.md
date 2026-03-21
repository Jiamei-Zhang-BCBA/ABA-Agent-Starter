# ABA SaaS API Optimization Design

**Date**: 2026-03-21
**Status**: Approved
**Approach**: Phased (Sprint 1→4), security-first

---

## Sprint 1: Security Hardening

### 1.1 CORS Whitelist
- Replace `allow_origins=["*"]` with configurable `cors_origins` list in `config.py`
- Default: `["http://localhost:8000", "http://127.0.0.1:8000"]`
- Production: set via `CORS_ORIGINS` env var

### 1.2 JWT Secret Safety
- Startup check: refuse to start in non-dev mode with default secret
- Dev mode: auto-generate random secret per session
- Add explicit warning in `.env.example`

### 1.3 File Upload Limits
- `max_upload_size_mb: int = 20` in config
- `max_uploads_per_job: int = 5` in config
- Enforce in `routers/jobs.py` before processing

### 1.4 Form Input Validation
- New `services/form_validator.py`
- Validate required fields present
- Type checking (number, text, textarea)
- Strip unknown fields (prevent injection)

### 1.5 Rate Limiting
- Use `slowapi` middleware
- `POST /jobs`: 10/min per user
- `POST /auth/login`: 5/min per IP
- `GET` endpoints: 60/min per user
- Disable via `RATE_LIMIT_ENABLED=false` in dev

---

## Sprint 2: Production Readiness

### 2.1 Worker Refactor
- Unified `JobProcessor` class used by both Celery and local thread
- Job timeout: default 300s, configurable
- Auto-retry: max 2 retries, 30s delay
- Cancel: `POST /jobs/{id}/cancel`, Worker checks status before proceeding

### 2.2 Audit Logging
- New `audit_logs` table: tenant_id, user_id, action, resource_type, resource_id, detail_json, ip_address, created_at
- Actions tracked: job.created, job.output_edited, review.approved, review.rejected, client.created
- `services/audit_service.py`: `log_action()` called at each critical operation

### 2.3 Database Migrations
- Remove `create_all()` from `main.py` lifespan
- Generate initial Alembic migration from current schema
- Add `scripts/migrate.py` for pre-startup migration
- Docker entrypoint: `alembic upgrade head && uvicorn ...`

### 2.4 Structured Logging
- JSON format logs with: timestamp, level, request_id, user_id, tenant_id, action, duration_ms
- `middleware/logging_middleware.py`: auto-attach context to every request
- Skill execution logs include: skill name, model, token counts, duration

### 2.5 Enhanced Health Check
- `GET /health` checks: database connectivity, storage accessibility, Claude CLI availability
- Returns active job count and version
- 503 if any dependency unavailable

---

## Sprint 3: Testing & Reliability

### 3.1 Deep Form Validation
- Number fields: range validation (e.g. age 1-99)
- select_client/select_staff: verify UUID belongs to current tenant
- File fields: validate extension against `accept` list
- Textarea: max 5000 chars

### 3.2 Skill Execution Error Handling
- `SkillResult` gains `warnings: list[str]` and `raw_output: str`
- Empty output detection → raise SkillExecutionError
- Short output warning (< 50 chars)
- Prompt leak detection: mark + filter (not blind delete)
- Warnings stored in Job, displayed in frontend

### 3.3 Test Suite
```
tests/
├── conftest.py              # In-memory SQLite + fixtures
├── test_auth.py             # Login, token refresh, permission denied
├── test_feature_gate.py     # Plan × role gating (pure logic)
├── test_form_validator.py   # Required, type, range, cross-tenant
├── test_jobs_api.py         # Job create, list, status flow
├── test_vault_service.py    # Local storage read/write/append/rules
├── test_file_processor.py   # txt/docx/pdf parsing
└── test_review_flow.py      # Submit → review → approve → deliver
```
- MockSkillExecutor returns fixed text (no Claude dependency)
- Target: ≥60% coverage on core paths

### 3.4 CI Check Script
- `scripts/check.py`: syntax check, import check, pytest, coverage report

---

## Sprint 4: Frontend Experience

### 4.1 WebSocket Job Status
- `ws://host/ws/jobs?token=xxx`
- Worker broadcasts status changes: queued → parsing → processing → delivered
- Frontend auto-updates status badges; auto-loads output on delivery
- In-memory connection pool (no Redis dependency in dev)

### 4.2 Cost Estimation
- Each FeatureModule gains `_estimated_tokens` and `_estimated_cost_cents`
- `GET /features/{id}/schema` includes `cost_estimate` object
- Frontend shows gray text below form: "预估消耗: 约 ¥0.07-0.50"

### 4.3 Job Cancellation
- `POST /jobs/{id}/cancel`
- Cancellable in: queued, parsing states
- Processing: cancel signal, Worker checks before next step
- Frontend: red cancel button on non-terminal jobs

### 4.4 Error Translation
- `services/error_translator.py`: map technical errors to friendly Chinese messages
- Frontend: friendly message + collapsible technical detail for admins

### 4.5 Split-Pane Editor
- Output edit modal: left = Markdown source, right = live rendered preview
- Real-time sync as user types
- Action bar: Cancel, Save, Download .md
