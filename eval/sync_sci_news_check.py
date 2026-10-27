"""
ตรวจตัวดึงข่าว SCI Connect ที่มาแทน Edge Function — Phase 4

เหตุที่ต้องมี: งานนี้ลบข้อมูลได้ ถ้าเงื่อนไขการตัดข่าวเก่าผิด ข่าวในระบบจะหายไป
ทีละรอบจนหมดโดยไม่มีใครสังเกต — และมันทำงานเองทุก 30 นาที

ข้อกำหนดที่ห้ามหลุด
    - **ตัดข่าวเก่าทิ้งเฉพาะเมื่อรอบนั้นเพิ่มของใหม่ได้จริง**
      เว็บต้นทางล่มหนึ่งรอบต้องไม่ทำให้ข้อมูลหาย
    - กันซ้ำด้วย detail_url ไม่ใช่ชื่อข่าว
    - แปลงวันที่พุทธศักราชถูกต้อง แปลงไม่ได้ต้องไม่ทำให้ข่าวตกหล่น
    - คำบรรยายจากหน้ารายละเอียดมาก่อนคำบรรยายย่อในการ์ด

ทั้งหมดเป็น offline: ไม่ต่อเน็ต ไม่ต่อฐานข้อมูล ไม่แตะ production

    python -m eval.sync_sci_news_check
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/course_advisor")
os.environ.setdefault("JWT_SECRET", "local-test-only")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import sci_news as s  # noqa: E402

CARD_HTML = """
<article class="news-card">
  <img src="https://example/a.jpg" alt="">
  <h2>ข่าวหนึ่ง &amp; ข่าวต่อ</h2>
  <p>คำบรรยายย่อ   ที่มีช่องว่างเยอะ</p>
  <div class="card-meta">
    <span>2 ก.ย. 2569</span>
  </div>
  <a class="card-primary-link" href="https://sci.pnru.ac.th/sciconnect_detail.php?slug=abc">อ่านต่อ</a>
</article>
<article class="news-card">
  <h2>ข่าวสอง</h2>
  <p>คำบรรยายสอง</p>
  <div class="card-meta">
    <span>ไม่ใช่วันที่</span>
  </div>
  <a class="card-primary-link" href="https://sci.pnru.ac.th/sciconnect_detail.php?slug=def">อ่านต่อ</a>
</article>
"""

DETAIL_HTML = """
<p class="lead">หัวเรื่อง</p>
<div>บรรทัดหนึ่ง<br>บรรทัดสอง <b>ตัวหนา</b></div>
<div class="source-action">
  <a class="btn btn-gold" href="https://facebook.com/post?id=1&amp;x=2">ดูโพสต์</a>
