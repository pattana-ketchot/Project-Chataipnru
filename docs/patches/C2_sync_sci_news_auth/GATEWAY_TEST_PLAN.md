# แผนทดสอบ Gateway บนโปรเจกต์แยก `c1-migration-test`

> ทำบน **โปรเจกต์ทดสอบเท่านั้น** · ห้ามทำบน production
> **ไม่อ่านและไม่แสดงค่า key/token/secret** — ทุกคำสั่งรับค่าแบบไม่แสดงบนจอ
> **รอบแรกไม่ต้อง rotate หรือ revoke signing key ใด ๆ**

| สถานะก่อนเริ่ม | |
|---|---|
| `deno check` | **ผ่าน** |
| `deno test` | **14 ผ่าน 0 ล้ม** — ดู `TEST_STATUS.md` |
| แผนนี้ (G1–G8) | **ผ่านครบ 8 ข้อบนโปรเจกต์ทดสอบ** — ดู `TEST_STATUS.md` ข้อ 5 |

---

## 0. ทำไม unit tests ยืนยัน gateway ไม่ได้

ชุดทดสอบเรียก `handler()` **โดยตรง** จึงข้าม gateway ทั้งหมด

| unit test ครอบ | ครอบ **ไม่ได้** |
|---|---|
| ตรรกะในโค้ด — method, cron secret, role/status | **พฤติกรรมของ gateway ก่อนโค้ดทำงาน** |
| โค้ดปฏิเสธ anon key ที่มาถึงตัวมัน | **gateway ปล่อยหรือปฏิเสธคำขอนั้นก่อนถึงโค้ดหรือไม่** |
| | **`verify_jwt` รับ JWT แบบใหม่ไหม** |
| | **`pg_cron` ส่ง header เพิ่มได้จริงไหม** |

---

## 1. สิ่งที่ต้องเตรียม

| # | สิ่งที่ต้องมี | ได้จากไหน |
|---|---|---|
| 1 | โปรเจกต์ `c1-migration-test` ที่ deploy Edge Function ฉบับใหม่แล้ว | Dashboard ของโปรเจกต์ทดสอบ |
| 2 | `PROJECT_REF` | Dashboard → Settings → API |
| 3 | `ANON_KEY` | Dashboard → Settings → API |
| 4 | `SYNC_CRON_SECRET` ตั้งใน Edge Function secrets ของโปรเจกต์ทดสอบ | Dashboard → Edge Functions → Secrets |
| 5 | บัญชีทดสอบ **admin + approved** | สร้างในโปรเจกต์ทดสอบ |
| 6 | บัญชีทดสอบ **role = user** | สร้างในโปรเจกต์ทดสอบ |
| 7 | ตาราง `user_profiles` และ `external_news` | คัดลอกโครงสร้างจาก production |

> ข้อ 5–7 เป็นการเขียนข้อมูล **แต่ทำบนโปรเจกต์ทดสอบ** จึงไม่ขัดข้อห้าม

---

## 2A. ตั้งค่า — Bash / Git Bash / WSL

```bash
read -rp  'PROJECT_REF (test): ' REF
read -rsp 'ANON_KEY (test): '    ANON && echo
FN="https://$REF.supabase.co/functions/v1/sync-sci-news"

# แสดงเฉพาะรหัส HTTP และเนื้อหาสั้น ๆ ไม่แสดง header
probe() {
  local label="$1"; shift
  printf '%-34s ' "$label"
  curl -s -o /tmp/c2body.txt -w 'HTTP %{http_code}' "$@" "$FN"
  printf '  body=%s\n' "$(head -c 120 /tmp/c2body.txt)"
}
```

เมื่อเสร็จทั้งหมด

```bash
unset ANON REF; rm -f /tmp/c2body.txt
```

---

## 2B. ตั้งค่า — Windows PowerShell

> PowerShell ไม่มี `read -rsp` ใช้ `Read-Host -AsSecureString` แทน
> **ค่าที่รับมาจะไม่ปรากฏบนจอและไม่เข้า history**

