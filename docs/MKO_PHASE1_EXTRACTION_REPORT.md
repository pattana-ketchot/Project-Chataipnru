# รายงานผลการสกัดข้อมูล มคอ. — Phase 1

สร้างเมื่อ 2026-09-15 04:49 จากฐานข้อมูล local · ตัวสกัดรุ่น `mko-phase1-2026.09.15`

> ทำงานเฉพาะบนเครื่อง local ไม่ได้แตะฐานข้อมูล production ไม่มีการเรียกโมเดลภาษาในการสกัดค่า ค่าที่สถานะ `verified` ทั้งหมดเป็นการยืนยันอัตโนมัติด้วยกฎ ยังไม่มีคนตรวจ (`auto:two_locations_agree` = ค่าเดียวกันจากอย่างน้อยสองหน้าของเล่มเดียวกัน, `auto:documents_agree` = ค่าตรงกันระหว่างฉบับเต็มกับใบสรุปของหลักสูตรฉบับปีเดียวกัน)

## ภาพรวม

| รายการ | จำนวน |
|---|---|
| หลักสูตร (ฉบับปี) | 24 |
| เอกสาร | 31 |
| หน้าใน `mko.document_pages` | 4,129 |
| หน้าที่มีข้อความจาก OCR เดิม | 186 |
| หน้าสารบัญ (ไม่ใช้สกัดค่า) | 58 |
| หน้าที่ข้อความมีร่องรอยฟอนต์เพี้ยน | 22 |
| การสกัดที่ล้มเหลว | 0 |

รูปแบบเอกสารที่ตรวจพบ: `brief` 10, `std2565` 3, `tqf2` 17, `web_page` 1

## สรุปราย field (ระดับหลักสูตร)

นับสถานะที่ดีที่สุดของแต่ละหลักสูตรจากทุกเอกสารของหลักสูตรนั้น (verified > candidate > needs_review > not_found) · "สกัดได้" = verified หรือ candidate

| field | สกัดได้ | verified | candidate | needs_review | not_found |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | **24/24** | 7 | 17 | 0 | 0 |
| ชื่อหลักสูตร (อังกฤษ) | **24/24** | 7 | 17 | 0 | 0 |
| ชื่อปริญญา (ไทย) | **20/24** | 1 | 19 | 0 | 4 |
| อักษรย่อปริญญา (ไทย) | **23/24** | 7 | 16 | 0 | 1 |
| ชื่อปริญญา (อังกฤษ) | **20/24** | 1 | 19 | 0 | 4 |
| อักษรย่อปริญญา (อังกฤษ) | **23/24** | 7 | 16 | 0 | 1 |
| ระดับการศึกษา | **24/24** | 7 | 17 | 0 | 0 |
| ปีหลักสูตร (พ.ศ.) | **23/24** | 20 | 3 | 0 | 1 |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | **23/24** | 20 | 3 | 0 | 1 |
| จำนวนหน่วยกิตรวม | **24/24** | 20 | 4 | 0 | 0 |
| วัตถุประสงค์ (จำนวนข้อ) | **22/24** | 6 | 16 | 1 | 1 |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | **20/24** | 0 | 20 | 1 | 3 |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | **19/24** | 0 | 19 | 0 | 5 |

## สรุปราย field (ระดับเอกสาร)

| field | verified | candidate | needs_review | not_found |
|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | 14 | 17 | 0 | 0 |
| ชื่อหลักสูตร (อังกฤษ) | 14 | 17 | 0 | 0 |
| ชื่อปริญญา (ไทย) | 2 | 19 | 0 | 10 |
| อักษรย่อปริญญา (ไทย) | 14 | 16 | 0 | 1 |
| ชื่อปริญญา (อังกฤษ) | 2 | 19 | 0 | 10 |
| อักษรย่อปริญญา (อังกฤษ) | 14 | 16 | 0 | 1 |
| ระดับการศึกษา | 14 | 17 | 0 | 0 |
| ปีหลักสูตร (พ.ศ.) | 27 | 3 | 0 | 1 |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | 27 | 3 | 0 | 1 |
| จำนวนหน่วยกิตรวม | 27 | 4 | 0 | 0 |
| วัตถุประสงค์ (จำนวนข้อ) | 12 | 16 | 2 | 1 |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | 0 | 20 | 1 | 10 |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | 0 | 19 | 0 | 12 |

รายการข้อความที่เก็บใน `mko.list_items`: admission candidate 25, career candidate 118, career needs_review 9, objective candidate 72, objective needs_review 8, objective verified 62

## ผลเทียบกับชุดค่าที่ตรวจด้วยมือ (`eval/mko_gold.json`)

