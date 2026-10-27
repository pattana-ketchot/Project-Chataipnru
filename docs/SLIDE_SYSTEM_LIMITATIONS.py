# -*- coding: utf-8 -*-
"""สไลด์ 'ข้อจำกัดและจุดอ่อนของระบบในปัจจุบัน' ฉบับแก้ให้ตรงกับระบบจริง
ตัวเลขทุกตัวมาจากโค้ดและการวัด production เมื่อ 24 กันยายน 2569"""
import io, os

W, H = 1920, 1080
FONT = "'Tahoma','Segoe UI','Leelawadee UI',sans-serif"

INK    = "#0F172A"
MUTED  = "#64748B"
BODY   = "#334155"
TEAL   = "#12A5BC"          # ไอคอนและเส้นขอบ
TEAL_D = "#0B7C90"          # วงกลมตัวเลข
CARD_BD = "#BFE6EE"
EX_BG  = "#EAF7FA"
EX_BD  = "#CBE9F0"

out = io.StringIO()


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def text(x, y, s, size=17, fill=BODY, weight="normal", anchor="start"):
    out.write(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
              f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>\n')


def rrect(x, y, w, h, r, fill, stroke=None, sw=1.6, dash=None):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.write(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{st}{da}/>\n')


def icon(kind, cx, cy, color="#ffffff"):
    s = f'fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
    g = out.write
    if kind == "search":
        g(f'<circle cx="{cx-2}" cy="{cy-2}" r="9" {s}/>\n')
        g(f'<path d="M{cx+5},{cy+5} L{cx+12},{cy+12}" {s}/>\n')
    elif kind == "link":
        g(f'<path d="M{cx-2},{cy+6} l-4,4 a6,6 0 0 1 -8.5,-8.5 l4,-4" {s}/>\n')
        g(f'<path d="M{cx+2},{cy-6} l4,-4 a6,6 0 0 1 8.5,8.5 l-4,4" {s}/>\n')
        g(f'<path d="M{cx-5},{cy+5} l10,-10" {s}/>\n')
    elif kind == "cloud":
        g(f'<path d="M{cx-11},{cy+5} a6.5,6.5 0 0 1 1.5,-12.8 a8.5,8.5 0 0 1 16.2,-1.4 '
          f'a6.5,6.5 0 0 1 0.8,12.9 z" {s}/>\n')
    elif kind == "sync":
        g(f'<path d="M{cx-10},{cy-2} a10,10 0 0 1 17,-6.6 l3,3" {s}/>\n')
        g(f'<path d="M{cx+10},{cy+2} a10,10 0 0 1 -17,6.6 l-3,-3" {s}/>\n')
        g(f'<path d="M{cx+10},{cy-9} v4.4 h-4.4 M{cx-10},{cy+9} v-4.4 h4.4" {s}/>\n')
    elif kind == "bang":
        g(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{color}"/>\n')
        g(f'<path d="M{cx},{cy-4.5} v5" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round"/>\n')
        g(f'<circle cx="{cx}" cy="{cy+4} " r="1.3" fill="#ffffff"/>\n')
    elif kind == "bulb":
        g(f'<path d="M{cx},{cy-10} a7.5,7.5 0 0 1 4.5,13.5 v2.5 h-9 v-2.5 A7.5,7.5 0 0 1 {cx},{cy-10} z" {s}/>\n')
        g(f'<path d="M{cx-3.5},{cy+9} h7 M{cx-2.5},{cy+12} h5" {s}/>\n')


# ---- เนื้อหา 4 การ์ด ------------------------------------------------------
CARDS = [
    dict(ic="search", th="คำย่อและคำเรียกติดปาก", en="(Vocabulary Gap)",
         body=["ระบบค้นข้อมูลด้วยการเทียบความหมายของ",
               "เวกเตอร์เพียงอย่างเดียว ไม่มีการค้นด้วย",
               "คำสำคัญ จึงจับคำพ้องความหมายได้ดี แต่",
               "พลาดกับคำย่อและคำเรียกติดปาก เพราะ",
               "เอกสาร มคอ.2 ใช้ชื่อทางการเสมอ"],
         ex=["“จบวิทคอมล่ะไปสายงานไหนได้บ้าง” ได้คะแนน",
             "ความใกล้เคียง 0.531 ตกเกณฑ์ ส่วนถ้าพิมพ์",
             "ชื่อเต็มได้ 0.720 ถามเรื่องเดียวกันแต่ตอบ",
             "ได้อันเดียว แก้ด้วยตารางคำย่อ 51 คำ",
             "ครอบคลุม 15 สาขา"]),

    dict(ic="link", th="ชื่อหลักสูตรซ้ำกัน", en="(Name Disambiguation)",
         body=["ระบบมี 24 หลักสูตร เพราะนับแยกตามปีที่",
               "ปรับปรุง ทำให้มีชื่อซ้ำกันถึง 6 คู่ ถ้าคำถาม",
               "ไม่ระบุปี ระบบอาจดึงเนื้อหาจากฉบับที่ไม่",
               "ตรงกับที่ผู้ถามต้องการ โดยไม่มีสัญญาณ",
               "เตือนว่าหยิบผิดฉบับ"],
         ex=["วิทยาการคอมพิวเตอร์มีทั้งฉบับ 2561 และ",
             "2566 กรณียากที่สุดคือหลักสูตรการจัดการ",
             "เทคโนโลยีการเกษตรฯ ที่มีทั้งปริญญาโท",
             "และปริญญาเอก ปี 2568 เหมือนกัน"]),

    dict(ic="cloud", th="พึ่งพาโมเดลภายนอก", en="(External LLM Dependency)",
         body=["ขั้นตอนเรียบเรียงคำตอบเรียกใช้โมเดลภาษา",
               "จากผู้ให้บริการภายนอก เวลาตอบจึงขึ้นกับ",
               "บริการนั้น ซึ่งอยู่นอกการควบคุมของระบบ",
               "และมีโควตาจำกัดต่อนาที"],
         ex=["วัดจาก production คำถามที่ไม่เรียกโมเดล",
             "ตอบใน 0.158 วินาทีตามปกติ ขณะที่เรียก",
             "โมเดลตรง ๆ ด้วยโจทย์ “1+1” ใช้ 39–82",
             "วินาที ทั้งสี่โมเดล ความช้าอยู่ฝั่งผู้ให้บริการ"]),

    dict(ic="sync", th="ต้องนำเข้าข้อมูลเอง", en="(No Automatic Sync)",
         body=["เมื่อมีเอกสารใหม่หรือฉบับแก้ไข ต้องอัปโหลด",
               "และสร้างเวกเตอร์ใหม่ก่อน ระบบไม่ได้ซิงก์",
               "อัตโนมัติจากต้นทาง ผู้ใช้จึงยังเห็นข้อมูล",
               "เดิมจนกว่าจะมีการนำเข้ารอบใหม่"],
         ex=["มีช่องทางอัปโหลดผ่านหน้าผู้ดูแล และมี",
             "corpus_version ไว้ล้างแคชคำตอบเมื่อคลัง",
             "เอกสารเปลี่ยน แต่ยังต้องมีคนกดดำเนินการ",
             "ไม่ได้เกิดขึ้นเองอัตโนมัติ"]),
]

# ---- เริ่มวาด -------------------------------------------------------------
out.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
          f'viewBox="0 0 {W} {H}" font-family="{FONT}">\n')
out.write('<defs>\n'
          '<linearGradient id="hl" x1="0" y1="0" x2="1" y2="0">'
          '<stop offset="0%" stop-color="#22B8D8"/><stop offset="100%" stop-color="#2F6BE0"/>'
          '</linearGradient>\n'
          '<radialGradient id="bgA" cx="0" cy="0" r="1">'
          '<stop offset="0%" stop-color="#DCE7FA"/><stop offset="100%" stop-color="#ffffff"/>'
          '</radialGradient>\n'
          '<radialGradient id="bgB" cx="1" cy="1" r="1">'
          '<stop offset="0%" stop-color="#DFF3F8"/><stop offset="100%" stop-color="#ffffff"/>'
          '</radialGradient>\n</defs>\n')
out.write(f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n')
out.write(f'<rect width="{W}" height="{H}" fill="url(#bgA)" opacity="0.55"/>\n')
out.write(f'<rect width="{W}" height="{H}" fill="url(#bgB)" opacity="0.5"/>\n')
out.write(f'<rect x="46" y="28" width="{W-92}" height="{H-56}" rx="10" fill="#ffffff" opacity="0.92"/>\n')

# หัวกระดาษ
text(100, 70, "Database Design", 19, MUTED)
out.write(f'<text x="100" y="96" font-size="19" fill="{MUTED}">for the '
          f'<tspan font-weight="bold" fill="{INK}">SCI Advisor System</tspan></text>\n')
text(1820, 70, "4123204", 21, INK, "bold", "end")
text(1820, 96, "Advanced Database", 19, MUTED, anchor="end")

# ชื่อสไลด์
out.write(f'<text x="{W/2}" y="196" text-anchor="middle" font-size="52" font-weight="bold" '
          f'fill="{INK}">ข้อจำกัดและ<tspan fill="url(#hl)">จุดอ่อน</tspan>ของระบบในปัจจุบัน</text>\n')
text(W / 2, 238, "ข้อจำกัดต่อไปนี้วัดจากระบบที่ใช้งานจริง ทุกตัวเลขตรวจสอบย้อนกลับได้จากโค้ดและฐานข้อมูล",
     21, MUTED, anchor="middle")

CY, CH = 288, 536
CX0, CW, GAP = 70, 428, 22
EX_LH, BODY_LH = 25, 27

for i, c in enumerate(CARDS):
    x = CX0 + i * (CW + GAP)
    rrect(x, CY, CW, CH, 18, "#ffffff", CARD_BD, 1.8)

    # หัวการ์ด: ไอคอน + เลขลำดับ + ชื่อ
    rrect(x + 24, CY + 24, 58, 58, 16, TEAL)
    icon(c["ic"], x + 53, CY + 53)
    out.write(f'<circle cx="{x+104}" cy="{CY+53}" r="18" fill="{TEAL_D}"/>\n')
    text(x + 104, CY + 60, str(i + 1), 19, "#ffffff", "bold", "middle")
    text(x + 24, CY + 118, c["th"], 20, INK, "bold")
    text(x + 24, CY + 142, c["en"], 14.5, TEAL_D)

    # เนื้อความ
    for j, line in enumerate(c["body"]):
        text(x + 24, CY + 180 + j * BODY_LH, line, 16.5, BODY)

    # กล่องตัวอย่าง วางชิดขอบล่างของการ์ดเสมอ ไม่ว่าเนื้อความจะยาวเท่าไร
    bh = 36 + 26 + len(c["ex"]) * EX_LH
    by = CY + CH - 24 - bh
    rrect(x + 20, by, CW - 40, bh, 14, EX_BG, EX_BD, 1.4)
    icon("bang", x + 44, by + 28, TEAL)
    text(x + 62, by + 33, "ตัวอย่าง / ผลกระทบ", 15.5, TEAL_D, "bold")
    for j, line in enumerate(c["ex"]):
        text(x + 34, by + 62 + j * EX_LH, line, 15.5, "#3E5060")

# แถบสรุป
SY, SH = 848, 116
rrect(CX0, SY, W - 2 * CX0, SH, 16, EX_BG, EX_BD, 1.6)
icon("bulb", CX0 + 44, SY + 58, TEAL_D)
out.write(f'<line x1="{CX0+78}" y1="{SY+26}" x2="{CX0+78}" y2="{SY+SH-26}" '
          f'stroke="{EX_BD}" stroke-width="2"/>\n')
text(CX0 + 100, SY + 48, "สรุป :", 18, TEAL_D, "bold")
text(CX0 + 176, SY + 48,
     "ข้อจำกัดทั้งสี่ข้อวัดได้จากระบบจริง ไม่ใช่การคาดการณ์  ปัจจุบันบรรเทาข้อ 1 ด้วยตารางขยายคำย่อที่เขียนด้วยมือ 51 คำ",
     17, BODY)
text(CX0 + 176, SY + 82,
     "แนวทางพัฒนาต่อ — เพิ่ม Hybrid Search ผสมการค้นด้วยคำสำคัญเข้ากับการค้นด้วยเวกเตอร์ เพื่อให้จับคำย่อและชื่อเฉพาะได้เองโดยไม่ต้องเขียนตาราง",
     17, BODY)

out.write('</svg>\n')

dst = r"D:\workspace\course-advisor-system-mko2\docs\SLIDE_SYSTEM_LIMITATIONS.svg"
with open(dst, "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("cards =", len(CARDS))
for c in CARDS:
    print("  ", c["en"], "body", len(c["body"]), "ex", len(c["ex"]))
print("saved ->", dst, os.path.getsize(dst), "bytes")
