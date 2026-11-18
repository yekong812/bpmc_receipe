import io
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
import pytest
from PIL import Image
from openpyxl import Workbook, load_workbook

os.environ["STORAGE_DIR"] = os.environ.setdefault(
    "BPMC_TEST_STORAGE", tempfile.mkdtemp(prefix="bpmc-test-")
)
os.environ["DATABASE_URL"] = f"sqlite:///{os.environ['STORAGE_DIR']}/test.db"
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import Base, engine
from backend.app.receipts import parse_receipt


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


def create(c, name="행사 A"):
    r = c.post(
        "/api/events", json={"name": name, "start_date": "2026-11-08", "end_date": "2026-11-15"}
    )
    assert r.status_code == 201, r.text
    return r.json()


def expense(e, amount=5000, **kw):
    return {
        "category_id": e["categories"][0]["id"],
        "expense_date": "2026-11-08",
        "item_name": "간식",
        "amount_krw": amount,
        "vendor": "상점",
        "purchased": True,
        **kw,
    }


def add(c, e, amount=5000, **kw):
    r = c.post(f"/api/events/{e['id']}/expenses", json=expense(e, amount, **kw))
    assert r.status_code == 201, r.text
    return r.json()


def image_zip(entries=None):
    im = io.BytesIO()
    Image.new("RGB", (30, 40), "white").save(im, format="PNG")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, raw in entries or [("photo.png", im.getvalue())]:
            z.writestr(name, raw)
    return out.getvalue()


def upload(c, e, data=None):
    r = c.post(
        f"/api/events/{e['id']}/receipts/upload",
        files={"file": ("receipts.zip", data or image_zip(), "application/zip")},
    )
    assert r.status_code == 200, r.text
    return c.get(f"/api/events/{e['id']}/receipts").json()[0]


