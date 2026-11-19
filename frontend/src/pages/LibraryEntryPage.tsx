import { ArrowLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { QueryView } from "../components/QueryState";
import { Badge, Card, CardTitle } from "../components/ui";
import { useFaultTitles, useLibraryEntry } from "../hooks/queries";
import { formatNumber, formatPercent } from "../lib/format";
import { backLink } from "../lib/links";
import { faultTitle } from "../lib/labels";
import type { CitedText, LibraryFaultResponse, LibrarySource } from "../types/api";

function Cite({ item, sources }: { item: CitedText; sources: LibrarySource[] }) {
  const n = sources.findIndex((s) => s.id === item.source) + 1;
  return (
    <>
      {item.text}{" "}
      <a href={`#source-${item.source}`} className="text-xs text-sky-800 hover:underline">
        [{n || item.source}]
      </a>
    </>
  );
}

function Section({ title, origin, children }: { title: string; origin: string; children: ReactNode }) {
  return (
    <Card>
      <CardTitle aside={<Badge className="border-slate-300 bg-slate-50 text-slate-600">{origin}</Badge>}>{title}</CardTitle>
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
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-sm text-slate-600">
        <Link to="/library" className="text-sky-800 hover:underline">Fault Library</Link>
        <ChevronRight aria-hidden="true" className="size-4" />
        <span aria-current="page">{entry.data?.fault.title ?? faultTitle(faultId)}</span>
      </nav>
      {back && (
        <Link to={back} className="inline-flex items-center gap-1 text-sm text-sky-800 hover:underline">
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
  const { fault: f, sources } = data;
  const titles = useFaultTitles();
  const m = f.measured;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{f.title}</h1>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge className="border-slate-300 bg-slate-50 text-slate-700">{f.equipment}</Badge>
          <Badge className="border-slate-300 bg-white text-slate-600">{f.dataset_label}</Badge>
          {data.review_status !== "reviewed" && (
            <Badge className="border-amber-300 bg-amber-50 text-amber-900">Not yet reviewed by an HVAC professional</Badge>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Definition" origin="Reference data">
          <p className="text-sm">{f.definition && <Cite item={f.definition} sources={sources} />}</p>
        </Section>
        <Section title="What FaultIQ measured" origin="Measured">
          <p className="text-sm">{f.observed && <Cite item={f.observed} sources={sources} />}</p>
        </Section>
      </div>

      <Section title="Symptoms" origin="Measured on held-out data">
        <p className="mb-2 text-xs text-slate-600">
          The signals that most often decided the diagnosis for this fault in FaultIQ's held-out tests.
        </p>
        {m.symptoms.length === 0 ? (
          <p className="text-sm text-slate-600">Too few held-out hours to report symptoms.</p>
        ) : (
          <table className="w-full text-left text-sm [&_td]:px-2 [&_th]:px-2">
            <thead className="text-xs text-slate-500">
              <tr>
                <th scope="col" className="py-1 font-medium">Signal</th>
                <th scope="col" className="font-medium">How it's measured</th>
                <th scope="col" className="font-medium">Hours it decided</th>
              </tr>
            </thead>
            <tbody>
              {m.symptoms.map((s) => (
                <tr key={s.feature} className="border-t border-slate-100">
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
          <p className="text-sm text-slate-600">Rarely confused with any other class in held-out tests.</p>
        ) : (
          <table className="w-full text-left text-sm [&_td]:px-2 [&_th]:px-2">
            <caption className="sr-only">Hours of mix-ups between this fault and others, in both directions</caption>
            <thead className="text-xs text-slate-500">
              <tr>
                <th scope="col" className="py-1 font-medium">Other class</th>
                <th scope="col" className="font-medium">Hours of {f.title.toLowerCase()} named as it</th>
                <th scope="col" className="font-medium">Hours of it named {f.title.toLowerCase()}</th>
              </tr>
            </thead>
            <tbody>
              {m.confused_with.map((c) => (
                <tr key={c.fault} className="border-t border-slate-100">
                  <th scope="row" className="py-1.5 font-normal">
                    {c.fault === "fault_free" ? (
                      "Normal operation"
                    ) : (
                      <Link to={`/library/${c.fault}`} className="text-sky-800 hover:underline">
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
        <p className="mb-2 text-sm text-slate-700">
          Precision {formatPercent(m.performance.precision)}, recall {formatPercent(m.performance.recall)} over{" "}
          {formatNumber(m.performance.test_hours)} held-out hours (most likely class, all points).
        </p>
        <table className="w-full text-left text-sm [&_td]:px-2 [&_th]:px-2">
          <caption className="sr-only">Results by severity</caption>
          <thead className="text-xs text-slate-500">
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
              <tr key={s.intensity} className="border-t border-slate-100">
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
                  <a href={s.url} className="text-sky-800 hover:underline" rel="noreferrer noopener" target="_blank">
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
