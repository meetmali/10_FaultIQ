"""FaultIQ pipeline command line.

python -m faultiq process-lbnl <raw-root> [--out DIR]
python -m faultiq process <file.csv> --mapping <mapping.toml> [--out DIR]
python -m faultiq draft-mapping <file.csv> [--name NAME]
python -m faultiq train-models <processed-dir> [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

import faultiq
from faultiq.ingestion.mapping import MappingError, draft_mapping_toml, load_mapping
from faultiq.log import configure_logging
from faultiq.pipeline import process_file, process_lbnl, write_manifest

DEFAULT_OUT = Path("data/processed") / f"v{faultiq.PIPELINE_VERSION}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="faultiq", description="FaultIQ batch pipeline")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lbnl = sub.add_parser("process-lbnl", help="process the LBNL RTU dataset")
    p_lbnl.add_argument("raw_root", type=Path)
    p_lbnl.add_argument("--out", type=Path, default=DEFAULT_OUT)

    p_one = sub.add_parser("process", help="process one CSV with a point mapping")
    p_one.add_argument("csv", type=Path)
    p_one.add_argument("--mapping", type=Path, required=True)
    p_one.add_argument("--out", type=Path, default=DEFAULT_OUT)

    p_draft = sub.add_parser("draft-mapping", help="print a starting mapping for a CSV export")
    p_draft.add_argument("csv", type=Path)
    p_draft.add_argument("--name", default="my_rtu")

    p_models = sub.add_parser("train-models", help="train the model files the worker loads")
    p_models.add_argument("processed", type=Path)
    p_models.add_argument("--out", type=Path, default=Path("models"))

    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if args.command == "train-models":
        from faultiq.explain.models import train_models  # heavy imports only when needed

        print(f"Wrote {train_models(args.processed, args.out)}")
        return 0

    if args.command == "draft-mapping":
        columns = pl.read_csv(args.csv, n_rows=0, infer_schema_length=0).columns
        sys.stdout.write(draft_mapping_toml(columns, name=args.name))
        return 0
    if args.command == "process":
        try:
            mapping = load_mapping(args.mapping)
        except MappingError as exc:
            print(f"Mapping problem: {exc}", file=sys.stderr)
            return 2
        outcome = process_file(args.csv, mapping, args.out)
        write_manifest(args.out, [outcome])
        print(f"{outcome.source_file}: {outcome.status} -> {args.out / outcome.report}")
        return 0 if outcome.status != "quarantined" else 1
    outcomes = process_lbnl(args.raw_root, args.out)
    counts = {
        s: sum(o.status == s for o in outcomes)
        for s in ("accepted", "accepted_with_warnings", "quarantined")
    }
    print(f"Processed {len(outcomes)} files into {args.out}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
