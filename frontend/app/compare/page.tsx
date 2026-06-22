import Link from "next/link";
import type { Metadata } from "next";
import { Check, X, Minus } from "lucide-react";

export const metadata: Metadata = {
  title: "DEEP vs ChatGPT vs Claude vs Gemini — Honest Comparison",
  description:
    "Privacy, offline support, document Q&A, memory, price, and data location compared. See where DEEP wins and where cloud AI is stronger.",
  openGraph: {
    title: "DEEP vs Cloud AI — Honest Comparison",
    description: "Privacy-first local AI vs ChatGPT, Claude, and Gemini. See the tradeoffs.",
    type: "website",
  },
};

type Cell = "yes" | "no" | "partial" | "text";

interface Feature {
  feature: string;
  deep: Cell | string;
  chatgpt: Cell | string;
  claude: Cell | string;
  gemini: Cell | string;
  note?: string;
}

const features: Feature[] = [
  {
    feature: "Privacy",
    deep: "yes",
    chatgpt: "no",
    claude: "no",
    gemini: "no",
    note: "DEEP processes everything locally. Cloud AI sends your documents to their servers.",
  },
  {
    feature: "Offline / Air-Gapped",
    deep: "yes",
    chatgpt: "no",
    claude: "no",
    gemini: "no",
    note: "DEEP works with zero internet. Cloud AI requires constant connectivity.",
  },
  {
    feature: "Document Q&A",
    deep: "yes",
    chatgpt: "yes",
    claude: "yes",
    gemini: "yes",
  },
  {
    feature: "Multi-Agent Pipeline",
    deep: "yes",
    chatgpt: "partial",
    claude: "partial",
    gemini: "no",
    note: "DEEP has 6-agent pipeline with tool dispatch. Cloud AI has single-model responses.",
  },
  {
    feature: "Persistent Memory",
    deep: "yes",
    chatgpt: "partial",
    claude: "partial",
    gemini: "partial",
    note: "DEEP has 3-layer L1→L2→L3 consolidating memory. Cloud AI has limited context windows.",
  },
  {
    feature: "Citation Tracking",
    deep: "yes",
    chatgpt: "partial",
    claude: "yes",
    gemini: "partial",
  },
  {
    feature: "Raw Reasoning Quality",
    deep: "partial",
    chatgpt: "yes",
    claude: "yes",
    gemini: "yes",
    note: "DEEP uses local models (7B-27B). Cloud AI uses frontier models (1T+ params). DEEP is weaker here — be honest about it.",
  },
  {
    feature: "Price",
    deep: "Free",
    chatgpt: "$20/mo",
    claude: "$20/mo",
    gemini: "$20/mo",
    note: "DEEP is free. You provide the GPU. Cloud AI requires monthly subscriptions.",
  },
  {
    feature: "Data Location",
    deep: "Your machine",
    chatgpt: "OpenAI servers",
    claude: "Anthropic servers",
    gemini: "Google servers",
  },
  {
    feature: "Rate Limits",
    deep: "None",
    chatgpt: "Yes",
    claude: "Yes",
    gemini: "Yes",
    note: "DEEP has no rate limits — your GPU is the only constraint.",
  },
  {
    feature: "Custom Model Selection",
    deep: "yes",
    chatgpt: "no",
    claude: "no",
    gemini: "no",
    note: "DEEP lets you choose any GGUF model. Cloud AI locks you to their models.",
  },
  {
    feature: "Open Source",
    deep: "yes",
    chatgpt: "no",
    claude: "no",
    gemini: "no",
  },
];

function CellRender({ value }: { value: Cell | string }) {
  if (value === "yes")
    return <Check className="h-4 w-4 text-emerald-500 mx-auto" aria-label="Yes" />;
  if (value === "no")
    return <X className="h-4 w-4 text-rose-500 mx-auto" aria-label="No" />;
  if (value === "partial")
    return <Minus className="h-4 w-4 text-amber-500 mx-auto" aria-label="Partial" />;
  return <span className="text-xs text-zinc-400 font-mono">{value}</span>;
}

export default function ComparePage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <section className="border-b border-zinc-900">
        <div className="max-w-5xl mx-auto px-6 py-16 text-center space-y-4">
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">
            DEEP vs Cloud AI — An Honest Comparison
          </h1>
          <p className="text-zinc-400 max-w-2xl mx-auto">
            We&apos;re honest about where DEEP is weaker. The competitive moat isn&apos;t better AI —
            it&apos;s trust and privacy for people who legally can&apos;t use cloud providers.
          </p>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-6 py-12">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left py-3 px-4 font-bold text-zinc-300">Feature</th>
                <th className="text-center py-3 px-4 font-bold text-indigo-400">DEEP</th>
                <th className="text-center py-3 px-4 font-bold text-zinc-400">ChatGPT</th>
                <th className="text-center py-3 px-4 font-bold text-zinc-400">Claude</th>
                <th className="text-center py-3 px-4 font-bold text-zinc-400">Gemini</th>
              </tr>
            </thead>
            <tbody>
              {features.map((f, i) => (
                <tr
                  key={f.feature}
                  className={`border-b border-zinc-900/50 ${i % 2 === 0 ? "bg-zinc-950/20" : ""}`}
                >
                  <td className="py-3 px-4 font-medium text-zinc-200">{f.feature}</td>
                  <td className="py-3 px-4 text-center bg-indigo-950/10">
                    <CellRender value={f.deep} />
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellRender value={f.chatgpt} />
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellRender value={f.claude} />
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellRender value={f.gemini} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Notes */}
        <div className="mt-8 space-y-3">
          {features
            .filter((f) => f.note)
            .map((f) => (
              <div key={f.feature} className="rounded-lg border border-zinc-900 bg-zinc-950/30 p-3">
                <span className="text-xs font-bold text-indigo-400 font-mono">{f.feature}:</span>
                <span className="text-xs text-zinc-400 ml-2">{f.note}</span>
              </div>
            ))}
        </div>

        {/* Legend */}
        <div className="mt-6 flex justify-center gap-6 text-xs text-zinc-500">
          <div className="flex items-center gap-1.5">
            <Check className="h-3 w-3 text-emerald-500" /> Full support
          </div>
          <div className="flex items-center gap-1.5">
            <Minus className="h-3 w-3 text-amber-500" /> Partial
          </div>
          <div className="flex items-center gap-1.5">
            <X className="h-3 w-3 text-rose-500" /> Not supported
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-zinc-900">
        <div className="max-w-2xl mx-auto px-6 py-16 text-center space-y-6">
          <h2 className="text-2xl font-bold">
            DEEP isn&apos;t trying to beat GPT-5 in raw reasoning.
          </h2>
          <p className="text-zinc-400">
            It&apos;s for the people who can&apos;t use cloud AI — and that&apos;s a market
            cloud providers structurally cannot serve.
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center justify-center rounded-xl bg-indigo-600 hover:bg-indigo-500 px-8 py-3.5 text-sm font-bold text-white shadow-lg shadow-indigo-600/20 transition"
          >
            Try DEEP →
          </Link>
        </div>
      </section>

      <footer className="border-t border-zinc-900 py-8">
        <div className="max-w-4xl mx-auto px-6 flex justify-between items-center text-xs text-zinc-600">
          <span>DEEP — Document Intelligence Platform</span>
          <Link href="/" className="hover:text-zinc-400 transition">
            ← Back to Home
          </Link>
        </div>
      </footer>
    </div>
  );
}
