import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from PIL import Image

from backend.app.llm_service import Settings, extract_receipt, mask_sensitive
from backend.app.receipts import parse_receipt
from backend.tests.test_system import client, create, upload, confirm_receipt

CFG = Settings(
    True, "test-key-never-real", "gpt-4.1-mini", "auto", False, 5, "https://api.openai.com/v1"
)
FIELDS = {
    "transaction_date": "2026-11-08",
    "transaction_time": "09:15",
    "merchant": "테스트 상점",
    "description": "간식 구매",
    "final_amount_krw": 7500,
    "currency": "KRW",
    "is_refund": False,
    "review_reasons": [],
}


def response(values=None, **extra):
    return {
        "status": "completed",
        "model": "gpt-4.1-mini-test",
        "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(FIELDS if values is None else values),
                    }
                ],
            }
        ],
        **extra,
    }


def transport(body=None, handler=None, status=200):
    return httpx.MockTransport(
        handler
        or (lambda request: httpx.Response(status, json=body if body is not None else response()))
    )


def test_disabled_and_complete_ocr_do_not_call_provider():
    def unexpected(_):
        raise AssertionError("No network call expected")

    weak = parse_receipt("")
    assert not extract_receipt(
        "unused",
        "",
        weak,
        settings=replace(CFG, enabled=False),
        transport=transport(handler=unexpected),
    ).attempted
    complete = parse_receipt("상점\n2026-11-08 09:15\n합계 7,500원")
    assert not extract_receipt(
        "unused",
        complete["ocr_text"],
        complete,
        settings=CFG,
        transport=transport(handler=unexpected),
    ).attempted


def test_text_masking_structured_request_and_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_MILLION", "1")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_MILLION", "2")
    text = "카드번호 1234-5678-1234-5678\n010-1234-5678\nuser@example.com\n간식 결제 금액 불명"

    def handle(request):
        assert request.url == httpx.URL("https://api.openai.com/v1/responses")
        assert request.headers["Authorization"] == "Bearer test-key-never-real"
        payload = json.loads(request.content)
        assert payload["store"] is False and payload["text"]["format"]["strict"] is True
        assert all(p["type"] == "input_text" for p in payload["input"][0]["content"])
        sent = payload["input"][0]["content"][0]["text"]
        assert (
            "1234-5678-1234-5678" not in sent
            and "010-1234-5678" not in sent
            and "user@example.com" not in sent
        )
        return httpx.Response(200, json=response())

    r = extract_receipt(
        "unused", text, parse_receipt(text), settings=CFG, transport=transport(handler=handle)
    )
    assert (
        r.candidate["final_amount_krw"] == 7500
        and r.candidate["transaction_at"] == "2026-11-08T09:15"
    )
    assert r.candidate["ocr_status"] == "검토 필요" and r.input_kind == "text"
    assert r.usage["total_tokens"] == 140 and r.estimated_cost_usd == "0.00018"


def test_vision_without_ocr_and_explicit_image_permission(tmp_path):
    path = tmp_path / "receipt.png"
    Image.new("RGB", (40, 50), "white").save(path)
    denied = extract_receipt(path, "", parse_receipt(""), settings=CFG)
    assert not denied.attempted and "ALLOW_IMAGES" in denied.error

    def handle(request):
        parts = json.loads(request.content)["input"][0]["content"]
        assert parts[1]["type"] == "input_image" and parts[1]["image_url"].startswith(
            "data:image/jpeg;base64,"
        )
        return httpx.Response(200, json=response())

    r = extract_receipt(
        path,
        "",
        parse_receipt(""),
        settings=replace(CFG, allow_images=True),
        transport=transport(handler=handle),
    )
    assert r.candidate["merchant"] == "테스트 상점" and r.input_kind == "image"
    denied = extract_receipt(path, "", parse_receipt(""), settings=replace(CFG, mode="text"))
    assert not denied.attempted and "OCR 텍스트" in denied.error


def test_missing_key_invalid_settings_and_masking():
    assert (
        "API 키"
        in extract_receipt("unused", "?", parse_receipt("?"), settings=replace(CFG, key="")).error
    )
    assert not extract_receipt(
        "unused",
        "?",
        parse_receipt("?"),
        settings=replace(CFG, base_url="http://unsafe.example/v1"),
    ).attempted
    assert not extract_receipt(
        "unused", "?", parse_receipt("?"), settings=replace(CFG, mode="bad")
    ).attempted
    masked = mask_sensitive(
        "900101-1234567 test@example.com 01012345678 카드번호 1234-****-****-1234"
    )
    for private in ["900101-1234567", "test@example.com", "01012345678", "1234-****-****-1234"]:
        assert private not in masked


@pytest.mark.parametrize(
    "fields",
    [
        {**FIELDS, "transaction_date": "2026-02-30"},
        {**FIELDS, "transaction_time": "25:01"},
        {**FIELDS, "final_amount_krw": 1.5},
        {**FIELDS, "final_amount_krw": -5},
        {**FIELDS, "final_amount_krw": True},
    ],
)
def test_invalid_values_are_reviewed_and_usage_preserved(fields):
    r = extract_receipt(
        "unused", "?", parse_receipt("?"), settings=CFG, transport=transport(response(fields))
    )
    assert r.candidate is None and r.error and r.usage["total_tokens"] == 140