| field | ตรวจ | correct | needs_review | not_found | wrong | ไม่ควรมีค่าแต่มี | verified ที่ผิด |
|---|---|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| ชื่อหลักสูตร (อังกฤษ) | 11 | 11 | 0 | 0 | 0 | 0 | 0 |
| ชื่อปริญญา (ไทย) | 11 | 11 | 0 | 0 | 0 | 0 | 0 |
| อักษรย่อปริญญา (ไทย) | 11 | 11 | 0 | 0 | 0 | 0 | 0 |
| อักษรย่อปริญญา (อังกฤษ) | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ระดับการศึกษา | 31 | 31 | 0 | 0 | 0 | 0 | 0 |
| ปีหลักสูตร (พ.ศ.) | 31 | 31 | 0 | 0 | 0 | 0 | 0 |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | 30 | 30 | 0 | 0 | 0 | 0 | 0 |
| จำนวนหน่วยกิตรวม | 31 | 31 | 0 | 0 | 0 | 0 | 0 |
| วัตถุประสงค์ (จำนวนข้อ) | 8 | 6 | 2 | 0 | 0 | 0 | 0 |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | 16 | 15 | 1 | 0 | 0 | 0 | 0 |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | 14 | 14 | 0 | 0 | 0 | 0 | 0 |

<details><summary>รายการที่ไม่ใช่ correct</summary>

| ไฟล์ | field | ค่าที่ตรวจไว้ | ผลของระบบ | ผล |
|---|---|---|---|---|
| cs66.pdf | objectives | 4 | 4 (needs_review) | needs_review |
| cs66_brief.pdf | objectives | 4 | 4 (needs_review) | needs_review |
| it66.pdf | careers | 9 | 9 (needs_review) | needs_review |

</details>

## ค่าที่ต้องให้คนตรวจ (needs_review) — 3 รายการ

| ไฟล์ | field | ค่า | หน้า | เหตุผล | ข้อความที่ยกมา |
|---|---|---|---|---|---|
| it66.pdf | careers | 9 | 6–7 | เลขข้อในเอกสารข้ามหรือซ้ำ ต้องตรวจการแบ่งรายการ | 8. อาชีพที่สามารถประกอบได้หลังสำเร็จการศึกษา 8.1 นักเทคโนโลยีสารสนเทศ 8.2 นักพั… |
| cs66_brief.pdf | objectives | 4 | 1 | รายการไม่ตรงกันระหว่างเอกสารของหลักสูตรเดียวกัน | วัตถุประสงค์ของหลักสูตร 1. เพื่อผลิตบัณฑิตให้มีความรู้ และทักษะด้านวิทยาการคอมพ… |
| cs66.pdf | objectives | 4 | 11 | รายการไม่ตรงกันระหว่างเอกสารของหลักสูตรเดียวกัน | 1.3 วัตถุประสงค์ของหลักสูตร 1.3.1 เพื่อผลิตบัณฑิตให้มีความรู้ และทักษะด้านวิทยา… |

## รายละเอียดรายหลักสูตร

### หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2560)

เอกสาร: `attm.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | attm.pdf | หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | attm.pdf | Bachelor of Applied Thai Traditional Medicine Program | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | attm.pdf | การแพทย์แผนไทยประยุกต์บัณฑิต | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | attm.pdf | พทป.บ. | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | attm.pdf | Bachelor of Applied Thai Traditional Medicine | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | attm.pdf | B.ATM. | candidate | 6 | — |
| ระดับการศึกษา | attm.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | attm.pdf | 2560 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | attm.pdf | new | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | attm.pdf | 149 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 15 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | attm.pdf | 4 ข้อ | candidate | 11–12 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | attm.pdf | 3 ข้อ | candidate | 8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | attm.pdf | 1 ข้อ | candidate | 13 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2565)

เอกสาร: `attm65.pdf` (tqf2), `attm65_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | attm65_brief.pdf | หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | attm65.pdf | หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | attm65_brief.pdf | Bachelor of Applied Thai Traditional Medicine Program | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | attm65.pdf | Bachelor of Applied Thai Traditional Medicine Program | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | attm65_brief.pdf | การแพทย์แผนไทยประยุกต์บัณฑิต | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | attm65.pdf | การแพทย์แผนไทยประยุกต์บัณฑิต | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | attm65_brief.pdf | พทป.บ. | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | attm65.pdf | พทป.บ. | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | attm65_brief.pdf | Bachelor of Applied Thai Traditional Medicine | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | attm65.pdf | Bachelor of Applied Thai Traditional Medicine | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | attm65_brief.pdf | B.ATM. | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | attm65.pdf | B.ATM. | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | attm65_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | attm65.pdf | bachelor | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | attm65_brief.pdf | 2565 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | attm65.pdf | 2565 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | attm65_brief.pdf | revised | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | attm65.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | attm65_brief.pdf | 147 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | attm65.pdf | 147 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 22 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | attm65_brief.pdf | 6 ข้อ | verified | 1 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | attm65.pdf | 6 ข้อ | verified | 12–13 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | attm65_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | attm65.pdf | 3 ข้อ | candidate | 8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | attm65_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | attm65.pdf | 1 ข้อ | candidate | 19 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน (พ.ศ. 2568)

