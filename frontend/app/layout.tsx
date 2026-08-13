import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Course Compass", description: "ผู้ช่วยค้นหาหลักสูตรที่เหมาะกับคุณ" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="th"><body>{children}</body></html>;
}
