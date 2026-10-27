# C1 — ผลตรวจหลักฐานขั้นสุดท้ายและการตัดสินใจ

> **READ-ONLY** — ไม่แก้ production · ไม่ apply migration · ไม่ `REVOKE` · ไม่ deploy · ไม่ restart · ไม่ push/merge
> **ไม่ทดสอบเลื่อนสิทธิ์ด้วยการเขียนฐานข้อมูลจริง** — วิเคราะห์จากโค้ดและกฎเท่านั้น

| รายการ | ค่า |
|---|---|
| วันที่ | 11 ตุลาคม 2569 |
| แทนที่ | `C1_RLS_RECONCILED_SECURITY_REVIEW.md` ในส่วนที่ยังเป็นสมมติฐาน |
| สถานะ | **`GO`** — ไม่เหลือเงื่อนไขที่บล็อก · เหลือการตัดสินใจเรื่องบัญชีทดสอบ |
| ปรับปรุง | 11 ต.ค. 2569 — ผลตรวจ view dependency · แผนทดสอบสิทธิ์ · ownership · **ผลตรวจบัญชี `editor`** |

---

## อ่านแบบเร็ว — สรุปภาษาง่าย ๆ

### ตรวจอะไรไปแล้ว

ได้โค้ดจริงของตัวกันสิทธิ์ในฐานข้อมูล Supabase มาอ่านแล้ว จากไฟล์ที่เจ้าของ export ไว้ 4 ไฟล์ — ได้ทั้งโค้ดฟังก์ชัน ตัวกระตุ้น (trigger) และกฎการแก้ไขข้อมูล

### พบอะไร

**ข่าวดีที่สุด — ตัวกันทำงานได้จริง**
เรื่องที่กังวลที่สุดคือผู้ใช้ทั่วไปอาจแก้ข้อมูลตัวเองให้กลายเป็นผู้ดูแล · **อ่านโค้ดแล้วยืนยันว่ากันได้จริง** ตัวกันตรวจทั้ง `role` และ `status` ถ้าใครที่ไม่ใช่ผู้ดูแลพยายามแก้ จะถูกปฏิเสธพร้อมข้อความแจ้งเตือน ไม่ใช่แค่เตือนแล้วปล่อยผ่าน

**ข่าวดีที่สอง — ปัญหาที่กลัวว่าจะทำให้ระบบล่ม ไม่เกิดแน่นอน**
กังวลว่าการแก้กฎการอ่านจะทำให้ระบบวนซ้ำไม่รู้จบ · ตอนนี้**พิสูจน์ได้จากของจริง** เพราะตัวกันที่ใช้งานอยู่ทุกวันนี้ใช้วิธีเดียวกันเป๊ะและไม่เคยมีปัญหา

**เรื่องที่ยังต้องแก้ — ตารางนี้ยังใครก็อ่านได้**
กฎชื่อ `Public profiles are viewable by everyone` ยังเปิดให้อ่านอีเมลและชื่อจริงของทุกคนแม้ไม่ล็อกอิน **นี่คือสิ่งที่เตรียมจะแก้**

**เรื่องที่ควรแก้ทีหลัง 2 เรื่อง**
สิทธิ์ `TRUNCATE` (ล้างข้อมูลทั้งตาราง) ให้ไว้กว้างเกินจำเป็น · และตัวกันมีช่องยกเว้นสำหรับงานฝั่งเซิร์ฟเวอร์ที่พึ่งพากฎอีกชั้นเพียงชั้นเดียว

### ยังไม่ได้แก้อะไรเลย

**ไม่มีการเปลี่ยนแปลงใด ๆ บน production** เอกสารนี้เป็นการอ่านและวิเคราะห์เท่านั้น

**ข่าวดีเพิ่มเติม — ตรวจทางอ้อมแล้วไม่พบอะไร**
เคยกังวลว่าอาจมี view หรือฟังก์ชันอื่นที่อ่านตารางนี้อ้อมไป ซึ่งจะทำให้แก้แล้วข้อมูลยังรั่วอยู่ · **ตรวจแล้วไม่พบเลย** จึงมั่นใจได้ว่าการแก้จะปิดช่องได้จริง

**เรื่องบัญชี `editor` — ตรวจแล้วกลับกลายเป็นข่าวดี**
เคยกังวลว่าไม่มีบัญชี `editor` ไว้ทดสอบ · ตรวจแล้วพบว่า **ไม่มีบัญชีแบบนี้ในระบบเลยแม้แต่คนเดียว** แปลว่า**ไม่มีใครที่จะได้รับผลกระทบจากการแก้ครั้งนี้** ความเสี่ยงจึงลดลง ไม่ใช่เพิ่มขึ้น

### ต้องการอะไรต่อ

**ไม่เหลือเงื่อนไขที่บล็อกแล้ว** เหลือแค่ตัดสินใจว่าจะสร้างบัญชีทดสอบขึ้นมาก่อนหรือจะแก้เลย — ทั้งสองทางยอมรับได้ ดูข้อ 8.5

---

## 1. ที่มาของหลักฐาน

พบไฟล์ที่เจ้าของ export จาก Supabase ไว้ที่โฟลเดอร์ดาวน์โหลด **4 ไฟล์**

| ไฟล์ | เนื้อหา | มี PII ไหม |
|---|---|---|
| `Supabase Snippet Untitled query.csv` | นิยาม `guard_user_profile_privileges()` | **ไม่มี** |
| `Supabase Snippet Untitled query (1).csv` | นิยาม `handle_new_user()` | **ไม่มี** |
| `Supabase Snippet Untitled query (2).csv` | trigger 3 ตัว | **ไม่มี** |
| `Supabase Snippet Untitled query (3).csv` | `UPDATE` policy 2 ตัว | **ไม่มี** |

ทุกไฟล์มีแต่โครงสร้างและกฎ **ไม่มีอีเมล ชื่อ หรือ `user_id` ของผู้ใช้คนใดเลย**

---

## 2. CONFIRMED — ยืนยันจากหลักฐานแล้ว

### 2.1 ✅ F1 ถูกกันได้จริง — ปิดเคส

```sql
CREATE OR REPLACE FUNCTION public.guard_user_profile_privileges()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN NEW;
  END IF;

  IF (NEW.role IS DISTINCT FROM OLD.role) OR (NEW.status IS DISTINCT FROM OLD.status) THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.user_profiles
      WHERE user_id = auth.uid() AND role = 'admin' AND status = 'approved'
    ) THEN
      RAISE EXCEPTION 'ไม่มีสิทธิ์เปลี่ยนแปลง role หรือ status ของผู้ใช้';
    END IF;
  END IF;

  RETURN NEW;
END;
$function$
```

ตรวจตามรายการที่ตั้งไว้ในรอบก่อน