```powershell
$Ref  = Read-Host 'PROJECT_REF (test)'
$Anon = ConvertFrom-SecureString -AsPlainText (Read-Host 'ANON_KEY (test)' -AsSecureString)
$Fn   = "https://$Ref.supabase.co/functions/v1/sync-sci-news"

function Probe {
  param(
    [string]$Label,
    [string]$Method = 'POST',
    [hashtable]$Headers = @{}
  )
  $code = 0; $body = ''
  try {
    $r = Invoke-WebRequest -Uri $Fn -Method $Method -Headers $Headers `
                           -SkipHttpErrorCheck -MaximumRedirection 0
    $code = $r.StatusCode
    $body = $r.Content
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    $body = $_.ErrorDetails.Message
  }
  $short = if ($body) { $body.Substring(0, [Math]::Min(120, $body.Length)) } else { '' }
  '{0,-34} HTTP {1}  body={2}' -f $Label, $code, $short
}
```

เมื่อเสร็จทั้งหมด

```powershell
Remove-Variable Anon, Ref, Fn -ErrorAction SilentlyContinue
[System.GC]::Collect()
```

| หมายเหตุ | |
|---|---|
| `-SkipHttpErrorCheck` | ต้องใช้ PowerShell 7+ · ถ้าเป็น 5.1 ให้พึ่งบล็อก `catch` แทน |
| `ConvertFrom-SecureString -AsPlainText` | ต้องใช้ PowerShell 7+ |
| PowerShell 5.1 | ใช้ `[Runtime.InteropServices.Marshal]::PtrToStringBSTR(...)` แทน หรือใช้ Git Bash จะง่ายกว่า |

---

## 3. ลำดับการทดสอบ

### 3.1 gateway ปฏิเสธก่อนถึงโค้ด

| ขั้น | ส่งอะไร | ต้องได้ |
|---|---|---|
| **G1** | ไม่ส่ง `apikey` และไม่ส่ง `Authorization` | **`401`** จาก gateway |
| **G2** | `apikey` ถูก แต่ `Authorization` เป็นข้อความมั่ว | **`401`** จาก gateway |

**Bash**

```bash
probe 'G1 ไม่มี credential' -X POST
probe 'G2 bearer มั่ว'      -X POST -H "apikey: $ANON" -H "Authorization: Bearer not-a-jwt"
```

**PowerShell**

```powershell
Probe 'G1 no credential'
Probe 'G2 bearer garbage' -Headers @{ apikey = $Anon; Authorization = 'Bearer not-a-jwt' }
```

> ทั้งสองข้อ **โค้ดของเราไม่เคยทำงาน** · ยืนยันจาก Edge Function logs ว่าไม่มี invocation

### 3.2 gateway ปล่อยผ่าน แล้วโค้ดเป็นผู้ปฏิเสธ

| ขั้น | ส่งอะไร | ต้องได้ | ใครปฏิเสธ |
|---|---|---|---|
| **G3** | `apikey` + `Authorization: Bearer <ANON_KEY>` | **`401`** | **โค้ดของเรา** |
| **G4** | เหมือน G3 แต่เป็น `GET` | **`405`** | โค้ดของเรา |
| **G5** | `apikey` + `x-cron-secret` ผิด | **`401`** | โค้ดของเรา |

**Bash**

```bash
probe 'G3 anon key เป็น bearer' -X POST -H "apikey: $ANON" -H "Authorization: Bearer $ANON"
probe 'G4 GET'                  -X GET  -H "apikey: $ANON" -H "Authorization: Bearer $ANON"
probe 'G5 cron secret ผิด'      -X POST -H "apikey: $ANON" -H "Authorization: Bearer $ANON" \
                                        -H "x-cron-secret: wrong-secret-value"
```

**PowerShell**

```powershell
$H = @{ apikey = $Anon; Authorization = "Bearer $Anon" }
Probe 'G3 anon key as bearer' -Headers $H
Probe 'G4 GET' -Method GET -Headers $H
Probe 'G5 cron secret wrong' -Headers ($H + @{ 'x-cron-secret' = 'wrong-secret-value' })
```

> **G3 คือข้อชี้ขาดของ patch นี้** — ก่อนแก้ได้ `200` และ sync ทำงาน · หลังแก้ต้องได้ `401`
>
> **วิธีแยกว่าใครปฏิเสธ** — ดู Edge Function logs
> มี invocation = โค้ดเราปฏิเสธ · ไม่มี = gateway ปฏิเสธ

### 3.3 เส้นทางที่ต้องผ่าน

| ขั้น | ส่งอะไร | ต้องได้ |
|---|---|---|
| **G6** | `apikey` + `Authorization: Bearer <ANON>` + `x-cron-secret` **ถูก** | **`200`** |
| **G7** | `apikey` + `Authorization: Bearer <token ของ admin>` | **`200`** |
| **G8** | `apikey` + `Authorization: Bearer <token ของ user>` | **`403`** |

**Bash**

```bash
read -rsp 'SYNC_CRON_SECRET: ' CRON && echo
probe 'G6 cron secret ถูก' -X POST -H "apikey: $ANON" -H "Authorization: Bearer $ANON" -H "x-cron-secret: $CRON"
unset CRON

