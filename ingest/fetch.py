"""Download World Bank WDI data. No credentials or .env files are used.

Run from the repository root: python ingest/fetch.py
Raw pages and a completion manifest go in ignored data/raw/world_bank/.
"""

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
from pathlib import Path
import random
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.worldbank.org/v2"


class FetchError(Exception):
    """An API response could not be downloaded or verified completely."""


def write_json(path, value):
    """Save readable JSON, preserving nulls and rejecting non-JSON numbers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def retry_delay(header, attempt):
    """Use Retry-After seconds/date, or exponential backoff with jitter."""
    if header:
        try:
            delay = float(header)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(header) -
                         datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                delay = -1
        if math.isfinite(delay) and delay >= 0:
            # End this run instead of sleeping for an unexpectedly long time.
            if delay > 60:
                raise FetchError("Retry-After exceeds 60 seconds; rerun later.")
            return delay
    return min(2 ** attempt, 30) + random.uniform(0, 0.5)


def validate_page(payload, page, per_page, expected):
    """Check the JSON envelope, stable totals, and exact expected page length."""
    if not isinstance(payload, list) or len(payload) != 2:
        raise FetchError("Invalid API envelope or API error payload.")
    metadata, rows = payload
    if not isinstance(metadata, dict) or not isinstance(rows, list):
        raise FetchError("Missing pagination metadata or record list.")
    try:
        actual_page = int(metadata["page"])
        pages = int(metadata["pages"])
        total = int(metadata["total"])
        actual_size = int(metadata["per_page"])
    except (KeyError, ValueError, TypeError) as error:
        raise FetchError("Invalid pagination fields.") from error
    if total <= 0 or pages != math.ceil(total / per_page):
        raise FetchError("Empty result or inconsistent page count.")
    if actual_page != page or actual_size != per_page or page > pages:
        raise FetchError("Wrong page number or page size.")
    signature = (pages, total, metadata.get("lastupdated"))
    if expected is not None and signature != expected:
        raise FetchError("Dataset metadata changed during pagination.")
    wanted = min(per_page, total - (page - 1) * per_page)
    if len(rows) != wanted:
        raise FetchError("Incomplete page: record count does not match metadata.")
    if not all(isinstance(row, dict) for row in rows):
        raise FetchError("A record is not a JSON object.")
    return signature


def request_page(session, url, params, expected, sleep=time.sleep):
    """Retry transient failures and malformed pages; reject permanent HTTP errors."""
    for attempt in range(5):  # Initial attempt plus at most four retries.
        retry_after = None
        try:
            response = session.get(url, params=params, timeout=(10, 40))
            if response.status_code == 429 or 500 <= response.status_code < 600:
                retry_after = response.headers.get("Retry-After")
                raise FetchError(f"Transient HTTP {response.status_code}.")
            response.raise_for_status()
            payload = response.json()
            signature = validate_page(payload, params["page"],
                                      params["per_page"], expected)
            return payload, signature
        except requests.HTTPError as error:
            raise FetchError(f"Permanent HTTP error: {response.status_code}.") from error
        except (requests.Timeout, requests.ConnectionError, ValueError, FetchError) as error:
            if attempt == 4:
                raise FetchError(f"Page failed after five attempts: {error}") from error
            sleep(retry_delay(retry_after, attempt))


def fetch_resource(session, resource, path, params, run_dir, pages_log):
    """Walk every page, reject duplicate keys, and save each validated raw response."""
    rows, seen = [], set()
    expected = None
    page = 1
    while True:
        query = dict(params, page=page)
        payload, expected = request_page(session, BASE_URL + path, query, expected)
        for row in payload[1]:
            try:
                key = ((row["countryiso3code"], row["indicator"]["id"], row["date"])
                       if resource.startswith("observations_") else row["id"])
            except (KeyError, TypeError) as error:
                raise FetchError(f"Missing natural key in {resource}.") from error
            if key in seen:
                raise FetchError(f"Duplicate record in {resource}: {key}")
            seen.add(key)
        filename = f"{resource}_page_{page:03d}.json"
        write_json(run_dir / filename, payload)
        pages_log.append({"file": filename, "endpoint": BASE_URL + path,
                          "parameters": query, "records": len(payload[1])})
        rows.extend(payload[1])
        if page == expected[0]:
            return rows
        page += 1
        time.sleep(0.25)


def validate_observations(rows, countries, indicators, config):
    """Verify foreign keys, requested years, unique observations, and numeric values."""
    counts = {indicator: 0 for indicator in config["indicators"]}
    seen = set()
    for row in rows:
        try:
            country, indicator = row["countryiso3code"], row["indicator"]["id"]
            year, value = int(row["date"]), row["value"]
        except (KeyError, ValueError, TypeError) as error:
            raise FetchError("Observation has missing/invalid fields.") from error
        if country not in countries or indicator not in indicators:
            raise FetchError("Observation references missing metadata.")
        if not config["start_year"] <= year <= config["end_year"]:
            raise FetchError("Observation is outside the requested years.")
        key = (country, indicator, year)
        if key in seen:
            raise FetchError(f"Duplicate observation: {key}")
        seen.add(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise FetchError("Observation value must be numeric or null.")
            counts[indicator] += 1
    if sum(counts.values()) < config["minimum_non_missing"]:
        raise FetchError("Fewer than the required non-missing observations.")
    return counts


def load_config(path):
    """Read only the explicit non-secret configuration and validate its bounds."""
    config = json.loads(path.read_text(encoding="utf-8"))
    for name in ("countries", "indicators"):
        values = config[name]
        if not values or len(values) != len(set(values)):
            raise FetchError(f"Empty or duplicate {name} in config.")
    if not 1 <= config["per_page"] <= 1000:
        raise FetchError("Use a page size between 1 and 1000.")
    if config["start_year"] > config["end_year"]:
        raise FetchError("Start year exceeds end year.")
    return config


def run(config):
    """Download linked resources, check completeness, and publish an authentic sample."""
    started = datetime.now(timezone.utc)
    run_dir = ROOT / "data/raw/world_bank" / started.strftime("%Y%m%dT%H%M%S%fZ")
    manifest = {"status": "incomplete", "started_at": started.isoformat(),
                "config": config, "pages": []}
    write_json(run_dir / "manifest.json", manifest)
    try:
        with requests.Session() as session:
            # No dotenv loading or environment-based proxy/authentication configuration.
            session.trust_env = False
            params = {"format": "json", "per_page": config["per_page"]}
            codes = ";".join(config["countries"])
            countries = fetch_resource(session, "countries", f"/country/{codes}",
                                       params, run_dir, manifest["pages"])
            country_ids = {row["id"] for row in countries}
            if country_ids != set(config["countries"]):
                raise FetchError("Requested country metadata is incomplete.")
            if any(row.get("region", {}).get("value") == "Aggregates" for row in countries):
                raise FetchError("Aggregate regions are not individual countries.")
            indicators, observations, coverage = [], [], {}
            for indicator in config["indicators"]:
                metadata = fetch_resource(session, f"indicator_{indicator}",
                                          f"/indicator/{indicator}", dict(params, source=config["source"]),
                                          run_dir, manifest["pages"])
                if len(metadata) != 1 or metadata[0]["id"] != indicator:
                    raise FetchError("Requested indicator metadata is incomplete.")
                if str(metadata[0].get("source", {}).get("id")) != config["source"]:
                    raise FetchError("Indicator is not from the requested source.")
                indicators.extend(metadata)
                data_params = dict(params, source=config["source"],
                                   date=f'{config["start_year"]}:{config["end_year"]}')
                data = fetch_resource(session, f"observations_{indicator}",
                                      f"/country/{codes}/indicator/{indicator}",
                                      data_params, run_dir, manifest["pages"])
                if any(row.get("indicator", {}).get("id") != indicator for row in data):
                    raise FetchError("Response contains the wrong indicator.")
                # The API may omit unavailable years entirely. Never invent those rows.
                returned_countries = {row.get("countryiso3code") for row in data}
                if returned_countries != country_ids:
                    raise FetchError("An indicator is missing a requested country.")
                wanted = len(countries) * (config["end_year"] - config["start_year"] + 1)
                coverage[indicator] = {
                    "first_returned_year": min(row["date"] for row in data),
                    "last_returned_year": max(row["date"] for row in data),
                    "absent_country_year_slots": wanted - len(data),
                }
                observations.extend(data)
            counts = validate_observations(observations, country_ids,
                                           {row["id"] for row in indicators}, config)
        # Pick actual numeric observations from each indicator, plus a null if present.
        sample_rows = []
        for indicator in config["indicators"]:
            sample_rows.extend([row for row in observations
                                if row["indicator"]["id"] == indicator and row["value"] is not None][:3])
        sample_rows.extend([row for row in observations if row["value"] is None][:1])
        sample_countries = {row["countryiso3code"] for row in sample_rows}
        sample = {"retrieved_at": started.isoformat(), "source": "World Development Indicators",
                  "license": "CC BY 4.0", "license_url": "https://datacatalog.worldbank.org/public-licenses",
                  "terms_url": "https://www.worldbank.org/ext/en/legal/terms-conditions/datasets",
                  "changes": "Subset of API records; original field values preserved.",
                  "countries": [row for row in countries if row["id"] in sample_countries],
                  "indicators": indicators, "observations": sample_rows}
        write_json(ROOT / "data/sample/world_bank_sample.json", sample)
        manifest.update(status="complete", observation_records=len(observations),
                        country_records=len(countries), indicator_records=len(indicators),
                        non_missing_by_indicator=counts, non_missing_total=sum(counts.values()),
                        coverage_by_indicator=coverage,
                        api_pages=len(manifest["pages"]),
                        total_resource_records=len(observations) + len(countries) + len(indicators))
    except Exception as error:
        manifest["error"] = str(error)
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({key: value for key, value in manifest.items()
                      if key not in ("config", "pages")}, indent=2))
    print(f"Raw responses: {run_dir}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "ingest/config.json")
    args = parser.parse_args()
    try:
        run(load_config(args.config))
    except (FetchError, requests.RequestException, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Fetch failed: {error}\n")
