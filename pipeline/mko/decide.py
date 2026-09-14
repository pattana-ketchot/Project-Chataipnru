"""
ตัดสินสถานะของค่าที่สกัดได้ — ค่าที่ไม่มั่นใจเป็น needs_review และค่าที่หาไม่เจอเป็น not_found เสมอ ไม่มีการเดา

กฎ (ตรงกับ docs/MKO_STRUCTURED_DATA_DESIGN.md หัวข้อ C และ H)
    not_found     ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด — ค่าเป็น NULL
    needs_review  พบหลายค่าที่ไม่ตรงกัน / ทุกตำแหน่งที่พบมาจากหน้าที่มี OCR / ข้อความมีร่องรอยฟอนต์เพี้ยน /
                  ค่าไม่ผ่านกฎตรวจ (เช่น ปีไม่ตรงกับชื่อหลักสูตรในระบบ) / เอกสารของหลักสูตรเดียวกันให้ค่าต่างกัน
    candidate     พบค่าเดียวที่ผ่านกฎตรวจ จากข้อความในไฟล์ (ไม่ใช่ OCR) แต่มีที่มาเพียงตำแหน่งเดียว
    verified      ยืนยันอัตโนมัติเท่านั้นใน Phase 1 และบันทึกผู้ยืนยันเป็นชื่อกฎ:
                    auto:two_locations_agree  ค่าเดียวกันจากข้อความในไฟล์อย่างน้อยสองหน้าของเล่มเดียวกัน
                    auto:documents_agree      ค่าเดียวกันจากเอกสารสองไฟล์ของหลักสูตรฉบับปีเดียวกัน (ฉบับเต็มกับใบสรุป)
                  ยังไม่มีการยืนยันโดยคน (ขั้นตรวจโดยคนอยู่ใน Phase 2)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pipeline.mko.doc import DocText, suspect_encoding
from pipeline.mko.fields import ListLocated, Located
from pipeline.mko.normalize import fold

AUTO_TWO_LOCATIONS = "auto:two_locations_agree"
AUTO_DOCUMENTS = "auto:documents_agree"

NOT_FOUND = "ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด"
REASON_OCR = "มาจากหน้าที่มีข้อความจาก OCR"
REASON_ENCODING = "ข้อความมีร่องรอยฟอนต์เพี้ยน (ำ แทน า)"


@dataclass(frozen=True)
class Evidence:
    start: int
    end: int
    location: str
    method: str


@dataclass
class FieldDecision:
    field_key: str
    status: str
    value_text: str | None = None
    value_int: int | None = None
    reason: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    reviewed_by: str | None = None

    @property
    def key(self):
        return self.value_int if self.value_int is not None else normalise_text(self.value_text)

    @property
    def shown(self) -> str:
        return str(self.value_int) if self.value_int is not None else (self.value_text or "")


@dataclass
class ItemDecision:
    seq: int
    text: str
    evidence: Evidence


@dataclass
class ListDecision:
    field_key: str
    item_type: str
    status: str
    reason: str | None = None
    block: Evidence | None = None
    items: list[ItemDecision] = field(default_factory=list)
    reviewed_by: str | None = None

    @property
    def key(self) -> tuple[str, ...]:
        return tuple(normalise_text(item.text) for item in self.items)


def normalise_text(text: str | None) -> str:
    """รูปที่ใช้เทียบค่าข้อความ: fold (ตัดช่องว่าง ำ→า) ตัวพิมพ์เล็ก และตัดจุดท้าย"""
    return fold(text or "").lower().rstrip(".")


def _evidence(located: Located, method: str | None = None) -> Evidence:
    return Evidence(located.start, located.end, located.location, method or located.method)


def _problems(doc: DocText, located: Located) -> list[str]:
    problems = []
    if doc.span_has_ocr(located.start, located.end):
        problems.append(REASON_OCR)
    if located.value_text and suspect_encoding(located.value_text):
        problems.append(REASON_ENCODING)
    return problems


def decide_scalar(doc: DocText, field_key: str, found: list[Located],
                  check: Callable[[Located], str | None] | None = None) -> list[FieldDecision]:
    """คืนการตัดสินหนึ่งรายการต่อค่าที่แตกต่างกัน (ปกติมีรายการเดียว ถ้าค่าขัดกันจะมีหลายรายการ ทุกรายการเป็น needs_review)"""
    if not found:
        return [FieldDecision(field_key, "not_found", reason=NOT_FOUND)]

    groups: dict[object, list[Located]] = {}
    for located in found:
        key = located.value_int if located.value_int is not None else normalise_text(located.value_text)
        groups.setdefault(key, []).append(located)

    conflict = " | ".join(
        str(locs[0].value_int) if locs[0].value_int is not None else (locs[0].value_text or "") for locs in groups.values()
    )
    decisions: list[FieldDecision] = []
    for locs in groups.values():
        clean = [loc for loc in locs if not _problems(doc, loc)]
        flagged = [loc for loc in locs if _problems(doc, loc)]
        evidence: list[Evidence] = []
        for loc in clean + flagged:
            ev = _evidence(loc)
            if all((ev.start, ev.end) != (x.start, x.end) for x in evidence):
                evidence.append(ev)
        first = (clean or flagged)[0]
        decision = FieldDecision(field_key, "candidate", first.value_text, first.value_int, evidence=evidence[:4])
        problem = check(first) if check else None
        clean_pages = {doc.page_at(loc.start).page_number for loc in clean}

        if len(groups) > 1:
            decision.status, decision.reason = "needs_review", f"พบหลายค่าไม่ตรงกันในเอกสาร: {conflict}"
        elif problem:
            decision.status, decision.reason = "needs_review", problem
        elif not clean:
            decision.status = "needs_review"
            decision.reason = "; ".join(sorted({p for loc in flagged for p in _problems(doc, loc)}))
        elif len(clean_pages) >= 2:
            decision.status, decision.reviewed_by = "verified", AUTO_TWO_LOCATIONS
            locations = ", ".join(sorted({loc.location for loc in clean}))
            decision.reason = f"ค่าเดียวกันจากหน้า {', '.join(map(str, sorted(clean_pages)))} ({locations})"
        decisions.append(decision)
    return decisions


def derive(field_key: str, source: list[FieldDecision], mapping: Callable[[str], str | None]) -> list[FieldDecision]:
    """ค่าที่อนุมานจากค่าอื่นโดยตรง (เช่น ระดับการศึกษาจากชื่อปริญญา) ใช้สถานะและหลักฐานเดียวกับค่าต้นทาง"""
    valued = [d for d in source if d.status != "not_found" and d.value_text]
    if not valued:
        return [FieldDecision(field_key, "not_found", reason=NOT_FOUND)]
    results = []
    for d in valued:
        value = mapping(d.value_text)
        if value is None:
            results.append(FieldDecision(field_key, "not_found", reason=f"อนุมานจาก \"{d.value_text}\" ไม่ได้"))
            continue
        results.append(FieldDecision(field_key, d.status, value, None, reason=d.reason,
                                     evidence=list(d.evidence), reviewed_by=d.reviewed_by))
    if len({r.key for r in results if r.status != "not_found"}) > 1:
        for r in results:
            if r.status != "not_found":
                r.status, r.reviewed_by, r.reason = "needs_review", None, "ค่าต้นทางขัดกัน"
    return results


def decide_list(doc: DocText, field_key: str, item_type: str, located: ListLocated | None,
                max_items: int = 30) -> ListDecision:
    if located is None:
        return ListDecision(field_key, item_type, "not_found", NOT_FOUND)

    a, b = doc.trimmed(located.start, located.end)
    block = Evidence(a, b, located.location, "list_parser")
    items = [
        ItemDecision(i + 1, doc.readable(s, e), Evidence(s, e, located.location, "list_parser"))
        for i, (s, e) in enumerate(located.items)
    ]
    decision = ListDecision(field_key, item_type, "candidate", block=block, items=items)

    problems, notes = [], []
    if not items:
        problems.append("พบหัวข้อแต่แยกรายการไม่ได้")
    if doc.span_has_ocr(located.start, located.end):
        problems.append(REASON_OCR)
    if items and suspect_encoding(" ".join(i.text for i in items), min_count=3):
        problems.append(REASON_ENCODING)
    if len(items) > max_items:
        problems.append(f"จำนวนรายการมากผิดปกติ ({len(items)})")
    if located.irregular_numbering:
        problems.append("เลขข้อในเอกสารข้ามหรือซ้ำ ต้องตรวจการแบ่งรายการ")
    if located.items_method == "paragraph" and items:
        notes.append("ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว")

    if problems:
        decision.status = "needs_review"
    decision.reason = "; ".join(problems + notes) or None
    return decision


def consolidate_course(extractions: list) -> None:
    """
    เทียบค่าระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน (ฉบับเต็มกับใบสรุป)

    ค่าตรงกันตั้งแต่สองไฟล์ขึ้นไป: ยกระดับ candidate เป็น verified (auto:documents_agree)
    ค่าไม่ตรงกัน: ทุกค่าที่เกี่ยวข้องเป็น needs_review ไม่เลือกค่าใดค่าหนึ่งให้
    """
    if len(extractions) < 2:
        return

    scalar_keys = {d.field_key for ex in extractions for d in ex.scalars}
    for field_key in sorted(scalar_keys):
        per_doc = [[d for d in ex.scalars if d.field_key == field_key] for ex in extractions]
        # เล่มที่ค่าขัดกันเองอยู่แล้วไม่นำมาเทียบ (เป็น needs_review อยู่แล้ว)
        valued = [(i, ds[0]) for i, ds in enumerate(per_doc)
                  if len(ds) == 1 and ds[0].status in ("candidate", "verified")]
        if len(valued) < 2:
            continue
        keys = {d.key for _, d in valued}
        if len(keys) > 1:
            shown = " | ".join(d.shown for _, d in valued)
            for _, d in valued:
                d.status, d.reviewed_by = "needs_review", None
                d.reason = f"ค่าไม่ตรงกันระหว่างเอกสารของหลักสูตรเดียวกัน: {shown}"
        else:
            for _, d in valued:
                if d.status == "candidate":
                    d.status, d.reviewed_by = "verified", AUTO_DOCUMENTS
                    d.reason = "ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน"

    list_keys = {d.field_key for ex in extractions for d in ex.lists}
    for field_key in sorted(list_keys):
        valued = [d for ex in extractions for d in ex.lists
                  if d.field_key == field_key and d.status in ("candidate", "verified") and d.items]
        if len(valued) < 2:
            continue
        if len({d.key for d in valued}) > 1:
            for d in valued:
                d.status, d.reviewed_by = "needs_review", None
                d.reason = "รายการไม่ตรงกันระหว่างเอกสารของหลักสูตรเดียวกัน"
        else:
            for d in valued:
                if d.status == "candidate":
                    d.status, d.reviewed_by = "verified", AUTO_DOCUMENTS
                    d.reason = "รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน"
