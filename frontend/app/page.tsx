import Link from "next/link";
import { FileText, Activity, Zap } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">
          Document Intelligence Platform
        </h1>
        <p className="text-lg text-zinc-400 max-w-xl">
          Local AI-powered document analysis with multi-agent reasoning,
          vectorless retrieval, and real-time performance monitoring.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          href="/solve"
          className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 px-6 py-4 transition-colors hover:border-zinc-700 hover:bg-zinc-800/50"
        >
          <Zap className="h-5 w-5 text-zinc-400" />
          <div>
            <div className="font-medium">Smart Solve</div>
            <div className="text-sm text-zinc-500">
              Multi-agent document Q&A
            </div>
          </div>
        </Link>

        <Link
          href="/documents"
          className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 px-6 py-4 transition-colors hover:border-zinc-700 hover:bg-zinc-800/50"
        >
          <FileText className="h-5 w-5 text-zinc-400" />
          <div>
            <div className="font-medium">Documents</div>
            <div className="text-sm text-zinc-500">
              Upload and query documents
            </div>
          </div>
        </Link>

        <Link
          href="/dashboard"
          className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 px-6 py-4 transition-colors hover:border-zinc-700 hover:bg-zinc-800/50"
        >
          <Activity className="h-5 w-5 text-zinc-400" />
          <div>
            <div className="font-medium">Performance Dashboard</div>
            <div className="text-sm text-zinc-500">
              Monitor inference telemetry
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
