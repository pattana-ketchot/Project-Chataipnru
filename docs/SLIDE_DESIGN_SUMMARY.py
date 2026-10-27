# -*- coding: utf-8 -*-
"""สไลด์ 'สรุปภาพรวมและผลการออกแบบฐานข้อมูล' ฉบับแก้ให้ตรงกับระบบจริง
ตัวเลขทุกตัวตรวจจากฐานข้อมูล production เมื่อ 24 กันยายน 2569"""
import io, os

W, H = 1920, 1080
FONT = "'Tahoma','Segoe UI','Leelawadee UI',sans-serif"

INK     = "#0F172A"
MUTED   = "#64748B"
BODY    = "#334155"
TEAL    = "#12A5BC"
TEAL_D  = "#0B7C90"
CARD_BD = "#BFE6EE"
TILE_BG = "#EAF7FA"
TILE_BD = "#CBE9F0"

out = io.StringIO()


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def text(x, y, s, size=17, fill=BODY, weight="normal", anchor="start"):
    out.write(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
              f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>\n')


def rrect(x, y, w, h, r, fill, stroke=None, sw=1.6):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    out.write(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{st}/>\n')


def icon(kind, cx, cy, color="#ffffff"):
    s = f'fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
    g = out.write
    if kind == "db":
        g(f'<ellipse cx="{cx}" cy="{cy-9}" rx="12" ry="5" {s}/>\n')
        g(f'<path d="M{cx-12},{cy-9} V{cy+9} a12,5 0 0 0 24,0 V{cy-9}" {s}/>\n')
        g(f'<path d="M{cx-12},{cy} a12,5 0 0 0 24,0" {s}/>\n')
    elif kind == "search":
        g(f'<circle cx="{cx-2}" cy="{cy-2}" r="9" {s}/>\n')
        g(f'<path d="M{cx+5},{cy+5} L{cx+12},{cy+12}" {s}/>\n')
    elif kind == "warn":
        g(f'<path d="M{cx},{cy-11} l12,20 h-24 z" {s}/>\n')
        g(f'<path d="M{cx},{cy-3} v5" {s}/>\n')
        g(f'<circle cx="{cx}" cy="{cy+6}" r="1.4" fill="{color}"/>\n')


# ---- เนื้อหา --------------------------------------------------------------
STATS = [
    ("28",    "ตารางใน PostgreSQL", "public 10 + mko 18"),
    ("6",     "วิว (View)",          "สำหรับอ่านข้อมูลที่ผ่านการตรวจ"),
    ("83",    "คอลัมน์",             "ใน schema public"),
    ("11",    "คีย์นอก",             "ใน schema public"),
    ("9,039", "ท่อนข้อความ",         "พร้อมเวกเตอร์ 1024 มิติ"),
    ("4,129", "หน้าเอกสาร",          "จาก มคอ.2 จำนวน 31 ฉบับ"),
]

CARDS = [
    dict(ic="db", th="โครงสร้างที่ออกแบบให้ย้อนตรวจได้", en="(Traceable by Design)",
         body=["ระบบใช้ PostgreSQL เป็นฐานข้อมูลหลักสำหรับเก็บทั้งข้อมูล",
               "หลักสูตรและเวกเตอร์ โดยมี Supabase แยกต่างหากสำหรับ",
               "จัดการเนื้อหาหน้าเว็บ ไม่ได้เชื่อมต่อกันโดยตรง",
               "",
               "ตารางผูกกันด้วยคีย์นอก 11 เส้น ทำให้คำตอบที่ดึงจาก",
               "เอกสารทุกคำตอบ อ้างอิงกลับไปยังไฟล์ต้นฉบับและ",
               "เลขหน้าได้จริง"]),

    dict(ic="search", th="ค้นด้วยความหมาย ตอบด้วย SQL", en="(Semantic + Structured)",
         body=["เก็บเนื้อหาเป็นเวกเตอร์ 1024 มิติพร้อมดัชนี ivfflat รองรับ",
               "การค้นตามความหมาย (Semantic Search) ผู้ใช้จึงไม่ต้อง",
               "พิมพ์คำให้ตรงกับที่เขียนไว้ในเอกสาร",
               "",
               "ส่วนคำถามเชิงโครงสร้าง เช่น จำนวนหน่วยกิตหรือชื่อ",
               "ปริญญา ตอบจาก schema mko ด้วย SQL ซึ่งเก็บค่าที่",
               "สกัดแล้วพร้อมหลักฐานและสถานะการตรวจทาน"]),

    dict(ic="warn", th="ข้อจำกัดตามสภาพจริง", en="(Current Limitations)",
         body=["ยังมีสี่ข้อที่ต้องพัฒนาต่อ — คำย่อและคำเรียกติดปากยัง",
               "พึ่งตารางที่เขียนด้วยมือ ชื่อหลักสูตรที่ซ้ำกันหลายปีการ",
               "ศึกษายังแยกไม่เด็ดขาด การเรียบเรียงคำตอบพึ่งโมเดล",
               "ภาษาจากผู้ให้บริการภายนอก และการนำเข้าเอกสารใหม่",
               "ยังต้องทำด้วยคน",
               "",
               "ทั้งหมดนี้คือสถานะความสามารถจริง ไม่ใช่เป้าหมายที่ตั้งไว้"]),
]

# ---- เริ่มวาด -------------------------------------------------------------
out.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
          f'viewBox="0 0 {W} {H}" font-family="{FONT}">\n')
out.write('<defs><linearGradient id="hl" x1="0" y1="0" x2="1" y2="0">'
          '<stop offset="0%" stop-color="#22B8D8"/><stop offset="100%" stop-color="#2F6BE0"/>'
          '</linearGradient>\n'
          '<radialGradient id="bgA" cx="0" cy="0" r="1">'
          '<stop offset="0%" stop-color="#DCE7FA"/><stop offset="100%" stop-color="#ffffff"/>'
          '</radialGradient>\n'
          '<radialGradient id="bgB" cx="1" cy="1" r="1">'
          '<stop offset="0%" stop-color="#DFF3F8"/><stop offset="100%" stop-color="#ffffff"/>'
          '</radialGradient></defs>\n')
out.write(f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n')
out.write(f'<rect width="{W}" height="{H}" fill="url(#bgA)" opacity="0.55"/>\n')
out.write(f'<rect width="{W}" height="{H}" fill="url(#bgB)" opacity="0.5"/>\n')
out.write(f'<rect x="46" y="28" width="{W-92}" height="{H-56}" rx="10" fill="#ffffff" opacity="0.92"/>\n')

text(100, 70, "Database Design", 19, MUTED)
out.write(f'<text x="100" y="96" font-size="19" fill="{MUTED}">for the '
          f'<tspan font-weight="bold" fill="{INK}">SCI Advisor System</tspan></text>\n')
text(1820, 70, "4123204", 21, INK, "bold", "end")
text(1820, 96, "Advanced Database", 19, MUTED, anchor="end")

out.write(f'<text x="{W/2}" y="192" text-anchor="middle" font-size="46" font-weight="bold" '
          f'fill="{INK}">สรุปภาพรวมและ<tspan fill="url(#hl)">ผลการออกแบบ</tspan>'
          f'ฐานข้อมูลระบบ SCI Advisor</text>\n')

# ---- แถบตัวเลข ------------------------------------------------------------
SX, SY, SH, SGAP = 70, 238, 116, 18
SW = (W - 2 * SX - SGAP * (len(STATS) - 1)) // len(STATS)
for i, (num, lab, sub) in enumerate(STATS):
    x = SX + i * (SW + SGAP)
    rrect(x, SY, SW, SH, 14, TILE_BG, TILE_BD, 1.5)
    text(x + SW / 2, SY + 48, num, 38, TEAL_D, "bold", "middle")
    text(x + SW / 2, SY + 76, lab, 17, INK, "bold", "middle")
    text(x + SW / 2, SY + 99, sub, 13.5, MUTED, anchor="middle")

# ---- การ์ด 3 ใบ -----------------------------------------------------------
CY, CH, CGAP = 396, 420, 28
CW = (W - 2 * SX - CGAP * 2) // 3
for i, c in enumerate(CARDS):
    x = SX + i * (CW + CGAP)
    rrect(x, CY, CW, CH, 18, "#ffffff", CARD_BD, 1.8)
    rrect(x + 28, CY + 28, 58, 58, 16, TEAL)
    icon(c["ic"], x + 57, CY + 57)
    out.write(f'<circle cx="{x+112}" cy="{CY+57}" r="18" fill="{TEAL_D}"/>\n')
    text(x + 112, CY + 64, str(i + 1), 19, "#ffffff", "bold", "middle")
    text(x + 28, CY + 124, c["th"], 21, INK, "bold")
    text(x + 28, CY + 149, c["en"], 14.5, TEAL_D)
    for j, line in enumerate(c["body"]):
        if line:
            text(x + 28, CY + 192 + j * 28, line, 17, BODY)

# ---- แถบปิดท้าย -----------------------------------------------------------
FY, FH = 852, 96
rrect(SX, FY, W - 2 * SX, FH, 16, TILE_BG, TILE_BD, 1.6)
out.write(f'<circle cx="{SX+46}" cy="{FY+46}" r="17" fill="{TEAL_D}"/>\n')
out.write(f'<path d="M{SX+39},{FY+46} l5,5 l10,-11" fill="none" stroke="#ffffff" '
          'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>\n')
out.write(f'<line x1="{SX+80}" y1="{FY+22}" x2="{SX+80}" y2="{FY+FH-22}" '
          f'stroke="{TILE_BD}" stroke-width="2"/>\n')
text(SX + 104, FY + 42, "สิ่งที่ยืนยันได้", 18, TEAL_D, "bold")
text(SX + 104, FY + 72,
     "ทุกตัวเลขบนสไลด์นี้อ่านจากฐานข้อมูล production โดยตรง และทุกค่าที่ระบบใช้ตอบ สาวกลับไปถึงชื่อไฟล์และเลขหน้าของเอกสารต้นฉบับได้",
     17, BODY)

out.write('</svg>\n')

dst = r"D:\workspace\course-advisor-system-mko2\docs\SLIDE_DESIGN_SUMMARY.svg"
with open(dst, "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("stats =", len(STATS), " cards =", len(CARDS))
print("card bottom =", CY + CH, " footer top =", FY)
print("saved ->", dst, os.path.getsize(dst), "bytes")
