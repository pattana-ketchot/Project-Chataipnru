export type User = { id: string; email: string; full_name: string | null; created_at: string };
export type Profile = { education_level: string | null; field_of_study: string | null; current_role: string | null; career_goal: string | null; skills: string[]; interests: string[]; language_preference: string; updated_at?: string | null };
export type Requirement = { id: string; req_type: string; req_value: string; priority: number; created_at: string };
export type Course = { id: string; code: string | null; title: string; provider: string | null; summary: string | null; mode: string | null; duration_weeks: number | null; price: number | null; currency: string; tags: string[] };
export type Recommendation = { course: Course; score: number; rationale: string; cited_chunk_ids: string[] };
export type RecommendResponse = { session_id: string; model_used: string; generated_at: string; recommendations: Recommendation[] };
export type ChatCitation = { chunk_id: string; course_id: string; course_title: string; page_number: number | null; score: number };
export type ChatReply = { session_id: string; reply: string; search_query: string; top_score: number; status: "answered" | "not_found" | "out_of_scope" | "small_talk"; in_scope: boolean; citations: ChatCitation[] };
/** ข้อความหนึ่งบรรทัดในหน้าจอสนทนา (ฝั่ง client เท่านั้น) */
export type ChatTurn = { role: "user" | "assistant"; content: string; citations?: ChatCitation[]; inScope?: boolean };
