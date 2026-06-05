"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  FileText, 
  Brain, 
  Activity, 
  Settings as SettingsIcon, 
  Zap, 
  BarChart3, 
  Database, 
  Layers, 
  X, 
  Gauge, 
  Menu,
  HelpCircle,
  LayoutGrid,
  ChevronLeft,
  ChevronRight,
  Monitor,
  Laptop,
  Smartphone,
  BookOpen,
  PenTool
} from "lucide-react";
import { useWebSocket } from "@/providers/websocket-provider";
import { Badge } from "@/components/ui/badge";
import { ErrorBoundary } from "@/components/error-boundary";
import { API_BASE_URL, secureFetch } from "@/lib/config";

const navSections = [
  {
    label: "Documents Hub",
    items: [
      { href: "/documents", label: "Library Node", icon: Database },
      { href: "/knowledge", label: "Knowledge Bases", icon: BarChart3 },
    ],
  },
  {
    label: "AI Orchestration",
    items: [
      { href: "/solve", label: "Smart Solve", icon: Zap },
      { href: "/chat", label: "Chat Lab", icon: Brain },
      { href: "/research", label: "Deep Research", icon: FileText },
      { href: "/guide", label: "Guided Tutor", icon: Brain },
      { href: "/questions", label: "Question Studio", icon: FileText },
      { href: "/notebooks", label: "Notebook Lab", icon: BookOpen },
      { href: "/cowriter", label: "CoWriter Studio", icon: PenTool },
    ],
  },
  {
    label: "Platform Infrastructure",
    items: [
      { href: "/dashboard", label: "Performance Observ", icon: Activity },
      { href: "/models", label: "Models Console", icon: Zap },
      { href: "/settings", label: "Runtime Settings", icon: SettingsIcon },
    ],
  },
];

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { solveStatus, metricsStatus } = useWebSocket();

  // Responsive Layout States
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Active targeted model selections
  const [activeSelections, setActiveSelections] = useState<{
    T1: { model_id: string } | null;
    T2: { model_id: string } | null;
    T3: { model_id: string } | null;
  }>({ T1: null, T2: null, T3: null });

  // Telemetry details
  const [vram, setVram] = useState({
    total_mb: 24576,
    used_mb: 8192,
    free_mb: 16384,
    utilization_pct: 33.3,
    pressure_level: "green",
    gpu_available: true,
  });

  async function loadSelections() {
    try {
      const response = await secureFetch(`${API_BASE_URL}/models/selection`);
      if (response.ok) {
        const data = await response.json();
        if (data.active_selections) {
          setActiveSelections(data.active_selections);
        } else if (data.active_selection) {
          setActiveSelections({ T1: null, T2: null, T3: data.active_selection });
        }
      }
    } catch (e) {
      console.error("Failed to load layout selections", e);
    }
  }

  async function loadTelemetry() {
    try {
      const response = await secureFetch(`${API_BASE_URL}/vram/status`);
      if (response.ok) {
        const data = await response.json();
        setVram(data);
      }
    } catch {}
  }

  useEffect(() => {
    loadSelections();
    loadTelemetry();
    
    const telemetryInterval = setInterval(loadTelemetry, 5000);
    const selectionsInterval = setInterval(loadSelections, 10000);
    
    // Auto-collapse sidebar on tablets/smaller devices
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarCollapsed(true);
        setRightPanelOpen(false);
      } else {
        setSidebarCollapsed(false);
        setRightPanelOpen(true);
      }
    };
    
    window.addEventListener("resize", handleResize);
    handleResize(); // Initial call
    
    return () => {
      clearInterval(telemetryInterval);
      clearInterval(selectionsInterval);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  const isConnected = solveStatus === "open" || metricsStatus === "open";

  const pressureBulbColor =
    vram.pressure_level === "green"
      ? "bg-emerald-500 shadow-emerald-500/50"
      : vram.pressure_level === "yellow"
        ? "bg-yellow-500 shadow-yellow-500/50"
        : vram.pressure_level === "orange"
          ? "bg-orange-500 shadow-orange-500/50"
          : "bg-red-500 shadow-red-500/50";

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-zinc-950 text-zinc-100 antialiased font-sans">
      
      {/* Skip navigation — visible only on focus for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-lg focus:bg-indigo-600 focus:px-4 focus:py-2 focus:text-sm focus:font-bold focus:text-white focus:shadow-lg"
      >
        Skip to main content
      </a>
      
      {/* ── STICKY CONTROL HEADER ── */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md px-3 md:px-4 select-none">
        
        {/* Logo and Mobile Toggle */}
        <div className="flex items-center gap-3 md:gap-6">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-900 bg-zinc-950 text-zinc-400 hover:text-white md:hidden focus:outline-none"
            title="Toggle Menu"
            aria-expanded={mobileMenuOpen}
          >
            <Menu className="h-4.5 w-4.5" />
          </button>

          <Link href="/" className="flex items-center gap-2 group focus:outline-none">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 font-black text-xs text-white shadow-lg shadow-indigo-600/30 group-hover:bg-indigo-500 transition">
              D
            </div>
            <span className="font-extrabold text-sm tracking-widest text-white font-sans uppercase">DEEP</span>
          </Link>
          <div className="hidden h-4 w-[1px] bg-zinc-800 md:block" />
          <div className="hidden lg:flex items-center gap-1.5 text-xs text-zinc-400">
            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Workspace:</span>
            <span className="font-semibold text-zinc-200">Quantum Systems Research</span>
          </div>
        </div>

        {/* Global Active Tier Selection Indicators */}
        <div className="hidden md:flex items-center gap-3.5 bg-zinc-900/30 border border-zinc-900 rounded-full px-3.5 py-1 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-[8px] font-extrabold font-mono text-indigo-400 bg-indigo-950/30 border border-indigo-900/20 px-1 rounded">T1</span>
            <span className="text-[10px] font-semibold text-zinc-300 truncate max-w-[80px]">
              {activeSelections.T1 ? activeSelections.T1.model_id : "Safe Cascade"}
            </span>
          </div>
          <div className="h-3 w-[1px] bg-zinc-850" />
          <div className="flex items-center gap-1">
            <span className="text-[8px] font-extrabold font-mono text-indigo-400 bg-indigo-950/30 border border-indigo-900/20 px-1 rounded">T2</span>
            <span className="text-[10px] font-semibold text-zinc-300 truncate max-w-[80px]">
              {activeSelections.T2 ? activeSelections.T2.model_id : "Safe Cascade"}
            </span>
          </div>
          <div className="h-3 w-[1px] bg-zinc-850" />
          <div className="flex items-center gap-1">
            <span className="text-[8px] font-extrabold font-mono text-indigo-400 bg-indigo-950/30 border border-indigo-900/20 px-1 rounded">T3</span>
            <span className="text-[10px] font-semibold text-zinc-300 truncate max-w-[80px]">
              {activeSelections.T3 ? activeSelections.T3.model_id : "Safe Cascade"}
            </span>
          </div>
        </div>

        {/* Interactive Telemetry & Settings Actions */}
        <div className="flex items-center gap-2.5">
          
          {/* Quick VRAM pressure indicator bulb */}
          <div className="flex items-center gap-2 bg-zinc-900/40 border border-zinc-900 px-2.5 py-1 rounded-lg text-xs font-mono">
            <span className="text-[9px] uppercase font-bold text-zinc-500 tracking-wider">VRAM</span>
            <span className="relative flex h-2 w-2 shrink-0">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${pressureBulbColor}`} />
              <span className={`relative inline-flex rounded-full h-2 w-2 ${pressureBulbColor}`} />
            </span>
            <span className="font-semibold text-zinc-200 hidden sm:inline">{Math.round(vram.utilization_pct)}%</span>
          </div>

          {/* Right Observability Toggle button */}
          <button
            type="button"
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            className={`hidden lg:flex h-8 w-8 items-center justify-center rounded-lg border transition ${
              rightPanelOpen
                ? "bg-zinc-800 border-zinc-700 text-white"
                : "bg-zinc-950 border-zinc-900 text-zinc-400 hover:text-white"
            } focus:outline-none`}
            title="Toggle dynamic context panel"
            aria-expanded={rightPanelOpen}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* ── CENTRAL SPLIT VIEWPORT ── */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* LEFT NAV SIDEBAR (RESPONSIVE COLLAPSIBLE) */}
        <aside 
          className={`hidden md:flex flex-col shrink-0 border-r border-zinc-900 bg-zinc-950/40 transition-all duration-300 relative select-none ${
            sidebarCollapsed ? "w-16" : "w-56"
          }`}
          aria-label="Navigation sidebar"
        >
          {/* Collapse Trigger arrow badge */}
          <button
            type="button"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="absolute top-3 -right-3 z-30 flex h-6 w-6 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white transition focus:outline-none"
            aria-label="Toggle sidebar collapse"
            aria-expanded={!sidebarCollapsed}
          >
            {sidebarCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
          </button>
          
          {/* Workspace navigation content */}
          <nav className="flex-1 space-y-6 p-4 overflow-y-auto overflow-x-hidden">
            {navSections.map((section) => (
              <div key={section.label} className="space-y-2">
                <span className={`px-2.5 text-[9px] font-bold uppercase tracking-widest text-zinc-500 font-mono block transition-opacity duration-200 ${
                  sidebarCollapsed ? "opacity-0 h-0 overflow-hidden" : "opacity-100"
                }`}>
                  {section.label}
                </span>
                
                <div className="flex flex-col gap-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`flex items-center justify-between group rounded-lg px-2.5 py-2.5 text-xs font-semibold transition relative ${
                          isActive
                            ? "bg-indigo-600/10 text-indigo-400 border border-indigo-500/20"
                            : "text-zinc-500 hover:bg-zinc-900/40 hover:text-zinc-300 border border-transparent"
                        }`}
                        title={sidebarCollapsed ? item.label : undefined}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <Icon className="h-4 w-4 shrink-0" />
                          <span className={`transition-opacity duration-200 truncate ${
                            sidebarCollapsed ? "opacity-0 w-0 h-0 overflow-hidden" : "opacity-100"
                          }`}>
                            {item.label}
                          </span>
                        </div>
                        {!sidebarCollapsed && isActive && <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          {/* Connection status section footer */}
          <div className="border-t border-zinc-900 p-4 bg-zinc-950/20">
            <div className="flex items-center justify-between text-[9px] font-bold font-mono text-zinc-500 uppercase">
              <span className={sidebarCollapsed ? "hidden" : "inline"}>Sockets</span>
              <span className={`h-1.5 w-1.5 rounded-full ${isConnected ? "bg-emerald-500" : "bg-zinc-750"}`} />
            </div>
            <div className={`mt-2 space-y-1 font-mono text-[9px] text-zinc-600 leading-normal ${
              sidebarCollapsed ? "hidden" : "block"
            }`}>
              <div className="flex justify-between">
                <span>Solve:</span>
                <span className={solveStatus === "open" ? "text-emerald-500" : "text-zinc-600"}>{solveStatus}</span>
              </div>
              <div className="flex justify-between">
                <span>Metrics:</span>
                <span className={metricsStatus === "open" ? "text-emerald-500" : "text-zinc-600"}>{metricsStatus}</span>
              </div>
            </div>
          </div>
        </aside>

        {/* MOBILE SIDEOVER SLIDE DRAWER MENU */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden bg-black/60 backdrop-blur-xs select-none">
            <div className="w-64 border-r border-zinc-850 bg-zinc-950 p-4.5 flex flex-col justify-between animate-slide-in relative">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="absolute top-4 right-4 p-1 rounded text-zinc-500 hover:text-white focus:outline-none"
                aria-label="Close mobile menu"
              >
                <X className="h-5 w-5" />
              </button>
              
              <div className="space-y-6 mt-6">
                <Link href="/" className="flex items-center gap-2 pb-4 border-b border-zinc-900">
                  <div className="flex h-6 w-6 items-center justify-center rounded bg-indigo-600 font-black text-xs text-white">D</div>
                  <span className="font-extrabold text-xs tracking-wider text-white">DEEP OVERLAY</span>
                </Link>

                <nav className="space-y-5">
                  {navSections.map((section) => (
                    <div key={section.label} className="space-y-1">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-600 font-mono block">{section.label}</span>
                      <div className="flex flex-col gap-0.5">
                        {section.items.map((item) => {
                          const Icon = item.icon;
                          const isActive = pathname === item.href;
                          return (
                            <Link
                              key={item.href}
                              href={item.href}
                              onClick={() => setMobileMenuOpen(false)}
                              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-xs font-semibold ${
                                isActive ? "bg-indigo-600/10 text-indigo-400" : "text-zinc-500 hover:bg-zinc-900"
                              }`}
                            >
                              <Icon className="h-4 w-4" />
                              <span>{item.label}</span>
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </nav>
              </div>

              <div className="border-t border-zinc-900 pt-4 text-[9px] font-mono text-zinc-600">
                Workspace: Quantum Systems
              </div>
            </div>
            {/* Tap outside backdrop */}
            <div className="flex-1" onClick={() => setMobileMenuOpen(false)} />
          </div>
        )}

        {/* PRIMARY WORKSPACE CONTENT FRAME (RESPONSIVE GRID) */}
        <main id="main-content" tabIndex={-1} className="flex-1 overflow-auto bg-zinc-950 select-text relative">
          <div className="w-full h-full p-3 sm:p-5 md:p-6 lg:p-8 max-w-[1600px] mx-auto">
            <ErrorBoundary fallbackTitle="Page Load Error">
              {children}
            </ErrorBoundary>
          </div>
        </main>

        {/* ── RIGHT DYNAMIC OBSERVAL PANEL (COLLAPSIBLE / RESPONSIVE HIDE) ── */}
        {rightPanelOpen && (
          <aside className="hidden lg:flex w-80 shrink-0 flex-col border-l border-zinc-900 bg-zinc-950/40 overflow-hidden animate-slide-in select-none" aria-label="Observability panel">
            
            {/* Header panel */}
            <div className="flex items-center justify-between border-b border-zinc-900 px-4.5 py-3">
              <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono">Dynamic Observ</span>
              <button
                type="button"
                onClick={() => setRightPanelOpen(false)}
                className="p-1 rounded text-zinc-500 hover:text-white hover:bg-zinc-900 transition focus:outline-none"
                aria-label="Close observability panel"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Dynamic Observability content sections */}
            <div className="flex-1 p-4.5 overflow-y-auto space-y-5">
              
              {/* Telemetry Dial stats */}
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-4 space-y-3.5">
                <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
                  <Gauge className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Hardware Telemetry</span>
                </div>
                
                <div className="grid grid-cols-2 gap-3 font-mono">
                  <div className="bg-zinc-950/50 border border-zinc-900 rounded p-2.5">
                    <div className="text-[9px] uppercase font-semibold text-zinc-500">Total VRAM</div>
                    <div className="text-xs font-bold text-zinc-200 mt-1">{(vram.total_mb / 1024).toFixed(1)} GB</div>
                  </div>
                  <div className="bg-zinc-950/50 border border-zinc-900 rounded p-2.5">
                    <div className="text-[9px] uppercase font-semibold text-zinc-500">Used VRAM</div>
                    <div className="text-xs font-bold text-zinc-200 mt-1">{(vram.used_mb / 1024).toFixed(1)} GB</div>
                  </div>
                </div>

                {/* Utilization gauge bar */}
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] text-zinc-400 font-mono">
                    <span>PRESSURE CAPACITY</span>
                    <span className="font-bold text-zinc-300">{Math.round(vram.utilization_pct)}%</span>
                  </div>
                  <div className="relative h-2 w-full rounded-full bg-zinc-900 overflow-hidden">
                    <div 
                      className={`absolute h-full rounded-full transition-all duration-500 ${
                        vram.pressure_level === "red" 
                          ? "bg-red-500" 
                          : vram.pressure_level === "orange" 
                            ? "bg-orange-500" 
                            : vram.pressure_level === "yellow" 
                              ? "bg-yellow-500" 
                              : "bg-indigo-500"
                      }`}
                      style={{ width: `${vram.utilization_pct}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Pipeline queues */}
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-4 space-y-3.5">
                <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
                  <Layers className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Pipeline Queues</span>
                </div>
                
                <div className="space-y-2 font-mono text-[9px]">
                  <div className="flex justify-between items-center bg-zinc-950/40 p-2 border border-zinc-900 rounded">
                    <span className="font-bold text-zinc-450">T1 RETRIEVAL QUEUE</span>
                    <Badge className="bg-indigo-600/10 text-indigo-400 border border-indigo-900/30 text-[9px] px-1 py-0 font-mono">4 SEM</Badge>
                  </div>
                  <div className="flex justify-between items-center bg-zinc-950/40 p-2 border border-zinc-900 rounded">
                    <span className="font-bold text-zinc-450">T2 REASONING QUEUE</span>
                    <Badge className="bg-indigo-600/10 text-indigo-400 border border-indigo-900/30 text-[9px] px-1 py-0 font-mono">2 SEM</Badge>
                  </div>
                  <div className="flex justify-between items-center bg-zinc-950/40 p-2 border border-zinc-900 rounded">
                    <span className="font-bold text-zinc-450">T3 SYNTHESIS QUEUE</span>
                    <Badge className="bg-indigo-600/10 text-indigo-400 border border-indigo-900/30 text-[9px] px-1 py-0 font-mono">1 SEM</Badge>
                  </div>
                </div>
              </div>

              {/* Active Agent States stream */}
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-4 space-y-3">
                <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
                  <Activity className="h-3.5 w-3.5 text-indigo-400" />
                  <span>Mission State logs</span>
                </div>

                <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
                  <div className="text-[10px] text-zinc-400 leading-normal border-l-2 border-zinc-800 pl-2">
                    <div className="font-bold font-mono text-zinc-450">SYSTEM INGESTION</div>
                    <p className="mt-0.5">Vector KB generator ready. Ingested 12 documents successfully.</p>
                  </div>
                  <div className="text-[10px] text-zinc-400 leading-normal border-l-2 border-zinc-800 pl-2">
                    <div className="font-bold font-mono text-zinc-450">KV CACHE STATE</div>
                    <p className="mt-0.5">Quantized cache active: asymmetric fp16 window allocation.</p>
                  </div>
                  <div className="text-[10px] text-zinc-400 leading-normal border-l-2 border-emerald-800 pl-2 bg-emerald-950/5">
                    <div className="font-bold font-mono text-emerald-400">HEALTH CHECK OK</div>
                    <p className="mt-0.5 text-emerald-300/80">LM Studio connected. Active GGUF model targeted on Tier 3.</p>
                  </div>
                </div>
              </div>

            </div>

            {/* Quick help button footer */}
            <div className="border-t border-zinc-900 p-4 bg-zinc-950/20 flex justify-between items-center">
              <span className="text-[9px] font-mono text-zinc-500">DEEP V2 ENGINE v2.0.4</span>
              <HelpCircle className="h-4 w-4 text-zinc-600 hover:text-white transition cursor-pointer" />
            </div>

          </aside>
        )}

      </div>

    </div>
  );
}
