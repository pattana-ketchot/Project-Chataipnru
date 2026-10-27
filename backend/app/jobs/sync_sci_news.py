"""
งานตั้งเวลาดึงข่าว SCI Connect — Phase 4 (มาแทน Edge Function + pg_cron ของ Supabase)

    docker compose ... exec -T backend python -m app.jobs.sync_sci_news --dry-run
    docker compose ... exec -T backend python -m app.jobs.sync_sci_news

ตั้งเวลาด้วย cron ของเซิร์ฟเวอร์ ไม่ต้องมีบริการภายนอก

รันในคอนเทนเนอร์เดียวกับ backend เพื่อให้ใช้การตั้งค่า ฐานข้อมูล และตรรกะชุดเดียวกัน
กับปุ่ม "ดึงข่าวทันที" ของผู้ดูแล — สองทางนี้ต้องให้ผลเหมือนกันเสมอ

กฎที่สำคัญที่สุด: **ตัดข่าวเก่าทิ้งเฉพาะเมื่อรอบนั้นเพิ่มของใหม่ได้จริง**
รอบที่เว็บต้นทางล่มต้องไม่ลบอะไรเลย ไม่งั้นข่าวในระบบหายไปทีละรอบจนหมด
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.sci_news import (KEEP_LATEST, SOURCE_URL, detail_url_for, extract_slug,
                                   fetch_url, parse_detail_page, parse_news_cards, row_for,
                                   should_prune)

INSERT = """
    insert into web.external_news
      (title, description, image_url, detail_url, published_text,
       published_at, source, slug, facebook_url)
    values (:title, :description, :image_url, :detail_url, :published_text,
            cast(:published_at as timestamptz), :source, :slug, :facebook_url)
    on conflict (detail_url) do nothing
"""

PRUNE = """
    delete from web.external_news where id in (
        select id from web.external_news
        order by published_at desc nulls last, synced_at desc
        offset :keep)
"""


def run(apply: bool) -> int:
    html = fetch_url(SOURCE_URL)
    if html is None:
        print("ดึงหน้าเว็บต้นทางไม่สำเร็จ — ไม่เปลี่ยนแปลงอะไร")
        return 1

    parsed = [c for c in parse_news_cards(html) if c.detail_url]
    print(f"อ่านข่าวจากหน้าเว็บได้ {len(parsed)} รายการ")
    if not parsed:
        print("ไม่พบข่าวในหน้าเว็บ — ไม่เปลี่ยนแปลงอะไร (โครงหน้าเว็บอาจเปลี่ยน)")
        return 1

    db = SessionLocal()
    try:
        urls = [c.detail_url for c in parsed]
        existing = {r["detail_url"] for r in db.execute(
            text("select detail_url from web.external_news where detail_url = any(:urls)"),
            {"urls": urls},
        ).mappings().all()}
        new_cards = [c for c in parsed if c.detail_url not in existing]
        print(f"มีอยู่แล้ว {len(existing)} · ใหม่ {len(new_cards)}")

        if not apply:
            for card in new_cards:
                print(f"  จะเพิ่ม: {card.title[:60]}")
            print("\n-- โหมดลองเท่านั้น ไม่ได้เขียนอะไร --")
            return 0

        inserted = 0
        for card in new_cards:
            slug = extract_slug(card.detail_url or "")
            description, facebook_url = (None, None)
            if slug:
                detail_html = fetch_url(detail_url_for(slug))
                if detail_html:
                    description, facebook_url = parse_detail_page(detail_html)
            result = db.execute(text(INSERT), row_for(card, description, facebook_url))
            inserted += result.rowcount or 0

        total = db.execute(
            text("select count(*) as n from web.external_news")).mappings().first()["n"]
        deleted = 0
        if should_prune(inserted, total):
            deleted = db.execute(text(PRUNE), {"keep": KEEP_LATEST}).rowcount or 0

        db.commit()
        print(f"เพิ่ม {inserted} · ลบของเก่า {deleted} · เหลือในตาราง {total - deleted}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ดึงข่าว SCI Connect เข้า web.external_news")
    parser.add_argument("--dry-run", action="store_true", help="ดูว่าจะเพิ่มอะไรโดยไม่เขียน")
    args = parser.parse_args()
    return run(apply=not args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
