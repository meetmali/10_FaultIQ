import { ArrowLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { QueryView } from "../components/QueryState";
import { Badge, Card, CardTitle, tableClass } from "../components/ui";
import { usePreferences } from "../app/preferences";
import { CutawaySchematic } from "../components/illustrations/CutawaySchematic";
import { IsometricRtu } from "../components/illustrations/IsometricRtu";
import { COMPONENT_LABEL, isComponent } from "../components/illustrations/components";
import { Meter } from "../components/visuals";
import { useFaultTitles, useLibraryEntry } from "../hooks/queries";
import { featureSignal } from "../lib/deviation";
import { formatNumber, formatPercent } from "../lib/format";
import { backLink } from "../lib/links";
import { faultTitle } from "../lib/labels";
import type { CitedText, LibraryFaultResponse, LibrarySource } from "../types/api";

function Cite({ item, sources }: { item: CitedText; sources: LibrarySource[] }) {
  const n = sources.findIndex((s) => s.id === item.source) + 1;
  return (
    <>
      {item.text}{" "}
      <a href={`#source-${item.source}`} className="text-xs text-accent hover:underline">
        [{n || item.source}]
      </a>
    </>
  );
}

function Section({ title, origin, children }: { title: string; origin: string; children: ReactNode }) {
  return (
    <Card>
      <CardTitle aside={<Badge className="border-line bg-raised text-muted">{origin}</Badge>}>{title}</CardTitle>
      {children}
    </Card>
  );
}

export default function LibraryEntryPage() {
  const { faultId = "" } = useParams();
  const [params] = useSearchParams();
  const back = backLink(params.get("from"));
  const entry = useLibraryEntry(faultId);

  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-sm text-muted">
        <Link to="/library" className="text-accent hover:underline">Fault Library</Link>
        <ChevronRight aria-hidden="true" className="size-4" />
        <span aria-current="page">{entry.data?.fault.title ?? faultTitle(faultId)}</span>
      </nav>
      {back && (
        <Link to={back} className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Back to the diagnosis
        </Link>
      )}
      <QueryView query={entry} loadingLabel="Loading fault…">
        {(data) => <Entry data={data} />}
      </QueryView>
    </div>
  );
}

function Entry({ data }: { data: LibraryFaultResponse }) {
  return usePreferences().persona === "operator" ? <OperatorEntry data={data} /> : <TechnicianEntry data={data} />;
}

/** The Operator's view of a fault: what it is in plain words, what to do, how reliable FaultIQ is. */
function OperatorEntry({ data }: { data: LibraryFaultResponse }) {
  const { fault: f, sources } = data;
  const comp = isComponent(f.component) ? f.component : null;
  return (
    <div className="grid items-start gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <h1 className="text-2xl font-semibold text-ink">{f.plain_name}</h1>
        <p className="text-sm text-muted">{f.title} · {f.equipment}</p>
        <IsometricRtu state="fault" component={comp} title={`${f.plain_name}. Affected part: ${comp ? COMPONENT_LABEL[comp] : f.equipment}.`} className="mt-2 max-w-2xl" />
      </div>
      <div className="space-y-4 lg:col-span-2">
        <Section title="What it means" origin="Measured">
          <p className="text-base text-ink-2">{f.plain_summary && <Cite item={f.plain_summary} sources={sources} />}</p>
        </Section>
        <Section title="What to do" origin="Cited, unreviewed">
          <p className="text-base text-ink">{f.what_to_do && <Cite item={f.what_to_do} sources={sources} />}</p>
          <p className="mt-2 text-xs text-muted">A suggestion to verify with a qualified technician, not an instruction.</p>
        </Section>
        <Section title="How reliable FaultIQ is" origin="Measured on held-out data">
          <div className="space-y-3">
            <Meter value={f.measured.performance.recall} label="How often FaultIQ spots it" />
            <Meter value={f.measured.performance.precision} label="How often it's right when it names it" />
          </div>
        </Section>
        <Sources sources={sources} />
      </div>
    </div>
  );
}

function Sources({ sources }: { sources: LibrarySource[] }) {
  return (
    <details className="rounded-2xl border border-line bg-surface p-4 text-sm">
      <summary className="cursor-pointer font-medium text-accent">References</summary>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-ink-2">
        {sources.map((s) => (
          <li key={s.id} id={`source-${s.id}`}>{s.citation}</li>
        ))}
      </ol>
    </details>
  );
}

