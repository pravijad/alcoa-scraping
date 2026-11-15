"""
ALCOA+ practice scraper for https://quotes.toscrape.com
(a site built specifically for learning web scraping).

How each principle is applied:
  Attributable    -> every row stores source URL, scraper version and run ID
  Legible         -> clean CSV with clear column names + human-readable log
  Contemporaneous -> UTC timestamp recorded at the moment each page is fetched
  Original        -> raw HTML saved untouched, with a SHA-256 hash per page
  Accurate        -> every record validated; bad rows go to rejected.csv, not dropped
  Complete        -> manifest counts pages, accepted rows and rejected rows
  Consistent      -> same columns, same format, same process every run
  Enduring        -> everything written to disk in a per-run folder
  Available       -> manifest.json indexes the run so it can be reviewed later

Setup:  pip install requests beautifulsoup4
Run:    python alcoa_scraper.py
"""

import csv
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

SCRAPER_VERSION = "1.0.1"  # 1.0.1: robots.txt fetched via requests (fixes macOS SSL error)
BASE_URL = "https://quotes.toscrape.com"
USER_AGENT = "ALCOA-Learning-Scraper/1.0 (practice project)"
DELAY_SECONDS = 1.0   # be polite: pause between requests
MAX_PAGES = 20        # safety limit

# ---- Per-run output folder (Enduring, Available) ----
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT_DIR = Path("runs") / RUN_ID
RAW_DIR = OUT_DIR / "raw_html"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---- Logging to file and screen (Attributable, Legible) ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(OUT_DIR / "scrape.log", encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("alcoa_scraper")

FIELDS = ["quote", "author", "tags", "source_url", "scraped_at_utc",
          "raw_html_file", "raw_html_sha256", "scraper_version", "run_id"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_robots(session: requests.Session) -> RobotFileParser:
    """Fetch robots.txt with requests (which bundles its own SSL certificates)."""
    rp = RobotFileParser()
    robots_url = urljoin(BASE_URL, "/robots.txt")
    try:
        response = session.get(robots_url, timeout=15)
        if response.status_code == 200:
            rp.parse(response.text.splitlines())
            log.info("Loaded robots.txt from %s", robots_url)
        else:
            rp.parse([])  # no robots.txt means no restrictions
            log.info("No robots.txt at %s (status %s); no restrictions", robots_url, response.status_code)
    except Exception as exc:
        rp.parse([])
        log.warning("Could not read robots.txt (%s); proceeding carefully", exc)
    return rp


def fetch(session: requests.Session, url: str, page_no: int) -> dict:
    """Fetch a page and save the untouched original (Original, Contemporaneous)."""
    response = session.get(url, timeout=15)
    fetched_at = utc_now()  # recorded at the moment of capture
    response.raise_for_status()

    raw = response.content
    digest = sha256_bytes(raw)
    raw_file = RAW_DIR / f"page_{page_no:03d}.html"
    raw_file.write_bytes(raw)

    log.info("Fetched %s (status %s, sha256 %s...)", url, response.status_code, digest[:12])
    return {"html": raw.decode("utf-8", errors="replace"), "fetched_at": fetched_at,
            "raw_file": str(raw_file), "sha256": digest}


def validate(record: dict) -> list[str]:
    """Return a list of problems; an empty list means the record is valid (Accurate)."""
    problems = []
    if not record["quote"].strip():
        problems.append("empty quote")
    if not record["author"].strip():
        problems.append("empty author")
    if len(record["quote"]) > 2000:
        problems.append("quote suspiciously long")
    return problems


def parse(page: dict, url: str) -> list[dict]:
    soup = BeautifulSoup(page["html"], "html.parser")
    records = []
    for block in soup.select("div.quote"):
        text_el = block.select_one("span.text")
        author_el = block.select_one("small.author")
        records.append({
            "quote": text_el.get_text(strip=True) if text_el else "",
            "author": author_el.get_text(strip=True) if author_el else "",
            "tags": "|".join(t.get_text(strip=True) for t in block.select("a.tag")),
            "source_url": url,
            "scraped_at_utc": page["fetched_at"],
            "raw_html_file": page["raw_file"],
            "raw_html_sha256": page["sha256"],
            "scraper_version": SCRAPER_VERSION,
            "run_id": RUN_ID,
        })
    next_link = soup.select_one("li.next a")
    next_url = urljoin(url, next_link["href"]) if next_link else None
    return records, next_url


def main():
    started = utc_now()
    log.info("Run %s started, scraper version %s", RUN_ID, SCRAPER_VERSION)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    robots = load_robots(session)

    accepted, rejected, errors = [], [], []
    url, page_no = BASE_URL + "/", 1

    while url and page_no <= MAX_PAGES:
        if not robots.can_fetch(USER_AGENT, url):
            log.warning("robots.txt disallows %s; stopping", url)
            break
        try:
            page = fetch(session, url, page_no)
            records, next_url = parse(page, url)
        except Exception as exc:
            log.error("Failed on %s: %s", url, exc)   # logged, never silently skipped
            errors.append({"url": url, "error": str(exc), "at": utc_now()})
            break

        for rec in records:
            problems = validate(rec)
            if problems:
                rejected.append({**rec, "rejection_reason": "; ".join(problems)})
                log.warning("Rejected record on %s: %s", url, problems)
            else:
                accepted.append(rec)

        url, page_no = next_url, page_no + 1
        time.sleep(DELAY_SECONDS)

    # ---- Write outputs (Legible, Consistent, Enduring) ----
    data_file = OUT_DIR / "quotes.csv"
    with open(data_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(accepted)

    rejected_file = OUT_DIR / "rejected.csv"
    with open(rejected_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS + ["rejection_reason"])
        writer.writeheader()
        writer.writerows(rejected)

    # ---- Manifest: the audit summary for this run (Complete, Available) ----
    manifest = {
        "run_id": RUN_ID,
        "scraper_version": SCRAPER_VERSION,
        "source": BASE_URL,
        "started_utc": started,
        "finished_utc": utc_now(),
        "pages_fetched": page_no - 1 - len(errors),
        "records_accepted": len(accepted),
        "records_rejected": len(rejected),
        "errors": errors,
        "output_files": {
            "quotes.csv": sha256_bytes(data_file.read_bytes()),
            "rejected.csv": sha256_bytes(rejected_file.read_bytes()),
        },
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("Done: %d accepted, %d rejected. Output in %s",
             len(accepted), len(rejected), OUT_DIR)


if __name__ == "__main__":
    main()
