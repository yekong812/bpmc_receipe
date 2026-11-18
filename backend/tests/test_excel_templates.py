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
