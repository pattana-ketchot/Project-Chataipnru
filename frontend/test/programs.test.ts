import { describe, expect, it } from "vitest";
import { editionYear, latestEditions, shortTitle } from "@/lib/programs";
import type { Course } from "@/lib/types";

const course = (id: string, title: string): Course => ({
  id, title, code: null, provider: null, summary: null, mode: null,
  duration_weeks: null, price: null, currency: "THB", tags: [],
});

describe("shortTitle", () => {
  it("ตัดคำนำหน้าและปีออกจากชื่อเต็ม", () => {
    expect(shortTitle("หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"))
      .toBe("วิทยาการคอมพิวเตอร์");
    expect(shortTitle("หลักสูตรศิลปศาสตรบัณฑิต สาขาวิชาคหกรรมศาสตร์ (พ.ศ. 2564)"))
      .toBe("คหกรรมศาสตร์");
  });

  it("ไม่กลืนชื่อสาขาที่ซ้ำกับชื่อปริญญา", () => {
    // ชื่อสาขากับชื่อปริญญาเป็นคำเดียวกันในหลักสูตรนี้ และไม่มีคำว่า "สาขาวิชา" คั่น
    // การตัดชื่อปริญญาแบบตะกละจะกลืนชื่อสาขาไปด้วยจนเหลือสตริงว่าง
    expect(shortTitle("หลักสูตรการแพทย์แผนไทยประยุกต์บัณฑิต (พ.ศ. 2565)"))
      .toBe("การแพทย์แผนไทยประยุกต์");
  });
});

describe("editionYear", () => {
  it("อ่านปีท้ายชื่อ และคืน 0 เมื่อไม่มี", () => {
    expect(editionYear("สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)")).toBe(2561);
    expect(editionYear("สาขาวิชาวิทยาการคอมพิวเตอร์")).toBe(0);
  });
});

describe("latestEditions", () => {
  it("เก็บเฉพาะฉบับปีล่าสุดของแต่ละสาขา", () => {
    const out = latestEditions([
      course("a", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2561)"),
      course("b", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (พ.ศ. 2566)"),
      course("c", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาคณิตศาสตร์ (พ.ศ. 2564)"),
    ]);
    expect(out.map(c => c.id).sort()).toEqual(["b", "c"]);
  });

  it("ไม่สนใจลำดับที่ฉบับเก่าและใหม่ถูกส่งเข้ามา", () => {
    const older = course("old", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2561)");
    const newer = course("new", "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาเทคโนโลยีสารสนเทศ (พ.ศ. 2566)");
    expect(latestEditions([newer, older]).map(c => c.id)).toEqual(["new"]);
    expect(latestEditions([older, newer]).map(c => c.id)).toEqual(["new"]);
  });
});
