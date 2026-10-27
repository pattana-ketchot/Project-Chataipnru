# -*- coding: utf-8 -*-
"""สร้าง ER diagram ของ schema public เป็น SVG จากข้อมูลที่ตรวจจากฐานข้อมูลจริง
ทุกชื่อคอลัมน์ในไฟล์นี้ลอกมาจากผล information_schema ไม่มีการเดา"""
import io, os, sys

# ส่ง --bw เพื่อสร้างฉบับขาวดำสำหรับพิมพ์ลงเล่มรายงาน
BW = "--bw" in sys.argv

W, H = 1570, 1075
FONT = "'Tahoma','Segoe UI','Leelawadee UI',sans-serif"
ROW_H, HDR_H, PAD_B = 21, 32, 8

NAVY = "#17365d"
LINE = "#1f3d6b"

# ---- จานสีโหมดขาวดำ -------------------------------------------------------
# ไม่ได้แค่ลดความอิ่มสี เพราะสีพาสเทลเดิมพอแปลงเป็นเทาแล้วจะกลายเป็นระดับเดียวกันหมด
# จึงกำหนดระดับเทาใหม่ให้หัวตารางเข้มพอจะแยกจากตัวเนื้อ และเส้นทุกเส้นเป็นดำสนิท
BW_STROKE, BW_HEAD, BW_BODY = "#4a4a4a", "#e4e4e4", "#ffffff"
BW_INK, BW_TYPE, BW_SOFT = "#000000", "#565656", "#4a4a4a"
# สีชื่อคอลัมน์: ปกติเป็นดำอมน้ำเงินจาง โหมดขาวดำใช้ดำสนิท
COL_NAME = "#000000" if BW else "#1a1a2e"
if BW:
    NAVY = "#2b2b2b"
    LINE = "#141414"

# ---- ข้อมูลตาราง: (ชื่อคอลัมน์, ชนิด, ป้ายกำกับ) -------------------------
TABLES = [
    dict(name="public.users", x=30, y=132, w=255,
         stroke="#2f9e68", head="#d5f2e3", body="#f2fcf7",
         cols=[("id","uuid","PK"),("email","citext","UQ"),
               ("password_hash","text",""),("full_name","text",""),
               ("is_active","boolean",""),("is_admin","boolean",""),
               ("created_at","timestamptz",""),("updated_at","timestamptz","")]),

    dict(name="public.course_documents", x=465, y=132, w=290,
         stroke="#2478cd", head="#d7e9fb", body="#f2f8fe",
         cols=[("id","uuid","PK"),("course_id","uuid","FK"),
               ("original_filename","text",""),("file_sha256","text",""),
               ("storage_path","text",""),("page_count","integer",""),
               ("extraction_status","text",""),("extraction_error","text",""),
               ("uploaded_by","uuid","FK"),("uploaded_at","timestamptz","")]),

    dict(name="public.course_chunks", x=880, y=132, w=255,
         stroke="#7645bd", head="#e5daf7", body="#f7f3fd",
         cols=[("id","uuid","PK"),("course_id","uuid","FK"),
               ("document_id","uuid","FK"),("chunk_index","integer",""),
               ("page_number","integer",""),("content","text",""),
               ("token_count","integer",""),("embedding","vector(1024)",""),
               ("metadata","jsonb",""),("created_at","timestamptz","")]),

    dict(name="public.courses", x=1250, y=132, w=270,
         stroke="#d79a1c", head="#fdefc9", body="#fffaed",
         cols=[("id","uuid","PK"),("code","text","UQ"),
               ("title","text",""),("provider","text",""),
               ("summary","text",""),("mode","text",""),
               ("duration_weeks","numeric",""),("price","numeric",""),
               ("currency","text",""),("tags","jsonb",""),
               ("is_active","boolean",""),("created_at","timestamptz",""),
               ("updated_at","timestamptz","")]),

    dict(name="public.user_profiles", x=150, y=382, w=290,
         stroke="#d94a76", head="#fbdbe6", body="#fef4f7",
         cols=[("user_id","uuid","PK, FK"),("education_level","text",""),
               ("field_of_study","text",""),("current_role","text",""),
               ("career_goal","text",""),("skills","jsonb",""),
               ("interests","jsonb",""),("language_preference","text",""),
               ("metadata","jsonb",""),("updated_at","timestamptz","")]),

    dict(name="public.user_requirements", x=150, y=667, w=246,
         stroke="#1f9e93", head="#d0efec", body="#f1fbfa",
         cols=[("id","uuid","PK"),("user_id","uuid","FK"),
               ("req_type","text",""),("req_value","text",""),
               ("priority","smallint",""),("created_at","timestamptz","")]),

    dict(name="public.chat_sessions", x=560, y=495, w=235,
         stroke="#2f97d9", head="#d3ebf9", body="#f1f9fe",
         cols=[("id","uuid","PK"),("user_id","uuid","FK"),
               ("started_at","timestamptz",""),("ended_at","timestamptz","")]),

    dict(name="public.chat_messages", x=560, y=689, w=235,
         stroke="#d98125", head="#fce4c8", body="#fff7ee",
         cols=[("id","uuid","PK"),("session_id","uuid","FK"),
               ("role","text",""),("content","text",""),
               ("created_at","timestamptz","")]),

    dict(name="public.recommendations", x=975, y=529, w=290,
         stroke="#5f4dd6", head="#dcd7f8", body="#f4f2fd",
         cols=[("id","uuid","PK"),("user_id","uuid","FK"),
               ("course_id","uuid","FK"),("session_id","uuid","FK"),
               ("score","numeric",""),("rationale","text",""),
               ("retrieved_chunk_ids","uuid[]",""),("model_used","text",""),
               ("created_at","timestamptz","")]),

    dict(name="public.chat_answer_cache", x=1285, y=645, w=255,
         stroke="#d94a76", head="#fbdbe6", body="#fef4f7",
         cols=[("question_key","text","PK"),("corpus_version","text",""),
               ("status","text",""),("reply","text",""),
               ("citations","jsonb",""),("hits","integer",""),
               ("created_at","timestamptz",""),("last_used_at","timestamptz","")]),
]