def confirm_receipt(c, r, amount=5000, dt="2026-11-08T09:15:00"):
    res = c.patch(
        f"/api/receipts/{r['id']}",
        json={
            "transaction_at": dt,
            "merchant": "상점",
            "description": "간식",
            "final_amount_krw": amount,
            "review_reason": "",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def preview(c, e, data):
    r = c.post(f"/api/events/{e['id']}/excel/import/preview", files={"file": ("test.xlsx", data)})
    assert r.status_code == 200, r.text
    return r.json()


def test_event_isolation_category_rename_and_totals(client):
    c = client
    a = create(c)
    b = create(c, "행사 B")
    add(c, a, 1000)
    add(c, a, 2000, purchased=False)
    cid = a["categories"][0]["id"]
    cat = {**a["categories"][0], "name": "다과"}
    assert c.patch(f"/api/categories/{cid}", json=cat).status_code == 200
    da = c.get(f"/api/events/{a['id']}").json()
    db = c.get(f"/api/events/{b['id']}").json()
    assert (
        da["total_krw"] == 3000
        and da["expense_count"] == 2
        and da["categories"][0]["name"] == "다과"
    )
    assert db["total_krw"] == 0 and db["categories"][0]["name"] == "음식/선물"
    bad = expense(b, category_id=cid)
    assert c.post(f"/api/events/{b['id']}/expenses", json=bad).status_code == 422


def test_category_protection_and_move(client):
    c = client
    e = create(c)
    x = add(c, e)
    cat = e["categories"][0]
    id = cat["id"]
    assert c.delete(f"/api/categories/{id}").status_code == 409
    assert c.patch(f"/api/categories/{id}", json={**cat, "is_active": False}).status_code == 200
    assert c.post(f"/api/events/{e['id']}/expenses", json=expense(e)).status_code == 422
    assert c.patch(f"/api/expenses/{x['id']}", json={**x, "item_name": "수정"}).status_code == 200
    target = e["categories"][1]["id"]
    assert c.delete(f"/api/categories/{id}?move_to={target}").status_code == 204
    assert c.get(f"/api/events/{e['id']}/expenses").json()[0]["category_id"] == target


def test_bulk_atomic_rollback_and_version(client):
    c = client
    e = create(c)
    add(c, e)
    e = c.get(f"/api/events/{e['id']}").json()
    other = create(c, "다른 행사")
    r = c.put(
        f"/api/events/{e['id']}/expenses",
        json={
            "version": e["version"],
            "expenses": [
                expense(e, 100),
                expense(e, 200, category_id=other["categories"][0]["id"]),
            ],
        },
    )
    assert r.status_code == 422
    current = c.get(f"/api/events/{e['id']}").json()
    assert current["total_krw"] == 5000 and current["version"] == e["version"]
    r = c.put(
        f"/api/events/{e['id']}/expenses",
        json={"version": e["version"], "expenses": [expense(e, 7000)]},
    )
    assert r.status_code == 200, r.text
    assert (
        c.put(
            f"/api/events/{e['id']}/expenses", json={"version": e["version"], "expenses": []}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("value", [-1, 1.5, "NaN", 10**13])
def test_money_validation(client, value):
    c = client
    e = create(c)
    assert c.post(f"/api/events/{e['id']}/expenses", json=expense(e, value)).status_code == 422


def test_excel_roundtrip_style_categories_and_literal_formula(client):
    c = client
    e = create(c)
    x = add(c, e, 12345, item_name='=HYPERLINK("evil")')
    add(c, e, 6789, category_id=e["categories"][1]["id"])
    r = c.get(f"/api/events/{e['id']}/excel/export?draft=true")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.worksheets[0]
    assert ws["D6"].data_type == "s" and ws["H3"].value == 19134
    assert len(ws.data_validations.dataValidation) == 1 and ws["C5"].fill.fgColor.rgb.endswith(
        "DDECDD"
    )
    target = create(c, "가져올 행사")
    p = preview(c, target, r.content)
    assert not p["errors"] and len(p["rows"]) == 2
    commit = c.post(
        f"/api/events/{target['id']}/excel/import/commit",
        json={"job_id": p["job_id"], "accept_warnings": True},
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["event"]["total_krw"] == 19134
    again = c.get(f"/api/events/{target['id']}/excel/export?draft=true")
    p2 = preview(c, target, again.content)
    assert p2["rows"][0]["item_name"] == x["item_name"] and len(p2["warnings"]) == 2
    assert (
        c.post(
            f"/api/events/{target['id']}/excel/import/commit", json={"job_id": p["job_id"]}
        ).status_code
        == 409
    )


def test_excel_errors_warnings_mapping_and_replace(client):
    c = client
    e = create(c)
    add(c, e)
    data = xlsx(
        [
            ["지출일", "항목", "품목", "총계"],
            ["11.8", "새 항목", "과자", 1234],
            [None, "새 항목", "물", 2000],
        ]
    )
    p = preview(c, e, data)
    assert len(p["warnings"]) == 2 and p["new_categories"] == ["새 항목"]
    body = {"job_id": p["job_id"], "mode": "replace"}
    assert c.post(f"/api/events/{e['id']}/excel/import/commit", json=body).status_code == 422
    body.update(confirm_replace=True, accept_warnings=True, category_mapping={"새 항목": "환대"})
    res = c.post(f"/api/events/{e['id']}/excel/import/commit", json=body)
    assert res.status_code == 200, res.text
    assert res.json()["event"]["total_krw"] == 3234
    p = preview(
        c, e, xlsx([["지출일", "항목", "품목", "총계"], ["2026-11-08", "환대", "불량", -1]])
    )
    assert p["errors"]
    assert (
        c.post(
            f"/api/events/{e['id']}/excel/import/commit", json={"job_id": p["job_id"]}
        ).status_code
        == 422
    )
    p = preview(
        c, e, xlsx([["지출일", "항목", "품목", "총계"], ["2026-11-08", "환대", "수식", "=2+2"]])
    )
    assert p["errors"]
    raw = xlsx([["날짜열", "종류", "상품", "비용"], ["2026-11-08", "환대", "물", 2000]])
    p = preview(c, e, raw)
    assert p["needs_mapping"]
    r = c.post(
        f"/api/events/{e['id']}/excel/import/preview",
        files={"file": ("x.xlsx", raw)},
        data={"mapping": '{"header_row":1,"지출일":1,"항목":2,"품목":3,"총계":4}'},
    )
    assert len(r.json()["rows"]) == 1


def test_excel_wrong_event_and_stale_preview(client):
    c = client
    a = create(c)
    b = create(c, "B")
    p = preview(
        c, a, xlsx([["지출일", "항목", "품목", "총계"], ["2026-11-08", "환대", "물", 2000]])
    )
    assert (
        c.post(
            f"/api/events/{b['id']}/excel/import/commit", json={"job_id": p["job_id"]}
        ).status_code
        == 409
    )
    add(c, a)
    assert (
        c.post(
            f"/api/events/{a['id']}/excel/import/commit", json={"job_id": p["job_id"]}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "entries",
    [
        [("../escape.png", b"bad")],
        [("/absolute.png", b"bad")],
        [("fake.png", b"not an image")],
        [("script.html", b"<html>")],
    ],
)
def test_zip_security(client, entries):
    c = client
    e = create(c)
    res = c.post(
        f"/api/events/{e['id']}/receipts/upload", files={"file": ("bad.zip", image_zip(entries))}
    )
    assert res.status_code == 422
    assert c.get(f"/api/events/{e['id']}/receipts").json() == []


def test_receipt_zip_image_limit(client):
    endpoint = f"/api/events/{create(client)['id']}/receipts"
    entries = [("receipts/", b""), ("__MACOSX/._receipt.png", b"metadata")]
    for i in range(301):
        raw = io.BytesIO()
        Image.new("RGB", (30, 40), (i % 256, i // 256, 120)).save(raw, format="PNG")
        entries.append((f"receipts/{i}.png", raw.getvalue()))

    rejected = client.post(
        f"{endpoint}/upload", files={"file": ("receipts.zip", image_zip(entries))}
    )
    assert rejected.status_code == 422
    assert "최대 300장" in rejected.json()["detail"]
    assert client.get(endpoint).json() == []

    accepted = client.post(
        f"{endpoint}/upload", files={"file": ("receipts.zip", image_zip(entries[:-1]))}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["uploaded_count"] == 300


def test_receipt_allocation_duplicate_preview_export_and_cascade(client):
    c = client
    e = create(c)
    a = add(c, e, 3000)
    b = add(c, e, 2000)
    r = upload(c, e)
    res = c.post(
        f"/api/events/{e['id']}/receipts/upload", files={"file": ("duplicate.zip", image_zip())}
    )
    assert res.json()["duplicate_count"] == 1
    assert c.get(f"/api/receipts/{r['id']}/image").status_code == 200
    assert c.get(f"/api/events/{e['id']}/receipts/export-zip").status_code == 422
    confirm_receipt(c, r)
    url = f"/api/events/{e['id']}/receipt-links"
    assert (
        c.post(
            url, json={"expense_id": a["id"], "receipt_id": r["id"], "allocated_amount_krw": 3000}
        ).status_code
        == 200
    )
    assert (
        c.post(
            url, json={"expense_id": b["id"], "receipt_id": r["id"], "allocated_amount_krw": 2500}
        ).status_code
        == 422
    )
    assert (
        c.post(
            url, json={"expense_id": b["id"], "receipt_id": r["id"], "allocated_amount_krw": 2000}
        ).status_code
        == 200
    )
    d = c.get(f"/api/events/{e['id']}").json()
    assert d["matched_count"] == 2 and sum(l["allocated_amount_krw"] for l in d["links"]) == 5000
    assert c.post(f"/api/receipts/{r['id']}/review").json()["ocr_status"] == "검토 필요"
    assert (
        c.patch(
            f"/api/receipts/{r['id']}", json={"transaction_at": None, "final_amount_krw": 1000}
        ).status_code
        == 422
    )
    confirm_receipt(c, r)
    out = c.get(f"/api/events/{e['id']}/receipts/export-zip?draft=true")
    assert out.status_code == 200
    with zipfile.ZipFile(io.BytesIO(out.content)) as z:
        assert z.namelist() == ["receipts/1_5000.png", "receipts_summary.csv"]
    p = list(Path(os.environ["STORAGE_DIR"]).glob("receipts/*"))
    assert p
    assert c.delete(f"/api/events/{e['id']}").status_code == 204
    assert c.get(f"/api/receipts/{r['id']}/image").status_code == 404


def test_receipt_cross_event_and_new_expense(client):
    c = client
    a = create(c)
    b = create(c, "B")
    x = add(c, b)
    r = confirm_receipt(c, upload(c, a))
    assert (
        c.post(
            f"/api/events/{a['id']}/receipt-links",
            json={"expense_id": x["id"], "receipt_id": r["id"], "allocated_amount_krw": 5000},
        ).status_code
        == 422
    )
    url = f"/api/receipts/{r['id']}/create-expense?category_id={a['categories'][0]['id']}"
    assert c.post(url).status_code == 201
    assert c.post(url).status_code == 409


def test_ocr_missing_engine_keeps_manual_review(client, monkeypatch):
    import backend.app.main as main

    def missing(_):
        raise ImportError("not installed")

    monkeypatch.setattr(main, "recognize", missing)
    c = client
    e = create(c)
    r = upload(c, e)
    j = c.post(f"/api/events/{e['id']}/receipts/analyze").json()
    assert c.get(f"/api/jobs/{j['id']}").json()["status"] == "completed"
    receipt = c.get(f"/api/events/{e['id']}/receipts").json()[0]
    assert receipt["ocr_status"] == "검토 필요" and receipt["transaction_at"] is None


def test_parser_no_fabrication_and_ambiguous_totals():
    parsed = parse_receipt("상점\n2026-11-08 09:15\n최종 결제금액 5,000원")
    assert parsed["transaction_at"] == "2026-11-08T09:15:00" and parsed["final_amount_krw"] == 5000
    assert parsed["ocr_status"] == "검토 필요"
    parsed = parse_receipt("취소\n합계 5,000\n결제금액 4,000")
    assert (
        parsed["transaction_at"] is None
        and parsed["final_amount_krw"] is None
        and "취소" in parsed["review_reason"]
    )


def test_optimistic_lock_rejects_concurrent_change(client):
    from backend.app.db import SessionLocal
    from backend.app.models import Event
    from sqlalchemy.orm.exc import StaleDataError

    e = create(client)
    with SessionLocal() as a, SessionLocal() as b:
        first = a.get(Event, e["id"])
        second = b.get(Event, e["id"])
        first.name = "첫 저장"
        first.version += 1
        a.commit()
        second.name = "이전 버전 저장"
        second.version += 1
        with pytest.raises(StaleDataError):
            b.commit()
        b.rollback()
    assert client.get(f"/api/events/{e['id']}").json()["name"] == "첫 저장"


def test_excel_manual_mapping_missing_formula_and_replace(client):
    c = client
    e = create(c)
    add(c, e, 9999)
    raw = xlsx(
        [["날짜필드", "분류필드", "내역필드", "원화필드"], ["11.8", "새 항목", "다과", 5000]]
    )
    p = preview(c, e, raw)
    assert p["needs_mapping"]
    mapped = c.post(
        f"/api/events/{e['id']}/excel/import/preview",
        files={"file": ("map.xlsx", raw)},
        data={"mapping": '{"header_row":1,"지출일":1,"항목":2,"품목":3,"총계":4}'},
    ).json()
    assert len(mapped["rows"]) == 1 and mapped["warnings"]
    url = f"/api/events/{e['id']}/excel/import/commit"
    payload = {"job_id": mapped["job_id"], "mode": "replace", "accept_warnings": True}
    assert c.post(url, json=payload).status_code == 422
    assert c.get(f"/api/events/{e['id']}").json()["total_krw"] == 9999
    res = c.post(url, json={**payload, "confirm_replace": True})
    assert res.status_code == 200, res.text
    assert res.json()["event"]["total_krw"] == 5000 and res.json()["event"]["expense_count"] == 1
    bad = preview(
        c, e, xlsx([["지출일", "항목", "품목", "총계"], ["2026-11-08", "항목", "수식", "=1+2"]])
    )
    assert bad["errors"] and "수식" in bad["errors"][0]["message"]


def test_fifty_images_and_chronological_names(client):
    c = client
    e = create(c)
    entries = []
    for i in range(50):
        raw = io.BytesIO()
        Image.new("RGB", (30, 40), (i, 100, 120)).save(raw, format="PNG")
        entries.append((f"{i}.png", raw.getvalue()))
    result = c.post(
        f"/api/events/{e['id']}/receipts/upload", files={"file": ("50.zip", image_zip(entries))}
    )
    assert result.json()["uploaded_count"] == 50
    rs = c.get(f"/api/events/{e['id']}/receipts").json()
    for i, r in enumerate(rs):
        confirm_receipt(c, r, amount=1000 + i, dt=f"2026-11-08T09:{49-i:02d}:00")
    result = c.get(f"/api/events/{e['id']}/receipts/export-zip?draft=true")
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        assert (
            len(z.namelist()) == 51
            and z.namelist()[0] == "receipts/1_1049.png"
            and z.namelist()[-2] == "receipts/50_1000.png"
        )
