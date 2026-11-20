// Shown on every screen when the API reports demo mode (ADR 0017).
export function DemoBanner() {
  return (
    <div
      role="note"
      aria-label="Public demo notice"
      className="border-b border-warn-line bg-warn-soft px-6 py-2 text-sm text-warn"
    >
      <span aria-hidden="true">⚠ </span>
      <strong>Public demo.</strong> Everything shown here is sample data. The demo is read-only, so
      uploads are disabled. Don't enter real building data.
    </div>
  );
}
