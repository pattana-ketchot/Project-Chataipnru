"""
ตั้งรหัสผ่านใหม่ให้บัญชีผู้ดูแล เมื่อเข้าหน้าเว็บไม่ได้แล้ว

ใช้เมื่อไร
----------
ลืมรหัสผ่าน admin และระบบส่งอีเมลรีเซ็ตไม่ได้ (ยังไม่ได้ตั้ง SMTP)
ถ้ายังเข้าหน้าเว็บได้อยู่ ให้ใช้ /admin/profile หรือ /admin/reset-password แทน

วิธีรัน (บนเซิร์ฟเวอร์)
----------------------
    ssh -t -i ~/.ssh/oci.key ubuntu@<เซิร์ฟเวอร์> \
      'docker run --rm -it --network course-advisor-system_default \
         --env-file /home/ubuntu/course-advisor-system/.env \
         -v /home/ubuntu/reset_admin_password.py:/tmp/r.py:ro \
         --entrypoint python course-advisor-system-backend:counter-2569-10-16 \
         /tmp/r.py <อีเมลของบัญชี>'

สิ่งที่สคริปต์นี้ทำ
------------------
1. แสดงบัญชีที่ตรงกับอีเมล (ไม่แสดงค่าแฮช)
2. ถามรหัสผ่านใหม่สองครั้งแบบ **ไม่ขึ้นจอ** เพื่อไม่ให้ติดใน shell history หรือ log
3. สร้างค่าแฮชด้วยฟังก์ชันของระบบเอง (bcrypt_sha256) ไม่ใช่ bcrypt ธรรมดา
   ใช้ผิดแบบจะเข้าสู่ระบบไม่ได้ทั้งที่รหัสถูก
4. อัปเดตรหัสผ่าน ล้างตัวนับที่ล็อกบัญชี และปลดล็อก
5. ยกเลิกเซสชันเดิมทั้งหมดของบัญชีนั้น เพราะโทเคนเก่ายังใช้ได้อยู่หากไม่ยกเลิก
6. ตรวจซ้ำว่ารหัสใหม่ใช้ได้จริงก่อนจบ

สิ่งที่สคริปต์นี้ไม่ทำ
--------------------
ไม่สร้างบัญชีใหม่ · ไม่เปลี่ยน role หรือ status · ไม่แตะบัญชีอื่น
"""
from __future__ import annotations

import getpass
import sys

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402

from app.core.security import SCHEME_CURRENT, hash_password, verify_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

MIN_LEN = 8


def main() -> int:
    if len(sys.argv) != 2:
        print("ใช้: python reset_admin_password.py <อีเมลของบัญชี>")
        return 2
    email = sys.argv[1].strip()

    with SessionLocal() as db:
        row = db.execute(
            text("""SELECT id, email, role, status, is_active, locked_until, failed_login_count
                      FROM public.users WHERE email = :e"""),
            {"e": email},
        ).mappings().first()

        if row is None:
            print("ไม่พบบัญชีอีเมลนี้ — ตรวจตัวสะกดอีกครั้ง")
            print()
            print("บัญชีที่เข้าส่วนผู้ดูแลได้ในระบบตอนนี้:")
            for r in db.execute(text(
                """SELECT email, role, status FROM public.users
                    WHERE role IN ('admin', 'editor') ORDER BY role, email"""
            )).mappings():
                print("   %-40s role=%-7s status=%s" % (r["email"], r["role"], r["status"]))
            return 1

        print("พบบัญชี")
        print("   อีเมล   : %s" % row["email"])
        print("   role    : %s" % row["role"])
        print("   status  : %s" % row["status"])
        print("   ใช้งานอยู่ : %s" % ("ใช่" if row["is_active"] else "ไม่ — ตั้งรหัสใหม่แล้วก็ยังเข้าไม่ได้"))
        print("   ถูกล็อก  : %s" % (row["locked_until"] or "ไม่"))
        print()

        if row["role"] not in ("admin", "editor"):
            print("** หยุด ** บัญชีนี้ไม่ใช่ผู้ดูแล (role=%s)" % row["role"])
            print("สคริปต์นี้มีไว้กู้บัญชีผู้ดูแลเท่านั้น")
            return 1

        pw1 = getpass.getpass("รหัสผ่านใหม่ (พิมพ์แล้วจะไม่ขึ้นจอ): ")
        pw2 = getpass.getpass("พิมพ์ซ้ำอีกครั้ง: ")
        if pw1 != pw2:
            print("รหัสผ่านสองครั้งไม่ตรงกัน — ไม่ได้เปลี่ยนอะไร")
            return 1
        if len(pw1) < MIN_LEN:
            print("รหัสผ่านสั้นเกินไป ต้องยาวอย่างน้อย %d ตัวอักษร — ไม่ได้เปลี่ยนอะไร" % MIN_LEN)
            return 1

        new_hash = hash_password(pw1)

        db.execute(
            text("""UPDATE public.users
                       SET password_hash = :h,
                           password_scheme = :s,
                           failed_login_count = 0,
                           locked_until = NULL,
                           updated_at = now()
                     WHERE id = :id"""),
            {"h": new_hash, "s": SCHEME_CURRENT, "id": row["id"]},
        )

        # โทเคนที่ออกไปก่อนหน้านี้ยังใช้ได้ ถ้าไม่ยกเลิก การตั้งรหัสใหม่จะไม่ตัดคนที่ถืออยู่
        revoked = db.execute(
            text("""UPDATE public.auth_sessions
                       SET revoked_at = now()
                     WHERE user_id = :id AND revoked_at IS NULL"""),
            {"id": row["id"]},
        ).rowcount
        db.commit()

        check = db.execute(
            text("SELECT password_hash, password_scheme FROM public.users WHERE id = :id"),
            {"id": row["id"]},
        ).mappings().first()

    ok = verify_password(pw1, check["password_hash"], check["password_scheme"])
    print()
    print("เปลี่ยนรหัสผ่านแล้ว")
    print("   รูปแบบที่เก็บ : %s" % check["password_scheme"])
    print("   ยกเลิกเซสชันเดิม : %d เซสชัน" % revoked)
    print("   ตรวจซ้ำว่ารหัสใหม่ใช้ได้ : %s" % ("ผ่าน" if ok else "** ไม่ผ่าน — อย่าเพิ่งปิดหน้าต่างนี้ **"))
    if not ok:
        return 1
    print()
    print("ลองเข้าสู่ระบบที่หน้า /admin/login ได้เลย")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