def test_missing_time_refunds_foreign_currency_and_refusal():
    r = extract_receipt(
        "unused",
        "?",
        parse_receipt("?"),
        settings=CFG,
        transport=transport(response({**FIELDS, "transaction_time": None, "is_refund": True})),
    )
    assert r.candidate["transaction_at"] == "2026-11-08" and "취소" in r.candidate["review_reason"]
    r = extract_receipt(
        "unused",
        "?",
        parse_receipt("?"),
        settings=CFG,
        transport=transport(response({**FIELDS, "currency": "OTHER"})),
    )
    assert r.candidate["final_amount_krw"] is None
    body = response(output=[{"content": [{"type": "refusal", "refusal": "no"}]}])
    r = extract_receipt("unused", "?", parse_receipt("?"), settings=CFG, transport=transport(body))
    assert r.candidate is None and r.error


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_provider_errors_never_expose_provider_body(status):
    r = extract_receipt(
        "unused",
        "?",
        parse_receipt("?"),
        settings=CFG,
        transport=transport({"error": "secret test-key-never-real"}, status=status),
    )
    assert r.attempted and r.candidate is None and "test-key-never-real" not in r.error


def test_timeout_incomplete_and_bad_json():
    def timeout(_):
        raise httpx.ReadTimeout("test-key-never-real")

    r = extract_receipt(
        "unused", "?", parse_receipt("?"), settings=CFG, transport=transport(handler=timeout)
    )
    assert "시간" in r.error and "test-key" not in r.error
    r = extract_receipt(
        "unused",
        "?",
        parse_receipt("?"),
        settings=CFG,
        transport=transport(response(status="incomplete")),
    )
    assert r.candidate is None and r.usage
    r = extract_receipt(
        "unused",
        "?",
        parse_receipt("?"),
        settings=CFG,
        transport=transport(handler=lambda _: httpx.Response(200, text="bad json")),
    )
    assert r.candidate is None and "검증" in r.error


def test_llm_pipeline_creates_draft_and_preserves_manual_edits(client, monkeypatch):
    import backend.app.main as main

    monkeypatch.setenv("RECEIPT_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-real")
    monkeypatch.setenv("RECEIPT_LLM_MODE", "vision")
    monkeypatch.setenv("RECEIPT_LLM_ALLOW_IMAGES", "true")

    def no_ocr(_):
        raise AssertionError("vision must not initialize PaddleOCR")

    monkeypatch.setattr(main, "recognize", no_ocr)
    monkeypatch.setattr(
        main, "extract_receipt", lambda *args: extract_receipt(*args, transport=transport())
    )
    c = client
    e = create(c)
    r = upload(c, e)
    j = c.post(f"/api/events/{e['id']}/receipts/analyze")
    assert j.status_code == 202
    data = c.get(f"/api/events/{e['id']}").json()
    assert len(data["expenses"]) == 1 and data["expenses"][0]["amount_krw"] == 7500
    assert (
        data["receipts"][0]["merchant"] == "테스트 상점"
        and data["receipts"][0]["ocr_status"] == "검토 필요"
    )
    history = c.get(f"/api/receipts/{r['id']}/extractions").json()
    assert (
        history[0]["input_kind"] == "image"
        and json.loads(history[0]["usage_json"])["input_tokens"] == 100
    )
    assert "test-key-never-real" not in json.dumps(history)
    assert (
        c.post(
            f"/api/events/{e['id']}/receipt-links",
            json={
                "expense_id": data["expenses"][0]["id"],
                "receipt_id": r["id"],
                "allocated_amount_krw": 7000,
            },
        ).status_code
        == 200
    )
    confirm_receipt(c, r, 7000)
    assert c.post(f"/api/events/{e['id']}/receipts/analyze").status_code == 202
    after = c.get(f"/api/events/{e['id']}").json()
    assert len(after["expenses"]) == 1 and after["receipts"][0]["final_amount_krw"] == 7000
    assert "test-key-never-real" not in c.get("/api/health").text


def test_api_error_on_one_receipt_does_not_stop_remaining_images(client, monkeypatch):
    import io
    import backend.app.main as main
    from backend.tests.test_system import image_zip

    monkeypatch.setenv("RECEIPT_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-real")
    monkeypatch.setenv("RECEIPT_LLM_MODE", "vision")
    monkeypatch.setenv("RECEIPT_LLM_ALLOW_IMAGES", "true")
    calls = []

    def handle(request):
        calls.append(request)
        return (
            httpx.Response(429, json={"error": "private"})
            if len(calls) == 1
            else httpx.Response(200, json=response())
        )

    monkeypatch.setattr(
        main,
        "extract_receipt",
        lambda *args: extract_receipt(*args, transport=transport(handler=handle)),
    )
    images = []
    for i in range(2):
        raw = io.BytesIO()
        Image.new("RGB", (20, 20), (i, 20, 30)).save(raw, format="PNG")
        images.append((f"{i}.png", raw.getvalue()))
    c = client
    e = create(c)
    assert (
        c.post(
            f"/api/events/{e['id']}/receipts/upload", files={"file": ("two.zip", image_zip(images))}
        ).status_code
        == 200
    )
    job = c.post(f"/api/events/{e['id']}/receipts/analyze").json()
    status = c.get(f"/api/jobs/{job['id']}").json()
    assert status["status"] == "completed" and status["processed"] == 2 and len(calls) == 2
    data = c.get(f"/api/events/{e['id']}").json()
    assert sorted((r["final_amount_krw"] or 0) for r in data["receipts"]) == [0, 7500]
    assert any("한도" in r["review_reason"] for r in data["receipts"])