| # | เกณฑ์ | ผล |
|---|---|---|
| 1 | เทียบ **ทั้ง** `role` **และ** `status` | **ผ่าน** — `(NEW.role IS DISTINCT FROM OLD.role) OR (NEW.status IS DISTINCT FROM OLD.status)` |
| 2 | ใช้ `IS DISTINCT FROM` ไม่ใช่ `<>` | **ผ่าน** — จัดการ `NULL` ถูกต้อง `<>` จะได้ `NULL` แล้วหลุด |
| 3 | ปฏิเสธจริง ไม่ใช่แค่เตือน | **ผ่าน** — `RAISE EXCEPTION` ยกเลิกทั้ง transaction |
| 4 | ตรวจว่าผู้แก้เป็น `admin` **และ** `approved` | **ผ่าน** |
| 5 | เป็น `BEFORE UPDATE FOR EACH ROW` | **ผ่าน** — ยืนยันจาก trigger definition |
| 6 | ครอบทุกเส้นทาง ไม่ใช่เฉพาะหน้าเว็บ | **ผ่าน** — เป็น trigger ระดับฐานข้อมูล ครอบทั้ง PostgREST และ SQL ตรง |

**สถานการณ์ที่กังวล — ผู้ใช้ทั่วไปเลื่อนตัวเองเป็น admin**

```
ผู้ใช้ล็อกอิน -> UPDATE แถวตัวเอง set role='admin'
  -> RLS policy "Users can update own profile" ผ่าน (auth.uid() = user_id)
  -> trigger guard ทำงาน
       auth.uid() ไม่เป็น NULL -> ไม่เข้าทางลัด
       role เปลี่ยน -> ตรวจว่าผู้แก้เป็น admin approved ไหม -> ไม่ใช่
       -> RAISE EXCEPTION -> ทั้ง transaction ถูกยกเลิก
```

> **F1 ไม่ใช่ช่องโหว่** — ลดจาก "วิกฤต" เป็น **"ถูกกันแล้ว"** โดยมีข้อสังเกตในข้อ 3.1

### 2.2 ✅ ไม่มีความเสี่ยง recursion — พิสูจน์ได้จากของจริง

ตัวกันที่ใช้งานอยู่**ทุกวันนี้** ทำสิ่งนี้อยู่แล้ว

```sql
SECURITY DEFINER + SELECT 1 FROM public.user_profiles  ->  ทำงานปกติ ไม่เคย recursion
```

ประกอบกับ `rls_forced = false` ที่เจ้าของยืนยัน แปลว่า `SECURITY DEFINER` ข้าม RLS ได้จริงในฐานข้อมูลนี้

**ฟังก์ชันที่เราจะสร้าง (`c1_is_approved_staff`) ใช้รูปแบบเดียวกันเป๊ะ จึงปลอดภัยแน่นอน** — ไม่ใช่การคาดเดาจากทฤษฎี แต่เป็นรูปแบบที่ระบบนี้ใช้อยู่และทำงานได้

### 2.3 ✅ `handle_new_user()` ตั้งค่าเริ่มต้นปลอดภัย

```sql
INSERT INTO public.user_profiles (user_id, role, full_name, email)
VALUES (NEW.id, 'user', NEW.raw_user_meta_data->>'full_name', NEW.email);
```

| จุด | ผล |
|---|---|
| `role` เริ่มต้น | **`'user'`** — ไม่ใช่ `admin` ปลอดภัย |
| `status` | **ไม่ได้ระบุ** → ใช้ค่า default ของคอลัมน์ |
| ความเสี่ยงจาก `status` default | **ไม่มี** — ด่านต้องการ `role IN ('admin','editor')` **และ** `status='approved'` · เมื่อ `role='user'` ก็ไม่ผ่านอยู่ดีไม่ว่า `status` จะเป็นอะไร |
| trigger | `AFTER INSERT ON auth.users FOR EACH ROW` |

**รอบนี้แก้เฉพาะ `SELECT` policy จึงไม่กระทบการสมัครสมาชิก**

### 2.4 ✅ Trigger บน `user_profiles` มี 3 ตัว

| ชื่อ | เวลา | หน้าที่ |
|---|---|---|
| `guard_user_profile_privileges_trigger` | `BEFORE UPDATE FOR EACH ROW` | กัน `role`/`status` |
| `update_user_profiles_updated_at` | `BEFORE UPDATE FOR EACH ROW` | ตั้ง `updated_at` |
| *(บน `auth.users`)* `on_auth_user_created` | `AFTER INSERT FOR EACH ROW` | สร้างโปรไฟล์ |

> PostgreSQL เรียก `BEFORE` trigger เรียงตามชื่อ — `guard...` ขึ้นต้นด้วย `g` จึงทำงาน**ก่อน** `update...` ที่ขึ้นต้นด้วย `u` เป็นลำดับที่ถูกต้อง

**การ migration รอบนี้ไม่แตะ trigger ใดเลย**

### 2.5 ✅ R1 ยืนยัน — ยังเปิดอยู่

`SELECT` policy `Public profiles are viewable by everyone` · `USING (true)` · PERMISSIVE · roles `{public}`

ใครมี anon key (ซึ่งอยู่ใน JavaScript ของหน้าเว็บตามธรรมชาติ) อ่าน `email` และ `full_name` ของทุกคนได้

### 2.6 ✅ `UPDATE` policy 2 ตัว

```
Approved admins can update any profile
  USING: EXISTS (SELECT 1 FROM user_profiles p
                 WHERE p.user_id = auth.uid()
                   AND p.role::text = 'admin' AND p.status::text = 'approved')
  WITH CHECK: null

Users can update own profile
  USING: auth.uid() = user_id
  WITH CHECK: null
```

`WITH CHECK: null` ยังหมายถึง "ใช้ `USING` แทน" เหมือนเดิม **แต่ตอนนี้ไม่เป็นปัญหาแล้วเพราะมี trigger กันอยู่** — trigger ทำงานหลัง RLS ผ่าน จึงเป็นด่านที่สอง

### 2.7 ✅ ไม่พบ view หรือฟังก์ชันที่อ่านอ้อม (ในขอบเขตที่ตรวจ)

เจ้าของรันคำสั่งตรวจแล้ว

| คำสั่ง | ผล |
|---|---|
| `pg_depend` + `pg_rewrite` หา view/rule ที่พึ่งพา `public.user_profiles` | **`Success. No rows returned`** — ไม่มีเลย |
| ฟังก์ชันใน `public` ที่อ้างถึง `user_profiles` หรือ `TRUNCATE` | พบ **2 ตัวเท่านั้น** — `guard_user_profile_privileges` และ `handle_new_user` ซึ่งรู้จักและอ่านโค้ดแล้วทั้งคู่ |
| `proconfig` ของทั้งสองฟังก์ชัน | **`NULL`** — ยืนยันว่า**ไม่มี `SET search_path`** ตรงกับที่ประเมินไว้ในข้อ 3.2 |

**ความหมาย**

- **ไม่มี view ที่จะกลายเป็นช่องอ่านอ้อมหลังปิด policy** — การแก้ `SELECT` policy จะปิดช่องได้จริง ไม่ใช่แค่ดูเหมือนปิด
- **ไม่มีฟังก์ชันใน `public` ที่สั่ง `TRUNCATE`** — ลดความเสี่ยงของ F2 ลงอีก เพราะช่องทาง `POST /rpc/` ที่เคยกังวลไม่มีอยู่จริง
- **ไม่มีฟังก์ชันอื่นที่จะพังจากการเปลี่ยน policy**

