"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, Brain, Activity, Settings as SettingsIcon, Zap, BarChart3, Database } from "lucide-react";
import { useWebSocket } from "@/providers/websocket-provider";
import { Badge } from "@/components/ui/badge";
import { ErrorBoundary } from "@/components/error-boundary";

const navSections = [
  {
    label: "Documents",
    items: [
      { href: "/documents", label: "Library", icon: Database },
      { href: "/knowledge", label: "Knowledge Bases", icon: BarChart3 },
    ],
  },
  {
    label: "AI Features",
    items: [
      { href: "/solve", label: "Smart Solve", icon: Zap },
      { href: "/chat", label: "Chat", icon: Brain },
      { href: "/research", label: "Deep Research", icon: FileText },
      { href: "/guide", label: "Guided Learning", icon: Brain },
      { href: "/questions", label: "Question Generator", icon: FileText },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: Activity },
      { href: "/models", label: "Model Tiers", icon: Zap },
      { href: "/settings", label: "Settings", icon: SettingsIcon },
    ],
  },
];

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { solveStatus, metricsStatus, pressure } = useWebSocket();

  const isConnected = solveStatus === "open" || metricsStatus === "open";

  const pressureColor =
    pressure === "green"
      ? "bg-emerald-500"
      : pressure === "yellow"
        ? "bg-yellow-500"
        : pressure === "orange"
          ? "bg-orange-500"
          : "bg-red-500";

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-zinc-800 bg-zinc-950">
        <div className="flex h-14 items-center px-4 font-semibold text-sm tracking-wide uppercase border-b border-zinc-800">
          UDIP
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.label} className="mb-2">
              <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">
                {section.label}
              </div>
              <div className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-zinc-800 text-white"
                          : "text-zinc-500 hover:bg-zinc-800/60 hover:text-zinc-300"
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Connection status */}
        <div className="border-t border-zinc-800 p-3">
          <div className="mb-2 flex items-center gap-2 text-xs text-zinc-500">
            <span
              className={`h-2 w-2 rounded-full ${
                isConnected ? pressureColor : "bg-zinc-600"
              }`}
            />
            {isConnected ? "Connected" : "Disconnected"}
          </div>
          <div className="space-y-1 text-[10px] text-zinc-600 font-mono">
            <div>Solve :{solveStatus}</div>
            <div>Metrics :{metricsStatus}</div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-background">
        <ErrorBoundary fallbackTitle="Page Error">
          {children}
        </ErrorBoundary>
      </main>
    </div>
  );
}
