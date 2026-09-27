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

import logging
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("pipeline.crawl.http")

USER_AGENT = (
    "SCI-Advisor-Crawler/1.0 "
    "(+https://stpnru-advisor.duckdns.org; academic project; contact via faculty)"
)

# หน่วง 1.5 วินาทีต่อคำขอ เว็บคณะเป็น Apache เครื่องเดียว ไม่ได้อยู่หลัง CDN
DEFAULT_DELAY = 1.5


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
        if not self.allowed(url):
            logger.warning("robots.txt ไม่อนุญาต: %s", url)
            return None
        try:
            return self._raw_get(url)
        except httpx.HTTPError as e:
            logger.warning("ดึงไม่สำเร็จ %s — %s", url, e)
            return None

    def head(self, url: str) -> httpx.Response | None:
        """
        ใช้เช็คว่าไฟล์เปลี่ยนไหมโดยไม่ต้องโหลดทั้งไฟล์

        บางเซิร์ฟเวอร์ไม่รองรับ HEAD แล้วตอบ 405 กรณีนั้นผู้เรียกต้องถอยไปใช้ GET
        """
        if not self.allowed(url):
            logger.warning("robots.txt ไม่อนุญาต: %s", url)
            return None
        assert self._client is not None
        try:
            self._wait()
            self.requests_made += 1
            return self._client.head(url)
        except httpx.HTTPError as e:
            logger.warning("HEAD ไม่สำเร็จ %s — %s", url, e)
            return None