read -rsp 'ADMIN token (test): ' TKA && echo
probe 'G7 admin token' -X POST -H "apikey: $ANON" -H "Authorization: Bearer $TKA"; unset TKA

read -rsp 'USER token (test): ' TKU && echo
probe 'G8 user token' -X POST -H "apikey: $ANON" -H "Authorization: Bearer $TKU"; unset TKU
```

**PowerShell**

```powershell
$Cron = ConvertFrom-SecureString -AsPlainText (Read-Host 'SYNC_CRON_SECRET' -AsSecureString)
Probe 'G6 cron secret ok' -Headers ($H + @{ 'x-cron-secret' = $Cron })
Remove-Variable Cron

$Tka = ConvertFrom-SecureString -AsPlainText (Read-Host 'ADMIN token' -AsSecureString)
Probe 'G7 admin token' -Headers @{ apikey = $Anon; Authorization = "Bearer $Tka" }
Remove-Variable Tka

$Tku = ConvertFrom-SecureString -AsPlainText (Read-Host 'USER token' -AsSecureString)
Probe 'G8 user token' -Headers @{ apikey = $Anon; Authorization = "Bearer $Tku" }
Remove-Variable Tku
```

> **G6 และ G7 จะเขียนข้อมูลจริงในโปรเจกต์ทดสอบ** — เป็นจุดประสงค์ของการทดสอบ

### 3.4 วิธีดึง access token โดยไม่ให้ค่าโผล่

ที่ Console ของเบราว์เซอร์ขณะล็อกอินด้วยบัญชีที่ต้องการ **บนโปรเจกต์ทดสอบ**

```js
copy(JSON.parse(Object.entries(localStorage).find(([k])=>k.startsWith('sb-')&&k.endsWith('-auth-token'))[1]).access_token)
```

จะขึ้น `undefined` ซึ่งปกติ — คลิปบอร์ดได้ token แล้ว นำไปวางตอนที่ prompt ถาม

---

## 4. ทดสอบ `verify_jwt` ว่าเป็นด่านจริง

ข้อนี้พิสูจน์ว่า **ความปลอดภัยไม่ได้พึ่ง gateway** ซึ่งเป็นข้อสรุปที่ `README.md` ข้อ 7.2 อ้างไว้

| ขั้น | ทำอะไร | ต้องได้ |
|---|---|---|
| **V1** | ในโปรเจกต์ทดสอบ ตั้ง `verify_jwt = false` แล้ว deploy ซ้ำ | — |
| **V2** | ยิง G1 ซ้ำ (ไม่มี credential) | **`401` จากโค้ดเรา** — จะเห็น invocation ใน logs ต่างจากเดิม |
| **V3** | ยิง G3 ซ้ำ (anon key เป็น bearer) | **`401`** |
| **V4** | ยิง G6 ซ้ำ (cron secret ถูก) | **`200`** |
| **V5** | ยิง G7 ซ้ำ (admin token) | **`200`** |
| **V6** | ตั้ง `verify_jwt` กลับเป็น `true` แล้ว deploy ซ้ำ | — |

> **ถ้า V2–V5 ผ่านครบ แปลว่าเปลี่ยน `verify_jwt` ได้ในอนาคตโดยไม่ต้องแก้โค้ด**

---

## 5. ทดสอบ cron ในโปรเจกต์ทดสอบ

| ขั้น | ทำอะไร | ต้องได้ |
|---|---|---|
| **C1** | รัน `scripts/01_update_cron.sql` ในโปรเจกต์ทดสอบ | ผ่านการตรวจทุกข้อในสคริปต์ · ไม่มี exception |
| **C2** | ตรวจ `cron.job` | job เดิม `active = false` · job ใหม่ `active = true` |
| **C3** | รอหนึ่งรอบ แล้วดู **`status_code` จาก `pg_net`** | **`200`** |
| **C4** | ทดลอง rollback ด้วย `scripts/02_rollback_cron.sql` | คืนสภาพได้ |

> **C3 สำคัญ** — `cron.job_run_details` ที่ขึ้น `succeeded` **ยืนยันแค่การส่งงาน SQL ไม่ใช่ผล HTTP** · วิธีดูอยู่ใน `README.md` ข้อ 6.3
>
> **ห้าม `select *`** จากตารางผลตอบกลับของ `pg_net` เพราะคอลัมน์ `headers` มี secret อยู่

---

## 6. ตรวจสถานะ JWT signing keys

> **รอบแรกไม่ต้อง rotate และไม่ต้อง revoke** — ข้อนี้เป็นการ**บันทึกสถานะ**เพื่อรู้ว่าการออกแบบจะอยู่ได้นานแค่ไหน

### 6.1 ⚠ อย่าสรุปจากจำนวนคีย์ใน JWKS

เอกสารทางการระบุว่า **JWKS เผยแพร่เฉพาะ public key ของคีย์แบบ asymmetric เท่านั้น** ส่วน shared secret แบบเดิม *"ไม่มี public key counterpart"* จึงไม่ปรากฏที่นั่น

| ข้อจำกัดของ JWKS | รายละเอียด |
|---|---|
| ไม่บอกสถานะของคีย์ | ไม่ระบุว่าคีย์ไหนเป็น current, standby หรือ previously used |
| **มีแคชหลายชั้น** | edge cache 10 นาที · client library อาจบวกอีก 10 นาที · แคชล้างทุก 20 นาที |
| จึงอาจล้าสมัย | **ค่าที่เห็นอาจไม่ใช่สถานะปัจจุบัน** |

> **ผลว่างเปล่าไม่ได้แปลว่ายังใช้ legacy secret เสมอไป และผลที่มีคีย์ก็ไม่ได้บอกว่าคีย์นั้นถูกใช้ลงนามอยู่**

### 6.2 แหล่งที่เชื่อถือได้ — Dashboard

**Dashboard → Settings → JWT** (หน้า JWT Signing Keys) เป็นแหล่งเดียวที่บอกสถานะได้ถูกต้อง

| สถานะของคีย์ | ความหมาย |
|---|---|
| **Standby** | สร้างไว้แล้วแต่ **ยังไม่ถูกใช้ลงนาม** |
| **Current (in use)** | **ใช้ลงนาม JWT ใหม่อยู่** |
| **Previously used** | ไม่ลงนามใหม่แล้ว แต่ **ยังเชื่อถืออยู่** |
| **Revoked** | **ไม่เชื่อถือแล้ว** |
| ลบถาวร | **ย้อนกลับไม่ได้** |

หน้านี้ยังบอกด้วยว่า **legacy JWT secret ถูก migrate ไปแล้วหรือยัง**

> หลังเปลี่ยนสถานะใด ๆ ให้รออย่างน้อย **5 นาที** เพราะมีการจำกัดอัตรา

### 6.3 ขั้นบันทึกสถานะ (รอบแรกทำแค่นี้)

| ขั้น | ทำอะไร | บันทึกอะไร |
|---|---|---|
| **S1** | เปิด Dashboard → Settings → JWT ของ **โปรเจกต์ทดสอบ** | migrate แล้วหรือยัง · มีคีย์กี่ตัว · แต่ละตัวสถานะอะไร |
| **S2** | เปิดหน้าเดียวกันของ **production** | เหมือนกัน — **ดูอย่างเดียว ห้ามกดเปลี่ยนอะไร** |
| **S3** | ดึง JWKS เป็นหลักฐานประกอบ (ไม่ใช่ข้อสรุป) | จำนวนคีย์และ `alg` |

**Bash**

```bash
# JWKS เป็นข้อมูลสาธารณะ ไม่ใช่ความลับ
curl -s "https://$REF.supabase.co/auth/v1/.well-known/jwks.json" \
  | python -I -c "import json,sys; d=json.load(sys.stdin); ks=d.get('keys',[]); print('keys:', len(ks)); [print(' ', k.get('kty'), k.get('alg'), 'kid=', (k.get('kid') or '')[:8]+'...') for k in ks]"
