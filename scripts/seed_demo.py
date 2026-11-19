"""Load sample units into a running FaultIQ through its public API (ADR 0017, ADR 0025).

Usage (API running with DEMO_MODE=false, worker running, models trained):
    python3 scripts/seed_demo.py data/raw/LBNL_FDD_Data_Sets_RTU_all_3 --api http://localhost:8000

Creates one unit per sample file, uploads it and starts an analysis. Turn demo mode on afterwards:
the demo itself rejects every write. Uses only the standard library, so it runs anywhere.

LBNL files overlap the data the bundled models were trained on, so these analyses are a
demonstration of the product, not an evaluation (see the Phase 3-5 reports for that).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

# (unit name, site, file name, format, point set): a mix of faults, a healthy unit and basic points.
SAMPLES = [
    ("RTU-1", "Simulated office", "RTU_sim_condfouling20.csv", "lbnl_simulated", "all"),
    ("RTU-2", "Simulated office", "RTU_sim_evapfouling30.csv", "lbnl_simulated", "all"),
    ("RTU-3", "Simulated office", "RTU_sim_suctionpipe06bar.csv", "lbnl_simulated", "all"),
    ("RTU-4", "Simulated office", "RTU_sim_baseline.csv", "lbnl_simulated", "all"),
    ("RTU-5", "Simulated office", "RTU_sim_undercharge10.csv", "lbnl_simulated", "basic"),
    ("RTU-ORNL-1", "ORNL test building", "OA_damper_stuck_100_Summer_2021.csv", "lbnl_experimental", "all"),
    ("RTU-ORNL-2", "ORNL test building", "SA_temp_bias_4_Summer_2021.csv", "lbnl_experimental", "all"),
    ("RTU-ORNL-3", "ORNL test building", "ERTU_Summer_2021.csv", "lbnl_experimental", "all"),
]


def call(api: str, path: str, body: bytes, content_type: str) -> dict[str, object]:
    req = Request(f"{api}/api/v1{path}", data=body, method="POST", headers={"content-type": content_type})
    with urlopen(req, timeout=120) as resp:  # noqa: S310 (the URL is the operator's own API)
        result: dict[str, object] = json.loads(resp.read())
    return result


def post_json(api: str, path: str, payload: dict[str, object]) -> dict[str, object]:
    return call(api, path, json.dumps(payload).encode(), "application/json")


def upload(api: str, csv: Path, equipment_id: object, fmt: str) -> dict[str, object]:
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="equipment_id"\r\n\r\n{equipment_id}\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="format"\r\n\r\n{fmt}\r\n'.encode(),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{csv.name}"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode()
        + csv.read_bytes()
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return call(api, "/uploads", b"".join(parts), f"multipart/form-data; boundary={boundary}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args(argv)
    files = {p.name: p for p in args.raw_root.rglob("*.csv")}
    for name, site, file_name, fmt, point_set in SAMPLES:
        csv = files.get(file_name)
        if csv is None:
            print(f"skip {name}: {file_name} not found under {args.raw_root}", file=sys.stderr)
            continue
        unit = post_json(args.api, "/equipment", {"name": name, "site": site})
        up = upload(args.api, csv, unit["id"], fmt)
        analysis = post_json(args.api, "/analyses", {"upload_id": up["id"], "point_set": point_set})
        print(f"{name}: {file_name} -> analysis {analysis['id']} ({point_set} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