> ขอบเขตของข้อสรุปนี้อยู่ในข้อ 4.1 — **ไม่ได้แปลว่าไม่มีช่องทางอ่านอ้อมทุกประเภท**

---

## 3. POTENTIAL — ความเสี่ยงที่ระบุได้ แต่ยังไม่ใช่ช่องโหว่ที่ใช้ได้จริง

### 3.1 ⚠ ทางลัด `auth.uid() IS NULL` — ด่านเดียวไม่มีสำรอง

```sql
IF auth.uid() IS NULL THEN
  RETURN NEW;        -- ปล่อยผ่านทั้งหมด ไม่ตรวจอะไรเลย
END IF;
```

**ใครบ้างที่ `auth.uid()` เป็น `NULL`**

| ผู้เรียก | `auth.uid()` | UPDATE ผ่าน RLS ได้ไหม | ผล |
|---|---|---|---|
| `anon` (มี JWT แต่ไม่มี `sub`) | **NULL** | **ไม่ได้** — ทั้งสอง policy ต้องการ `auth.uid()` ที่ไม่ใช่ NULL | **ปลอดภัยเพราะ RLS กันไว้** |
| `service_role` | NULL | ได้ (ข้าม RLS) | **ข้ามตัวกันทั้งหมด** — เป็นเจตนาตามคอมเมนต์ |
| เชื่อมต่อฐานข้อมูลตรง | NULL | ได้ | ข้ามตัวกัน — เป็นเจตนา |

**ประเมิน**

| ประเด็น | ผล |
|---|---|
| ใช้โจมตีได้ตอนนี้ไหม | **ไม่ได้** — `anon` ถูก RLS ปฏิเสธก่อนถึง trigger |
| ปัญหาเชิงโครงสร้าง | **มี** — ความปลอดภัยของ `anon` พึ่ง RLS **ชั้นเดียว** · ถ้าวันใด RLS ถูกปิดหรือมีใครเพิ่ม policy ที่เปิดกว้าง ตัวกันจะไม่ช่วยอะไรเลยเพราะมันปล่อยผ่านทันทีที่ไม่มี JWT |
| `service_role` | ทุกอย่างที่ถือ service key เปลี่ยน `role` ของใครก็ได้ · เป็นการตัดสินใจเรื่องความไว้วางใจ ไม่ใช่บั๊ก **แต่ควรรู้ตัว** |

**ข้อเสนอ (ไม่ใช่รอบนี้)** — เปลี่ยนจาก "ไม่มี JWT = ปล่อย" เป็น "เป็น `service_role` เท่านั้น = ปล่อย" เพื่อให้มีสองชั้นจริง

```sql
-- แนวคิด ยังไม่ใช่โค้ดที่เสนอให้รัน
IF coalesce(auth.role(), current_user) IN ('service_role', 'postgres') THEN
  RETURN NEW;
ELSIF auth.uid() IS NULL THEN
  RAISE EXCEPTION 'ไม่มีสิทธิ์';
END IF;
```

### 3.2 ⚠ ทั้งสองฟังก์ชันไม่มี `SET search_path`

`guard_user_profile_privileges()` และ `handle_new_user()` เป็น `SECURITY DEFINER` แต่**ไม่มี `SET search_path`** ซึ่งเป็นช่องทางโจมตีที่รู้จักกันดี

**ประเมินความเสี่ยงจริง**

| จุดอ้างอิงในโค้ด | ระบุ schema ไหม | เสี่ยงไหม |
|---|---|---|
| `public.user_profiles` | **ระบุ** | ไม่เสี่ยง |
| `auth.uid()` | **ระบุ** | ไม่เสี่ยง |
| ตัวดำเนินการ `=`, `IS DISTINCT FROM` | — | ต่ำ · `pg_catalog` ถูกค้นก่อนเสมอ |

> **เป็นช่องว่างด้านการเสริมความแข็งแกร่ง ไม่ใช่ช่องโหว่ที่ใช้ได้ทันที** เพราะทุกการอ้างอิงที่สำคัญระบุ schema ไว้แล้ว · ควรเพิ่มเมื่อมีโอกาสแก้ฟังก์ชัน

**ฟังก์ชันที่เราจะสร้างใหม่มี `SET search_path` อยู่แล้ว**

### 3.3 ⚠ `TRUNCATE` — ยืนยันแล้วว่ามี แต่เรียกตรงไม่ได้

| ช่องทาง | สั่งได้ไหม |
|---|---|
| PostgREST จากหน้าเว็บ | **ไม่ได้** — ไม่มี verb ที่แปลงเป็น `TRUNCATE` |
| `POST /rpc/<ฟังก์ชัน>` ที่สั่ง `TRUNCATE` หรือรัน SQL ไดนามิก | **ได้ถ้ามีฟังก์ชันแบบนั้น** ← **ยังไม่ตรวจ** |
| ต่อฐานข้อมูลตรงด้วย role `anon` | ไม่ได้ — anon key เป็น JWT ไม่ใช่รหัสผ่านฐานข้อมูล |

**`TRUNCATE` ข้าม RLS และข้าม trigger ทั้งหมด** — ตัวกัน `guard_user_profile_privileges_trigger` เป็น trigger ของ `UPDATE` จึงไม่ทำงาน

> ไม่ใช่ช่องโหว่ที่กดใช้ได้ทันที แต่เป็นสิทธิ์เกินจำเป็นที่**ขยายความเสียหายของช่องโหว่อื่นทุกตัว** ควรถอด แต่อยู่นอกขอบเขตรอบนี้

### 3.4 ⚠ ตัวกันครอบเฉพาะ `UPDATE` ไม่ครอบ `INSERT`

ถ้าวันใดมีการเพิ่ม `INSERT` policy ให้ `authenticated` โดยไม่เพิ่มตัวกัน จะสร้างแถวที่ `role='admin'` ได้ตรง ๆ

**ตอนนี้ปลอดภัยเพราะไม่มี `INSERT` policy เลย** — บันทึกไว้เป็นข้อควรระวังสำหรับอนาคต

---

## 4. NOT VERIFIED — ยังไม่ได้ตรวจ

| # | สิ่งที่ยังไม่รู้ | บล็อกการแก้ `SELECT` ไหม |
|---|---|---|
| ~~1~~ | ~~มี view หรือฟังก์ชันที่อ่านอ้อมหรือไม่~~ | **ตรวจแล้ว — ดูข้อ 2.7** |
| 2 | รายการสิทธิ์ระดับตารางและคอลัมน์แบบละเอียดของ `anon`/`authenticated` | ไม่บล็อก · ต้องใช้ตอนเขียน `REVOKE` |
| 3 | ค่า default ของคอลัมน์ `status` | ไม่บล็อก (เหตุผลในข้อ 2.3) |
| 4 | ตารางอื่นที่มี policy `USING (true)` เหมือนกัน | ไม่บล็อก · บอกว่างานยังมีอีกเท่าไร |
| 5 | จำนวนบัญชี `editor` ที่ `approved` | **ใช่ — จำเป็นต่อการทดสอบ** |

### 4.1 ขอบเขตของการตรวจทางอ้อม — สิ่งที่ยัง **ไม่ได้** พิสูจน์

