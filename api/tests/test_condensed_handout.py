"""Xi Yao 1 condensed handout MVP tests."""

from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest

import api.services.condensed_handout as service
from api.services.condensed_handout import (
    CondensedHandoutError,
    get_condensed_handout_chapter,
    list_condensed_handout_chapters,
    save_condensed_handout_feedback,
    validate_handout_output,
)


def test_lists_mvp_chapters_without_generation_data(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "_load_latest_outputs", lambda engine, subject_code: [])

    result = list_condensed_handout_chapters(SimpleNamespace())

    assert result["subjectCode"] == "xi_yao_1"
    assert [item["chapterCode"] for item in result["chapters"]] == ["chapter_01", "chapter_03", "chapter_09"]
    assert result["chapters"][1]["status"] == "ready"
    assert result["chapters"][2]["status"] == "locked"


def test_returns_chapter_detail_without_prediction_language(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "_load_latest_output", lambda engine, chapter_code, subject_code: None)

    result = get_condensed_handout_chapter(SimpleNamespace(), chapter_code="chapter_03")
    serialized = str(result)

    assert result["title"] == "第三章 药物的体内过程"
    assert result["content"]["condensedBody"]
    assert result["sources"][0]["page"] == "p78"
    assert "真题佐证可说明" in result["content"]["reviewWarnings"][1]
    assert "押题" not in serialized
    assert "今年必考" not in serialized
    assert "稳过" not in serialized


def test_feedback_is_saved_with_public_shape(monkeypatch: pytest.MonkeyPatch):
    persisted: dict[str, object] = {}

    def fake_upsert(engine, *, chapter, principal_code):
        persisted["chapter"] = chapter
        persisted["principal_code"] = principal_code

    monkeypatch.setattr(service, "_load_latest_output", lambda engine, chapter_code, subject_code: None)
    monkeypatch.setattr(service, "_upsert_chapter_output", fake_upsert)

    saved = save_condensed_handout_feedback(
        SimpleNamespace(),
        chapter_code="chapter_03",
        status="needs_revision",
        note=" 易混点还要补充。 ",
        principal_code="org_teaching_materials",
    )

    assert saved["feedback"] == {"status": "needs_revision", "note": "易混点还要补充。"}
    assert persisted["principal_code"] == "org_teaching_materials"
    assert persisted["chapter"]["feedback"] == saved["feedback"]


def test_generated_output_with_prediction_terms_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "_load_latest_output", lambda engine, chapter_code, subject_code: None)
    data = get_condensed_handout_chapter(SimpleNamespace(), chapter_code="chapter_03")
    data["content"]["condensedBody"] = ["这个点今年必考。"]

    with pytest.raises(CondensedHandoutError, match="禁止表达"):
        validate_handout_output(data)


def test_routes_require_identity_and_return_chapter_detail(monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(service, "_load_latest_outputs", lambda engine, subject_code: [])
    monkeypatch.setattr(service, "_load_latest_output", lambda engine, chapter_code, subject_code: None)
    monkeypatch.setattr(main, "sync_engine", SimpleNamespace())
    monkeypatch.setattr(service, "_upsert_chapter_output", lambda engine, *, chapter, principal_code: None)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    anonymous = client.get("/api/condensed-handouts/xi-yao-1/chapters")
    allowed = client.get(
        "/api/condensed-handouts/xi-yao-1/chapters/chapter_03",
        headers={"X-Org-Code": "org_teaching_materials"},
    )
    feedback = client.post(
        "/api/condensed-handouts/xi-yao-1/chapters/chapter_03/feedback",
        headers={"X-Org-Code": "org_teaching_materials"},
        json={"status": "usable", "note": "可作为样稿继续评审。"},
    )

    assert anonymous.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["chapterCode"] == "chapter_03"
    assert feedback.status_code == 200
    assert feedback.json()["feedback"]["status"] == "usable"
