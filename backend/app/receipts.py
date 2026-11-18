import hashlib
import io
import re
import stat
import warnings
import zipfile
from datetime import datetime
from pathlib import PurePosixPath
from PIL import Image, ImageOps

MAX_ZIP = 60 * 1024**2
MAX_TOTAL = 250 * 1024**2
MAX_IMAGE = 20 * 1024**2
MAX_IMAGES = 300
MAX_ZIP_ENTRIES = 400
Image.MAX_IMAGE_PIXELS = 40_000_000


def unpack_images(data):
    if len(data) > MAX_ZIP:
        raise ValueError(f"ZIP은 {MAX_ZIP // 1024**2}MB까지 업로드할 수 있습니다.")
    images = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = archive.infolist()
        if len(files) > MAX_ZIP_ENTRIES:
            raise ValueError(f"ZIP 내부 항목은 최대 {MAX_ZIP_ENTRIES}개입니다.")
        for info in files:
            path = PurePosixPath(info.filename.replace("\\", "/"))
            if (
                path.is_absolute()
                or ".." in path.parts
                or ":" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise ValueError("안전하지 않은 ZIP 경로입니다.")
            if info.flag_bits & 1:
                raise ValueError("암호화 ZIP은 지원하지 않습니다.")
            if info.is_dir() or "__MACOSX" in path.parts or path.name.startswith("."):
                continue
            suffix = path.suffix.lower()
            if suffix not in [".jpg", ".jpeg", ".png", ".webp"]:
                raise ValueError(f"지원하지 않는 파일: {path.name}")
            if len(images) >= MAX_IMAGES:
                raise ValueError(f"영수증은 최대 {MAX_IMAGES}장까지 업로드할 수 있습니다.")
            total += info.file_size
            if (
                info.file_size > MAX_IMAGE
                or total > MAX_TOTAL
                or info.file_size / max(info.compress_size, 1) > 200
            ):
                raise ValueError("압축 해제 용량 또는 압축률 제한을 초과했습니다.")
            raw = archive.read(info)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as im:
                    if im.format not in ["JPEG", "PNG", "WEBP"]:
                        raise ValueError("이미지 확장자와 실제 형식을 확인하세요.")
                    actual = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[im.format]
                    im.verify()
            images.append((path.name, actual, raw, hashlib.sha256(raw).hexdigest()))
    if not images:
        raise ValueError("ZIP에 지원하는 영수증 이미지가 없습니다.")
    return images


def parse_receipt(text):
    reasons = []
    transaction = None
    amount = None
    dates = re.findall(
        r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})일?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?",
        text,
    )
    if len(set(dates)) == 1:
        try:
            transaction = datetime(*map(int, dates[0][:5]), int(dates[0][5] or 0)).isoformat(
                timespec="seconds"
            )
        except ValueError:
            reasons.append("거래일시 형식 확인")
    else:
        reasons.append("거래 날짜·시간 누락 또는 복수 후보")
    if transaction is None:
        date_candidates = re.findall(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})", text)
        if len(set(date_candidates)) == 1:
            try:
                transaction = datetime(*map(int, date_candidates[0])).date().isoformat()
            except ValueError:
                pass
    candidates = []
    for line in text.splitlines():
        if re.search(r"최종|결제\s*금액|합계|받을\s*금액|승인\s*금액|총\s*액", line):
            nums = re.findall(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{3,})(?:\s*원)?", line)
            if nums:
                candidates.append(int(nums[-1].replace(",", "")))
    if len(set(candidates)) == 1:
        amount = candidates[0]
    else:
        reasons.append("최종 결제금액 누락 또는 복수 후보")
    if re.search(r"취소|환불|반품", text):
        reasons.append("취소·환불 영수증 확인")
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    return {
        "transaction_at": transaction,
        "final_amount_krw": amount,
        "merchant": lines[0][:200] if lines else "",
        "description": " / ".join(lines[:3])[:1000],
        "review_reason": "; ".join(reasons),
        "ocr_text": text,
        "ocr_status": "검토 필요",
    }


_engine = None


def recognize(path):
    global _engine
    # Optional, lazily loaded: metadata review still works without heavyweight OCR.
    if _engine is None:
        from paddleocr import PaddleOCR

        _engine = PaddleOCR(
            lang="korean", use_doc_orientation_classify=False, use_doc_unwarping=False
        )
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((2400, 4000))
        import numpy as np

        result = list(_engine.predict(np.array(im)))
    return "\n".join(t for page in result for t in page.get("rec_texts", []))
