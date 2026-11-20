import { createContext, useContext } from "react";

export type Persona = "operator" | "technician";
export type ThemeChoice = "system" | "light" | "dark";

export interface Preferences {
  persona: Persona;
  setPersona: (p: Persona) => void;
  theme: ThemeChoice;
  setTheme: (t: ThemeChoice) => void;
  /** The theme actually shown, after resolving "system". */
  dark: boolean;
  /** The site filter shared by every screen ("" means all sites). */
  site: string;
  setSite: (s: string) => void;
}

export const PreferencesContext = createContext<Preferences | null>(null);

export function usePreferences(): Preferences {
  const p = useContext(PreferencesContext);
  if (!p) throw new Error("usePreferences must be used inside <PreferencesProvider>");
  return p;
}

/** Browser storage is a per-viewer convenience: it may be unavailable, so every access is guarded. */
export function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = window.localStorage.getItem(key);
    return v !== null && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeStored(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the choice simply isn't remembered */
  }
}