# ---- เส้นความสัมพันธ์ 11 เส้น --------------------------------------------
# pts = จุดหักมุม, lab = ป้าย 2 บรรทัด, lab_xy = ตำแหน่งป้าย, anchor
# ends = [(x,y,'1'|'N',dx,dy)] ตำแหน่งตัวเลขความสัมพันธ์
RELS = [
    dict(pts=[(285,190),(465,190)], lab=("uploaded_by","(NO ACTION)"),
         lab_xy=(375,182), anchor="middle", danger=True,
         ends=[(290,182,"1"),(455,182,"N")]),

    dict(pts=[(755,210),(880,210)], lab=("document_id","(CASCADE)"),
         lab_xy=(817,202), anchor="middle",
         ends=[(760,202,"1"),(871,202,"N")]),

    dict(pts=[(1135,210),(1250,210)], lab=("course_id","(CASCADE)"),
         lab_xy=(1192,202), anchor="middle",
         ends=[(1141,202,"N"),(1241,202,"1")]),

    dict(pts=[(600,132),(600,118),(1330,118),(1330,132)],
         lab=("course_id","(CASCADE)"), lab_xy=(965,94), anchor="middle",
         ends=[(590,130,"N"),(1340,130,"1")]),

    dict(pts=[(100,340),(100,435),(150,435)], lab=("user_id","(CASCADE)"),
         lab_xy=(96,466), anchor="middle",
         ends=[(110,352,"1"),(140,427,"1")]),

    dict(pts=[(60,340),(60,737),(150,737)], lab=("user_id","(CASCADE)"),
         lab_xy=(78,768), anchor="middle",
         ends=[(70,352,"1"),(140,729,"N")]),

    dict(pts=[(200,340),(200,362),(452,362),(452,465),(1050,465),(1050,529)],
         lab=("user_id","(CASCADE)"), lab_xy=(830,451), anchor="middle",
         ends=[(210,352,"1"),(1060,521,"N")]),

    dict(pts=[(452,465),(452,557),(560,557)], lab=("user_id","(CASCADE)"),
         lab_xy=(478,592), anchor="middle", junction_start=True,
         ends=[(508,549,"1"),(551,549,"N")]),

    dict(pts=[(650,619),(650,689)], lab=("session_id","(CASCADE)"),
         lab_xy=(668,647), anchor="start",
         ends=[(640,631,"1"),(640,681,"N")]),

    dict(pts=[(795,587),(975,587)], lab=("session_id","(SET NULL)"),
         lab_xy=(885,613), anchor="middle", danger=True,
         ends=[(801,579,"1"),(965,579,"N")]),

    dict(pts=[(1420,445),(1420,587),(1265,587)], lab=("course_id","(CASCADE)"),
         lab_xy=(1408,505), anchor="end",
         ends=[(1430,457,"1"),(1275,579,"N")]),
]


