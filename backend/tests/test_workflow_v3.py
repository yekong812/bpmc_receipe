import io
import json
import zipfile
from openpyxl import load_workbook
from backend.tests.test_system import client, create, add, upload, confirm_receipt


def latest(c, e):
    return c.get(f"/api/events/{e['id']}").json()


def review(c, e):
    current = latest(c, e)
    r = c.post(f"/api/events/{e['id']}/review", json={"version": current["version"]})
    assert r.status_code == 200, r.text
    return r.json()


def finalize(c, e, reason=""):
    current = latest(c, e)
    return c.post(
        f"/api/events/{e['id']}/finalize",
        json={
            "version": current["version"],
            "approval_reason": reason,
            "acknowledge_warnings": bool(reason),
        },
    )


def test_final_lock_reopen_versions_and_default_final_exports(client):
    c = client
    e = create(c)
    x = add(c, e, 8000)
    review(c, e)
    checks = c.get(f"/api/events/{e['id']}/finalize/check").json()
    assert not checks["errors"] and checks["warnings"]
    assert finalize(c, e).status_code == 422
    result = finalize(c, e, "영수증 없는 현금 지출, 사용자 확인")
    assert result.status_code == 200, result.text
    final = result.json()
    assert final["status"] == "최종 확정" and final["latest_final_version"] == 1
    assert c.patch(f"/api/expenses/{x['id']}", json={**x, "amount_krw": 7500}).status_code == 409
    assert (
        c.post(f"/api/events/{e['id']}/categories", json={"name": "잠금 검증"}).status_code == 409
    )
    assert c.delete(f"/api/expenses/{x['id']}").status_code == 409
    assert (
        c.post(f"/api/events/{e['id']}/finalize", json={"version": final["version"]}).status_code
        == 409
    )
    reopened = c.post(f"/api/events/{e['id']}/reopen", json={"version": final["version"]})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "재수정중"
    assert c.patch(f"/api/expenses/{x['id']}", json={**x, "amount_krw": 7500}).status_code == 200
    event_list = c.get("/api/events").json()[0]
    assert event_list["total_krw"] == 8000 and event_list["draft_total_krw"] == 7500
    export = c.get(f"/api/events/{e['id']}/excel/export")
    assert load_workbook(io.BytesIO(export.content)).worksheets[0]["H3"].value == 8000
    assert finalize(c, e, "현금 지출 정정").status_code == 200
    versions = c.get(f"/api/events/{e['id']}/versions").json()
    assert [v["version_no"] for v in versions] == [2, 1]
    v1 = c.get(f"/api/events/{e['id']}/versions/1").json()
    v2 = c.get(f"/api/events/{e['id']}/versions/2").json()
    assert v1["total_krw"] == 8000 and v2["total_krw"] == 7500
    assert c.get(f"/api/events/{e['id']}/changes").json()


def test_final_receipt_bytes_survive_revision_deletion(client):
    c = client
    e = create(c)
    x = add(c, e)
    r = confirm_receipt(c, upload(c, e))
    assert (
        c.post(
            f"/api/events/{e['id']}/receipt-links",
            json={"expense_id": x["id"], "receipt_id": r["id"], "allocated_amount_krw": 5000},
        ).status_code
        == 200
    )
    review(c, e)
    final = finalize(c, e)
    assert final.status_code == 200, final.text
    first = c.get(f"/api/events/{e['id']}/receipts/export-zip").content
    assert (
        c.post(
            f"/api/events/{e['id']}/reopen", json={"version": final.json()["version"]}
        ).status_code
        == 200
    )
    assert c.delete(f"/api/receipts/{r['id']}").status_code == 204
    second = c.get(f"/api/events/{e['id']}/receipts/export-zip?version=1")
    assert second.status_code == 200
    with zipfile.ZipFile(io.BytesIO(first)) as a, zipfile.ZipFile(io.BytesIO(second.content)) as b:
        assert a.read("receipts/1_5000.png") == b.read("receipts/1_5000.png")


