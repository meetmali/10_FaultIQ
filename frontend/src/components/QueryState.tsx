import type { UseQueryResult } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { formatClock } from "../lib/format";
import { ApiError } from "../services/api";
import { Button } from "./ui";

// Loading, error, empty and stale states, the same way on every screen (section 11).

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-sm text-muted">
      <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-fault-line bg-fault-soft px-3 py-2 text-sm text-fault">
      <AlertTriangle aria-hidden="true" className="size-4" />
      <span>{message}</span>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">{children}</div>;
}

/** When the data was fetched, whether it's refreshing, and a warning if a refresh failed. */
export function Freshness({ query }: { query: UseQueryResult<unknown> }) {
  if (!query.dataUpdatedAt) return null;
  const failed = query.isError && query.data !== undefined;
  return (
    <p className={failed ? "text-xs text-warn" : "text-xs text-muted"} aria-live="polite">
      {failed
        ? `Couldn't refresh; showing data from ${formatClock(query.dataUpdatedAt)}.`
        : query.isFetching
          ? "Refreshing…"
          : `Updated ${formatClock(query.dataUpdatedAt)}`}
      {!query.isFetching && (
        <button
          type="button"
          onClick={() => query.refetch()}
          className="ml-2 inline-flex items-center gap-1 text-accent underline-offset-2 hover:underline"
        >
          <RefreshCw aria-hidden="true" className="size-3" />
          Refresh
        </button>
      )}
    </p>
  );
}

/** Renders loading or error for a query, otherwise its children with the data. */
export function QueryView<T>({
  query,
  children,
  loadingLabel,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
  loadingLabel?: string;
}) {
  if (query.data !== undefined) return <>{children(query.data)}</>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <Loading label={loadingLabel} />;
}
