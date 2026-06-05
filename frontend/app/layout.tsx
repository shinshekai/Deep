import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import { WebSocketProvider } from "@/providers/websocket-provider";
import { MemoryProvider } from "@/providers/memory-provider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Document Intelligence Platform",
  description:
    "Unified local AI document intelligence with multi-agent reasoning, vectorless retrieval, and real-time telemetry.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <MemoryProvider>
          <WebSocketProvider>{children}</WebSocketProvider>
        </MemoryProvider>
      </body>
    </html>
  );
}
