import { Compass } from "lucide-react";
export function Logo() { return <div className="flex items-center gap-2 font-black tracking-tight">{/* บังคับสีไอคอนเป็นสีเข้ม ไม่ให้รับสีจากพื้นหลัง — โลโก้อยู่บนแถบเมนูสีเขียวที่
      ตัวอักษรเป็นสีขาว ถ้าปล่อยให้สืบทอดมาจะกลายเป็นขาวบนพื้นเขียวอ่อนจนแทบมองไม่เห็น */}
    <span className="grid h-9 w-9 place-items-center rounded-full bg-lime text-ink"><Compass size={20}/></span>Course Compass</div>; }