เอกสาร: `agri68_phd.pdf` (std2565)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | agri68_phd.pdf | หลักสูตรปรัชญาดุษฎีบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหาร… | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | agri68_phd.pdf | Doctor of Philosophy Program in Agricultural Technology Management an… | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | agri68_phd.pdf | ปรัชญาดุษฎีบัณฑิต (การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | agri68_phd.pdf | ปร.ด. (การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | agri68_phd.pdf | Doctor of Philosophy (Agricultural Technology Management and Communit… | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | agri68_phd.pdf | Ph.D. (Agricultural Technology Management and Community Resource Admi… | candidate | 6 | — |
| ระดับการศึกษา | agri68_phd.pdf | doctoral | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | agri68_phd.pdf | 2568 | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2, 6, 8 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | agri68_phd.pdf | new | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2, 6, 8 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | agri68_phd.pdf | 48 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 26 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | agri68_phd.pdf | 4 ข้อ | candidate | 19 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | agri68_phd.pdf | 6 ข้อ | candidate | 8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | agri68_phd.pdf | 2 ข้อ | candidate | 91 | — |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาการจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ (พ.ศ. 2565)

เอกสาร: `en65.pdf` (tqf2), `en65_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | en65_brief.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาการจัดการสิ่งแวดล้อมและทรัพยากรธรรมช… | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | en65.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาการจัดการสิ่งแวดล้อมและทรัพยากรธรรมช… | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | en65_brief.pdf | Bachelor of Science Program in Environmental and Natural Resource Man… | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | en65.pdf | Bachelor of Science Program in Environmental and Natural Resource Man… | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | en65_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (ไทย) | en65.pdf | วิทยาศาสตรบัณฑิต (การจัดการสิ่งแวดล้อมและ ทรัพยากรธรรมชาติ) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | en65_brief.pdf | วท.บ. (การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | en65.pdf | วท.บ. (การจัดการสิ่งแวดล้อมและทรัพยากรธรรมชาติ) | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | en65_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | en65.pdf | Bachelor of Science (Environmental and Natural Resource Management) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | en65_brief.pdf | B.Sc. (Environmental and Natural Resource Management) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | en65.pdf | B.Sc. (Environmental and Natural Resource Management) | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | en65_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | en65.pdf | bachelor | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | en65_brief.pdf | 2565 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | en65.pdf | 2565 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | en65_brief.pdf | revised | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | en65.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | en65_brief.pdf | 135 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | en65.pdf | 135 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 21 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | en65_brief.pdf | 6 ข้อ | verified | 1 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | en65.pdf | 6 ข้อ | verified | 14–15 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | en65_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | en65.pdf | 6 ข้อ | candidate | 8–9 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | en65_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | en65.pdf | 1 ข้อ | candidate | 18 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรสมัยใหม่ (พ.ศ. 2564)

เอกสาร: `atm.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | atm.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาการจัดการ เทคโนโลยีการเกษตรสมัยใหม่ | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | atm.pdf | Bachelor of Science Program in Modern Agricultural Technology Managem… | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | atm.pdf | วิทยาศาสตรบัณฑิต (การจัดการเทคโนโลยีการเกษตรสมัยใหม่) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | atm.pdf | วท.บ. (การจัดการเทคโนโลยีการเกษตรสมัยใหม่) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | atm.pdf | Bachelor of Science (Modern Agricultural Technology Management) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | atm.pdf | B.Sc. (Modern Agricultural Technology Management) | candidate | 6 | — |
| ระดับการศึกษา | atm.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | atm.pdf | 2564 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | atm.pdf | revised | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | atm.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 19 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | atm.pdf | 5 ข้อ | candidate | 13–14 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | atm.pdf | 3 ข้อ | candidate | 8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | atm.pdf | 1 ข้อ | candidate | 16 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)

เอกสาร: `ma64.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | ma64.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | ma64.pdf | Bachelor of Science Program in Mathematics | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | ma64.pdf | วิทยาศาสตรบัณฑิต (คณิตศาสตร์) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | ma64.pdf | วท.บ. (คณิตศาสตร์) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | ma64.pdf | Bachelor of Science (Mathematics) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | ma64.pdf | B.Sc. (Mathematics) | candidate | 6 | — |
| ระดับการศึกษา | ma64.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | ma64.pdf | 2564 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | ma64.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | ma64.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 16 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | ma64.pdf | 4 ข้อ | candidate | 12–13 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | ma64.pdf | 5 ข้อ | candidate | 7–8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | ma64.pdf | 1 ข้อ | candidate | 14 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2569)

เอกสาร: `ma69.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | ma69.pdf | หลักสูตรวิทยาศาสตบัณฑิต สาขาวิชาคณิตศาสตร์ | candidate | 1 | — |
| ชื่อหลักสูตร (อังกฤษ) | ma69.pdf | Bachelor of Science Program in Mathematics | candidate | 1 | — |
| ชื่อปริญญา (ไทย) | ma69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (ไทย) | ma69.pdf | วท.บ. (คณิตศาสตร์) | candidate | 1 | — |
| ชื่อปริญญา (อังกฤษ) | ma69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (อังกฤษ) | ma69.pdf | B.Sc. (Mathematics) | candidate | 1 | — |
| ระดับการศึกษา | ma69.pdf | bachelor | candidate | 1 | — |
| ปีหลักสูตร (พ.ศ.) | ma69.pdf | 2569 | candidate | 1 | — |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | ma69.pdf | revised | candidate | 1 | — |
| จำนวนหน่วยกิตรวม | ma69.pdf | 124 | candidate | 1 | — |
| วัตถุประสงค์ (จำนวนข้อ) | ma69.pdf | 4 ข้อ | candidate | 1 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | ma69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | ma69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2564)

เอกสาร: `animation64.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | animation64.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | animation64.pdf | Bachelor of Science Program in Computer Animation and Multimedia | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | animation64.pdf | วิทยาศาสตรบัณฑิต (คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | animation64.pdf | วท.บ. (คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | animation64.pdf | Bachelor of Science (Computer Animation and Multimedia) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | animation64.pdf | B.Sc. (Computer Animation and Multimedia) | candidate | 6 | — |
| ระดับการศึกษา | animation64.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | animation64.pdf | 2564 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | animation64.pdf | revised | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | animation64.pdf | 127 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 21 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | animation64.pdf | 4 ข้อ | candidate | 13–14 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | animation64.pdf | 8 ข้อ | candidate | 8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | animation64.pdf | 1 ข้อ | candidate | 17–18 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย (พ.ศ. 2569)

เอกสาร: `animation69.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | animation69.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคอมพิวเตอร์แอนิเมชันและมัลติมีเดีย | candidate | 1 | — |
| ชื่อหลักสูตร (อังกฤษ) | animation69.pdf | Bachelor of Science Program in Computer Animation and Multimedia | candidate | 1 | — |
| ชื่อปริญญา (ไทย) | animation69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (ไทย) | animation69.pdf | วท.บ. (คอมพิวเตอร์แอนิเมชันและมัลติมีเดีย) | candidate | 1 | — |
| ชื่อปริญญา (อังกฤษ) | animation69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (อังกฤษ) | animation69.pdf | B.Sc. (Computer Animation and Multimedia) | candidate | 1 | — |
| ระดับการศึกษา | animation69.pdf | bachelor | candidate | 1 | — |
| ปีหลักสูตร (พ.ศ.) | animation69.pdf | 2569 | candidate | 1 | — |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | animation69.pdf | revised | candidate | 1 | — |
| จำนวนหน่วยกิตรวม | animation69.pdf | 127 | candidate | 1 | — |
| วัตถุประสงค์ (จำนวนข้อ) | animation69.pdf | 6 ข้อ | candidate | 1 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | animation69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | animation69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)

เอกสาร: `cs61.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | cs61.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | cs61.pdf | Bachelor of Science Program in Computer Science | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | cs61.pdf | วิทยาศาสตรบัณฑิต (วิทยาการคอมพิวเตอร์) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | cs61.pdf | วท.บ. (วิทยาการคอมพิวเตอร์) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | cs61.pdf | Bachelor of Science (Computer Science) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | cs61.pdf | B.Sc. (Computer Science) | candidate | 6 | — |
| ระดับการศึกษา | cs61.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | cs61.pdf | 2561 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cs61.pdf | revised | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | cs61.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 19 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | cs61.pdf | 4 ข้อ | candidate | 14 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cs61.pdf | 8 ข้อ | candidate | 7–8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cs61.pdf | 1 ข้อ | candidate | 16–17 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)

เอกสาร: `cs66.pdf` (tqf2), `cs66_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | cs66_brief.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | cs66.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ | verified | 2 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | cs66_brief.pdf | Bachelor of Science Program in Computer Science | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | cs66.pdf | Bachelor of Science Program in Computer Science | verified | 2 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | cs66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (ไทย) | cs66.pdf | วิทยาศาสตรบัณฑิต (วิทยาการคอมพิวเตอร์) | candidate | 2 | — |
| อักษรย่อปริญญา (ไทย) | cs66_brief.pdf | วท.บ. (วิทยาการคอมพิวเตอร์) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | cs66.pdf | วท.บ. (วิทยาการคอมพิวเตอร์) | verified | 2 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | cs66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | cs66.pdf | Bachelor of Science (Computer Science) | candidate | 2 | — |
| อักษรย่อปริญญา (อังกฤษ) | cs66_brief.pdf | B.Sc. (Computer Science) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | cs66.pdf | B.Sc. (Computer Science) | verified | 2 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | cs66_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | cs66.pdf | bachelor | verified | 2 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | cs66_brief.pdf | 2566 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | cs66.pdf | 2566 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 3 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cs66_brief.pdf | revised | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cs66.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 3 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | cs66_brief.pdf | 130 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | cs66.pdf | 130 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 12 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | cs66_brief.pdf | 4 ข้อ | needs_review | 1 | รายการไม่ตรงกันระหว่างเอกสารของหลักสูตรเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | cs66.pdf | 4 ข้อ | needs_review | 11 | รายการไม่ตรงกันระหว่างเอกสารของหลักสูตรเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cs66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cs66.pdf | 9 ข้อ | candidate | 3–4 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cs66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cs66.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2561)

