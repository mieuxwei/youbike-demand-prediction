import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "https";
  const origin = host ? `${protocol}://${host}` : "https://sites.openai.com";
  const imageUrl = `${origin}/og.png`;

  return {
    title: "YouBike 需求分析、可用車預測與調度模擬",
    description: "2023 歷史轉乘需求、2026 即時站點可用車基準與 HGB 預測，以及固定假設的離線調度模擬。",
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: {
      title: "YouBike 需求分析、可用車預測與調度模擬",
      description: "歷史觀測、目前車況、未來估計與假設性模擬，分開呈現研究證據。",
      type: "website",
      locale: "zh_TW",
      images: [{ url: imageUrl, width: 1536, height: 1024, alt: "YouBike 歷史需求觀測站" }],
    },
    twitter: { card: "summary_large_image", images: [imageUrl] },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-Hant"><body>{children}</body></html>;
}
