# -*- coding: utf-8 -*-
"""สไลด์ 'โครงสร้างฐานข้อมูลของระบบ' ฉบับแก้ให้ตรงกับระบบจริง
เนื้อหาทุกบรรทัดตรวจจากโค้ดและฐานข้อมูล production เมื่อ 24 กันยายน 2569"""
import io, os

W, H = 1920, 1080
FONT = "'Tahoma','Segoe UI','Leelawadee UI',sans-serif"

INK      = "#0F172A"
MUTED    = "#64748B"
BLUE     = "#2563EB"
BLUE_DK  = "#1D4ED8"
GREEN    = "#0F9D63"
CARD_BD  = "#E6EDF7"
PANEL_BD = "#DCE8F8"
PANEL_BG = "#FBFCFF"
ICON_BG  = "#EEF3FF"
ICON_BG2 = "#EAF7F1"

out = io.StringIO()


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=20, fill=INK, weight="normal", anchor="start", ls=""):
    extra = f' letter-spacing="{ls}"' if ls else ""
    out.write(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
              f'font-weight="{weight}" text-anchor="{anchor}"{extra}>{esc(s)}</text>\n')


def rrect(x, y, w, h, r, fill, stroke=None, sw=1.5):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    out.write(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{st}/>\n')


# ---- ไอคอน วาดในกรอบ 28x28 รอบจุด (cx, cy) --------------------------------
def icon(kind, cx, cy, color=BLUE):
    s = f'fill="none" stroke="{color}" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"'
    g = out.write
    if kind == "db":
        g(f'<ellipse cx="{cx}" cy="{cy-8}" rx="11" ry="4.5" {s}/>\n')
        g(f'<path d="M{cx-11},{cy-8} V{cy+8} a11,4.5 0 0 0 22,0 V{cy-8}" {s}/>\n')
        g(f'<path d="M{cx-11},{cy} a11,4.5 0 0 0 22,0" {s}/>\n')
    elif kind == "doc":
        g(f'<path d="M{cx-9},{cy-12} h11 l7,7 v17 a2,2 0 0 1 -2,2 h-16 a2,2 0 0 1 -2,-2 '
          f'v-22 a2,2 0 0 1 2,-2 z" {s}/>\n')
        g(f'<path d="M{cx+2},{cy-12} v7 h7" {s}/>\n')
        g(f'<path d="M{cx-5},{cy+1} h10 M{cx-5},{cy+7} h10" {s}/>\n')
    elif kind == "search":
        g(f'<circle cx="{cx-2}" cy="{cy-2}" r="8.5" {s}/>\n')
        g(f'<path d="M{cx+4.5},{cy+4.5} L{cx+11},{cy+11}" {s}/>\n')
    elif kind == "chat":
        g(f'<path d="M{cx-11},{cy-9} h22 a2,2 0 0 1 2,2 v12 a2,2 0 0 1 -2,2 h-13 '
          f'l-6,5 v-5 h-3 a2,2 0 0 1 -2,-2 v-12 a2,2 0 0 1 2,-2 z" {s}/>\n')
    elif kind == "grid":
        for dx in (-10, 1):
            for dy in (-10, 1):
                g(f'<rect x="{cx+dx}" y="{cy+dy}" width="9" height="9" rx="2" {s}/>\n')
    elif kind == "gear":
        g(f'<circle cx="{cx}" cy="{cy}" r="4.5" {s}/>\n')
        g(f'<path d="M{cx},{cy-12} v3 M{cx},{cy+9} v3 M{cx-12},{cy} h3 M{cx+9},{cy} h3 '
          f'M{cx-8.5},{cy-8.5} l2,2 M{cx+6.5},{cy+6.5} l2,2 '
          f'M{cx+8.5},{cy-8.5} l-2,2 M{cx-6.5},{cy+6.5} l-2,2" {s}/>\n')
        g(f'<circle cx="{cx}" cy="{cy}" r="9.5" {s}/>\n')
    elif kind == "shield":
        g(f'<path d="M{cx},{cy-12} l10,4 v8 c0,7 -5,11 -10,13 c-5,-2 -10,-6 -10,-13 v-8 z" {s}/>\n')
        g(f'<path d="M{cx-4},{cy+1} l3,3 l6,-6" {s}/>\n')
    elif kind == "monitor":
        g(f'<rect x="{cx-12}" y="{cy-10}" width="24" height="16" rx="2.5" {s}/>\n')
        g(f'<path d="M{cx},{cy+6} v4 M{cx-6},{cy+11} h12" {s}/>\n')
    elif kind == "bolt":
        g(f'<path d="M{cx+2},{cy-13} l-10,15 h8 l-2,12 l11,-16 h-9 z" '
          f'fill="{color}" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>\n')


# ---- เนื้อหา --------------------------------------------------------------
LEFT = [
    ("db",     "คลังข้อมูลหลักสูตรต้นฉบับ",
               "เก็บเอกสาร มคอ.2 พร้อมหลักฐานอ้างอิงย้อนกลับได้"),
    ("doc",    "เนื้อหาข้อความสกัด (Document Chunks)",
               "แบ่งข้อความจากเอกสารเป็นท่อนสำหรับใช้อ้างอิง"),
    ("search", "ค้นหาด้วยความหมาย (Semantic Search)",
               "เวกเตอร์ 1024 มิติ พร้อมดัชนี ivfflat"),
    ("chat",   "ประวัติการสนทนาและผลการแนะนำ",
               "chat_sessions · chat_messages · recommendations"),
    ("grid",   "ข้อมูลหลักสูตรที่สกัดแล้ว (schema mko)",
               "18 ตาราง 6 วิว พร้อมสถานะการตรวจทาน"),
]

RIGHT = [
    ("gear",    "ระบบผู้ดูแลและการจัดการเว็บ",
                "ข่าว บทความ และการตั้งค่าหน้าเว็บไซต์"),
    ("shield",  "บัญชีผู้ดูแลระบบ (Admin Auth)",
                "เข้าสู่ระบบเฉพาะผู้ดูแล ไม่ใช่ของนักศึกษา"),
    ("monitor", "ข้อมูลหลักสูตรสำหรับแสดงผล",
                "ใช้แสดงบนหน้าเว็บ แยกจากคลังความรู้ที่ใช้ตอบคำถาม"),
]

# ---- เริ่มวาด -------------------------------------------------------------
out.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
          f'viewBox="0 0 {W} {H}" font-family="{FONT}">\n')
