"""Deterministic evidence slides from saved metadata; never calls AI."""

import hashlib
import io
import math
from PIL import Image, ImageOps
from fastapi import HTTPException
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from .db import STORAGE

MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def select_receipts(snapshot, from_date="", to_date="", include_unverified=False):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "출력 시작일은 종료일 이전이어야 합니다.")
    numbered = [
        {**r, "receipt_number": r.get("receipt_number") or i}
        for i, r in enumerate(snapshot["receipts"], 1)
    ]
    selected = []
    for r in numbered:
        if r["ocr_status"] == "제외":
            continue
        day = (r.get("transaction_at") or "")[:10]
        if day and ((from_date and day < from_date) or (to_date and day > to_date)):
            continue
        unknown = (
            not r.get("transaction_at")
            or len(r["transaction_at"]) < 16
            or r.get("final_amount_krw") is None
            or r["ocr_status"] != "확인됨"
        )
        if unknown and not include_unverified:
            raise HTTPException(
                422,
                f"영수증 #{r['receipt_number']}의 날짜·시간·금액·검토 상태를 확인하거나 미확인 포함 옵션을 선택하세요.",
            )
        selected.append(r)
    return sorted(
        selected, key=lambda r: (r.get("transaction_at") or "9999", r["original_name"], r["id"])
    )


def generate_ppt(snapshot, from_date="", to_date="", include_unverified=False, per_slide=3):
    if per_slide != 3:
        raise HTTPException(422, "현재 레이아웃은 슬라이드당 3장입니다.")
    receipts = select_receipts(snapshot, from_date, to_date, include_unverified)
    if not receipts:
        raise HTTPException(422, "선택한 범위에 출력할 영수증이 없습니다.")
    prs = Presentation()
    slide_width = 13.333333
    prs.slide_width = Inches(slide_width)
    prs.slide_height = Inches(7.5)

    def text(slide, value, x, y, w, h, size, bold=False, color="284E3B", align=PP_ALIGN.LEFT):
        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = shape.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        tf.margin_left = tf.margin_right = Inches(0.04)
        tf.margin_top = tf.margin_bottom = 0
        for i, line in enumerate(value.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.alignment = align
            p.space_before = p.space_after = Pt(0)
            p.line_spacing = 1.0
            p.font.size = Pt(size)
            p.font.bold = bold
            p.font.name = "맑은 고딕"
            p.font.color.rgb = RGBColor.from_string(color)
        return shape

    pages = math.ceil(len(receipts) / 3)
    for page in range(pages):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        group = receipts[page * 3 : (page + 1) * 3]
        title = snapshot["name"] + " · 영수증 증빙자료"
        if not snapshot.get("final_version"):
            title = "[미확정 초안] " + title
        text(slide, title, 0.2, 0.12, 12.0, 0.28, 13, True)
        text(slide, f"{page+1} / {pages}", 12.25, 0.14, 0.88, 0.2, 8, align=PP_ALIGN.RIGHT)
        image_top = 0.48
        if from_date or to_date:
            text(
                slide,
                f'조회기간 {from_date or "전체"} ~ {to_date or "전체"}',
                0.2,
                0.42,
                12,
                0.17,
                8,
                color="73836E",
            )
            image_top = 0.66
        image_height = 6.75 - image_top
        left = 0.2
        gap = 0.15
        cell_w = (slide_width - 2 * left - (len(group) - 1) * gap) / len(group)
        for offset, r in enumerate(group):
            path = STORAGE / r["stored_path"]
            if not path.is_file():
                raise HTTPException(409, f"영수증 #{r['receipt_number']} 원본 파일이 없습니다.")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != r["sha256"]:
                raise HTTPException(
                    409, f"영수증 #{r['receipt_number']} 원본 해시가 일치하지 않습니다."
                )
            try:
                with Image.open(io.BytesIO(raw)) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    image.load()
                    image.thumbnail((2200, 3000))
                    size = image.size
                    converted = io.BytesIO()
                    image.save(converted, format="PNG")
                    converted.seek(0)
            except Exception as exc:
                raise HTTPException(
                    422, f"영수증 #{r['receipt_number']} 이미지가 손상되어 PPT를 만들 수 없습니다."
                ) from exc
            x = left + offset * (cell_w + gap)
            scale = min(cell_w / size[0], image_height / size[1])
            w = size[0] * scale
            h = size[1] * scale
            slide.shapes.add_picture(
                converted,
                Inches(x + (cell_w - w) / 2),
                Inches(image_top + (image_height - h) / 2),
                width=Inches(w),
                height=Inches(h),
            )
            amount = (
                f"₩ {r['final_amount_krw']:,}"
                if r.get("final_amount_krw") is not None
                else "금액 미확인"
            )
            stamp = (r.get("transaction_at") or "거래일시 미확인").replace("T", " ")
            caption = (
                f"영수증 #{r['receipt_number']} · {amount} · {stamp}\n"
                f"{r.get('merchant') or '구매처 미확인'}"
            )
            if r["ocr_status"] != "확인됨":
                caption += " · 검토 필요"
            text(
                slide,
                caption,
                x,
                6.81,
                cell_w,
                0.46,
                8,
                align=PP_ALIGN.CENTER,
            )
        text(
            slide,
            "BPMC · 저장된 영수증 원본 및 최종 수정값 기준",
            0.2,
            7.33,
            12,
            0.14,
            6.5,
            color="899582",
        )
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
