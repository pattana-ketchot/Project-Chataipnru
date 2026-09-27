"""
ที่เก็บไฟล์ที่ crawler โหลดมารออนุมัติ — ชั้นที่แยก "สัญญาของ API" ออกจาก "ที่เก็บไฟล์จริง"

กติกาเดียวกับ services/document_store.py ทั้งชุด ต่างกันสามเรื่อง
------------------------------------------------------------------
1. ไฟล์ในคิวยังไม่ได้อยู่ในคลังความรู้ จึงไม่มีแถวใน course_documents ให้เทียบ
   ลายนิ้วมือที่ใช้เทียบมาจาก mko.crawl_sources.file_sha256
2. ที่อยู่ไฟล์มาจาก mko.crawl_sources.staging_path ซึ่ง crawler เขียนไว้ ไม่ใช่จาก
   การสแกนโฟลเดอร์ เพราะไฟล์ในคิวเปลี่ยนบ่อยกว่าเอกสารในคลังมาก การทำดัชนีครั้งเดียว
   ต่อโปรเซสแบบ document_store จะทำให้ไฟล์ที่ crawl มาเมื่อสักครู่หาไม่เจอจนกว่าจะ
   restart backend
3. ตรวจลายเซ็น %PDF- ด้วย เพราะไฟล์ในคิวยังไม่ผ่านการนำเข้า จึงยังไม่เคยมีอะไรอ่าน
   เนื้อมันเลย ต่างจากเอกสารในคลังที่ผ่าน pipeline มาแล้ว

ความปลอดภัย
-----------
ไม่มีจุดใดรับ path จากผู้ใช้ ผู้ใช้ส่งมาได้เพียง crawl_source_id ที่เป็น UUID
path มาจากฐานข้อมูล และก่อนส่งไฟล์ยังตรวจสามชั้น

    1. resolve() แล้วต้องอยู่ใต้ CRAWL_STAGING_DIR จริง  ← กัน ../ และ symlink
    2. sha256 ต้องตรงกับที่ฐานข้อมูลบันทึกไว้              ← กันไฟล์ถูกสลับหลัง crawl
    3. ห้าไบต์แรกต้องเป็น %PDF-                          ← กันไฟล์ที่ไม่ใช่ PDF

ผิดข้อใดข้อหนึ่งคืน None ให้ route ตอบ 404 ข้อความเดียวกันทุกกรณี รายละเอียดอยู่ใน log

ข้อ 1 สำคัญเป็นพิเศษ: staging_path เขียนโดย crawler ซึ่งรันคนละโปรเซส (และใน Phase 3B
จะรันคนละคอนเทนเนอร์) ถ้าวันหนึ่งมีใครแก้ค่าในคอลัมน์นั้นได้ ที่นี่ต้องไม่กลายเป็น
ช่องอ่านไฟล์ใดก็ได้บนเครื่อง

ไม่ตั้งค่า CRAWL_STAGING_DIR = ปิดการเปิดดูไฟล์
----------------------------------------------
ค่าเริ่มต้นเป็นสตริงว่าง ระบบจะบอกว่าหาไฟล์ไม่พบเสมอ ส่วนคิวและการอนุมัติยังทำงานได้
ใช้เป็นสวิตช์ปิดได้ทันทีโดยไม่ต้อง deploy โค้ดใหม่ — หลักเดียวกับ DOCUMENTS_DIR
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.services.document_store import sha256_of

logger = logging.getLogger("course_advisor")
settings = get_settings()

PDF_SIGNATURE = b"%PDF-"


@dataclass(frozen=True)
class StagedFile:
    """ไฟล์ที่ผ่านการตรวจแล้วและพร้อมส่งออก"""

    path: Path
    filename: str
    media_type: str = "application/pdf"


class StagingStore:
    def __init__(self, root: str | Path | None = None) -> None:
        raw = str(root if root is not None else settings.crawl_staging_dir).strip()
        self._root = Path(raw).resolve() if raw else None

    @property
    def enabled(self) -> bool:
        return self._root is not None and self._root.is_dir()

    def open(self, crawl_source_id, staging_path: str | None, sha256: str | None) -> StagedFile | None:
        """คืนไฟล์ในคิวที่ตรงกับลายนิ้วมือนี้ หรือ None ถ้าไม่มี/ไม่ตรง/ไม่ปลอดภัย"""
        if not self.enabled or not staging_path or not sha256:
            return None

        root = self._root
        assert root is not None  # enabled รับประกันแล้ว

        try:
            resolved = Path(staging_path).resolve()
        except OSError:
            logger.warning("แปลงที่อยู่ไฟล์ในคิวไม่ได้ (crawl_source_id=%s)", crawl_source_id)
            return None

        # ชั้น 1 — ต้องอยู่ใต้โฟลเดอร์ที่อนุญาตจริง หลัง resolve แล้วเท่านั้น
        #
        # resolve() คลาย symlink และ .. ให้เรียบร้อยก่อน จึงตรวจของจริงไม่ใช่ของที่เขียนไว้
        # ถ้าตรวจก่อน resolve จะหลุดได้ด้วย staging/../../etc/passwd หรือด้วย symlink
        # ที่ชี้ออกนอกโฟลเดอร์
        if not resolved.is_relative_to(root):
            logger.warning("ปฏิเสธไฟล์ที่อยู่นอกโฟลเดอร์ staging (crawl_source_id=%s)", crawl_source_id)
            return None
        if not resolved.is_file():
            logger.warning("ไม่พบไฟล์ในคิวที่ฐานข้อมูลอ้างถึง (crawl_source_id=%s)", crawl_source_id)
            return None

        # ชั้น 2 — เนื้อไฟล์ต้องตรงกับที่ crawler บันทึกไว้
        try:
            if sha256_of(resolved) != sha256:
                logger.warning("ลายนิ้วมือไฟล์ในคิวไม่ตรงกับฐานข้อมูล (crawl_source_id=%s)", crawl_source_id)
                return None
        except OSError:
            logger.warning("อ่านไฟล์ในคิวไม่ได้ (crawl_source_id=%s)", crawl_source_id)
            return None

        # ชั้น 3 — ต้องเป็น PDF จริง
        try:
            with resolved.open("rb") as handle:
                if handle.read(len(PDF_SIGNATURE)) != PDF_SIGNATURE:
                    logger.warning("ไฟล์ในคิวไม่ใช่ PDF (crawl_source_id=%s)", crawl_source_id)
                    return None
        except OSError:
            logger.warning("อ่านหัวไฟล์ในคิวไม่ได้ (crawl_source_id=%s)", crawl_source_id)
            return None

        # ชื่อไฟล์ที่ส่งให้เบราว์เซอร์ — ใช้ชื่อในโฟลเดอร์ ไม่ใช่ค่าจากผู้ใช้
        return StagedFile(path=resolved, filename=resolved.name)


_store: StagingStore | None = None


def get_staging_store() -> StagingStore:
    """ตัวเดียวต่อโปรเซส"""
    global _store
    if _store is None:
        _store = StagingStore()
    return _store
