"""
Step 1.5: อ่านหน้าที่เป็นภาพสแกนด้วย OCR

ทำไมต้องมีขั้นนี้
----------------
extract_pdf ดึงได้เฉพาะข้อความที่ฝังอยู่ใน PDF จริง หน้าที่เป็นภาพสแกนจะได้ค่าว่าง
วัดกับคลังจริง 18 เล่ม (3,605 หน้า): มี 122 หน้าที่ดึงได้แต่หัวกระดาษกับเลขหน้า
ส่วนเนื้อหาเป็นภาพล้วน ทั้งหมดอยู่ในภาคผนวก ได้แก่ บันทึกข้อตกลงความร่วมมือ (MOU)
คำสั่งแต่งตั้งคณะกรรมการ ประวัติและผลงานทางวิชาการของอาจารย์ และหนังสือรับรอง
หลักสูตร — ข้อมูลอาจารย์ผู้สอนที่หน้ารายละเอียดหลักสูตรต้องใช้อยู่ในกลุ่มนี้

ทำไมใช้ Gemini ไม่ใช่ Tesseract
------------------------------
Tesseract ฟรีและรันในเครื่องได้ แต่ความแม่นกับภาษาไทยบนสแกนคุณภาพปานกลางต่ำกว่ามาก
และ OCR ที่อ่านผิดจะกลายเป็นข้อความมั่วในคลัง ซึ่งแย่กว่าไม่มีข้อมูลเลย เพราะระบบ
จะเอาไปตอบด้วยความมั่นใจ ที่นี่เลือกความแม่นเป็นหลักเพราะเป็นงานทำครั้งเดียว
ไม่ใช่งานที่รันทุกคำขอ

กันโมเดลแต่งเติมเอง
------------------
โมเดลภาษาที่เห็นภาพไม่ชัดมีแนวโน้มจะ "เดาให้ครบ" ตามรูปแบบเอกสารที่เคยเห็น คำสั่ง
จึงบังคับให้ถอดเฉพาะที่อ่านออก และให้ตอบด้วยเครื่องหมายที่ตกลงกันไว้เมื่ออ่านไม่ออก
ผลที่ได้ทุกหน้าถูกบันทึกแยกเป็นไฟล์ JSON ให้ตรวจด้วยตาก่อนนำเข้าคลังได้

    python -m pipeline.ocr --dir samples --out ocr_pages.json
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

import fitz
import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("pipeline.ocr")

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# เครื่องหมายที่ให้โมเดลตอบเมื่ออ่านไม่ออก เก็บไว้เป็นค่าเดียวเพื่อให้ฝั่งนำเข้า
# กรองทิ้งได้แน่นอน ไม่ต้องเดาจากข้อความ
UNREADABLE = "[[อ่านไม่ออก]]"

_PROMPT = f"""ถอดข้อความภาษาไทยและอังกฤษทั้งหมดที่เห็นในภาพหน้าเอกสารนี้ออกมาเป็นข้อความล้วน

