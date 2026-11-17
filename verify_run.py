"""
Verify an ALCOA scraping run produced by alcoa_scraper.py.

Checks:
  1. Output files still match the hashes recorded in manifest.json
  2. Every raw HTML page still matches the hash stored in quotes.csv
  3. Row counts in the CSVs match the counts in the manifest

Usage:  python verify_run.py runs/20261113T020000Z
"""

import csv
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run_dir: Path) -> int:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    problems = []

    # 1. Output files match the manifest
    for name, expected in manifest["output_files"].items():
        actual = sha256_file(run_dir / name)
        status = "OK" if actual == expected else "CHANGED"
        print(f"{status:8} {name}")
        if actual != expected:
            problems.append(f"{name} has changed since the run")

    # 2. Raw HTML pages match the hashes stored in the data
    data_name = next(n for n in manifest["output_files"] if n != "rejected.csv")
    with open(run_dir / data_name, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    checked = {}
    for row in rows:
        raw_path = Path(row["raw_html_file"])
        if raw_path in checked:
            continue
        ok = raw_path.exists() and sha256_file(raw_path) == row["raw_html_sha256"]
        checked[raw_path] = ok
        print(f"{'OK' if ok else 'CHANGED':8} {raw_path}")
        if not ok:
            problems.append(f"{raw_path} is missing or altered")

    # 3. Counts match the manifest
    with open(run_dir / "rejected.csv", encoding="utf-8") as f:
        rejected = list(csv.DictReader(f))
    if len(rows) != manifest["records_accepted"]:
        problems.append(f"accepted rows: CSV has {len(rows)}, manifest says {manifest['records_accepted']}")
    if len(rejected) != manifest["records_rejected"]:
        problems.append(f"rejected rows: CSV has {len(rejected)}, manifest says {manifest['records_rejected']}")

    print()
    if problems:
        print("INTEGRITY CHECK FAILED:")
        for p in problems:
            print(" -", p)
        return 1
    print(f"Run {manifest['run_id']} verified: {len(rows)} records, "
          f"{len(checked)} raw pages, scraper version {manifest['scraper_version']}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python verify_run.py runs/<run_id>")
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
