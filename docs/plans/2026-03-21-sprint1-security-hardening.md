# Sprint 1: Security Hardening — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all critical security gaps so the system can safely accept external users.

**Architecture:** Five independent hardening layers applied to the existing FastAPI app. Each task is self-contained — no task depends on another, so they can be committed independently.

**Tech Stack:** FastAPI, Pydantic Settings, slowapi (new dependency), pytest (new dependency)

---

### Task 1: CORS Whitelist

**Files:**
- Modify: `api/app/config.py` (add `cors_origins` field)
- Modify: `api/app/main.py:62-68` (replace wildcard CORS)
- Modify: `api/.env.example` (document CORS_ORIGINS)
- Create: `api/tests/test_cors.py`

**Step 1: Write the failing test**

Create `api/tests/__init__.py` (empty) and `api/tests/conftest.py`:

```python
# api/tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def client():
    """Sync test client for non-async tests."""
    from fastapi.testclient import TestClient
    return TestClient(app)
```

Create `api/tests/test_cors.py`:

```python
# api/tests/test_cors.py
def test_cors_rejects_unknown_origin(client):
    resp = client.options(
        "/health",
        headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "GET"},
    )
    # Should NOT have Access-Control-Allow-Origin for evil.com
    assert resp.headers.get("access-control-allow-origin") != "https://evil.com"


def test_cors_allows_localhost(client):
    resp = client.options(
        "/health",
        headers={"Origin": "http://localhost:8000", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"
```

**Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_cors.py -v`
Expected: `test_cors_rejects_unknown_origin` FAILS (currently CORS allows all origins)

**Step 3: Implement the fix**

In `api/app/config.py`, add after line 27 (`jwt_refresh_token_expire_days`):

```python
    # CORS
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
```

In `api/app/main.py`, replace lines 62-68:

```python
# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In `api/.env.example`, add:

```bash
# CORS allowed origins (comma-separated, no spaces)
# CORS_ORIGINS=["http://localhost:8000","http://127.0.0.1:8000"]
```

**Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_cors.py -v`
Expected: Both tests PASS

**Step 5: Commit**

```bash
git add api/app/config.py api/app/main.py api/.env.example api/tests/
git commit -m "fix: replace CORS wildcard with configurable whitelist"
```

---

### Task 2: JWT Secret Safety

**Files:**
- Modify: `api/app/config.py` (add env detection + random fallback)
- Modify: `api/app/main.py` (startup check)
- Modify: `api/.env.example` (add warning)
- Create: `api/tests/test_jwt_safety.py`

**Step 1: Write the failing test**

```python
# api/tests/test_jwt_safety.py
import os
from unittest.mock import patch
from app.config import Settings

def test_dev_mode_generates_random_secret():
    """In dev (SQLite), default secret should be replaced with a random one."""
    s = Settings(database_url="sqlite+aiosqlite:///./test.db")
    assert s.jwt_secret_key != "change-me-to-a-random-secret-in-production"
    assert len(s.jwt_secret_key) >= 32


def test_prod_mode_rejects_default_secret():
    """In prod (PostgreSQL), default secret must raise an error."""
    import pytest
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            database_url="postgresql+asyncpg://x:x@localhost/db",
            jwt_secret_key="change-me-to-a-random-secret-in-production",
        )


def test_prod_mode_accepts_custom_secret():
    """In prod with a real secret, no error."""
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/db",
        jwt_secret_key="a-real-secret-that-is-long-enough-1234567890",
    )
    assert s.jwt_secret_key == "a-real-secret-that-is-long-enough-1234567890"
```

**Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_jwt_safety.py -v`
Expected: `test_dev_mode_generates_random_secret` FAILS (currently returns default string)

**Step 3: Implement the fix**

Replace `api/app/config.py` entirely:

```python
import secrets
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

_DEFAULT_JWT_SECRET = "change-me-to-a-random-secret-in-production"


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./aba_dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage mode: "local" (filesystem) or "s3" (MinIO)
    storage_mode: str = "local"
    local_storage_path: str = "./storage"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "aba-vaults"
    minio_use_ssl: bool = False

    # Auth
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # CORS
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # Rate limiting
    rate_limit_enabled: bool = True

    # File upload limits
    max_upload_size_mb: int = 20
    max_uploads_per_job: int = 5

    # Claude execution mode
    claude_mode: str = "cli"
    anthropic_api_key: str = ""
    claude_cli_path: str = "claude"

    # Skills
    skills_base_path: str = "D:/OneDrive/wxob/ABA-Agent-Starter/.claude/skills"
    claude_md_path: str = "D:/OneDrive/wxob/ABA-Agent-Starter/CLAUDE.md"
    config_md_path: str = "D:/OneDrive/wxob/ABA-Agent-Starter/.claude/skills/_config.md"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _enforce_jwt_secret(self):
        is_dev = "sqlite" in self.database_url
        if self.jwt_secret_key == _DEFAULT_JWT_SECRET:
            if is_dev:
                # Auto-generate for dev convenience
                object.__setattr__(self, "jwt_secret_key", secrets.token_urlsafe(48))
            else:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_jwt_safety.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add api/app/config.py api/tests/test_jwt_safety.py
git commit -m "fix: enforce JWT secret safety — auto-generate in dev, reject default in prod"
```

