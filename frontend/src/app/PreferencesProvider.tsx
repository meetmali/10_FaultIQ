import { useEffect, useMemo, useState, type ReactNode } from "react";

import { PreferencesContext, readStored, writeStored, type Persona, type ThemeChoice } from "./preferences";

const PERSONAS = ["operator", "technician"] as const;
const THEMES = ["system", "light", "dark"] as const;

function systemDark(): boolean {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

/** Persona (Operator by default), theme (follows the system by default) and site (ADR 0026). */
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [persona, setPersonaState] = useState<Persona>(() => readStored("faultiq.persona", PERSONAS, "operator"));
  const [theme, setThemeState] = useState<ThemeChoice>(() => readStored("faultiq.theme", THEMES, "system"));
  const [site, setSiteState] = useState<string>(() => {
    try {
      return window.localStorage.getItem("faultiq.site") ?? "";
    } catch {
      return "";
    }
  });
  const [system, setSystem] = useState(systemDark);

  useEffect(() => {
    let media: MediaQueryList;
    try {
      media = window.matchMedia("(prefers-color-scheme: dark)");
    } catch {
      return;
    }
    const onChange = () => setSystem(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const dark = theme === "dark" || (theme === "system" && system);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  const value = useMemo(
    () => ({
      persona,
      setPersona: (p: Persona) => {
        setPersonaState(p);
        writeStored("faultiq.persona", p);
      },
      theme,
      setTheme: (t: ThemeChoice) => {
        setThemeState(t);
        writeStored("faultiq.theme", t);
      },
      dark,
      site,
      setSite: (s: string) => {
        setSiteState(s);
        writeStored("faultiq.site", s);
      },
    }),
    [persona, theme, dark, site],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}