function TechnicianEntry({ data }: { data: LibraryFaultResponse }) {
  const { fault: f, sources } = data;
  const titles = useFaultTitles();
  const m = f.measured;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{f.title}</h1>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge className="border-line bg-raised text-ink-2">{f.equipment}</Badge>
          <Badge className="border-line bg-surface text-muted">{f.dataset_label}</Badge>
          {data.review_status !== "reviewed" && (
            <Badge className="border-warn-line bg-warn-soft text-warn">Not yet reviewed by an HVAC professional</Badge>
          )}
        </div>
      </div>

      <Section title="Where it shows on the unit" origin="Measured on held-out data">
        <p className="mb-2 text-xs text-muted">The affected component, with the sensors whose readings decided this fault in FaultIQ's held-out tests outlined.</p>
        <CutawaySchematic
          readings={Object.fromEntries(m.symptoms.map((s) => [featureSignal(s.feature), { text: "deciding", tone: "warn" as const, note: `${s.deciding_hours} hours` }]))}
          fanOn
          compressorOn={f.equipment === "Refrigerant circuit"}
          damper={f.component === "oa_damper" ? 1 : 0.2}
          highlight={isComponent(f.component) ? f.component : null}
          emphasise={m.symptoms.map((s) => featureSignal(s.feature))}
          title={`Schematic highlighting ${isComponent(f.component) ? COMPONENT_LABEL[f.component] : f.equipment} and the deciding sensors for ${f.title}.`}
          className="max-h-[26rem]"
        />
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Definition" origin="Reference data">
          <p className="text-sm">{f.definition && <Cite item={f.definition} sources={sources} />}</p>
        </Section>
        <Section title="What FaultIQ measured" origin="Measured">
          <p className="text-sm">{f.observed && <Cite item={f.observed} sources={sources} />}</p>
        </Section>
      </div>

      <Section title="Symptoms" origin="Measured on held-out data">
        <p className="mb-2 text-xs text-muted">
          The signals that most often decided the diagnosis for this fault in FaultIQ's held-out tests.
        </p>
        {m.symptoms.length === 0 ? (
          <p className="text-sm text-muted">Too few held-out hours to report symptoms.</p>
        ) : (
          <table className={tableClass}>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="py-1 font-medium">Signal</th>
                <th scope="col" className="font-medium">How it's measured</th>
                <th scope="col" className="font-medium">Hours it decided</th>
              </tr>
            </thead>
            <tbody>
              {m.symptoms.map((s) => (
                <tr key={s.feature} className="border-t border-line">
                  <th scope="row" className="py-1.5 font-normal">{s.signal[0]!.toUpperCase() + s.signal.slice(1)}</th>
                  <td>
                    {s.kind === "residual" ? "Compared with the normal-behaviour model" : s.kind === "rule" ? "Economizer rule" : "Physics feature"}
                  </td>
                  <td className="tabular-nums">{formatNumber(s.deciding_hours)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Possible causes" origin="Cited, unreviewed">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {f.causes.map((c, i) => (
              <li key={i}><Cite item={c} sources={sources} /></li>
            ))}
          </ul>
        </Section>
        <Section title="Diagnostic checks" origin="Cited, unreviewed">
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {f.checks.map((c, i) => (
              <li key={i}><Cite item={c} sources={sources} /></li>
            ))}
          </ol>
        </Section>
      </div>

      <Section title="Often confused with" origin="Measured on held-out data">
        {m.confused_with.length === 0 ? (
          <p className="text-sm text-muted">Rarely confused with any other class in held-out tests.</p>
        ) : (
          <table className={tableClass}>
            <caption className="sr-only">Hours of mix-ups between this fault and others, in both directions</caption>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="py-1 font-medium">Other class</th>
                <th scope="col" className="font-medium">Hours of {f.title.toLowerCase()} named as it</th>
                <th scope="col" className="font-medium">Hours of it named {f.title.toLowerCase()}</th>
              </tr>
            </thead>
            <tbody>
              {m.confused_with.map((c) => (
                <tr key={c.fault} className="border-t border-line">
                  <th scope="row" className="py-1.5 font-normal">
                    {c.fault === "fault_free" ? (
                      "Normal operation"
                    ) : (
                      <Link to={`/library/${c.fault}`} className="text-accent hover:underline">
                        {titles[c.fault] ?? faultTitle(c.fault)}
                      </Link>
                    )}
                  </th>
                  <td className="tabular-nums">{formatNumber(c.named_as_other_hours)}</td>
                  <td className="tabular-nums">{formatNumber(c.other_named_as_this_hours)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="How well FaultIQ finds it" origin="Measured on held-out data">
        <p className="mb-2 text-sm text-ink-2">
          Precision {formatPercent(m.performance.precision)}, recall {formatPercent(m.performance.recall)} over{" "}
          {formatNumber(m.performance.test_hours)} held-out hours (most likely class, all points).
        </p>
        <table className={tableClass}>
          <caption className="sr-only">Results by severity</caption>
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="py-1 font-medium">Severity ({f.intensity_unit})</th>
              <th scope="col" className="font-medium">Hours</th>
              <th scope="col" className="font-medium">Right fault</th>
              <th scope="col" className="font-medium">Said no fault</th>
              <th scope="col" className="font-medium">Inconclusive</th>
            </tr>
          </thead>
          <tbody>
            {m.performance.by_severity.map((s) => (
              <tr key={s.intensity} className="border-t border-line">
                <th scope="row" className="py-1.5 font-normal tabular-nums">{s.intensity}</th>
                <td className="tabular-nums">{formatNumber(s.hours)}</td>
                <td className="tabular-nums">{formatPercent(s.right_fault)}</td>
                <td className="tabular-nums">{formatPercent(s.said_no_fault)}</td>
                <td className="tabular-nums">{formatPercent(s.inconclusive)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="References" origin="Sources">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {sources.map((s) => (
            <li key={s.id} id={`source-${s.id}`}>
              {s.citation}
              {s.url && (
                <>
                  {" "}
                  <a href={s.url} className="text-accent hover:underline" rel="noreferrer noopener" target="_blank">
                    (link)
                  </a>
                </>
              )}
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}
