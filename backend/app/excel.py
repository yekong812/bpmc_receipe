import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from .schemas import ExpenseIn

HEADERS = [
    "No.",
    "지출일",
    "항목",
    "품목",
    "총계",
    "구매처",
    "영수증 No.",
    "영수증 총합",
    "구매 여부",
]
ALIASES = {
    "지출일": ["지출일", "날짜", "구매일"],
    "항목": ["항목", "카테고리"],
    "품목": ["품목", "내역", "사용내역"],
    "총계": ["총계", "금액", "지출금액"],
    "구매처": ["구매처", "상호", "상호명"],
    "구매 여부": ["구매여부", "구매 여부"],
}


def clean(v):
    return str(v or "").strip().replace("\n", "").replace(" ", "")


def parse_date(v, year):
    if isinstance(v, (date, datetime)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat(), False
    parts = re.findall(r"\d+", str(v))
    if len(parts) == 2:
        return date(year, int(parts[0]), int(parts[1])).isoformat(), True
    if len(parts) == 3:
        return date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat(), False
    raise ValueError("날짜 형식을 확인하세요.")


def parse_excel(data, year, mapping=None):
    if len(data) > 15 * 1024**2:
        raise ValueError("Excel은 15MB까지 업로드할 수 있습니다.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(x.file_size for x in archive.infolist()) > 80 * 1024**2:
            raise ValueError("Excel 압축 해제 크기 제한을 초과했습니다.")
    wb = load_workbook(io.BytesIO(data), data_only=True)
    fw = load_workbook(io.BytesIO(data), data_only=False)
    ws = wb[wb.sheetnames[0]]
    if ws.max_row > 10000 or ws.max_column > 200:
        raise ValueError("최대 10,000행, 200열까지 지원합니다.")
    header_row, columns = None, {}
    for row in ws.iter_rows(max_row=min(ws.max_row, 50)):
        found = {}
        for cell in row:
            for key, aliases in ALIASES.items():
                if key not in found and clean(cell.value) in [clean(x) for x in aliases]:
                    found[key] = cell.column
        if all(k in found for k in ["지출일", "항목", "품목", "총계"]):
            header_row, columns = row[0].row, found
            break
    if mapping:
        header_row = int(mapping.get("header_row", 1))
        columns = {k: int(v) for k, v in mapping.items() if k != "header_row" and v}
    if not header_row or not all(k in columns for k in ["지출일", "항목", "품목", "총계"]):
        return {
            "rows": [],
            "errors": [],
            "warnings": [],
            "needs_mapping": True,
            "sample": [
                [str(c.value or "") for c in r] for r in ws.iter_rows(max_row=min(ws.max_row, 15))
            ],
        }
    rows, errors, warnings, previous, seen = [], [], [], None, set()
    merged = {}
    for area in ws.merged_cells.ranges:
        for r in range(area.min_row, area.max_row + 1):
            for c in range(area.min_col, area.max_col + 1):
                merged[r, c] = ws.cell(area.min_row, area.min_col).value
    for n in range(header_row + 1, ws.max_row + 1):

        def value(key):
            col = columns.get(key)
            return merged.get((n, col), ws.cell(n, col).value) if col else None

        item, amount = value("품목"), value("총계")
        if not item and amount is None:
            continue
        if clean(item) in ["합계", "총계", "총지출", "소계"] or clean(value("항목")) in [
            "합계",
            "총계",
            "소계",
        ]:
            continue
        try:
            for key in ["지출일", "항목", "품목", "총계"]:
                cell = fw[ws.title].cell(n, columns[key])
                if cell.data_type == "f" and value(key) is None:
                    raise ValueError("계산값 없는 수식입니다. Excel에서 계산 후 저장해주세요.")
            raw_date = value("지출일")
            if raw_date is None:
                if previous is None:
                    raise ValueError("첫 지출일이 비어 있습니다.")
                parsed = previous
                warnings.append(f"{n}행: 빈 날짜에 이전 날짜를 적용했습니다.")
            else:
                parsed, inferred = parse_date(raw_date, year)
                if inferred:
                    warnings.append(f"{n}행: 행사 연도 {year}년을 적용했습니다.")
            previous = parsed
            money = Decimal(re.sub(r"[₩원,\s]", "", str(amount)))
            if (
                not money.is_finite()
                or money != money.to_integral_value()
                or money < 0
                or money > 10**12
            ):
                raise ValueError("금액은 0 이상의 정수 원 단위여야 합니다.")
            if not str(item or "").strip() or not str(value("항목") or "").strip():
                raise ValueError("항목과 품목을 입력하세요.")
            row = {
                "expense_date": parsed,
                "category_name": str(value("항목")).strip(),
                "item_name": str(item).strip(),
                "amount_krw": int(money),
                "vendor": str(value("구매처") or "").strip(),
                "purchased": str(value("구매 여부")).lower()
                in ["true", "1", "yes", "y", "☑", "✓", "완료", "구매", "o"],
                "source_row": n,
            }
            if len(row["category_name"]) > 80:
                raise ValueError("항목명은 80자까지 입력할 수 있습니다.")
            ExpenseIn(
                category_id=1,
                **{k: v for k, v in row.items() if k not in ["category_name", "source_row"]},
            )
            signature = (parsed, row["item_name"], int(money), row["vendor"])
            if signature in seen:
                warnings.append(f"{n}행: 파일 내 중복 지출 후보입니다.")
            seen.add(signature)
            rows.append(row)
        except (ValueError, InvalidOperation, OverflowError) as exc:
            errors.append({"row": n, "message": str(exc) or "셀 값을 확인하세요."})
    return {
        "rows": rows,
        "errors": errors,
        "warnings": warnings,
        "needs_mapping": False,
        "sample": [],
    }


def export_excel(event, categories, expenses, receipts, links):
    wb = Workbook()
    ws = wb.active
    ws.title = "지출내역(구매LIST)"
    ws.merge_cells("A1:I1")
    ws["A1"] = "지출내역(구매LIST)"
    ws["A1"].font = Font(size=20, bold=True)
    ws.merge_cells("A2:F2")
    ws["A2"] = f"{event.name} · {event.start_date} ~ {event.end_date} · {event.status}"
    ws["G3"] = "총지출"
    ws["H3"] = sum(x.amount_krw or 0 for x in expenses)
    for c in ws[3][:9]:
        c.fill = PatternFill("solid", fgColor="DDECDD")
    for col, name in enumerate(HEADERS, 1):
        ws.cell(5, col, name)
    catmap = {c.id: c for c in categories}
    receiptmap = {r.id: getattr(r, "receipt_number", None) or i + 1 for i, r in enumerate(receipts)}
    for i, e in enumerate(expenses, 6):
        attached = [l for l in links if l.expense_id == e.id]
        values = [
            i - 5,
            date.fromisoformat(e.expense_date) if e.expense_date else None,
            catmap[e.category_id].name if e.category_id in catmap else "",
            e.item_name,
            e.amount_krw,
            e.vendor,
            ", ".join(str(receiptmap[l.receipt_id]) for l in attached),
            sum(l.allocated_amount_krw or 0 for l in attached) if attached else None,
            e.purchased,
        ]
        for col, val in enumerate(values, 1):
            ws.cell(i, col, val)
        ws.cell(i, 2).number_format = "yyyy.mm.dd"
        ws.cell(i, 3).fill = PatternFill(
            "solid",
            fgColor=(
                catmap[e.category_id].color.lstrip("#") if e.category_id in catmap else "FFFFFF"
            ),
        )
    ws["K5"] = "항목"
    ws["L5"] = "총계"
    for i, c in enumerate(categories, 6):
        ws.cell(i, 11, c.name)
        ws.cell(i, 12, sum(e.amount_krw or 0 for e in expenses if e.category_id == c.id))
    hidden = wb.create_sheet("항목목록")
    hidden.sheet_state = "hidden"
    active = [c for c in categories if c.is_active]
    for i, c in enumerate(active, 1):
        hidden.cell(i, 1, c.name)
    if active:
        wb.defined_names.add(
            DefinedName("EventCategories", attr_text=f"'항목목록'!$A$1:$A${len(active)}")
        )
        dv = DataValidation(type="list", formula1="EventCategories")
        dv.errorTitle = "항목 확인"
        dv.error = "행사 항목을 선택하세요."
        dv.showErrorMessage = True
        ws.add_data_validation(dv)
        dv.add("C6:C10000")
    thin = Side(style="thin", color="D4DED5")
    for row in ws:
        for cell in row:
            if cell.value is not None:
                cell.border = Border(bottom=thin)
                cell.alignment = Alignment(
                    vertical="center", horizontal="right" if cell.column in [5, 8, 12] else "left"
                )
                if isinstance(cell.value, str) and cell.value.startswith(("=", "+", "-", "@")):
                    cell.data_type = "s"
            if cell.row == 5:
                cell.fill = PatternFill("solid", fgColor="DDECDD")
                cell.font = Font(bold=True)
            if cell.column in [5, 8, 12] and cell.row != 5:
                cell.number_format = "₩#,##0"
    ws["H3"].number_format = "₩#,##0"
    ws.freeze_panes = "D6"
    ws.auto_filter.ref = f"A5:I{max(6,5+len(expenses))}"
    for col, width in zip("ABCDEFGHIJKL", [7, 16, 18, 32, 18, 20, 18, 18, 12, 4, 20, 20]):
        ws.column_dimensions[col].width = width
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    rs = wb.create_sheet("영수증목록")
    rs.append(["No.", "원본명", "거래일시", "상호", "금액", "연결 지출 ID", "상태", "검토 사유"])
    for i, r in enumerate(receipts, 1):
        rs.append(
            [
                i,
                r.original_name,
                r.transaction_at,
                r.merchant,
                r.final_amount_krw,
                ",".join(str(l.expense_id) for l in links if l.receipt_id == r.id),
                r.ocr_status,
                r.review_reason,
            ]
        )
    for row in rs:
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith(("=", "+", "-", "@")):
                cell.data_type = "s"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
