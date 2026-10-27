"""
ย้ายบัญชีผู้ใช้จาก Supabase Auth มาที่ public.users — Phase 4

    python -m pipeline.web.import_accounts --dry-run
    python -m pipeline.web.import_accounts --apply

**ผู้ใช้ไม่ต้องตั้งรหัสผ่านใหม่**
----------------------------
รายงานรุ่นก่อนเขียนว่า "รหัสผ่านย้ายไม่ได้" ซึ่ง **ผิด** ตรวจแล้วพบว่า

    Supabase Auth (GoTrue) เก็บ bcrypt ของรหัสผ่านไว้ที่ auth.users.encrypted_password
    ระบบนี้เก็บ bcrypt(base64(sha256(pw))) ไว้ที่ public.users.password_hash

ต่างกันที่ **รูปแบบ** ไม่ใช่ว่าย้ายไม่ได้ — คัดลอก hash มาแล้วทำเครื่องหมายว่าเป็นรูปแบบ
`bcrypt` ระบบจะตรวจด้วยรูปแบบนั้น แล้ว **อัปเกรดเป็นรูปแบบของระบบนี้เองในครั้งแรก
ที่เจ้าของเข้าสู่ระบบสำเร็จ** (ดู routes/auth.py) โดยเจ้าของไม่ต้องทำอะไรเลย

สิ่งที่ย้ายและไม่ย้าย
--------------------
ย้าย      อีเมล · ชื่อ · bcrypt hash · เวลายืนยันอีเมล · role/status จาก public.user_profiles
ไม่ย้าย   เซสชันที่ยังเปิดอยู่ (ทุกคนต้องเข้าสู่ระบบใหม่หนึ่งครั้ง) · ผู้ใช้ที่ไม่มีรหัสผ่าน
          (สมัครด้วย OAuth) ซึ่งจะถูกข้ามและรายงานไว้

ความปลอดภัย
-----------
- **ไม่พิมพ์ hash อีเมล หรือ connection string ออกมาเลย** รายงานเป็นจำนวนและสถานะเท่านั้น
- ผู้ใช้ที่มีอยู่แล้วในปลายทาง **ไม่ถูกเขียนทับรหัสผ่าน** กันการย้อนรหัสกลับเป็นของเก่า
- role/status ที่ผู้ดูแลตั้งไว้ในปลายทางแล้ว **ไม่ถูกเขียนทับ**
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# อ่านจาก auth.users ของ Supabase ตรง ๆ — ต้องใช้ connection string ของฐานข้อมูล
# ไม่ใช่ anon key เพราะ schema auth ไม่เปิดให้ PostgREST
SELECT_ACCOUNTS = """
    select u.id,
           lower(u.email) as email,
           u.encrypted_password,
           u.email_confirmed_at,
           u.raw_user_meta_data->>'full_name' as full_name,
           p.role   as profile_role,
           p.status as profile_status
      from auth.users u
      left join public.user_profiles p on p.user_id = u.id
     where u.email is not null
     order by u.created_at
"""

UPSERT = """
    insert into public.users
      (email, password_hash, password_scheme, full_name, role, status,
       email_verified_at, supabase_user_id, is_active)
    values (%(email)s, %(password_hash)s, 'bcrypt', %(full_name)s, %(role)s, %(status)s,
            %(email_verified_at)s, %(supabase_user_id)s, true)
    on conflict (email) do update set
      -- เติมเฉพาะสิ่งที่ปลายทางยังไม่มี · ไม่เขียนทับของที่ผู้ดูแลตั้งไว้แล้ว
      full_name        = coalesce(public.users.full_name, excluded.full_name),
      supabase_user_id = coalesce(public.users.supabase_user_id, excluded.supabase_user_id),
      email_verified_at = coalesce(public.users.email_verified_at, excluded.email_verified_at)
    returning (xmax = 0) as inserted
