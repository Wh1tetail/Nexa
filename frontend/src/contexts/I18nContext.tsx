import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import en from "@/i18n/en";
import { setHttpMessages } from "@/services/http";
import kk from "@/i18n/kk";
import ru, { type Dict } from "@/i18n/ru";

export type Locale = "ru" | "en" | "kk";
const DICTS: Record<Locale, Dict> = { ru, en, kk };

/** Interface languages: code, name in that language, short label for compact switchers. */
export const LOCALES: { code: Locale; name: string; short: string }[] = [
  { code: "ru", name: "Русский", short: "RU" },
  { code: "kk", name: "Қазақша", short: "ҚАЗ" },
  { code: "en", name: "English", short: "EN" },
];

export const isLocale = (v: unknown): v is Locale => LOCALES.some((l) => l.code === v);
const STORAGE_KEY = "nexa.locale";

interface I18nValue {
  t: Dict;
  locale: Locale;
  setLocale: (l: Locale) => void;
}

const I18nContext = createContext<I18nValue | null>(null);

function initialLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLocale(saved)) return saved;
  } catch {
    /* ignore */
  }
  return "ru"; // Russian by default
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    setHttpMessages({ generic: DICTS[locale].common.somethingWrong, offline: DICTS[locale].common.offline, lang: locale });
  }, [locale]);

  const value = useMemo(() => ({ t: DICTS[locale], locale, setLocale }), [locale, setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
