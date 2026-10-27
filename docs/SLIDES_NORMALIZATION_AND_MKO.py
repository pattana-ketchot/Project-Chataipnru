# -*- coding: utf-8 -*-
"""สองสไลด์เพิ่มเติมสำหรับวิชาฐานข้อมูลขั้นสูง
  A) การทำให้เป็นบรรทัดฐานและข้อยกเว้นที่ตั้งใจ
  B) schema mko และกลยุทธ์การทำดัชนี
ตัวเลขทุกตัวตรวจจากฐานข้อมูล production เมื่อ 24 กันยายน 2569"""
import io, os

W, H = 1920, 1080
FONT = "'Tahoma','Segoe UI','Leelawadee UI',sans-serif"
INK, MUTED, BODY = "#0F172A", "#64748B", "#334155"
TEAL, TEAL_D = "#12A5BC", "#0B7C90"
CARD_BD, TILE_BG, TILE_BD = "#BFE6EE", "#EAF7FA", "#CBE9F0"
AMBER_BG, AMBER_BD, AMBER_INK = "#FFF8E8", "#F2D9A0", "#8A6212"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


class Slide:
    def __init__(self):
        self.o = io.StringIO()
        o = self.o.write
        o(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
          f'viewBox="0 0 {W} {H}" font-family="{FONT}">\n')
        o('<defs><linearGradient id="hl" x1="0" y1="0" x2="1" y2="0">'
          '<stop offset="0%" stop-color="#22B8D8"/><stop offset="100%" stop-color="#2F6BE0"/>'
          '</linearGradient>'
          '<radialGradient id="bgA" cx="0" cy="0" r="1">'
          '<stop offset="0%" stop-color="#DCE7FA"/><stop offset="100%" stop-color="#ffffff"/>'
          '</radialGradient>'
          '<radialGradient id="bgB" cx="1" cy="1" r="1">'
          '<stop offset="0%" stop-color="#DFF3F8"/><stop offset="100%" stop-color="#ffffff"/>'
          '</radialGradient></defs>\n')
        o(f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n')
        o(f'<rect width="{W}" height="{H}" fill="url(#bgA)" opacity="0.55"/>\n')
        o(f'<rect width="{W}" height="{H}" fill="url(#bgB)" opacity="0.5"/>\n')
        o(f'<rect x="46" y="28" width="{W-92}" height="{H-56}" rx="10" fill="#ffffff" opacity="0.92"/>\n')
        self.text(100, 70, "Database Design", 19, MUTED)
        o(f'<text x="100" y="96" font-size="19" fill="{MUTED}">for the '
          f'<tspan font-weight="bold" fill="{INK}">SCI Advisor System</tspan></text>\n')
        self.text(1820, 70, "4123204", 21, INK, "bold", "end")
        self.text(1820, 96, "Advanced Database", 19, MUTED, anchor="end")

    def text(self, x, y, s, size=17, fill=BODY, weight="normal", anchor="start"):
        self.o.write(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
                     f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>\n')

    def rrect(self, x, y, w, h, r, fill, stroke=None, sw=1.6):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.o.write(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{st}/>\n')

    def title(self, pre, hi, post, sub):
        self.o.write(f'<text x="{W/2}" y="192" text-anchor="middle" font-size="48" '
                     f'font-weight="bold" fill="{INK}">{esc(pre)}'
                     f'<tspan fill="url(#hl)">{esc(hi)}</tspan>{esc(post)}</text>\n')
        self.text(W / 2, 236, sub, 21, MUTED, anchor="middle")

    def badge(self, x, y, n):
        self.o.write(f'<circle cx="{x}" cy="{y}" r="21" fill="{TEAL_D}"/>\n')
        self.text(x, y + 8, str(n), 21, "#ffffff", "bold", "middle")

    def save(self, path):
        self.o.write("</svg>\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.o.getvalue())
        return os.path.getsize(path)


# ==========================================================================
# สไลด์ A — การทำให้เป็นบรรทัดฐาน
# ==========================================================================
A_CARDS = [
    ("ทำตามหลักเต็มที่", "(1NF – 3NF)", [
        "user_profiles ใช้ user_id เป็นทั้งคีย์หลักและ",
        "คีย์นอก บังคับความสัมพันธ์ 1:1 ที่ระดับโครงสร้าง",
        "ไม่ต้องพึ่งการตรวจในโค้ด",
        "",
        "user_requirements และ chat_messages แยกเป็น",
        "ตารางของตัวเอง เพราะหนึ่งคนมีได้หลายเงื่อนไข",
        "และหนึ่งบทสนทนามีได้หลายข้อความ ไม่เก็บเป็น",
        "คอลัมน์ซ้ำ ๆ ในตารางแม่",
    ]),
    ("จงใจเก็บซ้ำ เพื่อความเร็ว", "(Denormalization)", [
        "course_chunks เก็บทั้ง course_id และ",
        "document_id ทั้งที่ document_id สาวไปถึง",
        "course_id ได้อยู่แล้ว",
        "",
        "เหตุผล: ตอนค้นด้วยเวกเตอร์ต้องกรองตาม",
        "หลักสูตรพร้อมกัน การเก็บซ้ำทำให้ไม่ต้อง join",
        "ข้ามตารางทุกคำถาม ความถูกต้องยังถูกบังคับ",
        "ด้วยคีย์นอกทั้งสองเส้นตามเดิม",
    ]),
    ("จงใจไม่ผูกความสัมพันธ์", "(No Foreign Key by Design)", [
        "chat_answer_cache ไม่มีคีย์นอกเลยสักเส้น",
        "ใช้ question_key เป็นคีย์หลักแทน",
        "",
        "เพราะแคชผูกกับคำถาม ไม่ได้ผูกกับคน คำถาม",
        "เดียวกันจากผู้ใช้คนไหนก็ใช้คำตอบเดิมได้",
        "",
        "ลบทั้งตารางทิ้งระบบยังทำงานได้ปกติ แค่ช้าลง",
        "เพราะต้องคิดคำตอบใหม่",
    ]),
]

# บรรทัดคำอธิบายต้องแบ่งเองตรงนี้ ห้ามตัดด้วยจำนวนตัวอักษร
# เพราะภาษาไทยไม่มีช่องว่างระหว่างคำ การตัดตามจำนวนจะหั่นกลางคำ
A_UNIQUE = [
    ("users", "email",
     ["ชนิด citext สมัครด้วยตัวพิมพ์", "ต่างกันแล้วซ้ำไม่ได้"]),
    ("courses", "code",
     ["รหัสหลักสูตรห้ามซ้ำ"]),
    ("course_documents", "course_id + file_sha256",
     ["อัปโหลดไฟล์เดิมเข้าหลักสูตร", "เดิมซ้ำไม่ได้"]),
    ("course_chunks", "document_id + chunk_index",
     ["ประมวลผลเอกสารซ้ำ", "ไม่สร้างท่อนซ้ำ"]),
]

s = Slide()
s.title("การทำให้เป็น", "บรรทัดฐาน", "และข้อยกเว้นที่ตั้งใจ",
        "ทุกการตัดสินใจด้านล่างนี้ตรวจได้จากโครงสร้างจริงของฐานข้อมูล ไม่ใช่การอธิบายย้อนหลัง")

CY, CH, GAP, X0 = 288, 400, 28, 70
CW = (W - 2 * X0 - GAP * 2) // 3
for i, (th, en, lines) in enumerate(A_CARDS):
    x = X0 + i * (CW + GAP)
    s.rrect(x, CY, CW, CH, 18, "#ffffff", CARD_BD, 1.8)
    s.badge(x + 52, CY + 54, i + 1)
    s.text(x + 88, CY + 48, th, 22, INK, "bold")
    s.text(x + 88, CY + 74, en, 15, TEAL_D)
    for j, ln in enumerate(lines):
        if ln:
            s.text(x + 32, CY + 128 + j * 29, ln, 17.5, BODY)

UY, UH = 730, 200
s.rrect(X0, UY, W - 2 * X0, UH, 16, TILE_BG, TILE_BD, 1.6)
s.text(X0 + 32, UY + 44, "คีย์ห้ามซ้ำ (UNIQUE) — กันข้อมูลซ้ำที่ระดับฐานข้อมูล ไม่ใช่ที่โค้ด",
       21, TEAL_D, "bold")
UW = (W - 2 * X0 - 64 - 3 * 20) // 4
for i, (tbl, cols, why) in enumerate(A_UNIQUE):
    x = X0 + 32 + i * (UW + 20)
    s.rrect(x, UY + 62, UW, 112, 12, "#ffffff", TILE_BD, 1.4)
    s.text(x + 18, UY + 90, tbl, 17, TEAL_D, "bold")
    s.text(x + 18, UY + 115, cols, 16.5, INK, "bold")
    for j, ln in enumerate(why):
        s.text(x + 18, UY + 142 + j * 20, ln, 14.5, MUTED)

pa = r"D:\workspace\course-advisor-system-mko2\docs\SLIDE_NORMALIZATION.svg"
print("A saved", s.save(pa), "bytes  cards bottom =", CY + CH, " unique top =", UY)

# ==========================================================================
# สไลด์ B — schema mko และดัชนี
# ==========================================================================
s = Slide()
s.title("schema ", "mko", " และกลยุทธ์การทำดัชนี",
        "ส่วนที่ทำให้ระบบตอบคำถามเชิงโครงสร้างได้ และค้นเนื้อหา 9,039 ท่อนได้ในระดับมิลลิวินาที")

PY, PH, PX, PW = 288, 560, 70, 880
GAPX = 20

# ---- ซ้าย: schema mko ----
s.rrect(PX, PY, PW, PH, 18, "#ffffff", CARD_BD, 1.8)
s.badge(PX + 52, PY + 54, 1)
s.text(PX + 88, PY + 48, "schema mko — ข้อมูลที่สกัดพร้อมหลักฐาน", 23, INK, "bold")
s.text(PX + 88, PY + 74, "18 ตาราง · 6 วิว แยกจาก schema public", 16, TEAL_D)
for j, ln in enumerate([
        "เก็บค่าที่สกัดจากเอกสาร มคอ.2 ทีละค่า พร้อมชี้ว่าค่านั้นมาจากเอกสารไหน",
        "หน้าไหน และผ่านการตรวจทานแล้วหรือยัง",
        "",
        "โซ่หลักฐาน:  field_values → evidence → course_documents → courses",
        "ทำให้ทุกค่าที่ระบบใช้ตอบ สาวกลับไปถึงไฟล์ต้นฉบับและเลขหน้าได้",
        "",
        "ค่าจะถูกนำไปใช้ตอบก็ต่อเมื่อสถานะเป็น verified แล้วเท่านั้น",
        "วิว v_live_values ทำหน้าที่กรองชั้นนี้ให้",
]):
    if ln:
        s.text(PX + 32, PY + 128 + j * 30, ln, 18, BODY)

for i, (num, lab) in enumerate([("787", "หลักฐาน (evidence)"),
                                ("403", "ค่าที่สกัดได้"),
                                ("103", "ค่าที่เผยแพร่แล้ว")]):
    tw = (PW - 64 - 40) // 3
    x = PX + 32 + i * (tw + 20)
    s.rrect(x, PY + 402, tw, 96, 12, TILE_BG, TILE_BD, 1.4)
    s.text(x + tw / 2, PY + 448, num, 34, TEAL_D, "bold", "middle")
    s.text(x + tw / 2, PY + 476, lab, 15.5, MUTED, anchor="middle")

# ---- ขวา: ดัชนี ----
QX = PX + PW + GAPX
s.rrect(QX, PY, PW, PH, 18, "#ffffff", CARD_BD, 1.8)
s.badge(QX + 52, PY + 54, 2)
s.text(QX + 88, PY + 48, "กลยุทธ์การทำดัชนี (Index)", 23, INK, "bold")
s.text(QX + 88, PY + 74, "ดัชนีทั้งหมด 52 ตัว = ประกาศเอง 15 + เกิดจาก PK/UNIQUE 37", 16, TEAL_D)
for j, ln in enumerate([
        "ดัชนีสำคัญที่สุดคือดัชนีเวกเตอร์บน course_chunks.embedding",
        "ใช้ชนิด ivfflat ซึ่งค้นแบบประมาณ เร็วกว่าไล่เทียบทุกแถวมาก",
]):
    s.text(QX + 32, PY + 128 + j * 30, ln, 18, BODY)

s.rrect(QX + 32, PY + 200, PW - 64, 66, 10, "#F5F7FA", "#DDE3EC", 1.4)
s.o.write(f'<text x="{QX+50}" y="{PY+228}" font-size="15.5" fill="#1F3D6B" '
          f'font-family="Consolas,monospace">CREATE INDEX idx_course_chunks_embedding</text>\n')
s.o.write(f'<text x="{QX+50}" y="{PY+252}" font-size="15.5" fill="#1F3D6B" '
          f'font-family="Consolas,monospace">  ON course_chunks USING ivfflat (embedding vector_cosine_ops)</text>\n')

s.rrect(QX + 32, PY + 288, PW - 64, 210, 12, AMBER_BG, AMBER_BD, 1.5)
s.text(QX + 54, PY + 324, "บทเรียนจากการใช้งานจริง", 19, AMBER_INK, "bold")
for j, ln in enumerate([
        "ดัชนี ivfflat เลือกผู้เข้าชิงจากดัชนีก่อน แล้วค่อยกรองด้วย WHERE",
        "พอกรองให้เหลือหลักสูตรเดียว ผู้เข้าชิงที่ดัชนีเลือกมาอาจไม่มีของ",
        "หลักสูตรนั้นเลย ผลคือคืนแถวว่างโดยไม่แจ้งข้อผิดพลาด",
        "",
        "ทดสอบแล้วได้ 0 แถว ทั้งที่หลักสูตรนั้นมีข้อความอยู่จริง 422 ท่อน",
        "แก้โดยปิดการใช้ดัชนีเฉพาะกรณีที่กรองแล้วเหลือน้อย",
]):
    if ln:
        s.text(QX + 54, PY + 356 + j * 26, ln, 16, "#6B5116")

FY = 886
s.rrect(X0, FY, W - 2 * X0, 90, 16, TILE_BG, TILE_BD, 1.6)
s.o.write(f'<circle cx="{X0+46}" cy="{FY+45}" r="17" fill="{TEAL_D}"/>\n')
s.o.write(f'<path d="M{X0+39},{FY+45} l5,5 l10,-11" fill="none" stroke="#ffffff" '
          'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>\n')
s.o.write(f'<line x1="{X0+80}" y1="{FY+22}" x2="{X0+80}" y2="{FY+68}" '
          f'stroke="{TILE_BD}" stroke-width="2"/>\n')
s.text(X0 + 104, FY + 56,
       "สองส่วนนี้ทำงานคู่กัน — ดัชนีเวกเตอร์หาว่าเนื้อหาอยู่ตรงไหน ส่วน schema mko ตอบว่าค่านั้นคืออะไรและมาจากเอกสารหน้าไหน",
       18, BODY)

pb = r"D:\workspace\course-advisor-system-mko2\docs\SLIDE_MKO_AND_INDEX.svg"
print("B saved", s.save(pb), "bytes  panel bottom =", PY + PH, " footer top =", FY)