if BW:
    for _t in TABLES:
        _t["stroke"], _t["head"], _t["body"] = BW_STROKE, BW_HEAD, BW_BODY


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box_height(t):
    return HDR_H + len(t["cols"]) * ROW_H + PAD_B


out = io.StringIO()
out.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
          f'viewBox="0 0 {W} {H}" font-family="{FONT}">\n')
out.write(f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n')

# แถบหัวเรื่อง
out.write(f'<rect x="0" y="0" width="{W}" height="74" fill="{NAVY}"/>\n')
out.write(f'<text x="{W/2}" y="34" text-anchor="middle" font-size="26" '
          f'font-weight="bold" fill="#ffffff">'
          'ER Diagram \u2014 PostgreSQL schema public (10 \u0e15\u0e32\u0e23\u0e32\u0e07)</text>\n')
out.write(f'<text x="{W/2}" y="60" text-anchor="middle" font-size="14" '
          f'fill="{"#d6d6d6" if BW else "#c8dcf5"}">'
          '\u0e42\u0e04\u0e23\u0e07\u0e2a\u0e23\u0e49\u0e32\u0e07\u0e10\u0e32\u0e19\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e23\u0e30\u0e1a\u0e1a SCI Advisor '
          '(\u0e15\u0e23\u0e27\u0e08\u0e08\u0e32\u0e01\u0e10\u0e32\u0e19\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25 production \u0e27\u0e31\u0e19\u0e17\u0e35\u0e48 24 '
          '\u0e01\u0e31\u0e19\u0e22\u0e32\u0e22\u0e19 2569)</text>\n')

# เส้นความสัมพันธ์ วาดก่อนกล่องเพื่อให้กล่องทับหัวเส้น
for r in RELS:
    pts = " ".join(f"{x},{y}" for x, y in r["pts"])
    out.write(f'<polyline points="{pts}" fill="none" stroke="{LINE}" '
              'stroke-width="1.6" stroke-linejoin="round"/>\n')
    for idx, (x, y) in enumerate((r["pts"][0], r["pts"][-1])):
        if idx == 0 and r.get("junction_start"):
            # จุดแยกออกจากเส้นหลัก ใช้จุดทึบ ไม่ใช่วงกลมกลวงแบบปลายที่ต่อกับตาราง
            out.write(f'<circle cx="{x}" cy="{y}" r="3.4" fill="{LINE}"/>\n')
        else:
            out.write(f'<circle cx="{x}" cy="{y}" r="3.6" fill="#ffffff" '
                      f'stroke="{LINE}" stroke-width="1.6"/>\n')

# กล่องตาราง
for t in TABLES:
    x, y, w = t["x"], t["y"], t["w"]
    h = box_height(t)
    out.write(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" '
              f'fill="{t["body"]}" stroke="{t["stroke"]}" stroke-width="2"/>\n')
    out.write(f'<path d="M{x},{y+HDR_H} v-{HDR_H-9} a9,9 0 0 1 9,-9 h{w-18} '
              f'a9,9 0 0 1 9,9 v{HDR_H-9} z" fill="{t["head"]}"/>\n')
    out.write(f'<line x1="{x}" y1="{y+HDR_H}" x2="{x+w}" y2="{y+HDR_H}" '
              f'stroke="{t["stroke"]}" stroke-width="1.4"/>\n')
    out.write(f'<text x="{x+12}" y="{y+21}" font-size="14.5" font-weight="bold" '
              f'fill="{BW_INK if BW else "#123"}">{esc(t["name"])} ({len(t["cols"])})</text>\n')

    cx_type = x + w * 0.545
    cx_flag = x + w - 12
    for i, (cn, ct, cf) in enumerate(t["cols"]):
        ty = y + HDR_H + ROW_H * i + 15
        if i % 2 == 1:
            out.write(f'<rect x="{x+1.5}" y="{ty-14.5}" width="{w-3}" '
                      f'height="{ROW_H}" fill="#000000" opacity="0.022"/>\n')
        bold = ' font-weight="bold"' if cf else ''
        out.write(f'<text x="{x+12}" y="{ty}" font-size="12.5"{bold} '
                  f'fill="{COL_NAME}">{esc(cn)}</text>\n')
        out.write(f'<text x="{cx_type}" y="{ty}" font-size="12.5" '
                  f'fill="{BW_TYPE if BW else "#5a6470"}">{esc(ct)}</text>\n')
        if cf:
            col = BW_INK if BW else ("#c2185b" if cf == "UQ" else "#1565c0")
            out.write(f'<text x="{cx_flag}" y="{ty}" font-size="11.5" '
                      f'font-weight="bold" text-anchor="end" fill="{col}">{cf}</text>\n')

# ป้ายกำกับเส้น
for r in RELS:
    lx, ly = r["lab_xy"]
    a = r["anchor"]
    if BW:
        # CASCADE เป็นค่าปกติจึงใช้เทา ส่วน SET NULL / NO ACTION เป็นข้อยกเว้นจึงใช้ดำสนิท
        c2 = BW_INK if r.get("danger") else BW_SOFT
    else:
        c2 = "#c62828" if r.get("danger") else "#1565c0"
    out.write(f'<text x="{lx}" y="{ly}" font-size="11.5" font-weight="bold" '
              f'text-anchor="{a}" fill="{BW_INK if BW else "#17365d"}">{esc(r["lab"][0])}</text>\n')
    out.write(f'<text x="{lx}" y="{ly+15}" font-size="11.5" font-weight="bold" '
              f'text-anchor="{a}" fill="{c2}">{esc(r["lab"][1])}</text>\n')
    for ex, ey, et in r["ends"]:
        out.write(f'<text x="{ex}" y="{ey}" font-size="12" font-weight="bold" '
                  f'text-anchor="middle" fill="{BW_INK if BW else "#17365d"}">{et}</text>\n')

# ---- กล่องล่าง 3 กล่อง ---------------------------------------------------
def panel(x, y, w, h, title, fill, stroke):
    if BW:
        fill, stroke = "#f7f7f7", "#8a8a8a"
    out.write(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" '
              f'fill="{fill}" stroke="{stroke}" stroke-width="1.6" '
              'stroke-dasharray="6 4"/>\n')
    out.write(f'<text x="{x+16}" y="{y+26}" font-size="14.5" font-weight="bold" '
              f'fill="{NAVY}">{esc(title)}</text>\n')

PY, PH = 880, 178
panel(30, PY, 500, PH, "\u0e2a\u0e23\u0e38\u0e1b\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25 (schema public)", "#f2f7fc", "#7fa8d4")
for i, s in enumerate([
    "\u0e08\u0e33\u0e19\u0e27\u0e19\u0e15\u0e32\u0e23\u0e32\u0e07: 10 \u0e15\u0e32\u0e23\u0e32\u0e07",
    "\u0e08\u0e33\u0e19\u0e27\u0e19\u0e04\u0e2d\u0e25\u0e31\u0e21\u0e19\u0e4c\u0e23\u0e27\u0e21: 83 \u0e04\u0e2d\u0e25\u0e31\u0e21\u0e19\u0e4c",
    "\u0e04\u0e35\u0e22\u0e4c\u0e19\u0e2d\u0e01 (Foreign Key): 11 \u0e40\u0e2a\u0e49\u0e19",
    "\u0e15\u0e32\u0e23\u0e32\u0e07\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48\u0e21\u0e35\u0e04\u0e35\u0e22\u0e4c\u0e19\u0e2d\u0e01: chat_answer_cache",
    "\u0e04\u0e35\u0e22\u0e4c\u0e40\u0e14\u0e35\u0e48\u0e22\u0e27\u0e41\u0e1a\u0e1a\u0e04\u0e39\u0e48: course_documents (course_id, file_sha256)",
    "\u0e41\u0e25\u0e30 course_chunks (document_id, chunk_index)",
]):
    bullet = "\u2022 " if i < 5 else "\u00a0\u00a0\u00a0"
    out.write(f'<text x="{46 if i<5 else 58}" y="{PY+52+i*22}" font-size="13" '
              f'fill="{COL_NAME}">{esc(bullet + s)}</text>\n')

panel(550, PY, 490, PH, "\u0e04\u0e33\u0e2d\u0e18\u0e34\u0e1a\u0e32\u0e22\u0e2a\u0e31\u0e0d\u0e25\u0e31\u0e01\u0e29\u0e13\u0e4c", "#fafafa", "#9e9e9e")
out.write(f'<circle cx="576" cy="{PY+52}" r="3.6" fill="#fff" stroke="{LINE}" stroke-width="1.6"/>\n')
out.write(f'<line x1="580" y1="{PY+52}" x2="660" y2="{PY+52}" stroke="{LINE}" stroke-width="1.6"/>\n')
out.write(f'<circle cx="664" cy="{PY+52}" r="3.6" fill="#fff" stroke="{LINE}" stroke-width="1.6"/>\n')
out.write(f'<text x="570" y="{PY+42}" font-size="12" font-weight="bold" fill="#17365d">1</text>\n')
out.write(f'<text x="664" y="{PY+42}" font-size="12" font-weight="bold" fill="#17365d">N</text>\n')
out.write(f'<text x="686" y="{PY+57}" font-size="13" fill="{COL_NAME}">'
          '\u0e04\u0e27\u0e32\u0e21\u0e2a\u0e31\u0e21\u0e1e\u0e31\u0e19\u0e18\u0e4c\u0e41\u0e1a\u0e1a 1 \u0e15\u0e48\u0e2d \u0e2b\u0e25\u0e32\u0e22 (One-to-Many)</text>\n')
for i, (k, kc, s) in enumerate([
    ("(CASCADE)", "#1565c0", "\u0e25\u0e1a\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e49\u0e19\u0e17\u0e32\u0e07\u0e41\u0e25\u0e49\u0e27\u0e25\u0e1a\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e1b\u0e25\u0e32\u0e22\u0e17\u0e32\u0e07\u0e2d\u0e31\u0e15\u0e42\u0e19\u0e21\u0e31\u0e15\u0e34"),
    ("(SET NULL)", "#c62828", "\u0e25\u0e1a\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e49\u0e19\u0e17\u0e32\u0e07\u0e41\u0e25\u0e49\u0e27\u0e15\u0e31\u0e49\u0e07\u0e04\u0e48\u0e32\u0e40\u0e1b\u0e47\u0e19 NULL"),
    ("(NO ACTION)", "#c62828", "\u0e25\u0e1a\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e49\u0e19\u0e17\u0e32\u0e07\u0e44\u0e21\u0e48\u0e44\u0e14\u0e49 \u0e16\u0e49\u0e32\u0e22\u0e31\u0e07\u0e21\u0e35\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e2d\u0e49\u0e32\u0e07\u0e2d\u0e34\u0e07\u0e2d\u0e22\u0e39\u0e48"),
    ("PK / FK / UQ", "#1565c0", "\u0e04\u0e35\u0e22\u0e4c\u0e2b\u0e25\u0e31\u0e01 / \u0e04\u0e35\u0e22\u0e4c\u0e19\u0e2d\u0e01 / \u0e04\u0e48\u0e32\u0e2b\u0e49\u0e32\u0e21\u0e0b\u0e49\u0e33"),
]):
    yy = PY + 80 + i * 24
    if BW:
        kc = BW_INK if k in ("(SET NULL)", "(NO ACTION)") else BW_SOFT
    out.write(f'<text x="570" y="{yy}" font-size="12.5" font-weight="bold" fill="{kc}">{esc(k)}</text>\n')
    out.write(f'<text x="686" y="{yy}" font-size="13" fill="{COL_NAME}">{esc(s)}</text>\n')

panel(1060, PY, 480, PH, "\u0e2b\u0e21\u0e32\u0e22\u0e40\u0e2b\u0e15\u0e38", "#f7f5fd", "#9b8ed6")
notes = [
 "\u0e41\u0e1c\u0e19\u0e20\u0e32\u0e1e\u0e19\u0e35\u0e49\u0e41\u0e2a\u0e14\u0e07\u0e40\u0e09\u0e1e\u0e32\u0e30 schema public \u0e02\u0e2d\u0e07 PostgreSQL",
 "PostgreSQL \u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14\u0e21\u0e35 28 \u0e15\u0e32\u0e23\u0e32\u0e07 (public 10 + mko 18) \u0e41\u0e25\u0e30 6 views",
 "Supabase \u0e43\u0e0a\u0e49\u0e10\u0e32\u0e19\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e04\u0e19\u0e25\u0e30\u0e0a\u0e38\u0e14 \u0e21\u0e35 7 \u0e15\u0e32\u0e23\u0e32\u0e07 \u0e44\u0e21\u0e48\u0e23\u0e27\u0e21\u0e43\u0e19\u0e41\u0e1c\u0e19\u0e20\u0e32\u0e1e\u0e19\u0e35\u0e49",
 "course_chunks.embedding \u0e40\u0e01\u0e47\u0e1a\u0e40\u0e27\u0e01\u0e40\u0e15\u0e2d\u0e23\u0e4c 1024 \u0e21\u0e34\u0e15\u0e34 (pgvector)",
 "\u0e21\u0e35\u0e14\u0e31\u0e0a\u0e19\u0e35 ivfflat \u0e41\u0e1a\u0e1a vector_cosine_ops (lists = 100)",
 "\u0e40\u0e07\u0e37\u0e48\u0e2d\u0e19\u0e44\u0e02 NOT NULL \u0e41\u0e25\u0e30 CHECK \u0e14\u0e39\u0e17\u0e35\u0e48\u0e1e\u0e08\u0e19\u0e32\u0e19\u0e38\u0e01\u0e23\u0e21\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e43\u0e19\u0e40\u0e25\u0e48\u0e21\u0e23\u0e32\u0e22\u0e07\u0e32\u0e19",
]
BULLET = "\u2022 "
for i, s in enumerate(notes):
    txt = esc(BULLET + s)
    out.write(f'<text x="1076" y="{PY+52+i*22}" font-size="12.5" fill="{COL_NAME}">'
              f'{txt}</text>\n')

out.write('</svg>\n')

dst = (r"D:\workspace\course-advisor-system-mko2\docs\ER_DIAGRAM_PUBLIC_SCHEMA_BW.svg"
       if BW else
       r"D:\workspace\course-advisor-system-mko2\docs\ER_DIAGRAM_PUBLIC_SCHEMA.svg")
with open(dst, "w", encoding="utf-8") as f:
    f.write(out.getvalue())

total = sum(len(t["cols"]) for t in TABLES)
print("tables =", len(TABLES))
print("columns =", total)
print("relations =", len(RELS))
for t in TABLES:
    print("  ", t["name"], len(t["cols"]), "rows  bottom y =", t["y"] + box_height(t))
print("saved ->", dst, os.path.getsize(dst), "bytes")
