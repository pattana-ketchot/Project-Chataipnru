"""
เดินเว็บคณะเพื่อหาลิงก์ PDF หลักสูตร

ทำไมต้องจำว่าเจอลิงก์ที่หน้าไหน
--------------------------------
ชื่อไฟล์ PDF บนเว็บคณะเป็นค่าแฮช เช่น 24d048df23fb5ffcb042453161c9e5c8.pdf
ระบุสาขาจากชื่อไฟล์ไม่ได้เลย ตัวที่บอกได้คือ "หน้าที่พบลิงก์นั้น" ซึ่งมีหัวเรื่อง
เป็นชื่อสาขาอยู่ โมดูลนี้จึงเก็บ page_url กับ page_title ติดไปกับทุกลิงก์ที่เจอ

ทำไมใช้ regex ไม่ใช้ตัวแยก HTML
-------------------------------
หน้าเว็บเป็น PHP ที่ปั้น HTML ตรงไปตรงมา ไม่มี JavaScript สร้างเนื้อหา และเรา
ต้องการแค่ href กับหัวเรื่อง การเพิ่ม dependency ใหม่เข้ามาใน pipeline ที่ใช้
ใน production อยู่แล้วมีราคาสูงกว่าประโยชน์ที่ได้
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

from pipeline.crawl.http import PoliteClient

logger = logging.getLogger("pipeline.crawl.discover")

_A_TAG = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'>]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
_HEADING = re.compile(r"<h([1-4])\b[^>]*>(.*?)</h\1>", re.I | re.S)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


def _text(raw: str) -> str:
    """ถอดแท็กออกแล้วยุบช่องว่าง — ใช้กับข้อความในลิงก์และหัวเรื่อง"""
    s = _TAGS.sub(" ", raw)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class PdfLink:
    url: str
    filename: str
    link_text: str
    page_url: str
    page_title: str


@dataclass
class Page:
    url: str
    title: str
    headings: list[str]
    links: list[tuple[str, str]]          # (absolute url, ข้อความในลิงก์)
    pdf_links: list[PdfLink]


def parse_page(url: str, html: str) -> Page:
    m = _TITLE.search(html)
    title = _text(m.group(1)) if m else ""

    headings = [_text(h) for _, h in _HEADING.findall(html)]
    headings = [h for h in headings if h]

    links: list[tuple[str, str]] = []
    pdfs: list[PdfLink] = []
    for href, inner in _A_TAG.findall(html):
        absolute = urldefrag(urljoin(url, href.strip()))[0]
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        text = _text(inner)
        links.append((absolute, text))
        if urlparse(absolute).path.lower().endswith(".pdf"):
            pdfs.append(PdfLink(
                url=absolute,
                filename=urlparse(absolute).path.rsplit("/", 1)[-1],
                link_text=text,
                page_url=url,
                # หัวเรื่องแรกของหน้าคือชื่อสาขา ส่วน <title> เป็นข้อความกลางว่า
                # "รายละเอียดหลักสูตร" เหมือนกันทุกหน้า จึงใช้ระบุสาขาไม่ได้
                page_title=headings[0] if headings else title,
            ))
    return Page(url=url, title=title, headings=headings, links=links, pdf_links=pdfs)


def crawl(
    client: PoliteClient,
    seeds: list[str],
    allow_host: str,
    follow_patterns: list[str],
    max_pages: int = 80,
) -> tuple[list[Page], list[PdfLink], list[tuple[str, str]]]:
    """
    เดินจากหน้าตั้งต้น ตามลิงก์ที่ตรงกับ follow_patterns เท่านั้น

    จำกัดขอบเขตสองชั้น: ต้องเป็นโฮสต์เดียวกัน และเส้นทางต้องตรงรูปแบบที่ระบุ
    เพราะเว็บคณะมีลิงก์ออกไปข้างนอกและมีหน้าข่าวจำนวนมากที่ไม่เกี่ยวกับหลักสูตร
    ถ้าไม่จำกัดจะกลายเป็นการไล่เก็บทั้งเว็บ ซึ่งทั้งช้าและไม่สุภาพ
    """
    seen: set[str] = set()
    queue = list(seeds)
    pages: list[Page] = []
    pdfs: list[PdfLink] = []
    errors: list[tuple[str, str]] = []
    patterns = [re.compile(p) for p in follow_patterns]

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        resp = client.get(url)
        if resp is None:
            errors.append((url, "ดึงไม่สำเร็จ หรือ robots.txt ไม่อนุญาต"))
            continue
        if resp.status_code != 200:
            errors.append((url, f"http {resp.status_code}"))
            continue
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            errors.append((url, f"ไม่ใช่ HTML ({ctype})"))
            continue

        page = parse_page(url, resp.text)
        pages.append(page)
        pdfs.extend(page.pdf_links)
        logger.info("[%d] %s — พบ PDF %d ลิงก์", len(pages), url, len(page.pdf_links))

        for link, _ in page.links:
            if link in seen or link in queue:
                continue
            if urlparse(link).netloc != allow_host:
                continue
            if any(p.search(link) for p in patterns):
                queue.append(link)

    if queue:
        logger.warning("หยุดที่ %d หน้าตามขีดจำกัด ยังเหลือในคิว %d", max_pages, len(queue))

    # ลิงก์ PDF เดียวกันอาจปรากฏหลายหน้า เก็บครั้งแรกที่เจอไว้
    unique: dict[str, PdfLink] = {}
    for p in pdfs:
        unique.setdefault(p.url, p)
    return pages, list(unique.values()), errors
