"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

type Locale = "en" | "zh";
type Translations = Record<string, string>;

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
  locales: { code: Locale; label: string }[];
}

const I18nContext = createContext<I18nContextValue | null>(null);

const LOCALES: { code: Locale; label: string }[] = [
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
];

let enTranslations: Translations = {};

async function loadTranslations(locale: Locale): Promise<Translations> {
  if (locale === "en") {
    if (Object.keys(enTranslations).length === 0) {
      enTranslations = (await import("@/locales/en.json")).default;
    }
    return enTranslations;
  }
  return (await import(`@/locales/${locale}.json`)).default;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [messages, setMessages] = useState<Translations>({});

  useEffect(() => {
    const stored = localStorage.getItem("deep-locale") as Locale | null;
    if (stored && (stored === "en" || stored === "zh")) {
      setLocaleState(stored);
    }
  }, []);

  useEffect(() => {
    loadTranslations(locale).then(setMessages);
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    localStorage.setItem("deep-locale", l);
    setLocaleState(l);
  }, []);

  const t = useCallback(
    (key: string) => messages[key] || key,
    [messages]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, locales: LOCALES }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useT() {
  const ctx = useContext(I18nContext);
  if (!ctx) return { t: (key: string) => key, locale: "en" as Locale, setLocale: () => {}, locales: LOCALES };
  return ctx;
}