</div>
"""


class TextChecks(unittest.TestCase):
    def test_แปลง_entity_กลับเป็นอักขระ(self):
        self.assertEqual(s.decode_entities("a&amp;b&lt;c&gt;d&quot;e&#039;f&nbsp;g"),
                         "a&b<c>d\"e'f g")

    def test_ยุบช่องว่างซ้ำและตัดหัวท้าย(self):
        self.assertEqual(s.clean_text("  ก   ข \n ค  "), "ก ข ค")

    def test_ข้อความว่างไม่พัง(self):
        self.assertEqual(s.clean_text(""), "")


class CardChecks(unittest.TestCase):
    def setUp(self):
        self.cards = s.parse_news_cards(CARD_HTML)

    def test_อ่านได้ครบทุกการ์ด(self):
        self.assertEqual(len(self.cards), 2)

    def test_หัวข้อถูกแปลง_entity(self):
        self.assertEqual(self.cards[0].title, "ข่าวหนึ่ง & ข่าวต่อ")

    def test_คำบรรยายถูกยุบช่องว่าง(self):
        self.assertEqual(self.cards[0].description, "คำบรรยายย่อ ที่มีช่องว่างเยอะ")

    def test_อ่านรูปและลิงก์ได้(self):
        self.assertEqual(self.cards[0].image_url, "https://example/a.jpg")
        self.assertIn("slug=abc", self.cards[0].detail_url)

    def test_การ์ดที่ไม่มีรูปยังอ่านได้(self):
        self.assertIsNone(self.cards[1].image_url)
        self.assertEqual(self.cards[1].title, "ข่าวสอง")

    def test_html_ว่างได้รายการว่าง(self):
        self.assertEqual(s.parse_news_cards(""), [])
        self.assertEqual(s.parse_news_cards("<html></html>"), [])

    def test_โครงหน้าเว็บเปลี่ยนได้รายการว่าง_ไม่พัง(self):
        """เปลี่ยนโครงแล้วต้องได้ศูนย์ ซึ่งทำให้งานหยุดโดยไม่ลบอะไร"""
        self.assertEqual(s.parse_news_cards("<div class='news'>ข่าว</div>"), [])


class DateChecks(unittest.TestCase):
    def test_แปลงวันที่พุทธศักราช(self):
        self.assertEqual(s.parse_thai_date("2 ก.ย. 2569"), "2026-09-02")
        self.assertEqual(s.parse_thai_date("15 ธ.ค. 2568"), "2025-12-15")
        self.assertEqual(s.parse_thai_date("1 ม.ค. 2570"), "2027-01-01")

    def test_เติมศูนย์ให้วันและเดือน(self):
        self.assertEqual(s.parse_thai_date("5 ก.พ. 2569"), "2026-02-05")

    def test_รูปแบบที่แปลงไม่ได้คืน_None(self):
        for text in ("", "ไม่ใช่วันที่", "2026-09-02", "2 September 2569", "32 ก.ย."):
            self.assertIsNone(s.parse_thai_date(text), text)

    def test_เดือนที่ไม่รู้จักคืน_None(self):
        self.assertIsNone(s.parse_thai_date("2 ม.ย. 2569"))


class SlugChecks(unittest.TestCase):
    def test_อ่าน_slug_จากลิงก์(self):
        self.assertEqual(
            s.extract_slug("https://sci.pnru.ac.th/sciconnect_detail.php?slug=abc"), "abc")

    def test_ลิงก์ที่ไม่มี_slug_คืน_None(self):
        self.assertIsNone(s.extract_slug("https://sci.pnru.ac.th/x.php"))
        self.assertIsNone(s.extract_slug(""))


class DetailChecks(unittest.TestCase):
    def test_อ่านคำบรรยายเต็มและลิงก์เฟซบุ๊ก(self):
        description, facebook = s.parse_detail_page(DETAIL_HTML)
        self.assertIn("บรรทัดหนึ่ง", description)
        self.assertIn("บรรทัดสอง", description)
        self.assertNotIn("<b>", description)
        self.assertEqual(facebook, "https://facebook.com/post?id=1&x=2")

    def test_หน้าที่อ่านไม่ได้คืน_None_ทั้งคู่(self):
        self.assertEqual(s.parse_detail_page("<html></html>"), (None, None))
        self.assertEqual(s.parse_detail_page(""), (None, None))


class RowChecks(unittest.TestCase):
    def setUp(self):
        self.cards = s.parse_news_cards(CARD_HTML)

    def test_คำบรรยายจากหน้ารายละเอียดมาก่อน(self):
        row = s.row_for(self.cards[0], "คำบรรยายเต็ม", None)
        self.assertEqual(row["description"], "คำบรรยายเต็ม")

    def test_ไม่มีคำบรรยายเต็มใช้ของการ์ดแทน(self):
        row = s.row_for(self.cards[0], None, None)
        self.assertEqual(row["description"], "คำบรรยายย่อ ที่มีช่องว่างเยอะ")

    def test_แถวมีฟิลด์ครบตามตาราง(self):
        row = s.row_for(self.cards[0], None, None)
        for key in ("title", "description", "image_url", "detail_url", "published_text",
                    "published_at", "source", "slug", "facebook_url"):
            self.assertIn(key, row)

    def test_ข่าวที่แปลงวันที่ไม่ได้ยังถูกเก็บ(self):
        row = s.row_for(self.cards[1], None, None)
        self.assertIsNone(row["published_at"])
        self.assertEqual(row["title"], "ข่าวสอง")

    def test_แหล่งที่มาคงที่(self):
        self.assertEqual(s.row_for(self.cards[0], None, None)["source"], "sci_connect")


class PruneChecks(unittest.TestCase):
    def test_ไม่เพิ่มของใหม่ห้ามลบอะไร(self):
        """ข้อสำคัญสุด — เว็บต้นทางล่มหนึ่งรอบต้องไม่ทำให้ข่าวหาย"""
        self.assertFalse(s.should_prune(0, 100))
        self.assertFalse(s.should_prune(0, s.KEEP_LATEST + 1))

    def test_เพิ่มของใหม่แต่ยังไม่เกินเพดานก็ไม่ลบ(self):
        self.assertFalse(s.should_prune(1, s.KEEP_LATEST))
        self.assertFalse(s.should_prune(5, s.KEEP_LATEST - 1))

    def test_เพิ่มของใหม่และเกินเพดานจึงลบ(self):
        self.assertTrue(s.should_prune(1, s.KEEP_LATEST + 1))

    def test_เพดานเป็นค่าบวกที่สมเหตุสมผล(self):
        self.assertGreaterEqual(s.KEEP_LATEST, 5)


class SafetyChecks(unittest.TestCase):
    """
    คำสั่ง SQL ของการซิงค์อยู่สองที่ — งานตั้งเวลา กับปุ่มของผู้ดูแล
    ทั้งสองต้องมีกฎความปลอดภัยเหมือนกัน ไม่งั้นทางหนึ่งจะลบข้อมูลในแบบที่อีกทางไม่ลบ
    """

    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "backend" / "app"
        self.sources = {
            "งานตั้งเวลา": (root / "jobs" / "sync_sci_news.py").read_text(encoding="utf-8"),
            "ปุ่มผู้ดูแล": (root / "api" / "routes" / "site_admin.py").read_text(encoding="utf-8"),
        }

    def test_คำสั่งลบมีขอบเขตเสมอ(self):
        """ลบโดยไม่มี offset คือลบข่าวทั้งตาราง"""
        for name, src in self.sources.items():
            if "delete from web.external_news" in src:
                self.assertIn("offset", src, f"{name} ลบโดยไม่จำกัดขอบเขต")

    def test_การเพิ่มกันซ้ำที่ระดับฐานข้อมูลด้วย(self):
        for name, src in self.sources.items():
            self.assertIn("on conflict (detail_url) do nothing", src, name)

    def test_ตัดของเก่าต่อเมื่อ_should_prune_อนุญาต(self):
        for name, src in self.sources.items():
            self.assertIn("should_prune(", src, f"{name} ลบโดยไม่ผ่านกฎกลาง")

    def test_เขียนลง_web_เท่านั้น(self):
        for name, src in self.sources.items():
            self.assertNotIn("into public.", src, name)
            self.assertNotIn("delete from public.", src, name)
            self.assertNotIn("delete from mko.", src, name)

    def test_ตรรกะล้วนไม่มีคำสั่ง_sql_เลย(self):
        """ไฟล์ตรรกะต้องทดสอบได้โดยไม่ต้องมีฐานข้อมูล"""
        src = (Path(__file__).resolve().parents[1] / "backend" / "app" / "services"
               / "sci_news.py").read_text(encoding="utf-8")
        for word in ("insert into", "delete from", "select "):
            self.assertNotIn(word, src.lower())

    def test_ทั้งสองทางใช้ตรรกะชุดเดียวกัน(self):
        for name, src in self.sources.items():
            self.assertIn("app.services.sci_news", src, f"{name} ไม่ได้ใช้ตรรกะกลาง")


class DetailUrlChecks(unittest.TestCase):
    """
    URL ของหน้ารายละเอียดต้องเข้ารหัสก่อนเสมอ

    slug ของเว็บต้นทางเป็นชื่อเรื่องเต็ม มีช่องว่างและภาษาไทย การต่อสตริงตรง ๆ
    ทำให้ http.client โยน InvalidURL แล้วงานดึงข่าวล้มทั้งรอบตั้งแต่รายการแรก
    โดยที่ไม่มีข่าวใดถูกบันทึกเลย — เจอตอนรันจริงบนเซิร์ฟเวอร์ ไม่ใช่จากชุดทดสอบ
    """

    def test_slug_ที่มีช่องว่างและภาษาไทยถูกเข้ารหัส(self):
        url = s.detail_url_for("SCI Connect ฉบับที่ 24 ปีที่ 1 เดือนกรกฎาคม 2569")
        self.assertNotIn(" ", url)
        self.assertIn("slug=SCI+Connect", url)

    def test_url_ที่ได้ผ่านด่านของ_http_client(self):
        import http.client
        from urllib.parse import urlparse
        parts = urlparse(s.detail_url_for("SCI Connect ฉบับที่ 7 ปีที่ 1 เดือนพฤษภาคม 2569"))
        # _validate_path โยน InvalidURL ถ้ามีช่องว่างหรืออักขระควบคุม
        http.client.HTTPSConnection("example.invalid")._validate_path(
            parts.path + "?" + parts.query)

    def test_อักขระพิเศษไม่ทำให้พารามิเตอร์อื่นเพี้ยน(self):
        self.assertIn("slug=a%26b%3Dc+d", s.detail_url_for("a&b=c d"))

    def test_slug_ธรรมดาไม่ถูกเปลี่ยนรูป(self):
        self.assertTrue(s.detail_url_for("simple-slug").endswith("slug=simple-slug"))



if __name__ == "__main__":
    unittest.main()