"""

VALID_ROLES = ("admin", "editor", "user")
VALID_STATUS = ("pending", "approved", "rejected")


def normalise(row: dict) -> dict | None:
    """
    แปลงแถวจากต้นทางเป็นค่าที่ปลายทางรับได้ — คืน None ถ้าย้ายไม่ได้

    role/status ที่ไม่รู้จักถูกปรับเป็นค่าที่ปลอดภัยที่สุด ไม่ใช่ปล่อยให้ CHECK ล้มทั้งชุด
    """
    if not row.get("encrypted_password"):
        return None  # สมัครด้วย OAuth หรือยังไม่เคยตั้งรหัสผ่าน

    role = row.get("profile_role") or "user"
    status = row.get("profile_status") or "pending"
    return {
        "email": row["email"],
        "password_hash": row["encrypted_password"],
        "full_name": row.get("full_name"),
        # ค่าที่ไม่รู้จักถูกลดเป็นสิทธิ์ต่ำสุด — ให้สิทธิ์เกินอันตรายกว่าให้น้อยไป
        "role": role if role in VALID_ROLES else "user",
        "status": status if status in VALID_STATUS else "pending",
        "email_verified_at": row.get("email_confirmed_at"),
        "supabase_user_id": str(row["id"]),
    }


def summarise(rows: list[dict]) -> dict:
    """นับอย่างเดียว ไม่คืนอีเมลหรือ hash ออกมา"""
    prepared = [normalise(r) for r in rows]
    usable = [p for p in prepared if p]
    counts: dict[str, int] = {}
    for p in usable:
        key = f"{p['role']}/{p['status']}"
        counts[key] = counts.get(key, 0) + 1
    return {
        "ทั้งหมด": len(rows),
        "ย้ายได้": len(usable),
        "ข้าม (ไม่มีรหัสผ่าน)": len(rows) - len(usable),
        "แยกตามสิทธิ์": counts,
    }


def run(source_dsn: str, dest_dsn: str, apply: bool) -> int:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(source_dsn, row_factory=dict_row) as src:
        try:
            rows = src.execute(SELECT_ACCOUNTS).fetchall()
        except psycopg.errors.InsufficientPrivilege:
            print("อ่าน auth.users ไม่ได้ — ต้องใช้ connection string ที่มีสิทธิ์อ่าน schema auth")
            return 1

    report = summarise(rows)
    for key, value in report.items():
        print(f"  {key}: {value}")

    if not apply:
        print("\n-- โหมดลองเท่านั้น ไม่ได้เขียนอะไร ใช้ --apply เมื่อพร้อม --")
        return 0

    inserted = updated = 0
    with psycopg.connect(dest_dsn, row_factory=dict_row) as dest:
        with dest.transaction():
            for row in rows:
                prepared = normalise(row)
                if prepared is None:
                    continue
                result = dest.execute(UPSERT, prepared).fetchone()
                if result and result["inserted"]:
                    inserted += 1
                else:
                    updated += 1

    print(f"\nเพิ่มบัญชีใหม่ {inserted} · อัปเดตบัญชีเดิม {updated}")
    print("บัญชีที่ย้ายมาใช้รหัสผ่านเดิมได้ทันที และจะถูกอัปเกรดรูปแบบเองตอนเข้าสู่ระบบครั้งแรก")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ย้ายบัญชีจาก Supabase Auth")
    parser.add_argument("--apply", action="store_true", help="เขียนจริง (ค่าตั้งต้นคือลองเท่านั้น)")
    parser.add_argument("--dry-run", action="store_true", help="ลองเท่านั้น (ค่าตั้งต้น)")
    args = parser.parse_args()

    source = os.environ.get("SUPABASE_DB_URL", "")
    dest = os.environ.get("DATABASE_URL", "")
    if not source or not dest:
        print("ต้องตั้ง SUPABASE_DB_URL และ DATABASE_URL ก่อน (ไม่ต้องใส่ในคำสั่ง)")
        return 2

    return run(source, dest.replace("postgresql+psycopg://", "postgresql://"),
               apply=args.apply and not args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