การตรวจรอบนี้พิสูจน์ว่า **ไม่มี view หรือ rule ที่พึ่งพา `public.user_profiles`** และ **ไม่มีฟังก์ชันใน schema `public` ที่อ้างถึงชื่อตารางหรือ `TRUNCATE`** นอกจากสองตัวที่รู้จักแล้ว

**แต่ไม่ได้พิสูจน์ว่าไม่มีช่องทางอ่านอ้อมทุกประเภท** รายการที่ยังอยู่นอกขอบเขต

| ช่องทางที่ยังไม่ครอบ | ทำไมคำสั่งที่รันไม่เห็น | ความเสี่ยง |
|---|---|---|
| ฟังก์ชันใน schema อื่นที่ไม่ใช่ `public` | คำสั่งกรอง `pronamespace = 'public'` | ต่ำ–กลาง · Supabase มี schema `auth`, `storage`, `graphql_public` |
| **Supabase Realtime** — ถ้าตารางอยู่ใน publication `supabase_realtime` | เป็นคนละกลไก ไม่ปรากฏใน `pg_depend` หรือ `pg_proc` | **กลาง** · ผู้ที่ subscribe อาจได้รับข้อมูลแถวที่เปลี่ยน |
| **GraphQL endpoint** (`pg_graphql`) | เปิดเผยตารางอัตโนมัติผ่าน schema แยก | กลาง · **แต่ `pg_graphql` เคารพ RLS** จึงถูกปิดไปด้วยกัน |
| SQL ที่ประกอบชื่อตารางแบบไดนามิก | `ilike '%user_profiles%'` จับไม่ได้ถ้าชื่อถูกต่อจากตัวแปร | ต่ำ |
| Foreign table / FDW | ไม่อยู่ใน `pg_rewrite` | ต่ำมาก |
| Materialized view ที่สร้างไว้ก่อนแล้วไม่ refresh | คำสั่งครอบ `pg_rewrite` จึงน่าจะเห็น แต่ข้อมูลที่ค้างอยู่ในนั้นไม่หายไปตาม policy | ต่ำ |

**คำสั่งตรวจเพิ่มถ้าต้องการความมั่นใจสูงขึ้น** (ไม่บล็อก สามารถทำภายหลังได้)

```sql
-- ตารางนี้เปิด Realtime อยู่ไหม
select pubname from pg_publication_tables
where schemaname = 'public' and tablename = 'user_profiles';

-- ฟังก์ชันใน schema อื่นที่อ้างถึงตารางนี้
select n.nspname, p.proname, p.prosecdef
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname not in ('pg_catalog','information_schema')
  and pg_get_functiondef(p.oid) ilike '%user_profiles%';
```

> **ประเมิน** — ช่องทางที่เหลือมีความเสี่ยงต่ำถึงกลาง และ **ไม่มีช่องทางใดที่จะทำให้การแก้ `SELECT` policy ไร้ผล** เพราะกลไกหลักของ Supabase (PostgREST และ GraphQL) เคารพ RLS ทั้งคู่ · Realtime เป็นข้อยกเว้นเดียวที่ควรตรวจ แต่ส่งเฉพาะแถวที่**เปลี่ยนแปลง** ไม่ใช่การอ่านทั้งตาราง จึงไม่เทียบเท่า R1

## 5. Migration และ Rollback — ฉบับสุดท้าย

### 5.1 หลักการ — แก้น้อยที่สุด

| สิ่งที่แตะ | สิ่งที่**ไม่**แตะ |
|---|---|
| `SELECT` policy 1 ตัว (ถอดแล้วสร้างใหม่ 2 ตัว) | `UPDATE` policy ทั้ง 2 ตัว |
| สร้างฟังก์ชันใหม่ชื่อขึ้นต้น `c1_` | `guard_user_profile_privileges()` · `handle_new_user()` |
| | trigger ทั้ง 3 ตัว |
| | สิทธิ์ระดับตารางและคอลัมน์ · ไม่มี `GRANT`/`REVOKE` ใด ๆ |

### 5.2 Migration

```sql
-- C1 — จำกัดการอ่าน public.user_profiles (แก้ R1)
--
-- ยืนยันแล้ว:
--   rls_enabled = true · rls_forced = false
--   SELECT policy ที่เปิดมีตัวเดียว: "Public profiles are viewable by everyone"
--   รูปแบบ SECURITY DEFINER + SELECT บน user_profiles ใช้งานได้จริงอยู่แล้ว
--     (guard_user_profile_privileges() ทำแบบนี้ทุกวันนี้โดยไม่เกิด recursion)
--
-- ไม่แตะ: UPDATE policy · trigger ทั้งหมด · สิทธิ์ทั้งหมด

begin;

-- 1) ฟังก์ชันตรวจสิทธิ์ ตั้งชื่อขึ้นต้น c1_ เพื่อไม่ทับของเดิม
--    ต่างจาก guard_user_profile_privileges() ตรงที่รวม editor ด้วย
--    เพราะหน้ารายการเนื้อหาของ editor ต้องอ่านชื่อผู้เขียน
create or replace function public.c1_is_approved_staff()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select exists (
    select 1 from public.user_profiles
    where user_id = auth.uid()
      and role in ('admin','editor')
      and status = 'approved'
  );
$$;

revoke all on function public.c1_is_approved_staff() from public, anon;
grant execute on function public.c1_is_approved_staff() to authenticated;

-- 2) ถอด policy เดิมที่เปิดให้ทุกคนอ่าน
drop policy if exists "Public profiles are viewable by everyone" on public.user_profiles;

-- 3) อ่านแถวของตัวเอง
create policy c1_user_profiles_select_own
  on public.user_profiles for select
  to authenticated
  using (auth.uid() = user_id);

-- 4) ผู้ดูแลและผู้แก้ไขที่อนุมัติแล้ว อ่านได้ทุกแถว
create policy c1_user_profiles_select_staff
  on public.user_profiles for select
  to authenticated
  using (public.c1_is_approved_staff());

commit;
```

### 5.3 ตรวจทันทีหลัง commit — ก่อนประกาศสำเร็จ

```sql
-- 1) ต้องไม่เหลือ policy ที่เปิดให้อ่าน
select policyname, cmd, permissive, roles::text, qual
from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd in ('SELECT','ALL');
-- ต้องไม่มีแถวใดที่ qual = 'true'

-- 2) ต้องไม่ recursion
select count(*) from public.user_profiles where user_id = auth.uid();

-- 3) UPDATE policy เดิมต้องครบ 2 ตัว
select policyname from pg_policies
where schemaname='public' and tablename='user_profiles' and cmd='UPDATE';

-- 4) trigger ต้องครบ 2 ตัวบนตารางนี้
select tgname from pg_trigger
where tgrelid='public.user_profiles'::regclass and not tgisinternal
order by tgname;
-- ต้องได้ guard_user_profile_privileges_trigger และ update_user_profiles_updated_at
```

### 5.4 Rollback

```sql
begin;

drop policy if exists c1_user_profiles_select_own   on public.user_profiles;
drop policy if exists c1_user_profiles_select_staff on public.user_profiles;

create policy "Public profiles are viewable by everyone"
  on public.user_profiles
  as permissive
  for select
  to public
  using (true);

drop function if exists public.c1_is_approved_staff();

commit;
```

