import { AlertTriangle, CheckCircle2, CircleHelp, Loader2, MinusCircle, XCircle, type LucideIcon } from "lucide-react";

import { cn } from "../lib/cn";
import { KIND_HELP, KIND_LABEL, REVIEW_LABEL, STATUS_LABEL } from "../lib/labels";
import { KIND_TONE, REVIEW_TONE, STATUS_TONE, TONE } from "../lib/tone";
import { Badge } from "./ui";

// Status is never shown by colour alone: every badge has an icon and a text label (section 11).

const STATUS_ICON: Record<string, LucideIcon> = {
  fault: AlertTriangle,
  abnormal: CircleHelp,
  normal: CheckCircle2,
  analysing: Loader2,
  analysis_failed: XCircle,
  no_data: MinusCircle,
};

export function StatusBadge({ status }: { status: string }) {
  const Icon = STATUS_ICON[status] ?? MinusCircle;
  return (
    <Badge className={TONE[STATUS_TONE[status] ?? "idle"]}>
      <Icon aria-hidden="true" className={cn("size-3.5", status === "analysing" && "animate-spin")} />
      {STATUS_LABEL[status] ?? status}
    </Badge>
  );
}

const KIND_ICON: Record<string, LucideIcon> = {
  fault: AlertTriangle,
  inconclusive: CircleHelp,
  no_supported_fault: CircleHelp,
  not_diagnosable: MinusCircle,
};

export function KindBadge({ kind }: { kind: string }) {
  const Icon = KIND_ICON[kind] ?? MinusCircle;
  return (
    <Badge className={TONE[KIND_TONE[kind] ?? "idle"]} title={KIND_HELP[kind]}>
      <Icon aria-hidden="true" className="size-3.5" />
      {KIND_LABEL[kind] ?? kind}
    </Badge>
  );
}

const REVIEW_ICON: Record<string, LucideIcon> = {
  unreviewed: MinusCircle,
  needs_review: CircleHelp,
  confirmed: CheckCircle2,
  rejected: XCircle,
};

export function ReviewBadge({ status }: { status: string }) {
  const Icon = REVIEW_ICON[status] ?? MinusCircle;
  return (
    <Badge className={TONE[REVIEW_TONE[status] ?? "idle"]}>
      <Icon aria-hidden="true" className="size-3.5" />
      {REVIEW_LABEL[status] ?? status}
    </Badge>
  );
}
