import type { Metadata } from "next";
import "@fontsource-variable/noto-sans-kr";
import "./globals.css";
import AppShell from "../components/AppShell";
export const metadata: Metadata = {
  title: "BPMC · 통합 지출 관리",
  description: "행사별 지출내역과 영수증을 한 곳에서 관리합니다.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
