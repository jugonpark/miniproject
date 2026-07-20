import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "MOODWAVE", description: "상황·분위기 기반 AI 음악 큐레이터" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
