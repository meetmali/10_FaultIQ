import { AlertTriangle, CheckCircle2, CircleHelp, Loader2, MinusCircle, XCircle, type LucideIcon } from "lucide-react";

import { KIND_HELP, KIND_LABEL, REVIEW_LABEL, STATUS_LABEL } from "../lib/labels";
import { Badge } from "./ui";

// Status is never shown by colour alone: every badge has an icon and a text label (section 11).

const STATUS: Record<string, { label: string; icon: LucideIcon; className: string }> = {
  fault: { label: STATUS_LABEL.fault!, icon: AlertTriangle, className: "border-red-300 bg-red-50 text-red-800" },
  abnormal: { label: STATUS_LABEL.abnormal!, icon: CircleHelp, className: "border-amber-300 bg-amber-50 text-amber-900" },
  normal: { label: STATUS_LABEL.normal!, icon: CheckCircle2, className: "border-emerald-300 bg-emerald-50 text-emerald-800" },
  analysing: { label: STATUS_LABEL.analysing!, icon: Loader2, className: "border-sky-300 bg-sky-50 text-sky-800" },
  analysis_failed: { label: STATUS_LABEL.analysis_failed!, icon: XCircle, className: "border-slate-400 bg-slate-100 text-slate-800" },
  no_data: { label: STATUS_LABEL.no_data!, icon: MinusCircle, className: "border-slate-300 bg-white text-slate-600" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.no_data!;
  const Icon = s.icon;
  return (
    <Badge className={s.className}>
      <Icon aria-hidden="true" className={status === "analysing" ? "size-3.5 animate-spin" : "size-3.5"} />
      {s.label}
    </Badge>
  );
}

const KIND: Record<string, { icon: LucideIcon; className: string }> = {
  fault: { icon: AlertTriangle, className: "border-red-300 bg-red-50 text-red-800" },
  inconclusive: { icon: CircleHelp, className: "border-amber-300 bg-amber-50 text-amber-900" },
  no_supported_fault: { icon: CircleHelp, className: "border-violet-300 bg-violet-50 text-violet-800" },
  not_diagnosable: { icon: MinusCircle, className: "border-slate-300 bg-slate-50 text-slate-700" },
};

export function KindBadge({ kind }: { kind: string }) {
  const k = KIND[kind] ?? KIND.not_diagnosable!;
  const Icon = k.icon;
  return (
    <Badge className={k.className} title={KIND_HELP[kind]}>
      <Icon aria-hidden="true" className="size-3.5" />
      {KIND_LABEL[kind] ?? kind}
    </Badge>
  );
}

const REVIEW: Record<string, { icon: LucideIcon; className: string }> = {
  unreviewed: { icon: MinusCircle, className: "border-slate-300 bg-white text-slate-600" },
  needs_review: { icon: CircleHelp, className: "border-amber-300 bg-amber-50 text-amber-900" },
  confirmed: { icon: CheckCircle2, className: "border-emerald-300 bg-emerald-50 text-emerald-800" },
  rejected: { icon: XCircle, className: "border-slate-400 bg-slate-100 text-slate-800" },
};

export function ReviewBadge({ status }: { status: string }) {
  const r = REVIEW[status] ?? REVIEW.unreviewed!;
  const Icon = r.icon;
  return (
    <Badge className={r.className}>
      <Icon aria-hidden="true" className="size-3.5" />
      {REVIEW_LABEL[status] ?? status}
    </Badge>
  );
}
