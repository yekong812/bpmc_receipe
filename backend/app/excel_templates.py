"""Import samples, kept independent of saved ledger data."""

import io
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from .excel import HEADERS
from .annual_excel import LEDGER_O, LEDGER_B

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def sample_workbook(kind, year, target="entries", categories=(), budgets=()):
    wb = Workbook()
    ws = wb.active
    tips = [
        "샘플의 예시 행을 실제 자료로 바꾸거나 삭제한 뒤 업로드하세요. 예시 행도 가져오기 대상입니다.",
        "첫 행의 열 제목은 유지하세요. 금액은 원 단위 정수로 입력하고 수식 대신 숫자를 입력하세요.",
        f"날짜는 {year}-01-10 형태로 입력하세요. 영수증 연결은 업로드 후 화면에서 별도로 확인하세요.",
    ]
    if kind == "event":
        ws.title = "행사비 지출내역"
        ws.append(HEADERS)
        names = list(categories) or ["식비"]
        ws.append(
            [
                1,
                date(year, 1, 10),
                names[0],
                "예시: 간식 구매",
                15000,
                "예시 구매처",
                None,
                None,
                "구매",
            ]
        )
        tips.append(
            "항목은 행사에 등록된 항목명을 사용하세요. 미등록 항목은 미리보기에서 매핑하세요."
        )
        tips.append(
            "영수증 No.·영수증 총합 열은 비워두세요. 이 열을 입력해도 영수증 연결은 생성되지 않습니다."
        )
    elif target == "budget":
        ws.title = "예산 현황"
        ws.append(["관", "항", "목", "예산", "세부내용"])
        ws.append(["공동체", "운영비", "팀장운영", 100000, "예시: 팀장 모임 운영"])
        ws.append(["공동체", "운영비", "소모품비", 50000, "예시: 사무용품 구매"])
        tips.append(
            "관·항·목을 모두 입력하세요. 예산은 목 단위로 입력합니다. 실지출·잔액은 장부에서 계산됩니다."
        )
    else:
        ordinary = kind == "ordinary"
        ws.title = "경상비 장부" if ordinary else "B 장부"
        ws.append(LEDGER_O if ordinary else LEDGER_B)
        if ordinary:
            items = {b.id: b for b in budgets}
            leaf = next((b for b in budgets if b.level == 3 and b.is_active), None)
            section = items.get(leaf.parent_id) if leaf else None
            names = [section.name, leaf.name] if section and leaf else ["운영비", "팀장운영"]
            ws.append([date(year, 1, 10), *names, "예시: 운영 간식", 0, 15000, None])
            tips.append(
                "먼저 예산표를 등록하고 항·목에 등록된 이름을 정확히 입력하세요. 예시 항·목이 없다면 실제 항목명으로 바꾸세요."
            )
        else:
            ws.append([date(year, 1, 1), "예시: 전년도 이월금", 100000, 0, None])
            ws.append([date(year, 1, 10), "예시: 회비 수입", 50000, 0, None])
            ws.append([date(year, 1, 11), "예시: 물품 구매", 0, 15000, None])
            ws.append([date(year, 1, 12), "예시: 카드 캐시백", 1000, 0, None])
            tips.append("수입 내용에 '이월' 또는 '캐시백'을 포함하면 해당 거래유형으로 분류됩니다.")
        tips.append(
            "한 행에는 수입 또는 지출 중 한쪽에만 양수 금액을 입력하고 다른 쪽은 0으로 입력하세요."
        )
        tips.append("영수증번호는 비워두세요. 가져오기는 영수증 연결을 자동 생성하지 않습니다.")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, date):
                cell.number_format = "yyyy-mm-dd"
            elif isinstance(cell.value, int):
                cell.number_format = "#,##0"
            elif isinstance(cell.value, str):
                cell.data_type = "s"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    guide = wb.create_sheet("작성 안내")
    guide.append(["샘플 양식 작성 안내"])
    for tip in tips:
        guide.append([tip])
    for sheet in wb:
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDECDD")
        for col in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(col)].width = 24
    guide.column_dimensions["A"].width = 120
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
