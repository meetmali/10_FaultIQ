// Display formatting. Times are shown in UTC, the timezone the API and the data use (ADR 0007).

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n: number) => String(n).padStart(2, "0");

/** "02 Aug 2018, 15:00", in UTC. Matches the pipeline's wording in explanations exactly. */
const dateTime = {
  format: (d: Date) =>
    `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`,
};
const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** System times (when an analysis ran): real UTC instants. */
export const formatDateTime = (iso: string | null | undefined): string =>
  iso ? `${dateTime.format(new Date(iso))} UTC` : "n/a";

/**
 * Data times (when an event happened): shown exactly as recorded in the uploaded file. Source
 * files carry no time zone, so the pipeline marks them UTC only to stop readers shifting them
 * (ADR 0025); formatting in UTC gives back the recorded numbers.
 */
export const formatDataTime = (iso: string | null | undefined): string =>
  iso ? dateTime.format(new Date(iso)) : "n/a";

export const formatClock = (ms: number): string => time.format(new Date(ms));

export const formatPercent = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined ? "n/a" : `${(x * 100).toFixed(digits)}%`;

/** A model probability is never shown as certain (ADR 0023): 99.5% and above reads "over 99%". */
export const formatConfidence = (x: number | null | undefined): string =>
  x === null || x === undefined
    ? "n/a"
    : x >= 0.995
      ? "over 99%"
      : x < 0.005
        ? "under 1%" // stored probabilities are rounded; "0%" would read as impossible
        : formatPercent(x);

export const formatNumber = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined
    ? "n/a"
    : x.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const UNITS: Record<string, string> = {
  degC: "°C",
  K: "K",
  kPa: "kPa",
  W: "W",
  "m3/s": "m³/s",
  fraction: "%",
  share: "%",
  ratio: "",
};

export const unitLabel = (unit: string): string => UNITS[unit] ?? unit;

export function formatValue(value: number, unit: string): string {
  if (unit === "fraction" || unit === "share") return formatPercent(value);
  const digits = unit === "kPa" || unit === "W" ? 0 : unit === "m3/s" || unit === "ratio" ? 2 : 1;
  const u = unitLabel(unit);
  return `${formatNumber(value, digits)}${u ? ` ${u}` : ""}`;
}
