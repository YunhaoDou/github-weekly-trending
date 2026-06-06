"""Take a daily snapshot of top GitHub repos by total star count.

Snapshots feed the weekly ranking script, which diffs two snapshots 7 days apart.

Output: snapshots/YYYY-MM-DD.json
Schema:
    {
      "captured_at": "YYYY-MM-DDTHH:MM:SSZ",
      "repos": {
        "owner/name": {
          "stars": int,
          "language": str | null,
          "topics": [str],
          "description": str | null
        },
        ...
      }
    }
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


GITHUB_API = "https://api.github.com/search/repositories"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("G_TOKEN")
HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# Pull top N repos. Each page is 100. 30 pages = top 3000.
# GitHub Search API caps at 1000 results per query, so we slice by star buckets.
TARGET_REPOS = 3000

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO_ROOT / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_page(query: str, page: int) -> list[dict]:
    """Fetch one page of search results."""
    for attempt in range(3):
        try:
            resp = requests.get(
                GITHUB_API,
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 100, "page": page},
                headers=HEADERS,
                timeout=20,
            )
            if resp.status_code == 403:
                # Rate limit — wait and retry once
                reset = resp.headers.get("X-RateLimit-Reset")
                if reset:
                    sleep_for = max(int(reset) - int(time.time()) + 2, 5)
                    print(f"  rate-limited, sleeping {sleep_for}s", file=sys.stderr)
                    time.sleep(min(sleep_for, 60))
                    continue
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    return []


def fetch_top_repos(target: int) -> dict[str, dict]:
    """Fetch top-`target` repos using star-bucketed queries to bypass the 1000-result cap."""
    repos: dict[str, dict] = {}
    # Bucket by star count tiers. Adjust thresholds as needed.
    buckets = [
        ">100000",
        "50000..100000",
        "30000..50000",
        "20000..30000",
        "15000..20000",
        "10000..15000",
        "7000..10000",
        "5000..7000",
        "3000..5000",
        "2000..3000",
        "1500..2000",
        "1000..1500",
    ]

    for bucket in buckets:
        if len(repos) >= target:
            break
        query = f"stars:{bucket}"
        for page in range(1, 11):  # max 1000 per bucket
            items = fetch_page(query, page)
            if not items:
                break
            for it in items:
                full = it["full_name"]
                if full in repos:
                    continue
                repos[full] = {
                    "stars": it["stargazers_count"],
                    "language": it.get("language"),
                    "topics": it.get("topics", []),
                    "description": it.get("description"),
                }
                if len(repos) >= target:
                    break
            if len(items) < 100:
                break
            time.sleep(1.5)  # courtesy delay
        if len(repos) >= target:
            break

    return repos


def main():
    if not TOKEN:
        print("Warning: no GITHUB_TOKEN set. You will be heavily rate-limited.", file=sys.stderr)

    date = datetime.now(timezone.utc).date().isoformat()
    out_path = SNAPSHOT_DIR / f"{date}.json"
    if out_path.exists():
        print(f"Snapshot for {date} already exists, skipping.")
        return

    print(f"Fetching top ~{TARGET_REPOS} repos...")
    repos = fetch_top_repos(TARGET_REPOS)
    print(f"Got {len(repos)} repos.")

    snapshot = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos": repos,
    }

    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
