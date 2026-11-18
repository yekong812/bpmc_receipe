import io
from openpyxl import load_workbook
from backend.tests.test_system import client, create
from backend.tests.test_v4 import book, budget, import_preview


def test_event_sample_download_can_be_previewed(client):
    e = create(client)
    base = f"/api/events/{e['id']}/excel/import"
    response = client.get(base + "/template")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert ".xlsx" in response.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(response.content))
    assert "작성 안내" in wb.sheetnames
    assert wb.active.cell(2, 3).value == e["categories"][0]["name"]
    preview = client.post(
        base + "/preview", files={"file": ("sample.xlsx", response.content)}
    ).json()
    assert not preview["errors"] and not preview["needs_mapping"]
    assert len(preview["rows"]) == 1
    assert client.get(f"/api/events/{e['id']}").json()["expenses"] == []


def test_annual_samples_match_each_import_target(client):
    ordinary = book(client, year=2028)
    budget(client, ordinary)
    b = book(client, kind="b", year=2028)
    for scope, target, count in [
        (ordinary, "budget", 2),
        (ordinary, "entries", 1),
        (b, "entries", 4),
    ]:
        url = f"/api/{scope['kind']}/books/{scope['id']}/excel/import/template"
        response = client.get(url, params={"target": target})
        assert response.status_code == 200, response.text
        wb = load_workbook(io.BytesIO(response.content))
        assert "작성 안내" in wb.sheetnames
        preview = import_preview(client, scope, response.content, target)
        assert not preview["errors"] and not preview["needs_mapping"], preview
        assert len(preview["rows"]) == count
        if target == "entries":
            assert all(row["transaction_date"].startswith("2028-") for row in preview["rows"])
        if scope["kind"] == "ordinary" and target == "entries":
            assert preview["rows"][0]["budget_name"] == "팀장운영"
        if scope["kind"] == "b":
            assert [r["entry_type"] for r in preview["rows"]] == [
                "carryover",
                "income",
                "expense",
                "cashback",
            ]
    assert (
        client.get(f"/api/b/books/{b['id']}/excel/import/template?target=budget").status_code == 422
    )
    assert client.get("/api/ordinary/books/999999/excel/import/template").status_code == 404


def test_missing_ordinary_classification_imports_as_other(client):
    from openpyxl import Workbook
    from backend.tests.test_v4 import detail

    b = book(client)
    wb = Workbook()
    ws = wb.active
    ws.append(["날짜", "항", "목", "내용", "수입", "지출"])
    ws.append(["2026-01-10", None, None, "미분류 지출", 0, 1000])
    ws.append(["2026-01-11", "없는 항", "없는 목", "미등록 분류", 0, 2000])
    ws.append(["2026-01-12", None, None, "미분류 수입", 3000, 0])
    data = io.BytesIO()
    wb.save(data)
    preview = import_preview(client, b, data.getvalue())
    assert not preview["errors"]
    assert all(r["temporary_classification"] for r in preview["rows"])
    assert detail(client, b)["budget"] == []  # preview never mutates budgets
    url = f"/api/ordinary/books/{b['id']}/excel/import/commit"
    r = client.post(
        url, json={"job_id": preview["job_id"], "mode": "append", "accept_warnings": True}
    )
    assert r.status_code == 200, r.text
    saved = detail(client, b)
    assert len(saved["budget"]) == 3
    assert all(i["name"] == "기타" for i in saved["budget"])
    leaf = next(i for i in saved["budget"] if i["level"] == 3)
    assert all(e["budget_item_id"] == leaf["id"] for e in saved["entries"])
    assert all(e["review_status"] == "검토 필요" for e in saved["entries"])
    assert "없는 항 / 없는 목" in saved["entries"][1]["note"]
    # Reimport reuses the same hierarchy and preserves original valid matches.
    preview = import_preview(client, b, data.getvalue())
    r = client.post(
        url, json={"job_id": preview["job_id"], "mode": "append", "accept_warnings": True}
    )
    assert r.status_code == 200, r.text
    assert len(detail(client, b)["budget"]) == 3
