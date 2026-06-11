"use client";

import { AlertCircle } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 space-y-3">
      <div className="flex items-center gap-2 text-red-400">
        <AlertCircle className="h-5 w-5" />
        <span className="font-bold text-xs uppercase font-mono">Solve Execution Failed</span>
      </div>
      <p className="text-xs text-zinc-400 leading-normal select-text">
        {message}
      </p>
      <button
        onClick={onDismiss}
        aria-label="Dismiss error"
        className="rounded-lg border border-red-800 bg-red-950/50 px-3 py-1.5 text-xs text-red-300 hover:bg-red-900 transition"
      >
        Dismiss
      </button>
    </div>
  );
}