เอกสาร: `cosmetic61.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | cosmetic61.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | cosmetic61.pdf | Bachelor of Science Program in Cosmetic Science | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | cosmetic61.pdf | วิทยาศาสตรบัณฑิต (วิทยาศาสตร์เครื่องสำอาง) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | cosmetic61.pdf | วท.บ. (วิทยาศาสตร์เครื่องสำอาง) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | cosmetic61.pdf | Bachelor of Science (Cosmetic Science) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | cosmetic61.pdf | B.Sc. (Cosmetic Science) | candidate | 6 | — |
| ระดับการศึกษา | cosmetic61.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | cosmetic61.pdf | 2561 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cosmetic61.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | cosmetic61.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 20 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | cosmetic61.pdf | 4 ข้อ | candidate | 13–14 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cosmetic61.pdf | 7 ข้อ | candidate | 7–8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cosmetic61.pdf | 1 ข้อ | candidate | 17 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง (พ.ศ. 2566)

เอกสาร: `cos66.pdf` (tqf2), `cos66_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | cos66_brief.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | cos66.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์เครื่องสำอาง | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | cos66_brief.pdf | Bachelor of Science Program in Cosmetic Science | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | cos66.pdf | Bachelor of Science Program in Cosmetic Science | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | cos66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (ไทย) | cos66.pdf | วิทยาศาสตรบัณฑิต (วิทยาศาสตร์เครื่องสำอาง) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | cos66_brief.pdf | วท.บ. (วิทยาศาสตร์เครื่องสำอาง) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | cos66.pdf | วท.บ. (วิทยาศาสตร์เครื่องสำอาง) | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | cos66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | cos66.pdf | Bachelor of Science (Cosmetic Science) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | cos66_brief.pdf | B.Sc. (Cosmetic Science) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | cos66.pdf | B.Sc. (Cosmetic Science) | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | cos66_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | cos66.pdf | bachelor | verified | 6 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | cos66_brief.pdf | 2566 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | cos66.pdf | 2566 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cos66_brief.pdf | revised | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cos66.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | cos66_brief.pdf | 130 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | cos66.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 20 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | cos66_brief.pdf | 6 ข้อ | verified | 1 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | cos66.pdf | 6 ข้อ | verified | 15 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cos66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cos66.pdf | 7 ข้อ | candidate | 7–8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cos66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cos66.pdf | 1 ข้อ | candidate | 18 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์และเทคโนโลยีการอาหาร (พ.ศ. 2561)