out.write(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>\n')

# หัวกระดาษ
text(100, 58, "Database Design", 20, MUTED)
out.write(f'<text x="100" y="86" font-size="20" fill="{MUTED}">for the '
          f'<tspan font-weight="bold" fill="{INK}">SCI Advisor System</tspan></text>\n')
text(1820, 58, "4123204", 22, INK, "bold", "end")
text(1820, 86, "Advanced Database", 20, MUTED, anchor="end")

# ชื่อสไลด์
out.write(f'<text x="100" y="196" font-size="58" font-weight="bold" fill="{INK}">'
          f'โครงสร้าง<tspan fill="{BLUE}">ฐานข้อมูล</tspan>ของระบบ</text>\n')
text(100, 240, "ระบบใช้ PostgreSQL เป็นฐานข้อมูลหลัก และใช้ Supabase สำหรับงานจัดการเนื้อหาหน้าเว็บ",
     23, MUTED)

PY, PH = 286, 736          # กรอบใหญ่
LX, LW = 100, 980          # คอลัมน์ซ้าย
RX, RW = 1120, 700         # คอลัมน์ขวา
CARD_H, GAP = 108, 10
CARDS_Y = PY + 138


def panel(px, pw, name, tagline, tint, accent, ikind):
    rrect(px, PY, pw, PH, 26, PANEL_BG, PANEL_BD, 1.8)
    out.write(f'<circle cx="{px+76}" cy="{PY+68}" r="40" fill="{tint}"/>\n')
    icon(ikind, px + 76, PY + 68, accent)
    text(px + 140, PY + 60, name, 36, accent, "bold")
    text(px + 140, PY + 94, tagline, 21, MUTED)
    out.write(f'<line x1="{px+28}" y1="{PY+118}" x2="{px+pw-28}" y2="{PY+118}" '
              f'stroke="{PANEL_BD}" stroke-width="1.5"/>\n')


def cards(px, pw, items, accent, tint):
    for i, (ik, title, desc) in enumerate(items):
        cy = CARDS_Y + i * (CARD_H + GAP)
        rrect(px + 26, cy, pw - 52, CARD_H, 16, "#FFFFFF", CARD_BD, 1.4)
        rrect(px + 48, cy + 26, 56, 56, 15, tint)
        icon(ik, px + 76, cy + 54, accent)
        text(px + 124, cy + 48, title, 23.5, INK, "bold")
        text(px + 124, cy + 79, desc, 19.5, MUTED)


panel(LX, LW, "PostgreSQL", "ฐานข้อมูลหลักของระบบ · pgvector Extension", ICON_BG, BLUE_DK, "db")
cards(LX, LW, LEFT, BLUE, ICON_BG)

panel(RX, RW, "Supabase", "แพลตฟอร์มจัดการเนื้อหาหน้าเว็บ", ICON_BG2, GREEN, "bolt")
cards(RX, RW, RIGHT, GREEN, ICON_BG2)

# กล่องหมายเหตุใต้คอลัมน์ขวา
NY = CARDS_Y + 3 * (CARD_H + GAP) + 8
NH = PY + PH - NY - 26
rrect(RX + 26, NY, RW - 52, NH, 16, "#FFF8E8", "#F2D9A0", 1.4)
text(RX + 50, NY + 42, "หมายเหตุสำคัญ", 22, "#8A6212", "bold")
for i, line in enumerate([
        "ข้อมูลการสนทนาและคลังความรู้ที่ใช้ตอบคำถาม",
        "ทั้งหมดอยู่ใน PostgreSQL ไม่ได้อยู่ใน Supabase",
        "",
        "ตาราง courses มีทั้งสองฝั่งแต่คนละหน้าที่ —",
        "Supabase ใช้แสดงผล PostgreSQL ใช้ตอบคำถาม",
]):
    if line:
        text(RX + 50, NY + 74 + i * 26, line, 19, "#6B5116")

out.write('</svg>\n')

dst = r"D:\workspace\course-advisor-system-mko2\docs\SLIDE_DATABASE_STRUCTURE.svg"
with open(dst, "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("cards left =", len(LEFT), " right =", len(RIGHT))
print("note box y =", NY, "h =", NH, "(must be > 0)")
print("saved ->", dst, os.path.getsize(dst), "bytes")
