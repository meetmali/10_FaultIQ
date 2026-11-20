import * as Dialog from "@radix-ui/react-dialog";
import { Upload, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { useAnalyseNewData } from "../hooks/queries";
import { FORMAT_LABEL } from "../lib/labels";
import { ApiError } from "../services/api";
import type { EquipmentOverview, PointSet, UploadFormat } from "../types/api";
import { Button, Field, inputClass } from "./ui";

/** Upload a CSV export and start an analysis: the one write flow in the app (ADR 0024). */
export function UploadDialog({ equipment }: { equipment: EquipmentOverview[] }) {
  const id = useId();
  const navigate = useNavigate();
  const mutation = useAnalyseNewData();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState<string>(equipment[0]?.id ?? "new");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    const file = form.get("file");
    if (!(file instanceof File) || file.size === 0) return setError("Choose a CSV file to upload.");
    const name = String(form.get("name") ?? "").trim();
    if (target === "new" && !name) return setError("Give the new unit a name.");
    try {
      const { equipmentId, analysis } = await mutation.mutateAsync({
        file,
        equipmentId: target === "new" ? undefined : target,
        newEquipment: target === "new" ? { name, site: String(form.get("site") ?? "").trim() } : undefined,
        format: form.get("format") as UploadFormat,
        pointSet: form.get("point_set") as PointSet,
      });
      setOpen(false);
      navigate(`/equipment/${equipmentId}?analysis=${analysis.id}`);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Upload failed.");
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button>
          <Upload aria-hidden="true" className="size-4" />
          Analyse new data
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-lg bg-surface p-5 shadow-xl">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Analyse new data</Dialog.Title>
              <Dialog.Description className="text-sm text-muted">
                Upload a CSV export. FaultIQ validates it, then runs detection, diagnosis and explanation.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" aria-label="Close">
                <X aria-hidden="true" className="size-4" />
              </Button>
            </Dialog.Close>
          </div>
          <form onSubmit={submit} className="space-y-3">
            <Field label="Equipment" htmlFor={`${id}-eq`}>
              <select id={`${id}-eq`} className={inputClass} value={target} onChange={(e) => setTarget(e.target.value)}>
                {equipment.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                    {e.site ? ` (${e.site})` : ""}
                  </option>
                ))}
                <option value="new">New unit…</option>
              </select>
            </Field>
            {target === "new" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Unit name" htmlFor={`${id}-name`}>
                  <input id={`${id}-name`} name="name" className={inputClass} maxLength={200} required />
                </Field>
                <Field label="Site (optional)" htmlFor={`${id}-site`}>
                  <input id={`${id}-site`} name="site" className={inputClass} maxLength={200} />
                </Field>
              </div>
            )}
            <Field
              label="Export format"
              htmlFor={`${id}-format`}
              hint="Only formats with trained models can be analysed. Other exports need a site baseline first."
            >
              <select id={`${id}-format`} name="format" className={inputClass} defaultValue="lbnl_simulated">
                {Object.entries(FORMAT_LABEL).map(([v, label]) => (
                  <option key={v} value={v}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Points to use"
              htmlFor={`${id}-ps`}
              hint="Basic points are what a typical building automation system records; results are weaker."
            >
              <select id={`${id}-ps`} name="point_set" className={inputClass} defaultValue="all">
                <option value="all">All points</option>
                <option value="basic">Basic points only</option>
              </select>
            </Field>
            <Field label="CSV file" htmlFor={`${id}-file`} hint="Up to 100 MB. Stored under a server-generated name.">
              <input id={`${id}-file`} name="file" type="file" accept=".csv,text/csv" className="text-sm" required />
            </Field>
            {error && (
              <p role="alert" className="rounded-md border border-fault-line bg-fault-soft px-3 py-2 text-sm text-fault">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Dialog.Close asChild>
                <Button variant="secondary">Cancel</Button>
              </Dialog.Close>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Uploading…" : "Upload and analyse"}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
