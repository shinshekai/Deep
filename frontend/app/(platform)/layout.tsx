"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, Activity, Brain, Settings } from "lucide-react";
import { useWebSocket } from "@/providers/websocket-provider";
import { Badge } from "@/components/ui/badge";

const navItems = [
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/chat", label: "Chat", icon: Brain },
  { href: "/dashboard", label: "Dashboard", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { status, conditionState } = useWebSocket();

  const statusColor =
    status === "open"
      ? conditionState && conditionState !== "green"
        ? conditionState === "yellow"
          ? "yellow"
          : "red"
        : "green"
      : status === "connecting"
        ? "yellow"
        : "red";

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-zinc-800 bg-zinc-950">
        <div className="flex h-14 items-center px-4 font-semibold text-sm tracking-wide uppercase border-b border-zinc-800">
          Doc Intelligence
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-zinc-800 text-white"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Connection status */}
        <div className="border-t border-zinc-800 p-3">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span
              className={`h-2 w-2 rounded-full ${
                statusColor === "green"
                  ? "bg-emerald-500"
                  : statusColor === "yellow"
                    ? "bg-yellow-500"
                    : "bg-red-500"
              }`}
            />
            {status === "open" ? "Connected" : status === "connecting" ? "Connecting..." : "Disconnected"}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-background">{children}</main>
    </div>
  );
}