> **ของเดิมที่ไม่ได้แตะ จึงไม่ต้องสร้างคืน** — `UPDATE` policy, trigger ทั้งหมด, `guard_user_profile_privileges()`, `handle_new_user()` ยังอยู่ครบตลอดกระบวนการ

### 5.5 `REVOKE TRUNCATE` — เสนอแยก ยังไม่รัน

```sql
-- ⚠ ต้องดูรายการสิทธิ์แบบละเอียดก่อน และขออนุมัติแยก
revoke truncate on table public.user_profiles from anon, authenticated;
```

| ข้อควรระวัง | เหตุผล |
|---|---|
| **ห้าม `revoke all`** | จะถอด `SELECT`/`UPDATE` ที่ Login หน้าผู้ดูแลและ M3 ใช้จริง → พังทันที |
| ถอดทีละสิทธิ์ที่ระบุชื่อ | ควบคุมผลได้ |
| กระทบ Login ไหม | **ไม่** — Login ใช้ Supabase Auth ไม่แตะตารางนี้ |
| กระทบ `/admin/users` ไหม | **ไม่** — ใช้ `SELECT` และ `UPDATE` ซึ่งไม่ถูกถอด |
| กระทบ M3 ไหม | **ไม่** — ตรวจโค้ดแล้ว M3 **อ่านอย่างเดียว ไม่มี `TRUNCATE` ไม่มีการเขียน** |

---

## 6. ผลกระทบต่อ editor และการอ่านข้อมูล

### 6.1 ก่อนและหลัง

| ผู้เรียก | ก่อนแก้ | หลังแก้ |
|---|---|---|
| `anon` | **อ่านได้ทุกแถว ทุกคอลัมน์** | **อ่านไม่ได้เลย** |
| `authenticated` role `user` | อ่านได้ทุกแถว | **เฉพาะแถวตัวเอง** |
| `editor` ที่ `approved` | อ่านได้ทุกแถว | **อ่านได้ทุกแถว (คงเดิม)** |
| `admin` ที่ `approved` | อ่านได้ทุกแถว | **อ่านได้ทุกแถว (คงเดิม)** |

### 6.2 ทำไมต้องรวม `editor`

หน้ารายการเนื้อหาที่ `editor` เข้าได้ เรียก

```js
.from("user_profiles").select("user_id, full_name, email").in("user_id", [...])
```

เพื่อแสดงชื่อผู้สร้างและผู้แก้ไข **ถ้าให้เฉพาะ `admin` ชื่อผู้เขียนจะหายไปสำหรับ `editor`**

> **ข้อแลกเปลี่ยนที่ต้องรู้** — `editor` ยังอ่าน `email` ของทุกคนได้ · ทางที่ดีกว่าคือทำ view ที่คืนเฉพาะ `user_id, full_name` แต่ต้องแก้โค้ดหน้าเว็บซึ่งเป็นรีโปของทีมออกแบบ **บันทึกเป็นงานถัดไป**

### 6.3 M3 WebAPI ไม่กระทบ

| ไฟล์ | อ่านอะไร | ขอบเขต |
|---|---|---|
| `webapi/auth.mjs:312` | `role, status` | `.eq("user_id", userId)` **แถวตัวเอง** |
| `webapi/api/_lib/adminAuth.js:31` | `role, status` | `.eq('user_id', user.id)` **แถวตัวเอง** |

ทั้งคู่ใช้ client ที่ผูกกับ token ของผู้เรียก จึงเข้าเงื่อนไข `c1_user_profiles_select_own`

**ตรวจซ้ำแล้วว่าโค้ด M3 ไม่มีการเขียนและไม่มี `TRUNCATE` ใด ๆ บนตารางนี้**

ถ้าอ่านไม่ได้ M3 **ล้มแบบปลอดภัย** — `readProfile` คืน `null` → `role: null` → ปฏิเสธ · ยืนยันด้วยชุดทดสอบ `webapi/auth.test.mjs:368`

---

## 7. แผนทดสอบสิทธิ์ — ไม่เปิดเผยข้อมูลส่วนบุคคล

**หลักการ** — ทุกข้อวัดด้วย **จำนวนนับ** หรือ **ค่า true/false** หรือ **รหัส HTTP** เท่านั้น ไม่มีข้อใดสั่งให้แสดง `email`, `full_name` หรือ `user_id`

### 7.1 คำสั่งกลางที่ใช้ซ้ำได้ทุกบทบาท

รันใน **Supabase SQL Editor** ขณะสวมบทบาทผู้ใช้ หรือรันผ่านหน้าเว็บที่ล็อกอินด้วยบัญชีนั้น

```sql
-- จำนวนแถวที่ผู้เรียกนี้อ่านได้ — ไม่คืนข้อมูลใด ๆ
select count(*) as rows_visible from public.user_profiles;

-- อ่านแถวตัวเองได้ไหม
select count(*) as own_row from public.user_profiles where user_id = auth.uid();
```

หรือจาก **Console ของเบราว์เซอร์** ขณะล็อกอินด้วยบัญชีที่ต้องการทดสอบ

```js
const { count } = await supabase.from('user_profiles').select('*', { count: 'exact', head: true });
console.log('rows_visible =', count);
```

> `head: true` คือขอเฉพาะจำนวน **ไม่ดึงข้อมูลแถวกลับมาเลย**

### 7.2 ก่อนแก้ — เก็บค่าฐานไว้เทียบ

| บทบาท | `rows_visible` คาดว่า | บันทึกค่าจริง |
|---|---|---|
| anon | เท่ากับจำนวนผู้ใช้ทั้งหมด | ______ |
| user | เท่ากับจำนวนผู้ใช้ทั้งหมด | ______ |
| editor | เท่ากับจำนวนผู้ใช้ทั้งหมด | ______ |
| admin | เท่ากับจำนวนผู้ใช้ทั้งหมด | ______ |

**ทั้งสี่ควรได้เลขเดียวกัน** เพราะ policy ปัจจุบันเปิดให้ทุกคน

### 7.3 หลังแก้ — ผลที่ต้องได้

