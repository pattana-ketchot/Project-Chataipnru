"""
ที่เก็บไฟล์เอกสารต้นฉบับ — ชั้นที่แยก "สัญญาของ API" ออกจาก "ที่เก็บไฟล์จริง"

ทำไมต้องมีชั้นนี้
----------------
เส้นทาง /documents/{id}/pdf ต้องคงเดิมตลอด แม้วันหนึ่งจะย้ายไฟล์จากดิสก์ไปเก็บใน
ฐานข้อมูล (ROUND 2 ของ docs/PDF_ENDPOINT_PRE_IMPLEMENT_REPORT.md) การเปลี่ยนที่เก็บ
จึงต้องแตะแค่ไฟล์นี้ไฟล์เดียว ไม่ใช่ route และไม่ใช่หน้าเว็บ

หาไฟล์ด้วยลายนิ้วมือ ไม่ใช่ด้วย path
------------------------------------
คอลัมน์ course_documents.storage_path บันทึกที่อยู่บนเครื่องที่นำเข้า ซึ่งปนกันสองรูปแบบ
(Windows 18 แถว / POSIX 13 แถว) และไม่ตรงกับที่เก็บบนเซิร์ฟเวอร์ จึงใช้ไม่ได้
ที่นี่จึงทำดัชนี sha256 -> path จากการสแกนโฟลเดอร์ แล้วจับคู่กับ file_sha256 ของแถวใน
ฐานข้อมูล เป็นกติกาเดียวกับ pipeline/mko/run.py::local_files() ที่ใช้อยู่แล้ว
ผลพลอยได้คือย้ายหรือเปลี่ยนชื่อไฟล์แล้วระบบยังหาเจอ ตราบใดที่เนื้อไฟล์ไม่เปลี่ยน

ความปลอดภัย
-----------
ไม่มีจุดใดรับ path จากผู้ใช้ ผู้ใช้ส่งมาได้เพียง document_id ที่เป็น UUID เท่านั้น
path ทุกเส้นมาจากการสแกนโฟลเดอร์ที่ผู้ดูแลตั้งไว้ และก่อนส่งไฟล์ยังตรวจซ้ำสองชั้น
คืออยู่ใต้ DOCUMENTS_DIR จริง และ sha256 ตรงกับที่ฐานข้อมูลบันทึกไว้

ไม่ตั้งค่า DOCUMENTS_DIR = ปิดฟีเจอร์
-----------------------------------
ค่าเริ่มต้นเป็นสตริงว่าง ระบบจะบอกว่าหาเอกสารไม่พบเสมอ ใช้เป็นสวิตช์ปิดฟีเจอร์ได้ทันที
โดยไม่ต้อง deploy โค้ดใหม่ (ถอด environment ออกแล้ว recreate backend อย่างเดียว)
"""
from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger("course_advisor")
settings = get_settings()

# อ่านทีละก้อนแทนการอ่านทั้งไฟล์เข้าหน่วยความจำ เอกสารบางเล่มใหญ่หลายสิบเมกะไบต์
_CHUNK = 1 << 20


@dataclass(frozen=True)
class StoredDocument:
    """ไฟล์ที่พร้อมส่งออก — route ใช้แค่สามค่านี้ ไม่รู้ว่ามาจากดิสก์หรือฐานข้อมูล"""

    path: Path
    filename: str
    media_type: str = "application/pdf"


class DocumentStore(Protocol):
    def open(self, document_id, filename: str, sha256: str) -> StoredDocument | None:
        """คืนไฟล์ที่ตรงกับลายนิ้วมือนี้ หรือ None ถ้าไม่มี/ไม่ตรง"""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


class FilesystemDocumentStore:
    """
    อ่านไฟล์จากโฟลเดอร์กลางบนเซิร์ฟเวอร์ (ROUND 1)

    ทำดัชนีครั้งเดียวต่อโปรเซสแล้วใช้ซ้ำ เพราะการสแกนต้องอ่านทุกไฟล์เพื่อคำนวณ sha256
    ซึ่งกับชุดปัจจุบัน (30 ไฟล์ 85 MB) ใช้เวลาไม่ถึงวินาที แต่ไม่ควรทำทุกคำขอ
    ผลที่ตามมาที่ยอมรับแล้ว: ไฟล์ที่เพิ่มเข้ามาหลังโปรเซสเริ่มจะยังไม่ถูกเห็นจนกว่าจะ
    restart backend ซึ่งเกิดไม่บ่อยเพราะเอกสารหลักสูตรแทบไม่เปลี่ยน
    """

    def __init__(self, root: str | Path | None = None) -> None:
        raw = str(root if root is not None else settings.documents_dir).strip()
        self._root = Path(raw).resolve() if raw else None
        self._index: dict[str, Path] | None = None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._root is not None and self._root.is_dir()

    def _build_index(self) -> dict[str, Path]:
        index: dict[str, Path] = {}
        if self._root is None:
            return index
        # เฉพาะ .pdf — ไฟล์ข้อความอย่าง ph_web.txt ไม่ใช่เอกสารที่เปิดผ่านเส้นทางนี้
        for path in sorted(self._root.rglob("*.pdf")):
            if not path.is_file():
                continue
            try:
                index.setdefault(sha256_of(path), path)
            except OSError:
                logger.warning("อ่านไฟล์เอกสารไม่ได้ ข้ามไฟล์นี้")
        logger.info("ดัชนีเอกสารต้นฉบับ: %d ไฟล์", len(index))
        return index

    def _files(self) -> dict[str, Path]:
        if self._index is None:
            with self._lock:
                if self._index is None:
                    self._index = self._build_index()
        return self._index

    def open(self, document_id, filename: str, sha256: str) -> StoredDocument | None:
        if not self.enabled:
            return None
        path = self._files().get(sha256)
        if path is None:
            return None
        # ตรวจซ้ำสองชั้นก่อนส่งออก แม้ path จะมาจากดัชนีของเราเองก็ตาม
        #
        # ชั้นแรกกันกรณีมี symlink หรือการตั้งค่าผิดพาให้หลุดออกนอกโฟลเดอร์ที่อนุญาต
        # ชั้นที่สองกันกรณีไฟล์ถูกสลับหรือเสียหายหลังสร้างดัชนี — ถ้าไม่ตรงแปลว่าไฟล์นี้
        # ไม่ใช่เอกสารที่ระบบใช้สกัดข้อมูล จึงไม่ควรส่งให้ผู้ใช้ในนามของเอกสารนั้น
        resolved = path.resolve()
        if self._root is None or not resolved.is_relative_to(self._root):
            logger.warning("ปฏิเสธไฟล์ที่อยู่นอกโฟลเดอร์เอกสาร (document_id=%s)", document_id)
            return None
        try:
            if sha256_of(resolved) != sha256:
                logger.warning("ลายนิ้วมือไฟล์ไม่ตรงกับฐานข้อมูล (document_id=%s)", document_id)
                return None
        except OSError:
            logger.warning("อ่านไฟล์เอกสารไม่ได้ตอนส่งออก (document_id=%s)", document_id)
            return None
        return StoredDocument(path=resolved, filename=filename)


_store: FilesystemDocumentStore | None = None


def get_document_store() -> FilesystemDocumentStore:
    """ตัวเดียวต่อโปรเซส เพื่อให้ดัชนีถูกสร้างครั้งเดียว — ROUND 2 สลับคลาสที่นี่จุดเดียว"""
    global _store
    if _store is None:
        _store = FilesystemDocumentStore()
    return _store