def test_auto_draft_and_reanalysis_preserve_user_edits(client, monkeypatch):
    import backend.app.main as main

    monkeypatch.setattr(
        main, "recognize", lambda _: "상점\n2026-11-08 09:15\n최종 결제금액 8,000원"
    )
    c = client
    e = create(c)
    r = upload(c, e)
    assert c.post(f"/api/events/{e['id']}/receipts/analyze").status_code == 202
    data = latest(c, e)
    assert data["status"] == "작성중" and len(data["expenses"]) == 1
    x = data["expenses"][0]
    assert (
        x["amount_krw"] == 8000 and x["review_status"] == "검토 필요" and x["source_type"] == "ocr"
    )
    assert (
        c.patch(
            f"/api/expenses/{x['id']}", json={**x, "amount_krw": 7500, "review_status": "확인됨"}
        ).status_code
        == 200
    )
    confirm_receipt(c, r, 8000)
    monkeypatch.setattr(
        main, "recognize", lambda _: "다른 상점\n2026-11-08 09:15\n최종 결제금액 9,000원"
    )
    assert c.post(f"/api/events/{e['id']}/receipts/analyze").status_code == 202
    data = latest(c, e)
    assert len(data["expenses"]) == 1 and data["expenses"][0]["amount_krw"] == 7500
    assert data["receipts"][0]["final_amount_krw"] == 8000
    history = c.get(f"/api/receipts/{r['id']}/extractions").json()
    assert (
        len(history) == 2 and json.loads(history[0]["extracted_json"])["final_amount_krw"] == 9000
    )


def test_failed_ocr_draft_keeps_missing_fields_and_blocks_final(client, monkeypatch):
    import backend.app.main as main

    monkeypatch.setattr(main, "recognize", lambda _: "")
    c = client
    e = create(c)
    upload(c, e)
    assert c.post(f"/api/events/{e['id']}/receipts/analyze").status_code == 202
    x = latest(c, e)["expenses"][0]
    assert x["expense_date"] is None and x["amount_krw"] is None
    assert c.get(f"/api/events/{e['id']}/finalize/check").json()["errors"]
    review(c, e)
    assert finalize(c, e, "검토").status_code == 422


def test_existing_expense_candidate_does_not_generate_duplicate(client, monkeypatch):
    import backend.app.main as main

    monkeypatch.setattr(
        main, "recognize", lambda _: "상점\n2026-11-08 09:15\n최종 결제금액 5,000원"
    )
    c = client
    e = create(c)
    add(c, e)
    upload(c, e)
    assert c.post(f"/api/events/{e['id']}/receipts/analyze").status_code == 202
    assert len(latest(c, e)["expenses"]) == 1 and not latest(c, e)["links"]
    assert c.get(f"/api/events/{e['id']}/receipt-suggestions").json()[0]["candidates"]


def test_date_only_receipt_remains_date_only_and_exports_review_folder(client):
    from backend.app.receipts import parse_receipt

    parsed = parse_receipt("상점\n2026-11-08\n결제금액 5,000원")
    assert parsed["transaction_at"] == "2026-11-08"
    c = client
    e = create(c)
    r = upload(c, e)
    confirmed = confirm_receipt(c, r, 5000, "2026-11-08")
    assert confirmed["transaction_at"] == "2026-11-08"
    result = c.get(f"/api/events/{e['id']}/receipts/export-zip?draft=true")
    assert result.status_code == 200
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        assert z.namelist()[0] == "review_required/1_5000.png"


def test_exclude_duplicate_and_body_limit(client):
    c = client
    e = create(c)
    r = upload(c, e)
    excluded = c.post(f"/api/receipts/{r['id']}/exclude")
    assert excluded.status_code == 200 and excluded.json()["ocr_status"] == "제외"
    assert (
        c.post(
            "/api/events",
            content=b"{}",
            headers={"content-type": "application/json", "content-length": str(60 * 1024**2)},
        ).status_code
        == 413
    )
