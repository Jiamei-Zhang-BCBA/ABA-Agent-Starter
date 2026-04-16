# api/tests/test_review_ai_revise.py
"""Tests for AI-assisted review revision."""

import json
from unittest.mock import patch, MagicMock

import pytest

from app.services.review_service import ai_revise_content
from fastapi.testclient import TestClient
from app.main import app

_client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for ai_revise_content (mocked subprocess)
# ---------------------------------------------------------------------------

@patch("app.services.review_service.subprocess.run")
def test_ai_revise_success(mock_run):
    # Claude CLI returns usage tokens nested under `usage.input_tokens`
    # (cache_read + cache_creation are summed in by review_service)
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "result": "# 修改后文档\n\n修改后的段落。",
            "usage": {
                "input_tokens": 500,
                "output_tokens": 200,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        }),
        stderr="",
    )

    result = ai_revise_content("# 原文\n\n原始段落。", "把段落改得更简洁")

    assert result["revised_content"] == "# 修改后文档\n\n修改后的段落。"
    assert result["input_tokens"] == 500
    assert result["output_tokens"] == 200


@patch("app.services.review_service.subprocess.run")
def test_ai_revise_cli_failure(mock_run):
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="rate limited",
    )

    with pytest.raises(RuntimeError, match="Claude CLI"):
        ai_revise_content("content", "instruction")


@patch("app.services.review_service.subprocess.run")
def test_ai_revise_non_json_fallback(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="# 修改后内容\n\n段落。",
        stderr="",
    )

    result = ai_revise_content("original", "revise it")

    assert result["revised_content"] == "# 修改后内容\n\n段落。"
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0


# ---------------------------------------------------------------------------
# Integration tests for HTTP endpoint
# ---------------------------------------------------------------------------

def test_ai_revise_requires_auth():
    res = _client.post("/api/v1/reviews/ai-revise", json={
        "content": "test",
        "instruction": "revise",
    })
    assert res.status_code in (401, 403)


def _register_and_get_token(email: str) -> str:
    resp = _client.post("/api/v1/users/register", json={
        "org_name": f"AIRevise-{email}",
        "admin_name": "管理员",
        "admin_email": email,
        "admin_password": "test123",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def test_ai_revise_rejects_empty_content():
    token = _register_and_get_token("revise_empty@test.com")
    res = _client.post(
        "/api/v1/reviews/ai-revise",
        json={"content": "", "instruction": "revise"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_ai_revise_rejects_empty_instruction():
    token = _register_and_get_token("revise_noinst@test.com")
    res = _client.post(
        "/api/v1/reviews/ai-revise",
        json={"content": "some content", "instruction": "  "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
