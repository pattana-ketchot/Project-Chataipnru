/**
 * ตัวเรียก API ของคิวตรวจไฟล์หลักสูตร (Phase 3B)
 *
 * เรียกเส้นทางที่ Phase 3A ทำไว้แล้วทั้งหมด ไม่ได้เพิ่มเส้นทางใหม่
 * ส่วนรายชื่อหลักสูตรใช้ GET /courses เดิมที่ lib/api.ts มีอยู่แล้ว
 *
 * ทำไมไม่มี staging_path ในไฟล์นี้เลย
 * ---------------------------------
 * backend ไม่ส่งมาให้โดยเจตนา (ดู db/migrations/004_crawl_decisions.sql) และหน้าเว็บ
 * ก็ไม่ควรรู้ที่อยู่ไฟล์บนเซิร์ฟเวอร์ การเปิดไฟล์ทำด้วย id เท่านั้น
 * ที่นี่จึงไม่มีที่ใดประกอบ path ของไฟล์เองแม้แต่จุดเดียว
 */
import { apiFetch } from "./api";

/** หนึ่งรายการในคิว — ตรงกับ QueueItem ใน backend/app/schemas/crawl_review.py */
export type QueueItem = {
  id: string;
  source_url: string;
  page_url: string | null;
  page_title: string | null;
  link_text: string | null;
  course_code: string | null;
  course_label: string | null;
  match_confidence: "high" | "medium" | "ambiguous" | "unknown" | null;
  match_score: number | null;
  match_candidates: string[];
  needs_review: boolean;
  review_reason: string | null;
  status: string;
  content_length: number | null;
  file_sha256: string | null;
  previous_sha256: string | null;
  has_staged_file: boolean;
  last_checked_at: string | null;
  first_seen_at: string;
};

export type QueueCounts = {
  total: number;
  needs_review: number;
  ambiguous: number;
  with_staged_file: number;
};

export type QueuePage = { counts: QueueCounts; items: QueueItem[] };

export type Decision = {
  id: string;
  crawl_source_id: string;
  file_sha256: string;
  decision: "approve" | "ignore";
  decided_by: string;
  decided_at: string;
  note: string | null;
  course_code: string | null;
  course_title: string | null;
  superseded_at: string | null;
  ingest_finished_at: string | null;
  document_id: string | null;
};

const base = "/crawl-review";

export const review = {
  pending: (token: string) => apiFetch<QueuePage>(`${base}/pending`, {}, token),

  /**
   * อนุมัติ — ต้องส่ง file_sha256 ที่เห็นบนหน้าจอกลับไปด้วย
   *
   * เป็นตัวล็อกแบบ optimistic ตาม Phase 3A ถ้า crawler โหลดไฟล์ใหม่ทับระหว่างที่
   * ผู้ดูแลกำลังเปิดดูอยู่ backend จะตอบ 409 แล้วหน้าเว็บต้องให้คนดูไฟล์ใหม่
   * ห้ามส่งซ้ำอัตโนมัติ
   */
  approve: (token: string, id: string, body: { file_sha256: string; course_code: string; note?: string }) =>
    apiFetch<Decision>(`${base}/${id}/approve`, { method: "POST", body: JSON.stringify(body) }, token),

  ignore: (token: string, id: string, body: { file_sha256: string; reason: string }) =>
    apiFetch<Decision>(`${base}/${id}/ignore`, { method: "POST", body: JSON.stringify(body) }, token),

  undo: (token: string, id: string, body: { file_sha256: string }) =>
    apiFetch<Decision>(`${base}/${id}/undo`, { method: "POST", body: JSON.stringify(body) }, token),

  /** ที่อยู่สำหรับเปิดไฟล์ในคิว — ประกอบจาก id เท่านั้น ไม่มี path ของไฟล์จริงเกี่ยวข้อง */
  pdfPath: (id: string) => `${base}/${id}/pdf`,
};

/** คำอธิบายความมั่นใจของการจับคู่หลักสูตร */
export const CONFIDENCE_TEXT: Record<string, string> = {
  high: "ตรงชัดเจน",
  medium: "ค่อนข้างตรง",
  ambiguous: "กำกวม ต้องเลือกเอง",
  unknown: "ระบุไม่ได้ ต้องเลือกเอง",
};

/** สาขาที่ระบบจับคู่ไม่ชัด ผู้ดูแลต้องเลือกหลักสูตรเองก่อนอนุมัติ */
export function mustChooseCourse(item: QueueItem): boolean {
  return item.match_confidence === "ambiguous" || item.match_confidence === "unknown"
    || !item.course_code;
}

export function formatBytes(n: number | null): string {
  if (n == null) return "ไม่ทราบขนาด";
  if (n < 1024) return `${n} ไบต์`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