เอกสาร: `fs61.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | fs61.pdf | หลักสูตรวิทยาศาสตรบัณฑิต วิทยาศาสตร์และเทคโนโลยีการอาหาร | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | fs61.pdf | Bachelor of Science Program in Food Science and Technology | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | fs61.pdf | วิทยาศาสตรบัณฑิต (วิทยาศาสตร์และเทคโนโลยีการอาหาร) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | fs61.pdf | วท.บ. (วิทยาศาสตร์และเทคโนโลยีการอาหาร) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | fs61.pdf | Bachelor of Science (Food Science and Technology) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | fs61.pdf | B.Sc. (Food Science and Technology) | candidate | 6 | — |
| ระดับการศึกษา | fs61.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | fs61.pdf | 2561 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | fs61.pdf | revised | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | fs61.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 22 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | fs61.pdf | 4 ข้อ | candidate | 15–16 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | fs61.pdf | 3 ข้อ | candidate | 7 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | fs61.pdf | 1 ข้อ | candidate | 19–20 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์และเทคโนโลยีสิ่งแวดล้อม (พ.ศ. 2560)

เอกสาร: `en60.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | en60.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาศาสตร์และเทคโนโลยีสิ่งแวดล้อม | candidate | 2 | — |
| ชื่อหลักสูตร (อังกฤษ) | en60.pdf | Bachelor of Science Program in Environmental Science and Technology | candidate | 2 | — |
| ชื่อปริญญา (ไทย) | en60.pdf | วิทยาศาสตรบัณฑิต (วิทยาศาสตร์และเทคโนโลยีสิ่งแวดล้อม) | candidate | 2 | — |
| อักษรย่อปริญญา (ไทย) | en60.pdf | วท.บ. (วิทยาศาสตร์และเทคโนโลยีสิ่งแวดล้อม) | candidate | 2 | — |
| ชื่อปริญญา (อังกฤษ) | en60.pdf | Bachelor of Science (Environmental Science and Technology) | candidate | 2 | — |
| อักษรย่อปริญญา (อังกฤษ) | en60.pdf | B.Sc. (Environmental Science and Technology ) | candidate | 2 | — |
| ระดับการศึกษา | en60.pdf | bachelor | candidate | 2 | — |
| ปีหลักสูตร (พ.ศ.) | en60.pdf | 2560 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 3 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | en60.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 3 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | en60.pdf | 138 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 19 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | en60.pdf | 7 ข้อ | candidate | 12–13 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | en60.pdf | 6 ข้อ | candidate | 4–5 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | en60.pdf | 1 ข้อ | candidate | 16 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีการจัดการสุขภาพ (พ.ศ. 2561)