---

### Task 3: File Upload Limits

**Files:**
- Modify: `api/app/config.py` (already added `max_upload_size_mb`, `max_uploads_per_job` in Task 2)
- Modify: `api/app/routers/jobs.py:41-112` (add size + count checks)
- Create: `api/tests/test_upload_limits.py`

**Step 1: Write the failing test**

```python
# api/tests/test_upload_limits.py
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _login_token():
    resp = client.post("/api/v1/auth/login", json={"email": "bcba@demo.com", "password": "demo123"})
    return resp.json()["access_token"]


def test_rejects_oversized_file():
    token = _login_token()
    # Create a file that exceeds 20MB limit
    big_file = io.BytesIO(b"x" * (21 * 1024 * 1024))
    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "privacy_filter", "form_data": "{}"},
        files={"files": ("big.txt", big_file, "text/plain")},
    )
    assert resp.status_code == 413


def test_rejects_too_many_files():
    token = _login_token()
    files = [("files", (f"file{i}.txt", io.BytesIO(b"hello"), "text/plain")) for i in range(6)]
    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "privacy_filter", "form_data": "{}"},
        files=files,
    )
    assert resp.status_code == 400
    assert "5" in resp.json()["detail"]


def test_accepts_valid_file():
    token = _login_token()
    small_file = io.BytesIO(b"test content")
    resp = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"feature_id": "privacy_filter", "form_data": "{}"},
        files={"files": ("test.txt", small_file, "text/plain")},
    )
    assert resp.status_code == 201
```

**Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_upload_limits.py::test_rejects_oversized_file -v`
Expected: FAILS (currently no size check, returns 201 or 500)

**Step 3: Implement the fix**

In `api/app/routers/jobs.py`, add checks inside `create_job()` after the `check_feature_access` call (around line 57). Insert before the job creation block:

```python
    from app.config import get_settings
    _settings = get_settings()

    # Validate file count
    if len(files) > _settings.max_uploads_per_job:
        raise HTTPException(
            status_code=400,
            detail=f"最多上传 {_settings.max_uploads_per_job} 个文件",
        )

    # Validate file sizes (read + check, then seek back)
    max_bytes = _settings.max_upload_size_mb * 1024 * 1024
    for f in files:
        content = await f.read()
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件 {f.filename} 超过 {_settings.max_upload_size_mb}MB 限制",
            )
        await f.seek(0)  # Reset for later read
```

**Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_upload_limits.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add api/app/routers/jobs.py api/tests/test_upload_limits.py
git commit -m "fix: enforce file upload size and count limits"
```

---

### Task 4: Form Input Validation

**Files:**
- Create: `api/app/services/form_validator.py`
- Modify: `api/app/routers/jobs.py` (call validator before creating job)
- Create: `api/tests/test_form_validator.py`

**Step 1: Write the failing test**

```python
# api/tests/test_form_validator.py
import pytest
from app.services.form_validator import validate_form_data


def test_rejects_missing_required_field():
    with pytest.raises(ValueError, match="必填"):
        validate_form_data("intake", {})
    # intake requires: child_alias, age


def test_rejects_wrong_type_for_number():
    with pytest.raises(ValueError, match="数值"):
        validate_form_data("intake", {
            "child_alias": "test",
            "age": "not-a-number",
        })


def test_strips_unknown_fields():
    result = validate_form_data("privacy_filter", {
        "source_description": "legit note",
        "injected_field": "should be stripped",
        "__proto__": "attack",
    })
    assert "injected_field" not in result
    assert "__proto__" not in result
    assert result["source_description"] == "legit note"


def test_passes_valid_form():
    result = validate_form_data("intake", {
        "child_alias": "doudou",
        "age": 4,
        "parent_note": "optional note",
    })
    assert result["child_alias"] == "doudou"
    assert result["age"] == 4


def test_allows_empty_optional_fields():
    result = validate_form_data("privacy_filter", {})
    # privacy_filter has source_description as optional
    assert isinstance(result, dict)
```

**Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_form_validator.py -v`
Expected: FAILS with `ModuleNotFoundError: No module named 'app.services.form_validator'`

**Step 3: Implement the validator**

```python
# api/app/services/form_validator.py
"""
Form input validation against FeatureModule.form_schema.
Enforces required fields, type checking, and strips unknown fields.
"""

from __future__ import annotations

from app.core.feature_registry import get_feature, FormField