```

**PowerShell**

```powershell
$jwks = Invoke-RestMethod "https://$Ref.supabase.co/auth/v1/.well-known/jwks.json"
'keys: {0}' -f @($jwks.keys).Count
$jwks.keys | ForEach-Object { '  {0} {1} kid={2}...' -f $_.kty, $_.alg, $_.kid.Substring(0,8) }
```

### 6.4 ตีความร่วมกัน

| Dashboard | JWKS | สรุป |
|---|---|---|
| ยังไม่ migrate | ไม่มีคีย์ | **ยังใช้ legacy HS256 อย่างเดียว** — การออกแบบปัจจุบันใช้ได้ |
| migrate แล้ว มี standby | อาจมีคีย์แล้ว | **ยังไม่ rotate** — ยังใช้ได้ แต่ต้องวางแผนก่อน rotate |
| มีคีย์ current เป็น asymmetric | มีคีย์ | **rotate แล้ว** — ดู `README.md` ข้อ 7.3 |
| legacy secret ถูก revoke | — | **cron ที่ส่ง anon key ใน `Authorization` จะได้ `401`** — ต้องแก้ทันที |

### 6.5 ถ้าจะทดสอบการรองรับคีย์แบบใหม่ (รอบถัดไป เท่านั้น)

> **ไม่ทำในรอบแรก** · ต้องขออนุมัติแยกและทำบนโปรเจกต์ทดสอบเท่านั้น

| ขั้น | ทำอะไร |
|---|---|
| 1 | ใน **โปรเจกต์ทดสอบ** migrate JWT secret แล้ว rotate |
| 2 | ล็อกอินบัญชี admin ทดสอบใหม่เพื่อให้ได้ token ที่ลงนามด้วยคีย์ใหม่ |
| 3 | ยิง G7 ซ้ำ — ต้องได้ `200` |
| 4 | ยิง G6 ซ้ำ — ถ้าได้ `401 Invalid JWT` แปลว่า cron path ต้องเปลี่ยน |
| 5 | พิจารณาเปลี่ยนไปใช้ `getClaims()` แทน `getUser()` ตามที่เอกสารแนะนำ |

---

## 7. ตารางบันทึกผล

| ขั้น | ต้องได้ | ได้จริง | ผ่าน |
|---|---|---|---|
| G1 ไม่มี credential | `401` | ______ | ☐ |
| G2 bearer มั่ว | `401` | ______ | ☐ |
| **G3 anon key เป็น bearer** | **`401`** | ______ | ☐ |
| G4 GET | `405` | ______ | ☐ |
| G5 cron secret ผิด | `401` | ______ | ☐ |
| G6 cron secret ถูก | `200` | ______ | ☐ |
| G7 admin token | `200` | ______ | ☐ |
| G8 user token | `403` | ______ | ☐ |
| V2–V5 ปิด `verify_jwt` | ผ่านครบ | ______ | ☐ |
| C1 รันสคริปต์ cron | ไม่มี exception | ______ | ☐ |
| C2 สถานะ job | เดิม false · ใหม่ true | ______ | ☐ |
| C3 `pg_net status_code` | `200` | ______ | ☐ |
| C4 rollback | คืนสภาพได้ | ______ | ☐ |
| S1 Dashboard (test) | บันทึกสถานะคีย์ | ______ | ☐ |
| S2 Dashboard (prod) | บันทึกสถานะคีย์ | ______ | ☐ |
| S3 JWKS | บันทึกจำนวนและ `alg` | ______ | ☐ |

---

## 8. ข้อห้ามระหว่างทดสอบ

| ข้อห้าม | เหตุผล |
|---|---|
| ทำขั้นใดก็ตามบน production | แผนนี้สำหรับโปรเจกต์ทดสอบเท่านั้น · ยกเว้น S2 ที่ **ดูอย่างเดียว** |
| **rotate หรือ revoke signing key ในรอบแรก** | ย้อนกลับไม่ได้บางส่วน · ไม่จำเป็นต่อการยืนยัน patch นี้ |
| แสดงค่า key/token/secret บนจอหรือในรายงาน | ใช้วิธีรับค่าแบบไม่แสดงและล้างตัวแปรทุกครั้ง |
| `select *` จากตารางผลตอบกลับของ `pg_net` | คอลัมน์ `headers` มี secret |
| ถือว่า unit test ยืนยัน gateway ได้ | ชุดทดสอบเรียก `handler()` โดยตรง |
| ถือว่า `job_run_details = succeeded` คือ sync สำเร็จ | ยืนยันแค่การส่งงาน SQL |
| **สรุปสถานะ signing key จากจำนวนคีย์ใน JWKS** | JWKS ไม่บอกสถานะและมีแคชหลายชั้น — ดูข้อ 6.1 |

---

## 9. เอกสารอ้างอิง

- [JWT Signing Keys](https://supabase.com/docs/guides/auth/signing-keys)
- [Securing Edge Functions](https://supabase.com/docs/guides/functions/auth)
- [Function Configuration](https://supabase.com/docs/guides/functions/function-configuration)
- [Authorization headers](https://supabase.com/docs/guides/functions/auth-headers)
- [Migrating to publishable and secret API keys](https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys)
