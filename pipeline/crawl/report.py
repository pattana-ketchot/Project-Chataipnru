"""
เขียนรายงานผลสำรวจเป็น Markdown

เขียนให้คนอ่านตัดสินใจได้ ไม่ใช่แค่รายการดิบ — ทุกไฟล์ต้องบอกได้ว่าควรทำอะไรต่อ
และถ้าระบบเดาหลักสูตรไม่ได้ต้องบอกตรง ๆ ไม่ใช่เดาให้ดูเรียบร้อย
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

_ORDER = ["อาจเปลี่ยนแปลง", "ไฟล์ใหม่", "ระบุไม่ได้", "ดึงไม่สำเร็จ", "ยังไม่ได้ตรวจ", "มีอยู่แล้ว"]

_ACTION = {
    "อาจเปลี่ยนแปลง": "ให้คนเปิดดูว่าเป็นฉบับปรับปรุงใหม่หรือไม่ ถ้าใช่จึงนำเข้าใน Phase 2",
    "ไฟล์ใหม่": "ยังไม่มีในระบบ ให้คนยืนยันว่าเป็นเอกสารหลักสูตรจริงก่อนนำเข้า",
    "ระบุไม่ได้": "จับคู่กับหลักสูตรไม่ได้ ต้องให้คนระบุเองหรือทำเครื่องหมายว่าไม่เกี่ยวข้อง",
    "ดึงไม่สำเร็จ": "ตรวจซ้ำอีกครั้ง อาจเป็นปัญหาชั่วคราวของเว็บปลายทาง",
    "ยังไม่ได้ตรวจ": "รันใหม่โดยไม่ใส่ --no-hash เพื่อให้เทียบ sha256 ได้",
    "มีอยู่แล้ว": "ไม่ต้องทำอะไร",
}


def _size(n: int | None) -> str:
    if not n:
        return "-"
    return f"{n/1024/1024:.2f} MB" if n >= 1024 * 1024 else f"{n/1024:.0f} KB"


def write_report(path: Path, *, findings, pages, errors, known,
                 started: datetime, finished: datetime,
                 requests_made: int, delay: float, hashed: bool) -> None:
    conf_counts: dict[str, int] = {}
    for f in findings:
        conf_counts[f.match.confidence] = conf_counts.get(f.match.confidence, 0) + 1

    by_status: dict[str, list] = {}
    for f in findings:
        by_status.setdefault(f.status, []).append(f)

    w: list[str] = []
    a = w.append

    a("# รายงานผลสำรวจ PDF หลักสูตรบนเว็บคณะ (Phase 1)\n")
    a(f"สำรวจเมื่อ {started.astimezone().strftime('%d %B %Y %H:%M')} น. "
      f"ใช้เวลา {(finished - started).total_seconds():.0f} วินาที\n")
    a("> **Phase 1 เป็นการตรวจอย่างเดียว** ไม่ได้นำเข้าเอกสาร ไม่ได้เขียนฐานข้อมูล "
      "และไม่ได้เก็บไฟล์ PDF ไว้บนเครื่อง\n")
    a("\n---\n")

    # ---- สรุป -----------------------------------------------------------
    a("\n## สรุป\n")
    a("| รายการ | จำนวน |")
    a("|---|---|")
    a(f"| หน้าเว็บที่เดินตรวจ | {len(pages)} |")
    a(f"| ลิงก์ PDF ที่พบ (ไม่ซ้ำ) | **{len(findings)}** |")
    for s in _ORDER:
        if s in by_status:
            a(f"| &nbsp;&nbsp;→ {s} | {len(by_status[s])} |")
    a(f"| เอกสารที่ระบบมีอยู่เดิม | {len(known)} |")
    a("| | |")
    for c in ("สูง", "ปานกลาง", "กำกวม", "ระบุไม่ได้"):
        if c in conf_counts:
            a(f"| ความมั่นใจในการจับคู่หลักสูตร: {c} | {conf_counts[c]} |")
    a(f"| คำขอ HTTP ที่ยิงไปทั้งหมด | {requests_made} |")
    a(f"| หน่วงเวลาระหว่างคำขอ | {delay} วินาที |")
    a("")

    if not hashed:
        a("> ⚠️ รอบนี้ข้ามการคำนวณ sha256 ผลจึงบอกได้แค่ว่าพบไฟล์อะไรบ้าง "
          "ไม่ได้บอกว่าซ้ำกับของเดิมหรือไม่\n")

    # ---- รายละเอียดแยกตามสถานะ ------------------------------------------
    for status in _ORDER:
        items = by_status.get(status)
        if not items:
            continue
        a(f"\n---\n\n## {status} — {len(items)} ไฟล์\n")
        a(f"**สิ่งที่ควรทำต่อ:** {_ACTION[status]}\n")
        for f in items:
            a(f"\n### {f.link.filename}\n")
            a(f"- **URL:** {f.link.url}")
            a(f"- **พบที่หน้า:** {f.link.page_url}")
            a(f"- **หัวเรื่องของหน้า:** {f.link.page_title or '-'}")
            if f.link.link_text:
                a(f"- **ข้อความบนลิงก์:** {f.link.link_text}")
            if f.match.confidence == "กำกวม":
                a(f"- **จับคู่หลักสูตรจากชื่อ:** ⚠️ **กำกวม** — ชื่อตรงกับ "
                  f"{len(f.match.candidates)} ฉบับ แยกจากชื่ออย่างเดียวไม่ได้")
                for c in f.match.candidates:
                    a(f"    - {c}")
                if f.matched_doc:
                    a(f"  → **แต่ sha256 ชี้ชัดว่าเป็นฉบับเดียวกับ** `{f.matched_doc.filename}` "
                      f"({f.matched_doc.course_title})")
            elif f.match.course_title:
                a(f"- **จับคู่หลักสูตร:** {f.match.course_title}  \n"
                  f"  (รหัส `{f.match.course_code}` · ความมั่นใจ **{f.match.confidence}** · คะแนน {f.match.score})")
            else:
                a(f"- **จับคู่หลักสูตร:** ❌ ระบุไม่ได้ (คะแนนสูงสุด {f.match.score})")
            a(f"- **ขนาด:** {_size(f.byte_size)}")
            if f.sha256:
                a(f"- **sha256:** `{f.sha256}`")
            if f.matched_doc:
                a(f"- **เอกสารในระบบที่เกี่ยวข้อง:** `{f.matched_doc.filename}` "
                  f"({f.matched_doc.page_count or '-'} หน้า · sha `{f.matched_doc.sha256[:16]}…`)")
            if f.etag:
                a(f"- **ETag:** `{f.etag}`")
            if f.last_modified:
                a(f"- **Last-Modified:** {f.last_modified}")
            if f.note:
                a(f"- **หมายเหตุ:** {f.note}")

    # ---- ปัญหาระหว่างเดินเว็บ --------------------------------------------
    if errors:
        a(f"\n---\n\n## หน้าที่เข้าไม่ได้ — {len(errors)} รายการ\n")
        a("| URL | สาเหตุ |")
        a("|---|---|")
        for url, why in errors:
            a(f"| {url} | {why} |")

    # ---- เอกสารในระบบที่ไม่พบบนเว็บ --------------------------------------
    found_sha = {f.sha256 for f in findings if f.sha256}
    orphans = [k for k in known if k.sha256 and k.sha256 not in found_sha]
    if orphans:
        a(f"\n---\n\n## เอกสารในระบบที่ไม่พบบนเว็บรอบนี้ — {len(orphans)} รายการ\n")
        a("อาจเป็นเอกสารที่ได้มาทางอื่น หรือเว็บคณะถอดลิงก์ออกแล้ว "
          "**ไม่ได้แปลว่าเอกสารมีปัญหา** แค่บอกว่ารอบนี้ crawler ไม่เจอ\n")
        a("| ไฟล์ | หลักสูตร | หน้า |")
        a("|---|---|---|")
        for k in sorted(orphans, key=lambda x: x.course_title):
            a(f"| `{k.filename}` | {k.course_title or '-'} | {k.page_count or '-'} |")

    # ---- วิธีทำซ้ำ -------------------------------------------------------
    a("\n---\n\n## วิธีสร้างรายงานนี้ใหม่\n")
    a("```bash")
    a("python -m pipeline.crawl.run --inventory <ไฟล์.tsv> --out CRAWL_PDF_DISCOVERY_REPORT.md")
    a("```")
    a("\nไฟล์ TSV สร้างจากฐานข้อมูลแบบอ่านอย่างเดียว ดูคำสั่งใน "
      "`docs/AUTOMATED_INGESTION_ANALYSIS.md`\n")

    path.write_text("\n".join(w), encoding="utf-8")