def validate_form_data(feature_id: str, form_data: dict) -> dict:
    """
    Validate form_data against the feature's form_schema.
    Returns sanitized dict with only known fields.
    Raises ValueError for validation failures.
    """
    feature = get_feature(feature_id)
    if feature is None:
        raise ValueError(f"Unknown feature: {feature_id}")

    schema_fields = {f.name: f for f in feature.form_schema}
    validated = {}

    for field in feature.form_schema:
        value = form_data.get(field.name)

        # Skip file fields (handled separately via multipart upload)
        if field.type == "file":
            continue

        # Skip select fields (client_id/staff_id handled by router)
        if field.type in ("select_client", "select_staff"):
            if value:
                validated[field.name] = str(value)
            continue

        # Required check
        if field.required and (value is None or str(value).strip() == ""):
            raise ValueError(f"必填字段缺失: {field.label}")

        if value is None:
            continue

        # Type validation
        validated[field.name] = _validate_field_type(field, value)

    return validated


def _validate_field_type(field: FormField, value) -> str | int | float:
    """Validate and coerce a single field value."""
    if field.type == "number":
        try:
            num = float(value) if "." in str(value) else int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field.label} 必须为数值")
        return num

    if field.type in ("text", "textarea"):
        text = str(value).strip()
        if field.type == "textarea" and len(text) > 5000:
            raise ValueError(f"{field.label} 超过 5000 字限制")
        if field.type == "text" and len(text) > 500:
            raise ValueError(f"{field.label} 超过 500 字限制")
        return text

    return str(value)
```

**Step 4: Wire it into the jobs router**

In `api/app/routers/jobs.py`, add import at top:

```python
from app.services.form_validator import validate_form_data
```

Inside `create_job()`, replace the raw `parsed_form` usage (after `json.loads`) with:

```python
    # Validate form_data against feature schema
    try:
        parsed_form = validate_form_data(feature_id, json.loads(form_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Step 5: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_form_validator.py -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```bash
git add api/app/services/form_validator.py api/app/routers/jobs.py api/tests/test_form_validator.py
git commit -m "feat: add form input validation against feature schema"
```

---

### Task 5: Rate Limiting

**Files:**
- Modify: `api/requirements.txt` (add `slowapi`)
- Create: `api/app/middleware/rate_limiter.py`
- Modify: `api/app/main.py` (register rate limiter)
- Modify: `api/app/routers/auth.py` (apply login rate limit)
- Modify: `api/app/routers/jobs.py` (apply job submission rate limit)
- Create: `api/tests/test_rate_limit.py`

**Step 1: Add dependency**

In `api/requirements.txt`, add under `# Utilities`:

```
slowapi==0.1.9
```

Run: `cd api && pip install slowapi==0.1.9`

**Step 2: Write the failing test**

```python
# api/tests/test_rate_limit.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_rate_limited_after_5_attempts():
    """POST /auth/login should be limited to 5/minute per IP."""
    for i in range(5):
        client.post("/api/v1/auth/login", json={"email": "bad@x.com", "password": "wrong"})

    resp = client.post("/api/v1/auth/login", json={"email": "bad@x.com", "password": "wrong"})
    assert resp.status_code == 429
    assert "rate" in resp.json().get("detail", "").lower() or resp.status_code == 429
```

**Step 3: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_rate_limit.py -v`
Expected: FAILS (returns 401, not 429)

**Step 4: Implement rate limiter**

```python
# api/app/middleware/rate_limiter.py
"""
Rate limiting middleware using slowapi.
Configurable via RATE_LIMIT_ENABLED env var.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
    default_limits=["60/minute"],
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
```

Update `api/app/main.py` — add after the CORS middleware block:

```python
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

Update `api/app/routers/auth.py` — add rate limit to login:

```python
from slowapi import Limiter
from app.middleware.rate_limiter import limiter
from fastapi import Request

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # ... existing code unchanged
```

Update `api/app/routers/jobs.py` — add rate limit to job creation:

```python
from app.middleware.rate_limiter import limiter
from fastapi import Request

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    feature_id: str = Form(...),
    # ... rest unchanged
```

**Step 5: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_rate_limit.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add api/requirements.txt api/app/middleware/rate_limiter.py api/app/main.py api/app/routers/auth.py api/app/routers/jobs.py api/tests/test_rate_limit.py
git commit -m "feat: add rate limiting — 5/min login, 10/min jobs, 60/min default"
```

---

### Task 6: Final Verification

**Files:** None (verification only)

**Step 1: Run all Sprint 1 tests together**

```bash
cd api && python -m pytest tests/ -v
```

Expected: All tests PASS (test_cors, test_jwt_safety, test_upload_limits, test_form_validator, test_rate_limit)

**Step 2: Manual smoke test**

```bash
cd api
rm -f aba_dev.db
python -m scripts.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verify in browser at `http://127.0.0.1:8000`:
- Login works
- Feature cards load
- Can submit a job with a small file
- Submitting 6+ files returns error
- Rapid login attempts get 429

**Step 3: Commit verification**

```bash
git add -A
git commit -m "chore: Sprint 1 security hardening complete — CORS, JWT, uploads, validation, rate limiting"
```