เอกสาร: `ht61.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | ht61.pdf | วิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีการจัดการสุขภาพ | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | ht61.pdf | Bachelor of Science Program in Technology of Health Management | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | ht61.pdf | วิทยาศาสตรบัณฑิต (เทคโนโลยีการจัดการสุขภาพ) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | ht61.pdf | วท.บ. (เทคโนโลยีการจัดการสุขภาพ) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | ht61.pdf | Bachelor of Science (Technology of Health Management) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | ht61.pdf | B.Sc. (Technology of Health Management) | candidate | 6 | — |
| ระดับการศึกษา | ht61.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | ht61.pdf | 2561 | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2, 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | ht61.pdf | revised | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2, 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | ht61.pdf | 130 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 19 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | ht61.pdf | 4 ข้อ | candidate | 13 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | ht61.pdf | 3 ข้อ | candidate | 7 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | ht61.pdf | 1 ข้อ | candidate | 16–17 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ (พ.ศ. 2568)

เอกสาร: `bio2568.pdf` (std2565), `bio2568_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | bio2568_brief.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบ… | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | bio2568.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบ… | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | bio2568_brief.pdf | Bachelor of Science Program in Biological Product Technology and Entr… | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | bio2568.pdf | Bachelor of Science Program in Biological Product Technology and Entr… | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | bio2568_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (ไทย) | bio2568.pdf | วิทยาศาสตรบัณฑิต (เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ) | candidate | 7 | — |
| อักษรย่อปริญญา (ไทย) | bio2568_brief.pdf | วท.บ. (เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | bio2568.pdf | วท.บ. (เทคโนโลยีผลิตภัณฑ์ชีวภาพกับการประกอบธุรกิจ) | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | bio2568_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | bio2568.pdf | Bachelor of Science (Biological Product Technology and Entrepreneursh… | candidate | 7 | — |
| อักษรย่อปริญญา (อังกฤษ) | bio2568_brief.pdf | B.Sc. (Biological Product Technology and Entrepreneurship) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | bio2568.pdf | B.Sc. (Biological Product Technology and Entrepreneurship) | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | bio2568_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | bio2568.pdf | bachelor | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | bio2568_brief.pdf | 2568 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | bio2568.pdf | 2568 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 7, 9 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | bio2568_brief.pdf | new | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | bio2568.pdf | new | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 7, 9 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | bio2568_brief.pdf | 127 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | bio2568.pdf | 127 | verified | 7 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 7, 27 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | bio2568_brief.pdf | 4 ข้อ | verified | 1 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | bio2568.pdf | 4 ข้อ | verified | 22 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | bio2568_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | bio2568.pdf | 5 ข้อ | candidate | 9–10 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | bio2568_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | bio2568.pdf | 2 ข้อ | candidate | 154 | — |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2561)

เอกสาร: `it61.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | it61.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | it61.pdf | Bachelor of Science Program in Information Technology | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | it61.pdf | วิทยาศาสตรบัณฑิต (เทคโนโลยีสารสนเทศ) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | it61.pdf | วท.บ. (เทคโนโลยีสารสนเทศ) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | it61.pdf | Bachelor of Science (Information Technology) | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | it61.pdf | B.Sc. (Information Technology) | candidate | 6 | — |
| ระดับการศึกษา | it61.pdf | bachelor | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | it61.pdf | 2561 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | it61.pdf | revised | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 7 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | it61.pdf | 127 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 21 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | it61.pdf | 4 ข้อ | candidate | 14–15 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | it61.pdf | 8 ข้อ | candidate | 8 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | it61.pdf | 1 ข้อ | candidate | 18–19 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)

เอกสาร: `it66.pdf` (tqf2), `it66_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | it66_brief.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | it66.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ | verified | 5 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | it66_brief.pdf | Bachelor of Science Program in Information Technology | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | it66.pdf | Bachelor of Science Program in Information Technology | verified | 5 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | it66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (ไทย) | it66.pdf | วิทยาศาสตรบัณฑิต (เทคโนโลยีสารสนเทศ) | candidate | 5 | — |
| อักษรย่อปริญญา (ไทย) | it66_brief.pdf | วท.บ. (เทคโนโลยีสารสนเทศ) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | it66.pdf | วท.บ. (เทคโนโลยีสารสนเทศ) | verified | 5 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | it66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | it66.pdf | Bachelor of Science (Information Technology) | candidate | 5 | — |
| อักษรย่อปริญญา (อังกฤษ) | it66_brief.pdf | B.Sc. (Information Technology) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | it66.pdf | B.Sc. (Information Technology) | verified | 5 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | it66_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | it66.pdf | bachelor | verified | 5 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | it66_brief.pdf | 2566 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | it66.pdf | 2566 | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 5, 6 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | it66_brief.pdf | revised | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | it66.pdf | revised | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 5, 6 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | it66_brief.pdf | 130 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | it66.pdf | 130 | verified | 5 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 5, 19 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | it66_brief.pdf | 5 ข้อ | verified | 1 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | it66.pdf | 5 ข้อ | verified | 13 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | it66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | it66.pdf | 9 ข้อ | needs_review | 6–7 | เลขข้อในเอกสารข้ามหรือซ้ำ ต้องตรวจการแบ่งรายการ |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | it66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | it66.pdf | 3 ข้อ | candidate | 16–17 | — |

### หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่ (พ.ศ. 2566)

เอกสาร: `food66.pdf` (tqf2), `food66_brief.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | food66_brief.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีอาหารและความเป็นผู้ประกอบกา… | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (ไทย) | food66.pdf | หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีอาหารและความเป็นผู้ประกอบกา… | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | food66_brief.pdf | Bachelor of Science Program in Food Technology and Modern Entrepreneu… | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อหลักสูตร (อังกฤษ) | food66.pdf | Bachelor of Science Program in Food Technology and Modern Entrepreneu… | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (ไทย) | food66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (ไทย) | food66.pdf | วิทยาศาสตรบัณฑิต (เทคโนโลยีอาหารและความเป็นผู้ประกอบการ สมัยใหม่) | candidate | 7 | — |
| อักษรย่อปริญญา (ไทย) | food66_brief.pdf | วท.บ. (เทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (ไทย) | food66.pdf | วท.บ. (เทคโนโลยีอาหารและความเป็นผู้ประกอบการสมัยใหม่) | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ชื่อปริญญา (อังกฤษ) | food66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | food66.pdf | Bachelor of Science (Food Technology and Modern Entrepreneurship) | candidate | 7 | — |
| อักษรย่อปริญญา (อังกฤษ) | food66_brief.pdf | B.Sc. (Food Technology and Modern Entrepreneurship) | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อักษรย่อปริญญา (อังกฤษ) | food66.pdf | B.Sc. (Food Technology and Modern Entrepreneurship) | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | food66_brief.pdf | bachelor | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ระดับการศึกษา | food66.pdf | bachelor | verified | 7 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | food66_brief.pdf | 2566 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ปีหลักสูตร (พ.ศ.) | food66.pdf | 2566 | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 7, 8 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | food66_brief.pdf | revised | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | food66.pdf | revised | verified | 2 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 2, 7, 8 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | food66_brief.pdf | 124 | verified | 1 | auto:documents_agree: ค่าตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| จำนวนหน่วยกิตรวม | food66.pdf | 124 | verified | 7 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 7, 23 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | food66_brief.pdf | 4 ข้อ | verified | 1 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| วัตถุประสงค์ (จำนวนข้อ) | food66.pdf | 4 ข้อ | verified | 16–17 | auto:documents_agree: รายการตรงกันระหว่างเอกสารของหลักสูตรฉบับปีเดียวกัน |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | food66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | food66.pdf | 4 ข้อ | candidate | 8–9 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | food66_brief.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | food66.pdf | 1 ข้อ | candidate | 20 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน (พ.ศ. 2568)

เอกสาร: `agri68_master.pdf` (std2565)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | agri68_master.pdf | หลักสูตรวิทยาศาสตรมหาบัณฑิต สาขาวิชาการจัดการเทคโนโลยีการเกษตรและบริห… | candidate | 6 | — |
| ชื่อหลักสูตร (อังกฤษ) | agri68_master.pdf | Master of Science Program in Agricultural Technology Management and C… | candidate | 6 | — |
| ชื่อปริญญา (ไทย) | agri68_master.pdf | วิทยาศาสตรมหาบัณฑิต (การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน) | candidate | 6 | — |
| อักษรย่อปริญญา (ไทย) | agri68_master.pdf | วท.ม. (การจัดการเทคโนโลยีการเกษตรและบริหารทรัพยากรชุมชน) | candidate | 6 | — |
| ชื่อปริญญา (อังกฤษ) | agri68_master.pdf | Master of Science (Agricultural Technology Management and Community R… | candidate | 6 | — |
| อักษรย่อปริญญา (อังกฤษ) | agri68_master.pdf | M.S. (Agricultural Technology Management and Community Resource admin… | candidate | 6 | — |
| ระดับการศึกษา | agri68_master.pdf | master | candidate | 6 | — |
| ปีหลักสูตร (พ.ศ.) | agri68_master.pdf | 2568 | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2, 6, 8 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | agri68_master.pdf | new | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2, 6, 8 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | agri68_master.pdf | 36 | verified | 6 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 6, 25 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | agri68_master.pdf | 5 ข้อ | candidate | 19–20 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | agri68_master.pdf | 6 ข้อ | candidate | 8–9 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | agri68_master.pdf | 3 ข้อ | candidate | 85 | — |

### หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาการประกอบอาหารและการบริการอาหาร (พ.ศ. 2569)

เอกสาร: `cook69.pdf` (brief)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | cook69.pdf | หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาการประกอบอาหารและการบริการอาหาร | candidate | 1 | — |
| ชื่อหลักสูตร (อังกฤษ) | cook69.pdf | Bachelor of Arts Program in Culinary Arts and Service | candidate | 1 | — |
| ชื่อปริญญา (ไทย) | cook69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (ไทย) | cook69.pdf | ศศ.บ. (การประกอบอาหารและการบริการอาหาร) | candidate | 1 | — |
| ชื่อปริญญา (อังกฤษ) | cook69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (อังกฤษ) | cook69.pdf | B.A. (Culinary Arts and Service) | candidate | 1 | — |
| ระดับการศึกษา | cook69.pdf | bachelor | candidate | 1 | — |
| ปีหลักสูตร (พ.ศ.) | cook69.pdf | 2569 | candidate | 1 | — |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | cook69.pdf | revised | candidate | 1 | — |
| จำนวนหน่วยกิตรวม | cook69.pdf | 128 | candidate | 1 | — |
| วัตถุประสงค์ (จำนวนข้อ) | cook69.pdf | 4 ข้อ | candidate | 1 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | cook69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | cook69.pdf | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |

### หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาคหกรรมศาสตร์ (พ.ศ. 2564)

เอกสาร: `ds2564.pdf` (tqf2)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | ds2564.pdf | หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาคหกรรมศาสตร์ | candidate | 1 | — |
| ชื่อหลักสูตร (อังกฤษ) | ds2564.pdf | Bachelor of Arts Program in Home Economics | candidate | 1 | — |
| ชื่อปริญญา (ไทย) | ds2564.pdf | ศิลปศาสตรบัณฑิต (คหกรรมศาสตร์) | candidate | 1 | — |
| อักษรย่อปริญญา (ไทย) | ds2564.pdf | ศศ.บ. (คหกรรมศาสตร์) | candidate | 1 | — |
| ชื่อปริญญา (อังกฤษ) | ds2564.pdf | Bachelor of Arts (Home Economics) | candidate | 1 | — |
| อักษรย่อปริญญา (อังกฤษ) | ds2564.pdf | B.A. (Home Economics) | candidate | 1 | — |
| ระดับการศึกษา | ds2564.pdf | bachelor | candidate | 1 | — |
| ปีหลักสูตร (พ.ศ.) | ds2564.pdf | 2564 | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2 (chapter1.item6, front) |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | ds2564.pdf | revised | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 2 (chapter1.item6, front) |
| จำนวนหน่วยกิตรวม | ds2564.pdf | 130 | verified | 1 | auto:two_locations_agree: ค่าเดียวกันจากหน้า 1, 14 (chapter1.item4, chapter3.it… |
| วัตถุประสงค์ (จำนวนข้อ) | ds2564.pdf | 5 ข้อ | candidate | 8–9 | — |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | ds2564.pdf | 11 ข้อ | candidate | 2–3 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | ds2564.pdf | 1 ข้อ | candidate | 11 | ไม่มีเลขข้อ เก็บทั้งย่อหน้าเป็นรายการเดียว |

### หลักสูตรสาธารณสุขศาสตรบัณฑิต สาขาวิชาสาธารณสุขศาสตร์

เอกสาร: `ph_web.txt` (web_page)

| field | ไฟล์ | ค่า | สถานะ | หน้า | หมายเหตุ |
|---|---|---|---|---|---|
| ชื่อหลักสูตร (ไทย) | ph_web.txt | หลักสูตรสาธารณสุขศาสตรบัณฑิต สาขาวิชาสาธารณสุขศาสตร์ | candidate | 1 | — |
| ชื่อหลักสูตร (อังกฤษ) | ph_web.txt | Bachelor of Public Health Program in Public Health | candidate | 1 | — |
| ชื่อปริญญา (ไทย) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (ไทย) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ชื่อปริญญา (อังกฤษ) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อักษรย่อปริญญา (อังกฤษ) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ระดับการศึกษา | ph_web.txt | bachelor | candidate | 1 | — |
| ปีหลักสูตร (พ.ศ.) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| ประเภทหลักสูตร (ใหม่/ปรับปรุง) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| จำนวนหน่วยกิตรวม | ph_web.txt | 129 | candidate | 3 | — |
| วัตถุประสงค์ (จำนวนข้อ) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |
| อาชีพหลังสำเร็จการศึกษา (จำนวนข้อ) | ph_web.txt | 7 ข้อ | candidate | 7 | — |
| คุณสมบัติผู้เข้าศึกษา (จำนวนข้อ) | ph_web.txt | — | not_found | — | ไม่พบหัวข้อหรือค่าในตำแหน่งที่รูปแบบเอกสารกำหนด |

