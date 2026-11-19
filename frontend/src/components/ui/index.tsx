// Small UI kit in the shadcn/ui style (ADR 0008): plain components we own, built on Tailwind.
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<Variant, string> = {
  primary: "bg-sky-700 text-white hover:bg-sky-800 disabled:bg-slate-300",
  secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 disabled:text-slate-400",
  ghost: "text-sky-800 hover:bg-sky-50 disabled:text-slate-400",
  danger: "bg-red-700 text-white hover:bg-red-800 disabled:bg-slate-300",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700 disabled:cursor-not-allowed",
        BUTTON[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("rounded-lg border border-slate-200 bg-white p-4 shadow-sm", className)} {...props} />;
}

export function CardTitle({ children, id, aside }: { children: ReactNode; id?: string; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <h2 id={id} className="text-base font-semibold text-slate-900">
        {children}
      </h2>
      {aside}
    </div>
  );
}

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        className,
      )}
      {...props}
    />
  );
}

export function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-sky-700";

/** A labelled number for summary rows. `sample` marks demo values (project plan, section 11). */
export function Stat({ label, value, sample }: { label: string; value: ReactNode; sample?: boolean }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-2 text-2xl font-semibold text-slate-900 tabular-nums">
        {value}
        {sample && <span className="text-xs font-normal text-amber-800">sample data</span>}
      </dd>
    </div>
  );
}