กฎที่ต้องทำตามอย่างเคร่งครัด:
1. ถอดเฉพาะสิ่งที่อ่านออกจากภาพจริงเท่านั้น ห้ามเติม ห้ามเดา ห้ามแต่งข้อความที่ไม่เห็น
2. ถ้าส่วนใดเลือนหรืออ่านไม่ออก ให้ใส่ (อ่านไม่ออก) ตรงตำแหน่งนั้น อย่าเดาคำแทน
3. รักษาลำดับบนลงล่างและซ้ายไปขวาตามที่เห็นในภาพ
4. ตารางให้ถอดทีละแถว คั่นแต่ละช่องด้วยเครื่องหมาย |
5. ห้ามสรุป ห้ามอธิบาย ห้ามใส่ความเห็น ตอบมาเฉพาะข้อความที่ถอดได้
6. ถ้าทั้งหน้าไม่มีข้อความที่อ่านออกเลย ให้ตอบว่า {UNREADABLE} เพียงอย่างเดียว"""

# ความละเอียดที่ใช้เรนเดอร์หน้าเป็นภาพ
#
# 200 DPI เป็นจุดที่ตัวอักษรไทยขนาด 14pt คมพอให้อ่านสระบนล่างออก ต่ำกว่านี้
# วรรณยุกต์กับสระอิ/อี เริ่มติดกันจนแยกไม่ออก สูงกว่านี้ไฟล์ใหญ่ขึ้นเร็วมาก
# โดยความแม่นแทบไม่เพิ่ม
_RENDER_DPI = 200

# หน้าที่ดึงข้อความได้น้อยกว่านี้ถือว่าเนื้อหาไม่ได้อยู่ในรูปข้อความ
#
# หน้าสแกนในคลังนี้ยังมีหัวกระดาษกับเลขหน้าเป็นข้อความจริงติดมาด้วยเสมอ ซึ่งยาว
# 55-135 ตัวอักษร ส่วนหน้าเนื้อหาปกติที่สั้นที่สุดยาวเกิน 400 ตัวอักษร ค่า 200
# จึงอยู่ในช่องว่างกว้างๆ ระหว่างสองกลุ่ม ไม่ใช่ค่าที่ปรับให้พอดีเส้น
_TEXT_FLOOR = 200


def pages_needing_ocr(pdf_path: Path) -> list[int]:
    """เลขหน้าที่เนื้อหาเป็นภาพ ไม่ใช่ข้อความ"""
    out: list[int] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            if len(page.get_text("text").strip()) >= _TEXT_FLOOR:
                continue
            # ต้องมีภาพอยู่จริงถึงจะคุ้มค่าส่งไป OCR หน้าว่างเปล่าไม่มีอะไรให้อ่าน
            if page.get_images(full=True):
                out.append(i)
    return out


def render_page(pdf_path: Path, page_number: int) -> bytes:
    with fitz.open(pdf_path) as doc:
        pix = doc[page_number - 1].get_pixmap(dpi=_RENDER_DPI)
        return pix.tobytes("jpeg", jpg_quality=85)


# เว้นระยะระหว่างคำขอ เพราะโควตาฟรีของ Gemini จำกัดเป็นจำนวนคำขอต่อนาที
#
# ยิงติดกันรัวๆ แล้วโดน 429 ตั้งแต่หน้าที่ 24 การรอให้ครบจังหวะตั้งแต่แรกเร็วกว่า
# การยิงแล้วโดนปฏิเสธแล้วค่อยรอ เพราะคำขอที่ถูกปฏิเสธก็นับโควตาเหมือนกัน
_MIN_INTERVAL_S = 4.5


def ocr_image(client: httpx.Client, model: str, image: bytes, max_retries: int = 5) -> str:
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": _PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}},
            ],
        }],
        # อุณหภูมิ 0 เพราะงานนี้คือการถอดความ ไม่ใช่การเขียน ความหลากหลายมีแต่โทษ
        "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
    }
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            r = client.post(f"/models/{model}:generateContent", json=payload)
            r.raise_for_status()
            data = r.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()
        except (httpx.HTTPError, KeyError, IndexError) as e:
            last = e
            # 429 คือโควตาต่อนาทีเต็ม ต้องรอให้หน้าต่างเวลาเลื่อนไปจริงๆ ไม่ใช่รอสองสาม
            # วินาทีแล้วยิงใหม่ ซึ่งได้ 429 ซ้ำจนครบจำนวนครั้งที่ยอมให้ลอง
            rate_limited = isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429
            delay = 60 * attempt if rate_limited else 3 * attempt
            logger.warning(
                "ลองใหม่ครั้งที่ %d/%d (%s) รอ %d วินาที",
                attempt, max_retries, "โควตาเต็ม" if rate_limited else type(e).__name__, delay,
            )
            time.sleep(delay)
    raise RuntimeError(f"OCR ล้มเหลวหลังลอง {max_retries} ครั้ง: {last}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR หน้าที่เป็นภาพสแกนในไฟล์หลักสูตร")
    parser.add_argument("--dir", required=True, help="โฟลเดอร์ที่เก็บไฟล์ PDF")
    parser.add_argument("--out", required=True, help="ไฟล์ JSON ที่จะเขียนผลลัพธ์")
    parser.add_argument("--model", default=os.environ.get("OCR_MODEL", "gemini-3.5-flash-lite"))
    parser.add_argument("--limit", type=int, help="จำกัดจำนวนหน้า ใช้ตอนลองก่อนรันจริง")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ไม่พบ GEMINI_API_KEY")

    out_path = Path(args.out)
    # เขียนผลสะสมลงไฟล์เดิมได้ เพื่อให้รันค้างแล้วรันต่อได้โดยไม่เสียของเดิม
    done: dict[str, str] = {}
    if out_path.is_file():
        done = json.loads(out_path.read_text(encoding="utf-8"))
        logger.info("มีผลเดิมอยู่แล้ว %d หน้า จะข้ามหน้าเหล่านั้น", len(done))

    targets: list[tuple[Path, int]] = []
    for pdf in sorted(Path(args.dir).glob("*.pdf")):
        for page in pages_needing_ocr(pdf):
            if f"{pdf.name}#{page}" not in done:
                targets.append((pdf, page))
    if args.limit:
        targets = targets[: args.limit]
    logger.info("ต้อง OCR ทั้งหมด %d หน้า", len(targets))

    client = httpx.Client(
        base_url=_BASE_URL,
        timeout=180,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
    )
    started = time.time()
    unreadable = 0
    next_slot = 0.0
    for i, (pdf, page) in enumerate(targets, start=1):
        key = f"{pdf.name}#{page}"
        if (wait := next_slot - time.monotonic()) > 0:
            time.sleep(wait)
        next_slot = time.monotonic() + _MIN_INTERVAL_S
        text = ocr_image(client, args.model, render_page(pdf, page))
        done[key] = text
        if UNREADABLE in text or len(text) < 20:
            unreadable += 1
        logger.info("[%d/%d] %s -> %d ตัวอักษร", i, len(targets), key, len(text))
        # เขียนทุกหน้า งานนี้ใช้เวลาเป็นสิบนาทีและอาจถูกขัดจังหวะได้
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "เสร็จใน %.1f นาที | อ่านออก %d หน้า | อ่านไม่ออก %d หน้า",
        (time.time() - started) / 60, len(targets) - unreadable, unreadable,
    )


if __name__ == "__main__":
    main()
