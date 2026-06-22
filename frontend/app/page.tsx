import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DEEP — Private AI for Documents You Can't Upload to the Cloud",
  description:
    "Local-first document intelligence with multi-agent reasoning, vectorless retrieval, and real-time telemetry. Your data never leaves your machine.",
  openGraph: {
    title: "DEEP — Private AI for Documents",
    description: "ChatGPT for documents you can't upload to the cloud. Local-first, air-gapped ready, zero telemetry.",
    type: "website",
  },
  keywords: ["local AI", "document analysis", "privacy", "RAG", "offline", "LM Studio", "Ollama", "air-gapped"],
};

const valueProps = [
  {
    icon: "Private",
    title: "Private by Design",
    desc: "Your documents never leave your machine. No cloud uploads, no telemetry, no data exfiltration paths. SQLite stays local.",
  },
  {
    icon: "Local",
    title: "Runs Anywhere",
    desc: "Works with LM Studio or Ollama on your GPU. Air-gapped verified — operates with zero internet access. One command to install.",
  },
  {
    icon: "Powerful",
    title: "Production-Grade AI",
    desc: "Multi-agent pipeline with tool dispatch, three-layer memory consolidation, PageIndex tree retrieval, and live streaming.",
  },
];

const useCases = [
  {
    title: "Researcher",
    desc: "Analyze papers with multi-hop reasoning and citation tracking. Keep your unpublished work private.",
  },
  {
    title: "Compliance Officer",
    desc: "Process sensitive legal documents without sending them to third-party APIs. Audit trail included.",
  },
  {
    title: "Student",
    desc: "Ask questions about textbooks and lecture notes. No API key needed — just LM Studio and a GPU.",
  },
  {
    title: "New Hire Training",
    desc: "Upload internal SOPs and let DEEP answer questions. Company data stays on-premises.",
  },
];

const faqs = [
  {
    q: "Is my data safe?",
    a: "Yes. All processing happens locally. DEEP uses SQLite with device-scoped UUID isolation, OS keyring for secrets, and Docker containers with read-only filesystems and capability dropping.",
  },
  {
    q: "Does it need internet?",
    a: "No. DEEP is air-gapped verified — it works with zero outbound network access. You only need LM Studio or Ollama running locally with models downloaded.",
  },
  {
    q: "What GPU do I need?",
    desc: undefined,
    a: "Any NVIDIA GPU with 6GB+ VRAM works. DEEP auto-detects your VRAM and routes queries to appropriate model tiers (T1 retrieval, T2 reasoning, T3 synthesis).",
  },
  {
    q: "How is this different from ChatGPT?",
    a: "ChatGPT uploads your documents to OpenAI's servers. DEEP keeps everything local. You own the hardware, the models, and the data. No subscription, no rate limits, no privacy concerns.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-zinc-900">
        <div className="max-w-4xl mx-auto px-6 py-20 md:py-32 text-center space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-900/30 bg-indigo-950/10 px-4 py-1.5 text-xs font-mono text-indigo-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Air-Gapped Ready · Zero Telemetry
          </div>
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight bg-gradient-to-b from-zinc-100 via-zinc-200 to-zinc-500 bg-clip-text text-transparent">
            ChatGPT for documents
            <br />
            you can&apos;t upload to the cloud
          </h1>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            DEEP is a local-first AI document intelligence platform with multi-agent reasoning,
            vectorless retrieval, and real-time telemetry. Your data never leaves your machine.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center pt-4">
            <Link
              href="/chat"
              className="inline-flex items-center justify-center rounded-xl bg-indigo-600 hover:bg-indigo-500 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-600/20 transition"
            >
              Get Started →
            </Link>
            <a
              href="https://github.com/shinshekai/Deep"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 hover:border-zinc-700 px-6 py-3 text-sm font-bold text-zinc-300 transition"
            >
              View on GitHub
            </a>
          </div>
          {/* Install command */}
          <div className="pt-4">
            <div className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5 text-xs font-mono text-zinc-400">
              <span className="text-emerald-400">$</span>
              <span>bash install.sh</span>
              <span className="text-zinc-700">·</span>
              <span className="text-emerald-500/60">copy & run</span>
            </div>
          </div>
        </div>
      </section>

      {/* Trust bar */}
      <section className="border-b border-zinc-900 bg-zinc-950/20">
        <div className="max-w-4xl mx-auto px-6 py-4 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
          <span>Read-Only Containers</span>
          <span className="text-zinc-700">·</span>
          <span>Capability Dropping</span>
          <span className="text-zinc-700">·</span>
          <span>SSRF Protection</span>
          <span className="text-zinc-700">·</span>
          <span>Constant-Time Auth</span>
          <span className="text-zinc-700">·</span>
          <span>Air-Gapped Verified</span>
        </div>
      </section>

      {/* Value props */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <div className="grid gap-8 md:grid-cols-3">
          {valueProps.map((vp) => (
            <div key={vp.title} className="space-y-3 text-center">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-indigo-900/30 bg-indigo-950/10 text-indigo-400 font-bold text-sm">
                {vp.icon[0]}
              </div>
              <h3 className="text-lg font-bold">{vp.title}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{vp.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Use cases */}
      <section className="border-y border-zinc-900 bg-zinc-950/20">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="text-2xl font-bold text-center mb-12">Who is DEEP for?</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {useCases.map((uc) => (
              <div
                key={uc.title}
                className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 space-y-2"
              >
                <h3 className="text-sm font-bold text-indigo-400">{uc.title}</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">{uc.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-6 py-20">
        <h2 className="text-2xl font-bold text-center mb-12">Frequently Asked Questions</h2>
        <div className="space-y-6">
          {faqs.map((faq) => (
            <div key={faq.q} className="space-y-2">
              <h3 className="text-sm font-bold text-zinc-200">{faq.q}</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">{faq.a}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-zinc-900">
        <div className="max-w-2xl mx-auto px-6 py-20 text-center space-y-6">
          <h2 className="text-3xl font-bold">Ready to try DEEP?</h2>
          <p className="text-zinc-400">
            One command. No API keys. No cloud. Just your GPU and your documents.
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center justify-center rounded-xl bg-indigo-600 hover:bg-indigo-500 px-8 py-3.5 text-sm font-bold text-white shadow-lg shadow-indigo-600/20 transition"
          >
            Launch DEEP →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-900 py-8">
        <div className="max-w-4xl mx-auto px-6 flex flex-wrap justify-between items-center gap-4 text-xs text-zinc-600">
          <span>DEEP — Document Intelligence Platform</span>
          <div className="flex gap-4">
            <a href="https://github.com/shinshekai/Deep" target="_blank" rel="noopener" className="hover:text-zinc-400 transition">
              GitHub
            </a>
            <Link href="/chat" className="hover:text-zinc-400 transition">
              Launch App
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
