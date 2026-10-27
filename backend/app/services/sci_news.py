"""
อ่านข่าว SCI Connect จากหน้าเว็บต้นทาง — Phase 4 (มาแทน Supabase Edge Function)

ไฟล์นี้เป็น **ตรรกะล้วน** ไม่ต่อฐานข้อมูล ใช้ร่วมกันสองที่
    - app/jobs/sync_sci_news.py   งานตั้งเวลาบนเซิร์ฟเวอร์
    - routes/site_admin.py        ปุ่มสั่งดึงทันทีของผู้ดูแล

อยู่ใน backend (ไม่ใช่ pipeline) เพราะ image ของ backend ไม่ได้คัดลอก pipeline เข้าไป
การแยกไว้คนละที่จะทำให้ปุ่มของผู้ดูแลใช้ไม่ได้ในคอนเทนเนอร์

ตรรกะเหมือนของเดิมทุกข้อ (ported จาก supabase/functions/sync-sci-news/index.ts)
    - กันซ้ำด้วย detail_url ไม่ใช่ชื่อข่าว เพราะชื่อซ้ำกันได้
    - **ตัดข่าวเก่าทิ้งเฉพาะเมื่อรอบนี้เพิ่มของใหม่ได้จริง**
      รอบที่ดึงไม่ได้หรือไม่มีของใหม่ ต้องไม่ลบอะไรเลย ไม่งั้นเว็บต้นทางล่มหนึ่งรอบ
      แล้วข่าวในระบบหายหมด
    - เก็บไว้ 15 ข่าวล่าสุด เรียงตามวันที่เผยแพร่ ข่าวที่แปลงวันที่ไม่ได้ไปอยู่ท้ายสุด
    - ดึงหน้ารายละเอียดเฉพาะข่าวใหม่ ไม่ยิงซ้ำทุกข่าวทุกรอบ

ส่วนบนของไฟล์เป็นตรรกะล้วน ทดสอบได้โดยไม่ต้องต่อเน็ตหรือฐานข้อมูล
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

SOURCE_URL = "https://sci.pnru.ac.th/sciconnect.php?typeconnect=1"
DETAIL_URL = "https://sci.pnru.ac.th/sciconnect_detail.php"
SOURCE_NAME = "sci_connect"
KEEP_LATEST = 15
TIMEOUT = 30

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

_ENTITIES = (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
             ("&#039;", "'"), ("&#39;", "'"), ("&nbsp;", " "))

_CARD = re.compile(r'<article class="news-card">.*?</article>', re.S)
_IMG = re.compile(r'<img src="([^"]+)"')
_TITLE = re.compile(r"<h2>(.*?)</h2>", re.S)
_DESC = re.compile(r"<p>(.*?)</p>", re.S)
_DATE = re.compile(r'<div class="card-meta">\s*<span>(.*?)</span>', re.S)
_LINK = re.compile(r'<a class="card-primary-link" href="([^"]+)"')
_DETAIL_BODY = re.compile(r'<p class="lead">.*?</p>\s*<div>(.*?)</div>\s*<div class="source-action">', re.S)
_FACEBOOK = re.compile(r'<a class="btn btn-gold" href="([^"]+)"')
_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?>", re.I)
_THAI_DATE = re.compile(r"^(\d{1,2})\s+(\S+)\s+(\d{4})$")


def decode_entities(text: str) -> str:
    for src, dst in _ENTITIES:
        text = text.replace(src, dst)
    return text


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", decode_entities(text)).strip()


@dataclass(frozen=True)
class Card:
    title: str
    description: str
    image_url: str | None
    detail_url: str | None
    published_text: str


def parse_news_cards(html: str) -> list[Card]:
    cards = []
    for block in _CARD.findall(html or ""):
        title = _TITLE.search(block)
        description = _DESC.search(block)
        image = _IMG.search(block)
        link = _LINK.search(block)
        date = _DATE.search(block)
        cards.append(Card(
            title=clean_text(title.group(1)) if title else "",
            description=clean_text(description.group(1)) if description else "",
            image_url=image.group(1) if image else None,
            detail_url=link.group(1) if link else None,
            published_text=clean_text(date.group(1)) if date else "",
        ))
    return cards


def parse_thai_date(text: str) -> str | None:
    """
    "2 ก.ย. 2569" -> "2026-09-02"

    แปลงไม่ได้คืน None — แถวนั้นยังถูกเก็บ เพียงแต่ไม่มีวันที่ไว้เรียง
    """
    match = _THAI_DATE.match((text or "").strip())
    if not match:
        return None
    day, month_th, year_be = match.groups()
    if month_th not in TH_MONTHS:
        return None
    try:
        year_ce = int(year_be) - 543
    except ValueError:
        return None
    return f"{year_ce:04d}-{TH_MONTHS.index(month_th) + 1:02d}-{int(day):02d}"


def extract_slug(detail_url: str) -> str | None:
    try:
        values = parse_qs(urlparse(detail_url).query).get("slug")
    except ValueError:
        return None
    return values[0] if values else None


def detail_url_for(slug: str) -> str:
    """
    ประกอบ URL ของหน้ารายละเอียดจาก slug — **ต้องเข้ารหัสก่อนเสมอ**

    slug ของเว็บต้นทางเป็นชื่อเรื่องเต็ม มีทั้งช่องว่างและภาษาไทย เช่น
        SCI Connect ฉบับที่ 24 ปีที่ 1 เดือนกรกฎาคม 2569

    ต่อสตริงตรง ๆ จะได้ URL ที่มีช่องว่าง แล้ว http.client โยน
        InvalidURL: URL can't contain control characters
    ทำให้งานดึงข่าวล้มทั้งรอบตั้งแต่รายการแรก และ **ไม่มีข่าวใดถูกบันทึกเลย**

    พบตอนรันจริงบนเซิร์ฟเวอร์ — dry-run ไม่เจอเพราะอ่านแค่หน้ารายการ ไม่เปิดหน้ารายละเอียด
    """
    return f"{DETAIL_URL}?{urlencode({'slug': slug})}"


def parse_detail_page(html: str) -> tuple[str | None, str | None]:
    """คืน (คำบรรยายเต็ม, ลิงก์เฟซบุ๊ก) — ไม่พบคืน None ทั้งคู่ได้"""
    body = _DETAIL_BODY.search(html or "")
    description = None
    if body:
        description = clean_text(_TAG.sub("", _BR.sub("\n", body.group(1))))
    facebook = _FACEBOOK.search(html or "")
    return description or None, decode_entities(facebook.group(1)) if facebook else None


def row_for(card: Card, description: str | None, facebook_url: str | None) -> dict:
    """ประกอบแถวที่จะเขียนลงฐานข้อมูล — คำบรรยายจากหน้ารายละเอียดมาก่อนถ้ามี"""
    return {
        "title": card.title,
        "description": description or card.description or None,
        "image_url": card.image_url,
        "detail_url": card.detail_url,
        "published_text": card.published_text or None,
        "published_at": parse_thai_date(card.published_text),
        "source": SOURCE_NAME,
        "slug": extract_slug(card.detail_url or ""),
        "facebook_url": facebook_url,
    }


def should_prune(inserted: int, total_rows: int) -> bool:
    """
    ตัดข่าวเก่าทิ้งได้เมื่อไร

    **เฉพาะเมื่อรอบนี้เพิ่มของใหม่ได้จริง** — รอบที่เว็บต้นทางล่มหรือไม่มีข่าวใหม่
    ต้องไม่ลบอะไรเลย ไม่งั้นข่าวในระบบจะหายไปทีละรอบจนหมด
    """
    return inserted > 0 and total_rows > KEEP_LATEST


def fetch_url(url: str) -> str | None:
    """
    ดึงหน้าเว็บหนึ่งหน้า — คืน None เมื่อดึงไม่สำเร็จ

    ไม่โยนข้อผิดพลาดออกไป เพราะผู้เรียกต้องตัดสินใจ "ไม่ทำอะไรเลย" ซึ่งปลอดภัยกว่า
    การล้มทั้งงานแล้วมีคนไปแก้ด้วยการลบข้อมูล
    """
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "sci-advisor-sync/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                return None
            return response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
