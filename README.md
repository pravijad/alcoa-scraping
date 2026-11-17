# alcoa-scraping

Python web scrapers built on **ALCOA+ data integrity principles**. Every record they collect can be traced to its source, the original pages are preserved with SHA-256 fingerprints, and an independent verifier proves that nothing has changed since the run.

The targets are two sites built for scraping practice. The sites are just practice material; the point of the project is the integrity layer, which carries over unchanged to any scraping pipeline whose output has to stand up to review.

## The scrapers

| Scraper | Site | Collects | Run size |
|---|---|---|---|
| `alcoa_scraper.py` | [quotes.toscrape.com](https://quotes.toscrape.com) | Quote, author, tags | 10 pages, 100 records |
| `books_scraper.py` | [books.toscrape.com](https://books.toscrape.com) | Title, price, rating, stock status, product URL | 50 pages, 1,000 records |

Both share the same integrity layer: raw page capture, hashing, validation, logging and a run manifest. Only the parsing and validation rules are specific to each site, which shows how the ALCOA+ structure carries over from one source to the next.

## What is ALCOA+?

ALCOA+ is a set of data integrity principles from regulated industries such as pharmaceuticals and clinical research, where regulators expect records to be trustworthy and auditable. It asks that data be **A**ttributable, **L**egible, **C**ontemporaneous, **O**riginal and **A**ccurate, plus **C**omplete, **C**onsistent, **E**nduring and **A**vailable.

## How each principle is implemented

| Principle | In this project |
|---|---|
| Attributable | Every row carries its `source_url`, `run_id` and `scraper_version` |
| Legible | Clean CSV with clear column names, ISO 8601 UTC timestamps, a readable log |
| Contemporaneous | `scraped_at_utc` is recorded at the moment each page is fetched |
| Original | Raw HTML is saved untouched, with a SHA-256 hash stored on every row. Source text is recorded exactly as published, including its own typos |
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

python3 alcoa_scraper.py          # quotes: about 15 seconds
python3 books_scraper.py          # books: about 1 minute
```

Each scraper checks `robots.txt` first and waits one second between requests.

## What a run produces

```
runs/20261117T215507Z/
├── books.csv         # the data (quotes.csv for the quotes scraper), with provenance on every row
├── rejected.csv      # records that failed validation, with reasons
├── raw_html/         # the original pages, exactly as captured
│   ├── page_001.html
│   └── ...
├── scrape.log        # audit trail of every action and error
└── manifest.json     # run summary: counts, timings, output file hashes
```

The run ID is a UTC timestamp, which avoids time zone ambiguity in records.

## The books scraper in detail

The books site has a few realistic puzzles, each handled explicitly:

| Challenge | Handling |
|---|---|
| Long titles are cut short on screen (`A Light in the ...`) | The full title is read from the link's `title` attribute |
| Prices include a currency sign (`£51.77`) | The sign is stripped and the value stored as `price_gbp` |
| Ratings appear only as a CSS class (`star-rating Three`) | The class word is mapped to a number from 1 to 5 |
| Pagination and product links are relative, and their form changes after page 1 (`catalogue/page-2.html`, then `page-3.html`) | Every link is resolved against the current page with `urljoin` |

Validation rejects any record with a missing title, a price that isn't a positive number, a rating outside 1 to 5, an unknown stock status or a missing product URL. An out-of-stock book is valid data, not an error.

## Verifying a run

```bash
python3 verify_run.py runs/20261117T215507Z
```

The verifier works with runs from either scraper. It reads the data file's name from the manifest, re-hashes every output file and raw page, compares them with the hashes recorded during the run, and checks the row counts against the manifest. It exits with a non-zero code on failure, so it can gate an automated pipeline.

### Tampering demonstration

Change a single letter in a data file (for example `Albert Einstein` to `Albert Einstien` in a quotes run), save, and run the verifier:

```
CHANGED  quotes.csv
OK       rejected.csv
OK       runs/20261115T224333Z/raw_html/page_001.html
...
INTEGRITY CHECK FAILED:
 - quotes.csv has changed since the run
```

The raw pages still pass, so the untouched originals remain available to compare against. Undo the edit and the check passes again, because the file is byte-for-byte identical to what the scraper wrote.

Note that the hashes are only as trustworthy as the manifest that stores them: someone able to edit both the data and the manifest could defeat this check. Storing manifests or their hashes somewhere the data's editors cannot change is a planned improvement.

## Versioning

Each scraper has its own `SCRAPER_VERSION`, bumped whenever its extraction logic changes, and each version is committed to Git. Since every row records the version that produced it, any record can be traced to the exact code and, through `requirements.txt`, the exact libraries behind it. If extraction turns out to be wrong, the fix is a new version re-run against the saved raw HTML; earlier outputs are never edited.

| Scraper | Version | Change |
|---|---|---|
| books | 1.0.0 | Initial release |
| quotes | 1.0.1 | `robots.txt` fetched with `requests`, fixing certificate errors on macOS python.org installs |
| quotes | 1.0.0 | Initial release |

## Responsible scraping

The scrapers identify themselves with a descriptive User-Agent, respect `robots.txt`, wait between requests and stop after a fixed page limit. Before adapting them to another site, check for an official API and read the site's terms of service.

## Notes

`runs/` and `venv/` are excluded by `.gitignore`. Scraped data belongs in durable, backed-up storage rather than a code repository, and the environment can be rebuilt from `requirements.txt`.
