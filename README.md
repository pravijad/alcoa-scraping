# alcoa-scraping

A Python web scraper built on **ALCOA+ data integrity principles**. Every record it collects can be traced to its source, the original pages are preserved with SHA-256 fingerprints, and an independent verifier proves that nothing has changed since the run.

The target is [quotes.toscrape.com](https://quotes.toscrape.com), a site built for scraping practice. The site is just practice material; the point of the project is the integrity layer, which carries over unchanged to any scraping pipeline whose output has to stand up to review.

## What is ALCOA+?

ALCOA+ is a set of data integrity principles from regulated industries such as pharmaceuticals and clinical research, where regulators expect records to be trustworthy and auditable. It asks that data be **A**ttributable, **L**egible, **C**ontemporaneous, **O**riginal and **A**ccurate, plus **C**omplete, **C**onsistent, **E**nduring and **A**vailable.

## How each principle is implemented

| Principle | In this project |
|---|---|
| Attributable | Every row carries its `source_url`, `run_id` and `scraper_version` |
| Legible | Clean CSV with clear column names, ISO 8601 UTC timestamps, a readable log |
| Contemporaneous | `scraped_at_utc` is recorded at the moment each page is fetched |
| Original | Raw HTML is saved untouched, with a SHA-256 hash stored on every row |
| Accurate | Each record is validated; failures go to `rejected.csv` with a reason, never silently dropped |
| Complete | Errors are logged, failed runs are kept, and the manifest counts pages, accepted and rejected rows |
| Consistent | Same columns and process every run; library versions pinned in `requirements.txt` |
| Enduring | Each run writes to its own folder on disk |
| Available | `manifest.json` indexes the run, and `verify_run.py` lets anyone check it independently |

## Quick start

Requires Python 3.10 or newer.

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python3 alcoa_scraper.py
```

The scraper fetches all 10 pages with a one-second pause between requests and checks `robots.txt` first.

## What a run produces

```
runs/20261115T224333Z/
├── quotes.csv        # the data, with provenance on every row
├── rejected.csv      # records that failed validation, with reasons
├── raw_html/         # the original pages, exactly as captured
│   ├── page_001.html
│   └── ...
├── scrape.log        # audit trail of every action and error
└── manifest.json     # run summary: counts, timings, output file hashes
```

The run ID is a UTC timestamp, which avoids time zone ambiguity in records.

## Verifying a run

```bash
python3 verify_run.py runs/20261115T224333Z
```

The verifier re-hashes every output file and raw page, compares them with the hashes recorded during the run, and checks the row counts against the manifest. It exits with a non-zero code on failure, so it can gate an automated pipeline.

### Tampering demonstration

Change a single letter in `quotes.csv` (for example `Albert Einstein` to `Albert Einstien`), save, and run the verifier:

```
CHANGED  quotes.csv
OK       rejected.csv
OK       runs/20261115T224333Z/raw_html/page_001.html
...
INTEGRITY CHECK FAILED:
 - quotes.csv has changed since the run
```

The raw pages still pass, so the untouched originals remain available to compare against. Undo the edit and the check passes again, because the file is byte-for-byte identical to what the scraper wrote.

## Versioning

`SCRAPER_VERSION` is bumped whenever the extraction logic changes, and each version is committed to Git. Since every row records the version that produced it, any record can be traced to the exact code and, through `requirements.txt`, the exact libraries behind it. If extraction turns out to be wrong, the fix is a new version re-run against the saved raw HTML; earlier outputs are never edited.

| Version | Change |
|---|---|
| 1.0.1 | `robots.txt` fetched with `requests`, fixing certificate errors on macOS python.org installs |
| 1.0.0 | Initial release |

## Responsible scraping

The scraper identifies itself with a descriptive User-Agent, respects `robots.txt`, waits between requests and stops after a fixed page limit. Before adapting it to another site, check for an official API and read the site's terms of service.

## Notes

`runs/` and `venv/` are excluded by `.gitignore`. Scraped data belongs in durable, backed-up storage rather than a code repository, and the environment can be rebuilt from `requirements.txt`.
