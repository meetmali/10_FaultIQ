// Small UI kit in the shadcn/ui style (ADR 0008), on design tokens so both themes work (ADR 0026).
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "ghost";

const BUTTON: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:opacity-90 disabled:opacity-50",
  secondary: "border border-line bg-surface text-ink hover:bg-raised disabled:opacity-50",
  ghost: "text-accent hover:bg-accent-soft disabled:opacity-50",
};

export function Button({ variant = "primary", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed",
        BUTTON[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("rounded-2xl border border-line bg-surface p-5 shadow-sm", className)} {...props} />;
}

export function CardTitle({ children, id, aside, sub }: { children: ReactNode; id?: string; aside?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
      <div>
        <h2 id={id} className="text-base font-semibold text-ink">{children}</h2>
        {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
      </div>
      {aside}
    </div>
  );
}

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap", className)}
      {...props}
    />
  );
}

export function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium text-ink-2">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-ink focus-visible:outline-2 focus-visible:outline-accent";

/** A labelled number. `sample` marks demo values (project plan, section 11). */
export function Stat({ label, value, sample, hint }: { label: string; value: ReactNode; sample?: boolean; hint?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-surface px-4 py-3">
      <dt className="text-xs font-medium tracking-wide text-muted uppercase">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-2 text-2xl font-semibold text-ink tabular-nums">
        {value}
        {sample && <span className="text-xs font-normal text-warn">sample data</span>}
      </dd>
      {hint && <dd className="mt-0.5 text-xs text-muted">{hint}</dd>}
    </div>
  );
}

/** Table styling shared by every table. */
export const tableClass = "w-full text-left text-sm [&_td]:px-2 [&_th]:px-2 [&_thead]:text-xs [&_thead]:text-muted";
