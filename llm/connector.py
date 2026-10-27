"""
Local LLM Connector — item 4 ของ requirement

เชื่อมต่อกับ Qwen / Llama ที่รันผ่าน Ollama (http://localhost:11434) แบบ
framework-agnostic (ไม่ผูกกับ FastAPI) ใช้ได้ทั้งจาก backend, pipeline,
notebook หรือ batch job อื่นๆ

ทำไมเลือก Ollama:
  - รองรับทั้ง /api/chat (LLM) และ /api/embeddings (embedding model) ในตัวเดียว
  - โมเดล gguf ของ Qwen2.5 / Llama3.x โหลดผ่าน `ollama pull` ได้ตรงๆ
  - ถ้าอยากเปลี่ยนไปใช้ vLLM/llama.cpp server ในอนาคต แก้แค่คลาสนี้ที่เดียว
    (ทุกที่ที่เรียกใช้งานผ่าน interface เดียวกันอยู่แล้ว)

SECURITY:
  - Local LLM endpoint ควร bind 127.0.0.1 หรืออยู่ใน internal network เท่านั้น
    (ดู docker-compose.yml) — ไม่ควร expose ตรงสู่ internet เพราะไม่มี auth
    ในตัว Ollama เอง
  - timeout ทุก request กันกรณีโมเดลค้าง/เครื่อง local โหลดหนักจน backend hang
  - ไม่ log เนื้อหา prompt/response แบบเต็มที่ INFO level เพราะอาจมี PII จาก
    user profile ปนอยู่ (log แค่ length/metadata พอ)
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("llm.connector")


class LLMConnectionError(RuntimeError):
    """
    โมเดล local ต่อไม่ได้ / timeout / ตอบผิดรูปแบบ

    `user_text` คือข้อความที่ "เขียนไว้ให้ผู้ใช้อ่าน" โดยเฉพาะ · ผู้เรียกฝั่งเว็บต้องส่ง
    ค่านี้ต่อให้ผู้ใช้ ไม่ใช่ str(exc) เพราะข้อความของ exception หลายตัวมีรายละเอียด
    วินิจฉัยต่อท้าย เช่น "ollama returned 500: {body}" หรือ "gemini ล้มเหลวหลังลอง 3
    ครั้ง: {last_exc}" ซึ่งไม่ได้เขียนให้ผู้ใช้อ่านและอาจพาเนื้อหาจากปลายทางออกมาด้วย
    (เจอจากการทดสอบ n1-05 เมื่อ 14 ต.ค. 2569: ผู้ใช้เห็นข้อความภายในของตัวเชื่อมต่อ)

    ไม่ตั้งค่านี้ = ไม่มีข้อความที่เขียนให้ผู้ใช้ ให้ผู้เรียกใช้ข้อความกลางของตัวเอง
    """

    def __init__(self, *args, user_text: str | None = None) -> None:
        super().__init__(*args)
        self.user_text = user_text


class LLMBudgetExceeded(LLMConnectionError):
    """
    คำขอนี้ใช้เวลารวมเกินเพดานที่ตั้งไว้ — หยุดลองต่อแล้วบอกผู้ใช้ว่าบริการขัดข้อง

    สืบทอดจาก LLMConnectionError เพื่อให้ผู้เรียกเดิมที่ดักจับชนิดนั้นอยู่แล้วรับมือได้
    เหมือนเดิม (ตอบข้อความบริการขัดข้อง ไม่เดาข้อมูล)
    """


# เพดานเวลารวมต่อหนึ่งคำขอที่ต้องใช้โมเดล นับรวมทุกอย่าง: การลองซ้ำ การพักรอ cooldown
# และการไล่โมเดลสำรอง
#
# ทำไมต้องเป็นเพดาน "รวม" ไม่ใช่ timeout ต่อครั้ง: 13 ต.ค. 2569 คำขอหนึ่งใช้เวลา 408
# วินาที โดยที่ timeout ต่อครั้งตั้งไว้แค่ 120 วินาที เพราะเวลาจริงเกิดจากการบวกกันของ
# การลองซ้ำสามครั้ง การไล่สี่โมเดล และการพักรอ cooldown — ไม่มีใครเกินเพดานของตัวเอง
# แต่ผู้ใช้รอเกือบเจ็ดนาที
_DEFAULT_BUDGET_S = float(os.getenv("RAG_TIME_BUDGET_S", "30"))

# เวลาที่คำขอปัจจุบันต้องจบ (เวลาแบบ monotonic) · None = ไม่จำกัด
_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "llm_request_deadline", default=None
)


def start_budget(seconds: float | None = None) -> float | None:
    """
    เริ่มนับเพดานเวลาของคำขอนี้ คืน "เวลาสิ้นสุด" (monotonic) หรือ None ถ้าไม่จำกัด

    ใช้ ContextVar เพราะแต่ละคำขอของ FastAPI ทำงานในบริบทของตัวเอง ค่าจึงไม่รั่ว
    ข้ามคำขอ และไม่ต้องส่งพารามิเตอร์ผ่านทุกชั้นของการเรียก

    **คืนค่าเป็นเวลาสิ้นสุด ไม่ใช่ token ของ ContextVar** — ตั้งใจเปลี่ยนจากแบบ token
    เพราะ token ใช้ได้เฉพาะในบริบทเดียวกับที่สร้าง แต่ stream_answer เป็น generator
    ที่ Starlette ปั๊มทีละ step ผ่าน threadpool และแต่ละ step ได้บริบท "สำเนาใหม่"
    ของคำขอ · ผลคือ reset ด้วย token ที่สร้างใน step แรกได้ ValueError
    ("was created in a different Context") ทุกคำขอ และค่าที่ตั้งไว้ก็มองไม่เห็น
    ข้าม step ทำให้เพดานเวลาไม่ถูกบังคับระหว่างสตรีมอยู่ดี
    เจอจากการรันชุดทดสอบผ่าน /chat-web จริงเมื่อ 14 ต.ค. 2569 — ล้มทั้ง 19/19 คำขอ
    ตัวเลขเวลาสิ้นสุดส่งต่อข้ามบริบทได้ จึงใช้ apply_budget() ตั้งซ้ำทุก step ได้
    """
    budget = _DEFAULT_BUDGET_S if seconds is None else seconds
    deadline = None if budget <= 0 else time.monotonic() + budget
    _deadline.set(deadline)
    return deadline


def apply_budget(deadline: float | None) -> None:
    """
    ตั้งเวลาสิ้นสุดเดิมในบริบทปัจจุบัน — เรียกทุกครั้งที่งานอาจย้ายบริบท

    ใช้กับ generator ที่ถูกปั๊มทีละ step (ดู stream_answer) เพื่อให้ทุก step
    เห็นเพดานเดียวกัน · เรียกซ้ำได้ ไม่ขยับเวลาสิ้นสุด เพราะรับค่าสัมบูรณ์เข้ามา
    """
    _deadline.set(deadline)


def reset_budget(_deadline_value=None) -> None:
    """
    เลิกบังคับเพดานในบริบทปัจจุบัน

    รับค่าที่ start_budget() คืนมาได้เพื่อให้ผู้เรียกเดิมเขียนเหมือนเดิม แต่ไม่ใช้ค่านั้น
    — ล้างเป็น None ตรงๆ เพราะไม่มีการตั้งเพดานซ้อนกันในระบบนี้ และการล้างแบบนี้
    ทำได้จากทุกบริบท ไม่ผูกกับบริบทที่สร้าง
    """
    _deadline.set(None)


def budget_left_s() -> float | None:
    """เหลือเวลาอีกกี่วินาที · None = ไม่ได้ตั้งเพดานไว้"""
    end = _deadline.get()
    return None if end is None else end - time.monotonic()


def check_budget(doing: str) -> None:
    """โยน LLMBudgetExceeded ถ้าหมดเวลาแล้ว · เรียกก่อนเริ่มงานที่กินเวลาทุกครั้ง"""
    left = budget_left_s()
    if left is not None and left <= 0:
        raise LLMBudgetExceeded(
            "ระบบใช้เวลาตอบเกินเพดานที่ตั้งไว้ขณะที่ผู้ให้บริการโมเดลขัดข้อง "
            f"จึงหยุดรอ (ขั้นที่กำลังทำ: {doing})",
            user_text="ระบบใช้เวลาตอบนานเกินเพดานที่ตั้งไว้ จึงหยุดรอครับ "
                      "ตอนนี้ผู้ให้บริการโมเดลขัดข้อง รบกวนลองใหม่อีกครั้งในอีกสักครู่",
        )


# เผื่อเวลาให้ปลายทางปิดการเชื่อมต่อและให้เราคืนคำตอบได้ทัน ไม่ตั้ง timeout เท่าที่เหลือพอดี
_BUDGET_SLACK_S = 0.5


def http_timeout(default_s: float, doing: str) -> float:
    """
    เวลาที่ยอมให้คำขอ HTTP ครั้งนี้ใช้ — ไม่เกินเวลาที่เหลือของคำขอทั้งหมด

    **จำเป็นต่อการบังคับเพดานจริง** การตรวจ check_budget ก่อนยิงอย่างเดียวไม่พอ
    เพราะถ้าปลายทางค้าง คำขอนั้นจะใช้เวลาตาม timeout ของตัวเอง (120 วินาที) ต่อไป
    ทั้งที่เพดานรวมเหลืออีกไม่กี่วินาที — ผู้ใช้จึงยังรอเกินเพดานอยู่ดี

    โยน LLMBudgetExceeded ทันทีถ้าเวลาหมดแล้ว
    """
    check_budget(doing)
    left = budget_left_s()
    if left is None:
        return default_s
    return max(min(default_s, left - _BUDGET_SLACK_S), 0.2)


def post_json_bounded(client: httpx.Client, path: str, payload: dict[str, Any], *,
                      timeout_s: float, doing: str) -> dict[str, Any]:
    """
    ยิง POST แล้วอ่านคำตอบแบบสตรีม พร้อมตรวจเพดานเวลารวมทุกก้อนที่อ่านได้

    **ทำไมไม่ใช้ client.post() ตรงๆ**
    timeout ของ httpx เป็น "เวลารอข้อมูลก้อนถัดไป" ไม่ใช่เวลารวมของคำขอ ถ้าปลายทาง
    ทยอยส่งข้อมูลเรื่อยๆ แต่ไม่ยอมจบ read timeout จะไม่เคยชน และคำขอค้างไม่จำกัดเวลา
    ทั้งที่ตั้งเพดานรวมไว้แล้ว — เป็นช่องเดียวกับที่เคยทำให้เส้นทางสตรีมพลาด แต่ฝั่ง
    "ไม่สตรีม" (ขั้นเขียนคำถามใหม่ ขั้นตรวจเอกสาร การฝังเวกเตอร์) ยังเหลืออยู่

    เจอจริง 14 ต.ค. 2569: ชุดทดสอบ /chat-web ยิงไปที่เซิร์ฟเวอร์ที่ส่งข้อมูลทุก 0.25
    วินาทีไม่หยุด คำขอค้างเกินสิบนาทีโดยเพดาน 6 วินาทีไม่ทำงานเลย

    การอ่านทีละก้อนทำให้มีจุดตรวจเพดานถี่เท่าที่ข้อมูลเข้ามา กรณีที่ปลายทางเงียบสนิท
    ยังอาศัย read timeout ซึ่ง http_timeout() จำกัดไว้ไม่เกินเวลาที่เหลืออยู่แล้ว
    """
    with client.stream("POST", path, json=payload,
                       timeout=http_timeout(timeout_s, doing)) as resp:
        if resp.status_code >= 400:
            # ต้องอ่าน body ให้จบก่อน ไม่งั้นข้อความอธิบายข้อผิดพลาดอ่านไม่ได้
            resp.read()
            resp.raise_for_status()
        buf = bytearray()
        for raw in resp.iter_bytes():
            check_budget(doing)
            buf += raw
    return json.loads(bytes(buf) or b"{}")


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class OllamaConnector:
    base_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen2.5:7b"
    embed_model: str = "nomic-embed-text"
    timeout_s: int = 120
    max_retries: int = 2
    _client: httpx.Client = field(init=False, repr=False)

    # เพดานความยาวคำตอบที่ผู้เรียกควรใช้กับโมเดลนี้ — ดูเหตุผลที่ answer_token_cap
    # ของ GeminiConnector ว่าทำไมแต่ละเจ้าต้องใช้ค่าไม่เท่ากัน
    answer_token_cap: int = 400

    # ขนาดหน้าต่างบริบทที่สั่ง Ollama ให้ใช้
    #
    # ต้องสั่งเอง เพราะค่าเริ่มต้นของ Ollama คือ 2,048 โทเคน ไม่ว่าโมเดลจะรองรับได้
    # เท่าไหร่ก็ตาม (qwen2.5 รองรับ 32,768) และเมื่อพรอมต์ยาวเกิน มันจะ "ตัดทิ้งเงียบๆ"
    # ไม่มี error ไม่มีคำเตือน
    #
    # วัดจริงบนเซิร์ฟเวอร์: ส่งเนื้อหาเข้าไป 4,926 โทเคน Ollama รายงานว่าอ่าน 2,050
    # แปลว่าเนื้อหาหายไปกว่าครึ่งก่อนโมเดลได้เห็น qwen2.5:3b จึงตอบว่า "ข้อมูลที่ให้มา
    # ไม่มีรายละเอียด" ซึ่งเป็นความจริงจากมุมของมัน — คำตอบอยู่ในส่วนที่ถูกตัดไปแล้ว
    #
    # ผลคือคุณภาพของโมเดลสำรองถูกประเมินต่ำกว่าความเป็นจริงมาโดยตลอด และคำตอบผิด
    # บางครั้งอาจมาจากการเห็นเอกสารไม่ครบ ไม่ใช่จากความสามารถของโมเดล
    #
    # ต้องตั้งเป็นสองเท่าของจำนวนโทเคนที่ต้องการให้อ่านจริง เพราะ Ollama แบ่งหน้าต่าง
    # ครึ่งหนึ่งไว้ให้คำตอบเสมอ วัดด้วยพรอมต์ยาว 98,100 ตัวอักษรกับ qwen2.5:1.5b:
    #
    #     สั่ง num_ctx  4,096  ->  อ่านพรอมต์ได้  2,050 โทเคน
    #     สั่ง num_ctx  8,192  ->  อ่านพรอมต์ได้  4,098 โทเคน
    #     สั่ง num_ctx 16,384  ->  อ่านพรอมต์ได้  8,194 โทเคน
    #
    # พรอมต์จริงที่ 25 chunk ยาวราว 20,500 ตัวอักษร คิดเป็นราว 10,000 โทเคนสำหรับ
    # ภาษาไทย จึงต้องตั้งอย่างน้อย 21,000 — ค่า 8,192 ที่ลองก่อนหน้ายังตัดเนื้อหาทิ้ง
    # กว่าครึ่ง และตัดแบบเงียบๆ ไม่มี error ให้เห็น
    #
    # ขนาดพรอมต์จริงกรณีหนักสุด นับจากส่วนประกอบทั้งหมดที่ส่งเข้าโมเดล:
    #
    #     เนื้อหา 25 ชิ้น (เฉลี่ยชิ้นละ 782 ตัวอักษร)   19,550 ตัวอักษร
    #     หัวข้อกำกับแต่ละชิ้น                            3,000
    #     คำสั่งระบบ                                      3,556
    #     ประวัติสนทนา 6 ข้อความ                          2,400
    #     รวม                                            28,506 ตัวอักษร ≈ 14,253 โทเคน
    #
    # ต้องการหน้าต่างอย่างน้อย 28,506 จึงตั้งเต็มที่โมเดลรองรับ (qwen2.5 = 32,768)
    # การตั้งต่ำกว่านี้ทำให้เนื้อหาถูกตัดทิ้งโดยไม่มีสัญญาณใดๆ ซึ่งเป็นความผิดพลาด
    # ชนิดที่มองไม่เห็นจากคำตอบ — โมเดลจะบอกว่า "ไม่มีข้อมูล" อย่างสุจริต เพราะมัน
    # ไม่ได้รับข้อมูลนั้นมาจริงๆ
    #
    # ถ้าเปลี่ยนไปใช้โมเดลที่รองรับหน้าต่างเล็กกว่านี้ ต้องลดจำนวนเนื้อหาต่อคำถาม
    # (CHAT_TOP_K) ลงตามด้วย ไม่ใช่ปล่อยให้ถูกตัดเอง
    num_ctx: int = 32768

    def __post_init__(self) -> None:
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout_s)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def embed(self, text: str) -> list[float]:
        payload = {"model": self.embed_model, "prompt": text}
        data = self._post_with_retry("/api/embeddings", payload)
        embedding = data.get("embedding")
        if not embedding:
            raise LLMConnectionError(f"embedding response missing 'embedding' field: {data!r}"[:200])
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Ollama /api/embeddings รับทีละข้อความ — วน loop ฝั่ง client
        # (ถ้าต้องการ throughput สูงกว่านี้ ค่อยสลับไปใช้ sentence-transformers
        # ที่รองรับ true batch บน GPU local แทน)
        return [self.embed(t) for t in texts]

    # ------------------------------------------------------------------
    # Chat / generation
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        json_mode: bool = False,
        num_predict: int | None = None,
    ) -> str:
        options: dict[str, Any] = {"temperature": temperature, "num_ctx": self.num_ctx}
        if num_predict is not None:
            options["num_predict"] = num_predict
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"  # Ollama บังคับ valid JSON output

        data = self._post_with_retry("/api/chat", payload)
        message = data.get("message", {})
        content = message.get("content")
        if content is None:
            raise LLMConnectionError(f"chat response missing content: {data!r}"[:200])
        return content

    def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        num_predict: int | None = None,
    ) -> Iterator[str]:
        """
        เหมือน chat() แต่ทยอยคืนข้อความทีละส่วนระหว่างที่โมเดลกำลังเขียน

        มีไว้เพื่อลด "เวลารอที่รู้สึกได้" ไม่ใช่เวลารวม — เซิร์ฟเวอร์ที่รันด้วย CPU
        เขียนได้ราว 8 โทเคน/วินาที คำตอบยาว 250 โทเคนจึงใช้เวลาราว 30 วินาที
        ถ้ารอจนจบค่อยส่ง ผู้ใช้จะเห็นแต่หน้าจอว่างตลอด 30 วินาทีนั้น

        ไม่มีการลองใหม่เหมือน _post_with_retry เพราะเมื่อส่งข้อความบางส่วนออกไปแล้ว
        การเริ่มใหม่จะทำให้ผู้ใช้เห็นคำตอบซ้ำสองรอบ ความล้มเหลวกลางคันจึงต้องโยน
        ออกไปให้ผู้เรียกตัดสินใจแทน
        """
        options: dict[str, Any] = {"temperature": temperature, "num_ctx": self.num_ctx}
        if num_predict is not None:
            options["num_predict"] = num_predict
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": options,
        }
        try:
            with self._client.stream(
                "POST", "/api/chat", json=payload,
                timeout=http_timeout(self.timeout_s, "เริ่มสตรีมจากโมเดลในเครื่อง"),
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    # ต้องตรวจทุกชิ้น ไม่ใช่พึ่ง read timeout อย่างเดียว — สตรีมที่ทยอย
                    # ส่งข้อมูลเรื่อย ๆ จะไม่เคยชน read timeout เลย แต่ยืดเวลารวมได้ไม่จำกัด
                    check_budget("อ่านสตรีมจากโมเดลในเครื่อง")
                    if not line:
                        continue
                    data = json.loads(line)
                    if chunk := data.get("message", {}).get("content"):
                        yield chunk
                    if data.get("done"):
                        return
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            raise LLMConnectionError(f"chat_stream failed: {type(e).__name__}: {e}"[:200]) from e

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            # โมเดลในเครื่องเป็นขั้นที่ช้าที่สุดของระบบ (วัดได้ 120 วินาทีต่อครั้งเมื่อ
            # ต้องโหลดโมเดลเข้าหน่วยความจำ) จึงต้องเคารพเพดานเวลารวมของคำขอด้วย
            try:
                return post_json_bounded(
                    self._client, path, payload, timeout_s=self.timeout_s,
                    doing=f"เรียกโมเดลในเครื่อง {path}",
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                logger.warning("ollama %s attempt %d/%d failed: %s", path, attempt, self.max_retries + 1, type(e).__name__)
            except httpx.HTTPStatusError as e:
                # 4xx/5xx จาก Ollama เอง (เช่น model ไม่ถูก pull ไว้) — ไม่ retry ซ้ำ ให้ fail ทันที
                raise LLMConnectionError(f"ollama returned {e.response.status_code}: {e.response.text[:300]}") from e
        raise LLMConnectionError(f"could not reach local LLM at {self.base_url}{path}") from last_exc

    def close(self) -> None:
        self._client.close()