| # | บทบาท | ทดสอบ | ต้องได้ |
|---|---|---|---|
| **A1** | **anon** | `rows_visible` | **0** |
| A2 | anon | หน้าแรก · หลักสูตร · เปรียบเทียบ · ค้นหาสาขา · แชท | ใช้ได้เหมือนเดิม |
| A3 | anon | `GET /api/sci-connect-news` | **200** |
| A4 | anon | `POST /api/admin/extract-file` ไม่มี token | **401** |
| **U1** | **user** | `rows_visible` | **1** |
| U2 | user | `own_row` | **1** |
| U3 | user | แก้ `full_name` ของตัวเอง | **สำเร็จ** |
| U4 | user | แก้ `role` ของตัวเองเป็น `admin` | **ถูกปฏิเสธ** — ข้อความจาก trigger |
| U5 | user | เปิด `/admin/dashboard` | ถูกปฏิเสธเหมือนเดิม |
| **E1** | **editor** | `rows_visible` | **เท่ากับค่าฐาน** · ⛔ `BLOCKED — ไม่มีบัญชี` |
| **E2** | **editor** | **รายการเนื้อหาแสดงชื่อผู้สร้าง/ผู้แก้ไข** | **เห็นเหมือนเดิม** · ⛔ `BLOCKED` — **ใช้ D2 ด้วยบัญชี admin แทนได้ เพราะเป็น query เดียวกัน** |
| E3 | editor | แดชบอร์ดแสดงจำนวนผู้ใช้ | ตัวเลขเท่าค่าฐาน · ⛔ `BLOCKED` |
| E4 | editor | `POST /api/admin/extract-file` พร้อม token | **200** · ⛔ `BLOCKED` |
| E5 | editor | แก้ `role` ของคนอื่น | ถูกปฏิเสธ · ⛔ `BLOCKED` |
| **D1** | **admin** | `rows_visible` | **เท่ากับค่าฐาน** |
| D2 | admin | `/admin/users` แสดงรายชื่อ | จำนวนแถวเท่าค่าฐาน |
| D3 | admin | แก้ `status` ของคนอื่น | **สำเร็จ** |
| D4 | admin | `POST /api/admin/extract-file` พร้อม token | **200** |
| **M1** | M3 | `/healthz` | `status=ok` · `authConfigured=true` · `dbConfigured=true` |
| **M2** | M3 | คอนเทนเนอร์ | `healthy` · restarts ไม่เพิ่ม |
| **M3** | M3 | log ของ webapi | ไม่มี `auth failed` ที่ไม่ได้ตั้งใจ |

### 7.4 ข้อที่ชี้ขาด

| ข้อ | ถ้าไม่ผ่านแปลว่า | ทำอะไร |
|---|---|---|
| **A1 ไม่ได้ 0** | **ถอด policy ไม่ครบ ช่องโหว่ยังเปิด** | **หยุด** ตรวจ `pg_policies` ใหม่ |
| **E2 ชื่อผู้เขียนหาย** | ลืมรวม `editor` ในฟังก์ชัน | **rollback** · ⛔ ทดสอบไม่ได้รอบนี้ — ใช้ **D2** ด้วย `admin` แทน |
| **E4 หรือ D4 ได้ 403** | ล็อกผู้ดูแลออกจากระบบ | **rollback ทันที** |
| **U4 สำเร็จ** | **trigger ไม่ทำงาน** — เรื่องใหญ่กว่า C1 | **หยุดทุกอย่าง** สอบสวนก่อน |

> **U4 เป็นการทดสอบเชิงลบที่ควรทำ** และทำได้โดยไม่เสี่ยง เพราะคาดว่าจะถูกปฏิเสธและ transaction จะถูกยกเลิกทั้งหมด **ถ้าสำเร็จขึ้นมาต้องแก้กลับทันทีและถือเป็นเหตุร้ายแรง** — ให้เจ้าของเป็นผู้ทดสอบเอง และทำบนบัญชีทดสอบ ไม่ใช่บัญชีผู้ใช้จริง

### 7.5 บัญชี `editor` — `BLOCKED — NO TEST ACCOUNT`

#### ผลตรวจ (11 ต.ค. 2569)

```sql
SELECT role, status, COUNT(*) AS total_accounts
FROM public.user_profiles
WHERE role = 'editor'
GROUP BY role, status
ORDER BY status;
```

```
Success. No rows returned
```

**ไม่มีบัญชี `role = 'editor'` อยู่ในระบบเลยแม้แต่บัญชีเดียว** ไม่ว่าสถานะใด

> คำสั่งนี้คืนเฉพาะ `role`, `status` และจำนวนนับ **ไม่มีข้อมูลผู้ใช้**

#### สถานะการทดสอบ

| รายการ | สถานะ |
|---|---|
| ทดสอบ **E1–E5** | **`BLOCKED — NO TEST ACCOUNT`** |
| ทดสอบ **A, U, D, M** | ทำได้ตามปกติ |

#### ผลที่ตามมา — เปลี่ยนการประเมินในทางที่ดี

การที่ไม่มี `editor` เลย ทำให้ความเสี่ยงของเส้นทางนี้ **ลดลง ไม่ใช่เพิ่มขึ้น**

| ประเด็น | ประเมิน |
|---|---|
| มีใครพังจากการแก้นี้วันนี้ไหม | **ไม่มี** — ไม่มีบัญชี `editor` ที่จะได้รับผลกระทบ |
| เส้นทาง `editor` ในฟังก์ชันใหม่ | **หลับอยู่** — `role in ('admin','editor')` มีแต่ `admin` ที่ตรงจริง |
| ถ้า `editor` ใช้ไม่ได้ จะรู้เมื่อไร | เมื่อสร้างบัญชี `editor` คนแรก · เห็นทันทีและ rollback ได้ |
| โอกาสที่ `admin` ผ่านแต่ `editor` ไม่ผ่าน | **ต่ำมาก** — เป็นนิพจน์เดียวกัน `role in ('admin','editor')` ไม่ได้แยกเส้นทาง |
| หน้าที่อ่านชื่อผู้เขียน (E2) | **ทดสอบได้ด้วยบัญชี `admin`** เพราะเป็น query เดียวกัน ต่างแค่บทบาทผู้เรียก |

> **ข้อสรุป** — การทดสอบ D1–D4 ด้วย `admin` ครอบคลุม**โค้ดเส้นทางเดียวกัน**กับ E1–E4 แล้ว · สิ่งที่ยังไม่พิสูจน์คือคำว่า `'editor'` ในรายการ `in (...)` ทำงานจริง ซึ่งเป็นความเสี่ยงที่เล็กมาก

### 7.6 แผนสร้างบัญชี `editor` สำหรับทดสอบ — ถ้าเลือกทำ

> **เป็นการเขียน production database ต้องขออนุมัติแยก** · ผู้ช่วยไม่สร้างบัญชีและไม่แก้ `role`/`status` ใด ๆ

#### หลักการ — ไม่แตะบัญชีผู้ใช้จริง

| ข้อห้าม | เหตุผล |
|---|---|
| **ห้ามเปลี่ยนบัญชีผู้ใช้จริงเป็น `editor`** | กระทบคนจริง และต้องจำว่าต้องเปลี่ยนกลับ |
| **ห้ามแก้ `role` ด้วย SQL ตรง** | ข้าม trigger `guard_user_profile_privileges` ซึ่งเป็นด่านป้องกัน · ใช้เส้นทางปกติจะพิสูจน์ด่านไปในตัว |
| ห้ามใช้อีเมลของคนจริง | ใช้อีเมลทดสอบที่แยกชัดเจน |

#### ขั้นตอนที่เสนอ

| # | ขั้น | ทำอย่างไร | เขียนอะไร |
|---|---|---|---|
| 1 | สมัครบัญชีทดสอบใหม่ | สมัครผ่านหน้าเว็บตามปกติด้วยอีเมลทดสอบ | `auth.users` 1 แถว + `user_profiles` 1 แถว (`role='user'` โดย `handle_new_user`) |
| 2 | ตั้งเป็น `editor` + `approved` | **ผ่านหน้า `/admin/users` ด้วยบัญชี `admin`** | `user_profiles` 1 แถว |
| 3 | ทดสอบ E1–E5 ตามข้อ 7.3 | — | ไม่เขียน |
| 4 | คืนสภาพ | ดูข้อ 7.7 | — |

