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
    title: "YouBike 歷史需求觀測站",
    description: "以 2023 年臺北轉乘資料與天氣預測 100 個高需求站點的每小時借車需求。",
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: {
      title: "YouBike 歷史需求觀測站",
      description: "看見城市下一小時的流動——2023 臺北轉乘需求歷史回測。",
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
