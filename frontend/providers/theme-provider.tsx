"use client";

import { createContext, useContext, useEffect, useState, type ReactNode, useCallback } from "react";
import { THEME_STORAGE_KEY, THEMES, type ThemeId } from "@/lib/theme-constants";
import { useCrossTabSync, sendCrossTabMessage } from "@/hooks/use-cross-tab-sync";

interface ThemeContextValue {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
  themes: typeof THEMES;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem(THEME_STORAGE_KEY) as ThemeId | null;
    if (stored && THEMES.some((t) => t.id === stored)) {
      applyTheme(stored);
      setThemeState(stored);
    }
  }, []);

  const setTheme = useCallback((t: ThemeId) => {
    applyTheme(t);
    localStorage.setItem(THEME_STORAGE_KEY, t);
    setThemeState(t);
    sendCrossTabMessage({ type: "theme", theme: t });
  }, []);

  useCrossTabSync(
    useCallback((data: Record<string, unknown>) => {
      if (data.type === "theme" && typeof data.theme === "string") {
        const t = data.theme as ThemeId;
        if (THEMES.some((th) => th.id === t)) {
          applyTheme(t);
          localStorage.setItem(THEME_STORAGE_KEY, t);
          setThemeState(t);
        }
      }
    }, [])
  );

  function applyTheme(t: ThemeId) {
    const el = document.documentElement;
    el.setAttribute("data-theme", t);
    if (t === "dark") {
      el.classList.add("dark");
    } else {
      el.classList.remove("dark");
    }
  }

  if (!mounted) {
    return (
      <ThemeContext.Provider value={{ theme: "dark", setTheme, themes: THEMES }}>
        {children}
      </ThemeContext.Provider>
    );
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
}