> ขั้นที่ 2 ใช้เส้นทางปกติของระบบ จึง **พิสูจน์ไปในตัว** ว่า `UPDATE` policy ของ admin และ trigger ยังทำงานถูกต้อง

#### ถ้าทำก่อน apply จะได้ประโยชน์เพิ่ม

สร้างบัญชีทดสอบ **ก่อน** แก้ policy แล้วเก็บค่าฐานตามข้อ 7.2 จะเทียบก่อน-หลังได้ครบทุกบทบาท

### 7.7 Cleanup หลังทดสอบ

| # | ขั้น | หมายเหตุ |
|---|---|---|
| 1 | เปลี่ยน `role` กลับเป็น `'user'` ผ่าน `/admin/users` | ตัดสิทธิ์ทันที |
| 2 | หรือเปลี่ยน `status` เป็นค่าที่ไม่ใช่ `approved` | ได้ผลเดียวกัน |
| 3 | ลบบัญชีออกจาก Supabase Auth ถ้าไม่ต้องการเก็บ | **เป็นการลบข้อมูล ต้องขออนุมัติแยกอีกชั้น** |
| 4 | ยืนยันว่าจำนวน `editor` กลับเป็น 0 | รันคำสั่งเดิมในข้อ 7.5 ต้องได้ `No rows returned` |

> **แนะนำให้เก็บบัญชีทดสอบไว้** โดยตั้ง `role='user'` แทนการลบ เพื่อใช้ซ้ำครั้งหน้าและหลีกเลี่ยงการลบข้อมูลใน production

#### บันทึกเพิ่ม

ฐานข้อมูล PostgreSQL ฝั่งเรามีบัญชีทดสอบค้างอยู่แล้ว **191 จาก 201 บัญชีเป็นโดเมนทดสอบ** การเพิ่มอีกหนึ่งไม่เปลี่ยนภาพรวม แต่ควรตั้งชื่อให้ชัดว่าเป็นบัญชีทดสอบของรอบ C1

---


## 8. GO / NO-GO

### 8.1 สถานะ

# `GO` แบบมีเงื่อนไข

ความเสี่ยงทางเทคนิคที่เคยเป็น blocker **หมดไปทั้งหมดแล้ว** เหลือการยืนยันทางอ้อมหนึ่งข้อและบัญชีทดสอบ

### 8.2 เงื่อนไข

| # | เงื่อนไข | สถานะ |
|---|---|---|
| 1 | รู้ชื่อและนิยาม `SELECT` policy เดิม | **ผ่าน** |
| 2 | รู้ว่ามี `SELECT` policy ที่เปิดกี่ตัว | **ผ่าน** — 1 ตัว |
| 3 | รู้ `UPDATE` policy เดิมครบ | **ผ่าน** — 2 ตัว มีนิยามเต็ม |
| 4 | ประเมินความเสี่ยง recursion | **ผ่าน** — พิสูจน์จากของจริงที่ใช้งานอยู่ |
| 5 | รู้ trigger ทั้งหมดบนตาราง | **ผ่าน** — 2 ตัว + 1 ตัวบน `auth.users` |
| 6 | **ยืนยันว่าตัวกัน `role`/`status` ทำงานจริง** | **ผ่าน** — อ่านโค้ดเต็มแล้ว ครบทั้ง 6 เกณฑ์ |
| 7 | รู้ค่าเริ่มต้นของโปรไฟล์ใหม่ | **ผ่าน** — `role='user'` ปลอดภัย |
| 8 | **ยืนยันว่าไม่มี view หรือฟังก์ชันที่อ่านอ้อม** | **ผ่านในขอบเขตที่ตรวจ** — view/rule ไม่พบเลย · ฟังก์ชันใน `public` พบแค่ 2 ตัวที่รู้จัก · **ขอบเขตอยู่ในข้อ 4.1** |
| 9 | มีบัญชี `editor` ที่ `approved` ไว้ทดสอบ | **`BLOCKED — NO TEST ACCOUNT`** — ยืนยันแล้วว่า**ไม่มีบัญชี `editor` ในระบบเลย** · **ไม่บล็อกการ apply** ดูข้อ 7.5 |
| 10 | รายการสิทธิ์ละเอียด (สำหรับ `REVOKE` แยก) | ยังไม่มี · **ไม่บล็อกรอบนี้** |
| 11 | เจ้าของฟังก์ชันใหม่ข้าม RLS ได้ | **ไม่บล็อก** — ล้มแบบเห็นชัดและย้อนได้ ดูข้อ 8.3 |

**ผ่าน 8 จาก 11** · ข้อ 9 เปลี่ยนจาก "รอยืนยัน" เป็น **"ยืนยันแล้วว่าไม่มีบัญชี"** ซึ่ง **ไม่ใช่อุปสรรคต่อการ apply** เพราะไม่มีผู้ใช้ที่จะได้รับผลกระทบ · ข้อ 10 และ 11 ไม่บล็อกรอบนี้

> **ไม่เหลือเงื่อนไขที่บล็อกการ apply แล้ว** — สิ่งที่เหลือคือการตัดสินใจว่าจะสร้างบัญชีทดสอบก่อนหรือไม่

### 8.3 ความพร้อมของ Migration · Rollback · Function Ownership

#### Migration

| จุดตรวจ | สถานะ |
|---|---|
| ชื่อ policy เดิมที่ต้องถอด | **รู้แน่นอน** — `Public profiles are viewable by everyone` ตัวเดียว |
| มี policy อื่นที่เปิดอ่านอีกไหม | **ไม่มี** |
| แตะ `UPDATE` policy ไหม | **ไม่แตะ** |
| แตะ trigger ไหม | **ไม่แตะ** ทั้ง 3 ตัว |
| มี `GRANT` / `REVOKE` ไหม | **ไม่มีเลยในรอบนี้** |
| ชื่อฟังก์ชันใหม่ชนของเดิมไหม | **ไม่ชน** — ของเดิมมีแค่ `guard_user_profile_privileges` และ `handle_new_user` |
| มี `SET search_path` ไหม | **มี** — `pg_catalog, public` · **ดีกว่าของเดิมที่ `proconfig = NULL`** |

#### Rollback

| จุดตรวจ | สถานะ |
|---|---|
| มีนิยาม policy เดิมแบบคำต่อคำไหม | **มี** — `as permissive · for select · to public · using (true)` |
| ต้องสร้าง trigger หรือฟังก์ชันเดิมคืนไหม | **ไม่ต้อง** เพราะไม่ได้แตะ |
| ลบเฉพาะของที่รอบนี้สร้างไหม | **ใช่** |
| ย้อนแล้วข้อมูลเสียหายไหม | **ไม่** — ไม่มีคำสั่งใดแตะข้อมูลในตาราง |

#### Function Ownership

`SECURITY DEFINER` รันด้วยสิทธิ์ของ **เจ้าของฟังก์ชัน** การข้าม RLS จึงขึ้นกับว่าเจ้าของเป็นใคร

