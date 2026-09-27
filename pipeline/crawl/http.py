"""
ตัวดึงหน้าเว็บที่สุภาพ — ใช้ร่วมกันทุกโมดูลใน crawl/

ทำไมต้องมีชั้นนี้แยก
--------------------
กติกาการดึงข้อมูลจากเว็บคนอื่นมีสามข้อที่ต้องทำทุกคำขอ ไม่ใช่ทำบางที่:
บอกว่าเราเป็นใคร (User-Agent) · เว้นจังหวะไม่ยิงรัว · เคารพ robots.txt
ถ้าปล่อยให้แต่ละโมดูลเรียก httpx เอง สักพักจะมีที่ที่ลืมข้อใดข้อหนึ่ง

เว็บที่ดึงเป็นของคณะตัวเอง การยิงถี่จนเว็บช้าจึงเป็นปัญหาที่หนักกว่าเรื่องเทคนิค

robots.txt ที่ไม่มีอยู่ ไม่ได้แปลว่าห้าม
-----------------------------------------
sci.pnru.ac.th ตอบ 404 สำหรับ /robots.txt ซึ่งตามมาตรฐาน RFC 9309 หมายถึง
"ไม่มีข้อห้าม" ไม่ใช่ "ห้ามทั้งหมด" ส่วน www.pnru.ac.th ระบุ Disallow: ว่าง
คืออนุญาตทุกเส้นทาง — ตรวจไว้เมื่อ 28 กันยายน 2569

ถึงอย่างนั้นก็ยังหน่วงเวลาทุกคำขออยู่ดี เพราะ robots.txt ไม่ได้บอกเรื่องความถี่
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("pipeline.crawl.http")

USER_AGENT = (
    "SCI-Advisor-Crawler/1.0 "
    "(+https://stpnru-advisor.duckdns.org; academic project; contact via faculty)"
)

# หน่วง 1.5 วินาทีต่อคำขอ เว็บคณะเป็น Apache เครื่องเดียว ไม่ได้อยู่หลัง CDN
DEFAULT_DELAY = 1.5

# ---- ขอบเขตที่ยอมให้ดึง -------------------------------------------------
#
# บังคับที่ชั้นนี้เพราะเป็นชั้นเดียวที่ทุกโมดูลใน crawl/ ต้องผ่าน
#
# discover.crawl() กรองโฮสต์เฉพาะ "หน้าที่จะเดินต่อ" แต่ลิงก์ PDF ที่เก็บได้
# (pdfs.extend(page.pdf_links)) ไม่ได้กรองเลย ลิงก์ .pdf ที่ชี้ออกนอกเว็บคณะบนหน้าของ
# คณะเองจึงเคยถูกดาวน์โหลดและเก็บลง staging ได้ การกันที่ตัวดึงจึงคุมได้ทุกทางเข้า
# ไม่ต้องหวังว่าทุกผู้เรียกจะกรองเอง
ALLOWED_HOSTS = frozenset({"sci.pnru.ac.th"})
ALLOWED_SCHEMES = frozenset({"http", "https"})
# พอร์ตอื่นบนโฮสต์เดียวกันอาจเป็นบริการอื่นที่ไม่ได้ตั้งใจเปิดสู่ภายนอก
ALLOWED_PORTS = frozenset({None, 80, 443})

# เพดานขนาดไฟล์ — ตรงกับ backend/app/core/config.py::max_pdf_size_mb (50)
# ถ้าแก้ที่นี่ต้องแก้ที่นั่นด้วย ไม่งั้นไฟล์ที่ crawler ยอมรับจะเปิดดูผ่านเว็บไม่ได้
MAX_PDF_BYTES = 50 * 1024 * 1024

# ลายเซ็นที่ต้องอยู่ต้นไฟล์ PDF ทุกไฟล์ตามมาตรฐาน
PDF_SIGNATURE = b"%PDF-"

# content-type ที่ถือว่าประกาศตรง — ที่ไม่อยู่ในนี้ยังรับได้ถ้าลายเซ็นถูก แต่จะถูกบันทึกไว้
PDF_CONTENT_TYPES = frozenset({"application/pdf", "application/x-pdf"})

# อ่านทีละ 64 KB ไม่ใช่ทั้งไฟล์ — เพดานหน่วยความจำจึงเป็นขนาดก้อน ไม่ใช่ขนาดไฟล์
_STREAM_CHUNK = 1 << 16


def url_rejection(url: str) -> str:
    """เหตุผลที่ไม่ยอมดึง URL นี้ — คืนสตริงว่างถ้าดึงได้

    คืนเหตุผลเป็นข้อความแทนการคืน bool เพราะต้องเอาไปเก็บใน crawl_sources.last_error
    ให้คนอ่านได้ว่าทำไมลิงก์นี้ไม่ผ่าน
    """
    try:
        parts = urlparse(url)
    except ValueError as e:
        return f"URL ผิดรูปแบบ ({e})"

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return f"scheme ไม่อนุญาต ({parts.scheme or 'ไม่มี'})"
    host = (parts.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return f"โฮสต์ไม่อนุญาต ({host or 'ไม่มี'})"
    try:
        port = parts.port
    except ValueError:
        return "พอร์ตผิดรูปแบบ"
    if port not in ALLOWED_PORTS:
        return f"พอร์ตไม่อนุญาต ({port})"
    return ""


@dataclass(frozen=True)
class Download:
    """ผลการดาวน์โหลดไฟล์หนึ่ง

    path ชี้ไปที่ไฟล์ชั่วคราวที่ผ่านการตรวจแล้วทุกด่าน ผู้เรียกต้องย้ายไปเก็บหรือลบทิ้ง
    ถ้า ok เป็น False จะไม่มีไฟล์ค้างไว้เลย — ตัวดาวน์โหลดลบของตัวเองก่อนคืนค่า
    """

    ok: bool
    reason: str = ""
    status_code: int | None = None
    size: int = 0
    sha256: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    content_type: str | None = None
    final_url: str | None = None
    path: Path | None = None

    @property
    def content_type_mismatch(self) -> bool:
        """ประกาศ content-type ไม่ตรงกับ PDF แต่ลายเซ็นในไฟล์ถูก"""
        return self.ok and (self.content_type or "") not in PDF_CONTENT_TYPES


@dataclass
class PoliteClient:
    delay: float = DEFAULT_DELAY
    timeout: float = 30.0
    _client: httpx.Client | None = field(default=None, init=False, repr=False)
    _robots: dict[str, urllib.robotparser.RobotFileParser] = field(default_factory=dict, init=False, repr=False)
    _last_request_at: float = field(default=0.0, init=False, repr=False)
    requests_made: int = field(default=0, init=False)

    def __enter__(self) -> "PoliteClient":
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "th,en;q=0.8"},
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    def __exit__(self, *exc) -> None:
        if self._client:
            self._client.close()

    # ---- robots.txt -----------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin in self._robots:
            return self._robots[origin]

        parser = urllib.robotparser.RobotFileParser()
        # ด่านซ้ำ: ตัวนี้เป็นที่เดียวที่ยิงผ่าน _raw_get ซึ่งไม่ตรวจอะไรเลย ถ้าใครเรียก
        # allowed() ด้วย URL นอกขอบเขตโดยตรง จะได้ไม่มีคำขอวิ่งออกไปหาโฮสต์นั้น
        if url_rejection(url):
            parser.disallow_all = True
            self._robots[origin] = parser
            return parser
        try:
            resp = self._raw_get(origin + "/robots.txt")
            if resp.status_code == 200 and "text/plain" in resp.headers.get("content-type", ""):
                parser.parse(resp.text.splitlines())
                logger.info("robots.txt ของ %s: อ่านได้ ใช้กติกาตามไฟล์", origin)
            else:
                # 404 หรือไม่ใช่ text/plain = ไม่มีข้อห้าม (RFC 9309)
                parser.parse([])
                logger.info("robots.txt ของ %s: ไม่มี (http %s) ถือว่าอนุญาต", origin, resp.status_code)
        except httpx.HTTPError as e:
            # ดึงไม่ได้ให้ถือว่าห้ามไว้ก่อน ปลอดภัยกว่าเดาว่าอนุญาต
            parser.disallow_all = True
            logger.warning("robots.txt ของ %s: ดึงไม่ได้ (%s) จะข้ามโดเมนนี้", origin, e)

        self._robots[origin] = parser
        return parser

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(USER_AGENT, url)

    # ---- คำขอ -----------------------------------------------------------
    def _wait(self) -> None:
        gap = time.monotonic() - self._last_request_at
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last_request_at = time.monotonic()

    def _raw_get(self, url: str) -> httpx.Response:
        """ใช้ภายในเท่านั้น — ไม่เช็ค robots เพราะใช้ดึงตัว robots.txt เอง"""
        assert self._client is not None, "ต้องใช้ผ่าน with PoliteClient() as c:"
        self._wait()
        self.requests_made += 1
        return self._client.get(url)

    def get(self, url: str) -> httpx.Response | None:
        reason = url_rejection(url)
        if reason:
            logger.warning("ไม่ดึง %s — %s", url, reason)
            return None
        if not self.allowed(url):
            logger.warning("robots.txt ไม่อนุญาต: %s", url)
            return None
        try:
            resp = self._raw_get(url)
        except httpx.HTTPError as e:
            logger.warning("ดึงไม่สำเร็จ %s — %s", url, e)
            return None
        # ตามมาตรฐานแล้ว redirect ออกนอกโฮสต์ที่อนุญาตถือว่าไม่ได้ดึงสำเร็จ
        reason = url_rejection(str(resp.url))
        if reason:
            logger.warning("redirect ออกนอกที่อนุญาต %s -> %s (%s)", url, resp.url, reason)
            return None
        return resp

    def head(self, url: str) -> httpx.Response | None:
        """
        ใช้เช็คว่าไฟล์เปลี่ยนไหมโดยไม่ต้องโหลดทั้งไฟล์

        บางเซิร์ฟเวอร์ไม่รองรับ HEAD แล้วตอบ 405 กรณีนั้นผู้เรียกต้องถอยไปใช้ GET
        """
        reason = url_rejection(url)
        if reason:
            logger.warning("ไม่ดึง %s — %s", url, reason)
            return None
        if not self.allowed(url):
            logger.warning("robots.txt ไม่อนุญาต: %s", url)
            return None
        assert self._client is not None
        try:
            self._wait()
            self.requests_made += 1
            resp = self._client.head(url)
        except httpx.HTTPError as e:
            logger.warning("HEAD ไม่สำเร็จ %s — %s", url, e)
            return None
        reason = url_rejection(str(resp.url))
        if reason:
            logger.warning("redirect ออกนอกที่อนุญาต %s -> %s (%s)", url, resp.url, reason)
            return None
        return resp

    # ---- ดาวน์โหลดไฟล์ --------------------------------------------------
    def download(self, url: str, dest_dir: Path, max_bytes: int = MAX_PDF_BYTES) -> Download:
        """
        ดาวน์โหลด PDF แบบทยอยอ่าน ตรวจทุกด่านก่อนคืนไฟล์ให้ผู้เรียก

        ทำไมไม่ใช้ resp.content
        ----------------------
        resp.content อ่านทั้งไฟล์เข้าหน่วยความจำก่อนแล้วจึงวัดขนาดได้ ซึ่งสายเกินไป —
        ไฟล์ใหญ่ผิดปกติจะกินหน่วยความจำจนโปรเซสตายก่อนที่จะมีใครได้ปฏิเสธมัน
        เครื่องที่รันเป็น Oracle Always Free (ARM, RAM จำกัด) จึงเจ็บจริง
        ที่นี่นับไบต์ไปพร้อมกับอ่าน เกินเพดานเมื่อไหร่หยุดทันที เพดานหน่วยความจำ
        คือขนาดก้อน (64 KB) ไม่ใช่ขนาดไฟล์

        ทำไมเขียนลงไฟล์ชั่วคราวก่อน
        --------------------------
        ชื่อไฟล์จริงใน staging ต้องมี sha256 ซึ่งรู้ครบเมื่ออ่านจบแล้วเท่านั้น และการ
        เขียนตรงลงชื่อจริงจะทิ้งไฟล์ครึ่ง ๆ ไว้ถ้าเน็ตหลุดกลางทาง ซึ่งอันตรายกว่าไม่มีไฟล์
        เพราะคนตรวจจะเห็นไฟล์ที่เปิดไม่ได้แล้วไม่รู้ว่าเพราะอะไร
        ไฟล์ชั่วคราวชื่อขึ้นต้นด้วยจุดและอยู่โฟลเดอร์เดียวกับปลายทาง เพื่อให้ผู้เรียก
        os.replace() ได้แบบ atomic (ข้ามไฟล์ซิสเทมไม่ได้)

        ลำดับการตรวจ — เรียงจากถูกไปแพง
        ------------------------------
            1. scheme / โฮสต์ / พอร์ต ของ URL ที่ขอ      (ไม่ยิงเลยถ้าไม่ผ่าน)
            2. robots.txt
            3. สถานะ HTTP
            4. scheme / โฮสต์ / พอร์ต ของ URL ปลายทางหลังตาม redirect
            5. content-length ที่ประกาศมา เทียบเพดาน     (ไม่อ่านเนื้อถ้าประกาศเกิน)
            6. ลายเซ็น %PDF- จากก้อนแรก                  (ยังไม่สร้างไฟล์ก่อนผ่านข้อนี้)
            7. ขนาดจริงระหว่างอ่าน เทียบเพดาน
            8. อ่านครบตามที่ประกาศไว้
        """
        reason = url_rejection(url)
        if reason:
            return Download(ok=False, reason=reason)
        if not self.allowed(url):
            return Download(ok=False, reason="robots.txt ไม่อนุญาต")

        assert self._client is not None, "ต้องใช้ผ่าน with PoliteClient() as c:"

        # ทุกทางออกต้องผ่านตัวแปรเดียวกัน เพื่อให้ finally ตัดสินได้แน่นอนว่าต้องลบไฟล์ไหม
        # ถ้าปล่อยให้บาง return สร้าง Download เองโดยไม่ผ่านที่นี่ วันหนึ่งจะมีทางออกที่
        # ลืมลบไฟล์ครึ่ง ๆ ทิ้ง หรือแย่กว่านั้นคือลบไฟล์ที่สำเร็จแล้ว
        tmp: Path | None = None
        outcome: Download | None = None

        def fail(reason: str, **kw) -> Download:
            nonlocal outcome
            outcome = Download(ok=False, reason=reason, **kw)
            return outcome

        try:
            self._wait()
            self.requests_made += 1
            with self._client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return fail(f"GET http {resp.status_code}", status_code=resp.status_code)

                final_url = str(resp.url)
                reason = url_rejection(final_url)
                if reason:
                    return fail(f"redirect ออกนอกที่อนุญาต — {reason}",
                                status_code=resp.status_code, final_url=final_url)

                ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower() or None
                declared = resp.headers.get("content-length")
                declared_n = int(declared) if declared and declared.isdigit() else None
                meta = dict(status_code=resp.status_code,
                            etag=resp.headers.get("etag"),
                            last_modified=resp.headers.get("last-modified"),
                            content_type=ctype, final_url=final_url)

                if declared_n is not None and declared_n > max_bytes:
                    return fail(f"ไฟล์ใหญ่เกินเพดาน — ประกาศ {declared_n} ไบต์ เพดาน {max_bytes}",
                                size=declared_n, **meta)

                digest = hashlib.sha256()
                size = 0
                head = b""
                handle = None
                try:
                    for chunk in resp.iter_bytes(_STREAM_CHUNK):
                        if not chunk:
                            continue
                        # ยังไม่สร้างไฟล์จนกว่าจะเห็นลายเซ็นครบและถูกต้อง
                        if handle is None:
                            head += chunk
                            if len(head) < len(PDF_SIGNATURE):
                                continue
                            if not head.startswith(PDF_SIGNATURE):
                                return fail("ไม่ใช่ PDF — ต้นไฟล์เป็น "
                                            f"{head[:len(PDF_SIGNATURE)]!r} ไม่ใช่ {PDF_SIGNATURE!r}",
                                            size=len(head), **meta)
                            dest_dir.mkdir(parents=True, exist_ok=True)
                            fd, name = tempfile.mkstemp(prefix=".part_", suffix=".pdf", dir=dest_dir)
                            tmp = Path(name)
                            handle = os.fdopen(fd, "wb")
                            chunk = head
                        size += len(chunk)
                        if size > max_bytes:
                            return fail(f"ไฟล์ใหญ่เกินเพดาน — อ่านได้ {size} ไบต์ เพดาน {max_bytes}",
                                        size=size, **meta)
                        digest.update(chunk)
                        handle.write(chunk)
                finally:
                    if handle is not None:
                        handle.close()

                if handle is None:
                    # เนื้อสั้นกว่าลายเซ็น หรือไม่มีเนื้อเลย
                    return fail(f"ไฟล์สั้นเกินกว่าจะเป็น PDF ({len(head)} ไบต์)",
                                size=len(head), **meta)
                if declared_n is not None and size != declared_n:
                    return fail(f"ดาวน์โหลดไม่ครบ — ได้ {size} ไบต์ จากที่ประกาศ {declared_n}",
                                size=size, **meta)

                outcome = Download(ok=True, size=size, sha256=digest.hexdigest(), path=tmp, **meta)
                return outcome
        except httpx.HTTPError as e:
            return fail(f"{type(e).__name__}: {e}")
        except OSError as e:
            return fail(f"เขียนไฟล์ชั่วคราวไม่ได้: {e}")
        finally:
            # ไฟล์ค้างต้องไม่เหลือไม่ว่าจะออกทางไหน รวมถึงทางที่ไม่ได้คิดไว้
            # (outcome เป็น None ได้เมื่อมี exception ที่ไม่ได้ดักไว้ เช่น KeyboardInterrupt)
            if tmp is not None and (outcome is None or not outcome.ok):
                tmp.unlink(missing_ok=True)
