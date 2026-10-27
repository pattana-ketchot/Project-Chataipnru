"""
ที่เก็บไฟล์ที่ผู้ดูแลอัปโหลด — Phase 4 (มาแทน Supabase Storage)

เก็บไฟล์บนดิสก์ของเซิร์ฟเวอร์ ส่วนข้อมูลประกอบอยู่ใน PostgreSQL ตามที่ออกแบบไว้

หลักความปลอดภัยสามข้อ
--------------------
1. **ชื่อไฟล์ที่ผู้ใช้ส่งมาไม่เคยกลายเป็นชื่อไฟล์บนดิสก์**
   ชื่อบนดิสก์คือ sha256 ของเนื้อไฟล์ ผู้ใช้จึงควบคุมพาธไม่ได้เลย ไม่ว่าจะส่ง
   "../../etc/passwd" หรือชื่อที่มีอักขระพิเศษมาก็ตาม ชื่อเดิมเก็บไว้ในฐานข้อมูล
   เพื่อแสดงผลและตั้งชื่อตอนดาวน์โหลดเท่านั้น

2. **ตรวจชนิดจากเนื้อไฟล์ ไม่ใช่จากนามสกุล**
   นามสกุลเป็นสิ่งที่ผู้ส่งตั้งเอง ไฟล์ .png ที่ข้างในเป็นอย่างอื่นจึงผ่านการตรวจ
   ด้วยนามสกุลได้ง่าย ที่นี่ดูลายเซ็นไบต์แรกด้วย

3. **ตรวจพาธอีกครั้งตอนอ่าน**
   แม้ชื่อบนดิสก์จะมาจากเราเอง แต่ค่าที่เก็บในฐานข้อมูลอาจถูกแก้ภายหลัง
   จึง resolve แล้วยืนยันว่ายังอยู่ใต้โฟลเดอร์ที่กำหนดเสมอ — ด่านเดียวกับที่
   services/document_store.py ใช้อยู่
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

# ชนิดที่ยอมรับ: นามสกุล -> (media type, ลายเซ็นไบต์แรกที่ยอมรับ)
# ลายเซ็นว่าง = ไม่ตรวจไบต์ (ใช้กับ svg ซึ่งเป็นข้อความ)
ALLOWED: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".webp": ("image/webp", (b"RIFF",)),
    ".gif": ("image/gif", (b"GIF87a", b"GIF89a")),
    ".pdf": ("application/pdf", (b"%PDF-",)),
    # .docx คือไฟล์ zip จึงขึ้นต้นด้วย PK
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              (b"PK\x03\x04",)),
    ".txt": ("text/plain; charset=utf-8", ()),
    ".md": ("text/markdown; charset=utf-8", ()),
}

# หมวดไหนรับชนิดไหนได้บ้าง
#
# logo กับ news แสดงบนหน้าเว็บสาธารณะ จึงรับเฉพาะรูป — ไม่รับไฟล์ข้อความหรือเอกสาร
# ที่ตรวจลายเซ็นไบต์ไม่ได้
#
# knowledge เป็นหมวดที่ต้องเข้าสู่ระบบก่อนอ่าน (ของเดิมเป็น bucket แบบ private
# ที่ใช้ signed URL) จึงรับเอกสารได้ด้วย
CATEGORY_TYPES: dict[str, tuple[str, ...]] = {
    "logo": (".png", ".jpg", ".jpeg", ".webp", ".gif"),
    "news": (".png", ".jpg", ".jpeg", ".webp", ".gif"),
    # เอกสารแนบของหลักสูตร — หน้ารายละเอียดหลักสูตรเป็นหน้าสาธารณะและให้ดาวน์โหลดได้
    # เหมือนของเดิมที่อยู่ใน bucket แบบ public
    "course-doc": (".pdf",),
    "knowledge": (".pdf", ".docx", ".txt", ".md"),
}

CATEGORIES = tuple(CATEGORY_TYPES)

# หมวดที่ต้องเข้าสู่ระบบก่อนอ่าน
#
# ของเดิม bucket `knowledge-files` เป็นแบบ private และใช้ signed URL
# การเปิดเป็นสาธารณะตอนย้ายจะเป็นการลดความปลอดภัยโดยไม่ได้ตั้งใจ
PRIVATE_CATEGORIES = ("knowledge",)


def category_of(relative_path: str) -> str:
    """หมวดของไฟล์หนึ่ง อ่านจากส่วนแรกของพาธ"""
    return (relative_path or "").split("/", 1)[0]


def is_private(relative_path: str) -> bool:
    return category_of(relative_path) in PRIVATE_CATEGORIES

# ชื่อไฟล์ที่ปลอดภัยพอจะส่งกลับใน Content-Disposition
_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|\r\n\x00]')


class FileRejected(ValueError):
    """ไฟล์ไม่ผ่านการตรวจ — ข้อความอธิบายให้ผู้ใช้อ่านได้"""


class StorageNotConfigured(RuntimeError):
    """ยังไม่ได้ตั้งค่า UPLOADS_DIR"""


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    original_name: str
    size: int
    media_type: str


def root() -> Path:
    s = get_settings()
    if not s.uploads_dir:
        raise StorageNotConfigured("ยังไม่ได้ตั้งค่า UPLOADS_DIR")
    return Path(s.uploads_dir).resolve()


def safe_display_name(name: str) -> str:
    """
    ชื่อที่ปลอดภัยพอจะใส่ใน Content-Disposition และแสดงบนหน้าเว็บ

    ตัดตัวคั่นพาธและอักขระควบคุมออก เหลือไว้แค่ชื่อฐาน
    """
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    cleaned = _UNSAFE_NAME.sub("_", base)[:120]
    return cleaned or "file"


def extension_of(name: str) -> str:
    ext = Path(safe_display_name(name)).suffix.lower()
    return ext


def check_type(name: str, head: bytes, category: str | None = None) -> str:
    """
    ตรวจว่ารับไฟล์นี้ได้ไหม คืน media type ถ้าผ่าน

    ตรวจสามชั้น — หมวดนี้รับชนิดนี้ไหม · นามสกุลอยู่ในรายการไหม · ลายเซ็นไบต์ตรงไหม
    ต้องผ่านครบทุกชั้น
    """
    ext = extension_of(name)
    allowed_here = CATEGORY_TYPES.get(category, tuple(ALLOWED)) if category else tuple(ALLOWED)
    if ext not in allowed_here:
        raise FileRejected(f"หมวดนี้รับเฉพาะไฟล์ {', '.join(sorted(allowed_here))}")
    media_type, signatures = ALLOWED[ext]
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise FileRejected("เนื้อไฟล์ไม่ตรงกับนามสกุล")
    return media_type


def check_size(size: int) -> None:
    limit = get_settings().upload_max_bytes
    if size <= 0:
        raise FileRejected("ไฟล์ว่าง")
    if size > limit:
        raise FileRejected(f"ไฟล์ใหญ่เกิน {limit // (1024 * 1024)} MB")


def relative_path_for(category: str, digest: str, ext: str) -> str:
    """
    พาธสัมพัทธ์ของไฟล์หนึ่ง — ชื่อมาจาก sha256 ของเนื้อไฟล์เท่านั้น

    แบ่งโฟลเดอร์ย่อยด้วยสองตัวแรกของ hash เพื่อไม่ให้ไฟล์หลายพันไฟล์อยู่โฟลเดอร์เดียว
    """
    if category not in CATEGORIES:
        raise FileRejected(f"หมวดไฟล์ไม่ถูกต้อง: {category}")
    return f"{category}/{digest[:2]}/{digest}{ext}"


def resolve_within_root(relative_path: str) -> Path:
    """
    แปลงพาธสัมพัทธ์เป็นพาธจริง แล้วยืนยันว่ายังอยู่ใต้โฟลเดอร์ที่กำหนด

    ด่านสุดท้ายที่กัน path traversal แม้ค่าที่เก็บในฐานข้อมูลจะถูกแก้ก็ตาม
    """
    base = root()
    candidate = (base / relative_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise FileRejected("พาธไฟล์ไม่ถูกต้อง") from None
    return candidate


def save(category: str, original_name: str, data: bytes) -> StoredFile:
    """
    บันทึกไฟล์หนึ่ง คืนข้อมูลที่ต้องเก็บลงฐานข้อมูล

    ไฟล์เดิมที่เนื้อเหมือนกันทุกไบต์จะใช้ไฟล์เดียวกัน (ชื่อมาจาก hash)
    จึงไม่มีไฟล์ซ้ำและการอัปโหลดซ้ำไม่ทำให้ของเดิมเสีย
    """
    check_size(len(data))
    media_type = check_type(original_name, data[:16], category)
    digest = hashlib.sha256(data).hexdigest()
    relative = relative_path_for(category, digest, extension_of(original_name))

    target = resolve_within_root(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        # เขียนไฟล์ชั่วคราวก่อนแล้วค่อยเปลี่ยนชื่อ กันไฟล์ครึ่ง ๆ ถ้าขัดข้องกลางคัน
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(data)
        temporary.replace(target)

    return StoredFile(relative_path=relative, original_name=safe_display_name(original_name),
                      size=len(data), media_type=media_type)


def open_stored(relative_path: str) -> tuple[Path, str]:
    """คืน (พาธจริง, media type) ถ้าไฟล์มีอยู่จริงและอยู่ในที่ที่ควรอยู่"""
    path = resolve_within_root(relative_path)
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    media_type = ALLOWED.get(path.suffix.lower(), ("application/octet-stream", ()))[0]
    return path, media_type