**หลักฐานที่ทำให้มั่นใจ** — `guard_user_profile_privileges()` ทำ `SELECT` จาก `public.user_profiles` แบบ `SECURITY DEFINER` และ **ทำงานได้ทุกวันนี้โดยไม่ recursion** แปลว่าเจ้าของของมันข้าม RLS ได้จริงในฐานข้อมูลนี้

> **ข้อปฏิบัติ** — สร้างฟังก์ชันใหม่ด้วย **วิธีและบัญชีเดียวกับที่สร้างของเดิม** คือรันผ่าน Supabase SQL Editor เพื่อให้ได้เจ้าของคนเดียวกัน

**ถ้าเจ้าของไม่ข้าม RLS จะเกิดอะไร** — การประเมิน `c1_user_profiles_select_staff` จะเรียกฟังก์ชัน ซึ่งไปอ่านตาราง ซึ่งต้องประเมิน policy อีกรอบ → **recursion**

| ลักษณะการล้ม | ประเมิน |
|---|---|
| เห็นทันทีไหม | **เห็น** — ขึ้นข้อความ `infinite recursion detected in policy` ไม่ใช่ความเงียบ |
| ล้มแบบเปิดสิทธิ์ไหม | **ไม่** — อ่านตารางไม่ได้เลย ไม่ใช่อ่านได้หมด |
| ย้อนได้ไหม | **ได้ทันที** ด้วย rollback ข้อ 5.4 |
| ข้อมูลเสียหายไหม | **ไม่** |

**สรุป: ไม่บล็อก** เพราะล้มแบบเห็นชัด ย้อนได้ทันที และไม่มีข้อมูลเสียหาย · ตรวจด้วยข้อ A1 และ U1 ทันทีหลัง apply

### 8.4 ทางเลือกสองทาง — เลือกทางใดก็เดินต่อได้

| | **ทาง ก — แก้เลย** | **ทาง ข — สร้างบัญชีทดสอบก่อน** |
|---|---|---|
| ทำอะไร | apply migration แล้วทดสอบ A, U, D, M | สร้างบัญชี `editor` ตามข้อ 7.6 → เก็บค่าฐาน → apply → ทดสอบครบ A, U, E, D, M → cleanup |
| ทดสอบ `editor` ได้ไหม | **ไม่ได้** — ใช้ D2 ด้วย `admin` แทน | **ได้ครบ** |
| เขียน production เพิ่มไหม | **ไม่** — มีแต่การแก้ policy | **ใช่** — เพิ่มบัญชีทดสอบ 1 บัญชี ต้องขออนุมัติแยก |
| ความเสี่ยงที่เหลือ | คำว่า `'editor'` ใน `in (...)` ยังไม่ถูกพิสูจน์ · **ไม่มีผู้ใช้ที่กระทบวันนี้** | แทบไม่เหลือ |
| เวลาที่ใช้ | สั้น | ยาวกว่า มีขั้น cleanup |
| ย้อนกลับได้ไหม | **ได้ทันที** | ได้ทันที + ต้อง cleanup บัญชี |

**ความเห็น** — **ทาง ก เพียงพอ** เพราะไม่มีบัญชี `editor` ที่จะพัง และการทดสอบด้วย `admin` ครอบโค้ดเส้นทางเดียวกัน · เลือกทาง ข เมื่อต้องการความมั่นใจสูงสุดหรือกำลังจะสร้าง `editor` จริงอยู่แล้ว

> ไม่ว่าเลือกทางไหน **ควรทดสอบ E1–E5 ทันทีที่มีบัญชี `editor` คนแรกในอนาคต**

### 8.5 NO-GO ระหว่าง apply

| อาการ | ทำอะไร |
|---|---|
| `infinite recursion detected in policy` | **rollback ทันที** |
| ข้อ 5.3 ข้อ 1 ยังเจอ `qual = 'true'` | **หยุด** — ถอดไม่ครบ ช่องโหว่ยังเปิด |
| ข้อ 5.3 ข้อ 3 ได้ไม่ครบ 2 แถว | **หยุด** — เผลอลบ `UPDATE` policy |
| ข้อ 5.3 ข้อ 4 trigger หายไป | **หยุด** — ตัวกันหาย อันตรายกว่าเดิม |
| ล็อกอินหน้าผู้ดูแลไม่ได้ | **rollback ทันที** |
| M3 `extract-file` พร้อม token ของ admin ได้ 403 | **rollback ทันที** |
| ชื่อผู้เขียนหายจากรายการเนื้อหาของ `editor` | **rollback** — ลืมรวม editor |

---

## 9. สิ่งที่ขอให้ทำต่อ

| ลำดับ | งาน | ปลดล็อกอะไร |
|---|---|---|
| ~~1~~ | ~~ตรวจ view และฟังก์ชันที่อ่านอ้อม~~ | **เสร็จแล้ว** — ไม่พบ ดูข้อ 2.7 |
| ~~1~~ | ~~ยืนยันว่ามีบัญชี `editor`~~ | **ตรวจแล้ว — ไม่มีเลย** ดูข้อ 7.5 · ไม่บล็อก |
| **1** | **เลือกทาง ก หรือ ข ตามข้อ 8.4** | ปลดล็อกการ apply |
| **2** | อนุมัติให้ apply migration ข้อ 5.2 แล้วทดสอบตามข้อ 7 | — |
| 4 | รายการสิทธิ์ละเอียด แล้วขออนุมัติ `REVOKE TRUNCATE` แยก | งานถัดไป |
| 5 | พิจารณาแก้ทางลัด `auth.uid() IS NULL` ในตัวกัน (ข้อ 3.1) | งานถัดไป |
| 6 | พิจารณาเพิ่ม `SET search_path` ให้ฟังก์ชันเดิมทั้งสอง (ข้อ 3.2) | งานถัดไป |
| 7 | ตรวจตารางอื่นที่มี policy `USING (true)` | งานถัดไป |

---

## 10. ยืนยันขอบเขต

| ข้อห้าม | สถานะ |
|---|---|
| แก้ production | **ไม่ได้ทำ** |
| Apply migration | **ไม่ได้ทำ** |
| `REVOKE` | **ไม่ได้ทำ** — เสนอไว้เพื่อขออนุมัติเท่านั้น |
| ทดสอบเลื่อนสิทธิ์ด้วยการเขียนฐานข้อมูลจริง | **ไม่ได้ทำ** — วิเคราะห์จากโค้ดและกฎเท่านั้น |
| Deploy / Restart / Push / Merge | **ไม่ได้ทำ** |
| เปิดเผย PII / token / secrets | **ไม่มีในเอกสารนี้** — ไฟล์หลักฐานทั้ง 4 ไม่มีข้อมูลผู้ใช้อยู่แล้ว |

```
Local  HEAD 427ce19 · mko-phase2 · ไฟล์โค้ดที่แก้ 0
Prod   webapi d2663f039a18 · running · healthy · restarts=0 · บริการอื่นไม่ถูกแตะ
```

**สถานะ: `GO` แบบมีเงื่อนไข — รอผลตรวจ view/ฟังก์ชันทางอ้อม และบัญชี `editor` แล้วขออนุมัติ apply**
