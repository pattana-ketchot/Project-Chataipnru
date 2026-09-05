/**
 * แถบเมนูที่ใช้ร่วมกันทุกหน้า
 *
 * เดิมแถบเมนูเขียนอยู่ในหน้าแรกหน้าเดียว หน้า /match กับ /compare จึงไม่มีเมนูเลย
 * เข้าไปแล้วออกไปไหนต่อไม่ได้นอกจากกดปุ่มย้อนกลับของเบราว์เซอร์
 *
 * ทำไมรับ onNavigate เข้ามาแทนที่จะใช้ลิงก์อย่างเดียว
 * -------------------------------------------------
 * หน้าแรกเป็นหน้าเดียวที่สลับเนื้อหาด้วย state ภายใน (แบบสอบถาม/แชท/รายการหลักสูตร
 * เป็น view ไม่ใช่ route) ถ้าบังคับให้ทุกที่ใช้ลิงก์ การกดเมนูบนหน้าแรกจะกลายเป็นการ
 * โหลดหน้าใหม่ทั้งหน้าและเสียสถานะบทสนทนาที่คุยค้างไว้
 *
 * จึงให้หน้าแรกส่งฟังก์ชันสลับ view เข้ามา ส่วนหน้าอื่นไม่ต้องส่ง แล้วเมนูจะใช้ลิงก์
 * พร้อม ?view= ให้หน้าแรกอ่านไปเปิดหน้าที่ถูกต้องเอง
 */
import Link from "next/link";
import { Logo } from "@/components/logo";

/** ป้ายเมนู, view ที่ตรงกับหน้าแรก (null = เป็น route ของตัวเอง), ที่อยู่ */
const ITEMS: [string, string | null, string][] = [
  ["หน้าแรก", "home", "/"],
  ["หลักสูตรทั้งหมด", "courses", "/?view=courses"],
  ["แบบสอบถาม", "survey", "/?view=survey"],
  ["คุยกับที่ปรึกษา", "chat", "/?view=chat"],
  ["ค้นหาสาขาที่เหมาะกับฉัน", null, "/match"],
  ["เปรียบเทียบสาขา", null, "/compare"],
];

export function SiteNav({ active, onNavigate, right }: {
  /** view ของหน้าแรก หรือ path ของหน้าอื่น เช่น "/match" */
  active?: string;
  /** ส่งมาเฉพาะจากหน้าแรก เพื่อสลับ view โดยไม่โหลดหน้าใหม่ */
  onNavigate?: (view: string) => void;
  /** ปุ่มมุมขวา เช่น เข้าสู่ระบบ/ออกจากระบบ — หน้าทดสอบไม่มี */
  right?: React.ReactNode;
}) {
  return <header className="sticky top-0 z-20 border-b border-ink/10 bg-sage text-white">
    <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-3">
      <Link href="/" aria-label="กลับหน้าแรก"><Logo/></Link>
      <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm font-bold">
        {ITEMS.map(([label, view, href]) => {
          const cls = (active === view || active === href)
            ? "border-b-2 border-lime pb-0.5"
            : "text-white/80 hover:text-white";
          return view && onNavigate
            ? <button key={label} className={cls} onClick={() => onNavigate(view)}>{label}</button>
            : <Link key={label} className={cls} href={href}>{label}</Link>;
        })}
      </nav>
      {right && <div className="ms-auto">{right}</div>}
    </div>
  </header>;
}
