"""Scrape github.com/trending?since=weekly and generate the README.

This is the single source of truth for this project. Runs daily via GitHub Actions.

Pipeline:
  1. Scrape /trending?since=weekly  (overall, ~25 repos)
  2. Scrape /trending/<lang>?since=weekly  for ~15 languages
  3. Deduplicate by full_name, keep the highest weekly delta seen
  4. Optionally enrich with GitHub Topics via API (needs GITHUB_TOKEN)
  5. Classify into project type (LLM/Agent, AI/ML, Web Framework, ...)
  6. Write README.md with three views: Top 100 Overall, By Language, By Project Type
"""
from __future__ import annotations

import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import classify  # noqa: E402


BASE = "https://github.com/trending"
LANG_BUCKETS = [
    "python", "javascript", "typescript", "go", "rust",
    "java", "c++", "c", "c#", "ruby", "php", "swift", "kotlin", "shell",
]

# Display name for each language slug (GitHub uses lowercase + special chars)
LANG_DISPLAY = {
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
    "go": "Go", "rust": "Rust", "java": "Java",
    "c++": "C++", "c": "C", "c#": "C#",
    "ruby": "Ruby", "php": "PHP", "swift": "Swift", "kotlin": "Kotlin", "shell": "Shell",
}

TOP_N_OVERALL = 100
TOP_N_PER_LANG = 25
TOP_N_PER_CATEGORY = 25

CATEGORY_ORDER = [
    "LLM / Agent", "AI / ML", "Web Framework", "CLI / DevTool",
    "DevOps / Infra", "Database / Storage", "Security",
    "Data / Analytics", "Mobile", "Game / Graphics", "Learning Resource", "Other",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"

TOKEN = os.environ.get("GITHUB_TOKEN")
API_HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    API_HEADERS["Authorization"] = f"Bearer {TOKEN}"

UA = {"User-Agent": "Mozilla/5.0 (compatible; github-weekly-trending)"}


def parse_int(s: str) -> int:
    s = s.strip().replace(",", "")
    if not s:
        return 0
    if s.endswith("k"):
        return int(float(s[:-1]) * 1000)
    if s.endswith("M") or s.endswith("m"):
        return int(float(s[:-1]) * 1_000_000)
    m = re.search(r"\d+", s)
    return int(m.group()) if m else 0


def fetch_page(language: str | None = None) -> str:
    url = BASE if not language else f"{BASE}/{language}"
    url += "?since=weekly"
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def parse_trending(html: str) -> list[dict]:
    """Parse the trending page HTML into structured repos."""
    soup = BeautifulSoup(html, "html.parser")
    repos: list[dict] = []
    for article in soup.select("article.Box-row"):
        h2 = article.select_one("h2 a")
        if not h2:
            continue
        full = h2.get("href", "").strip("/")
        if "/" not in full:
            continue

        desc_p = article.select_one("p")
        description = desc_p.get_text(" ", strip=True) if desc_p else ""

        lang_span = article.select_one('[itemprop="programmingLanguage"]')
        language = lang_span.get_text(strip=True) if lang_span else None

        # Total stars: <a href="/<repo>/stargazers">
        total_stars = 0
        for a in article.select("a"):
            href = a.get("href", "")
            if href.endswith("/stargazers"):
                total_stars = parse_int(a.get_text(" ", strip=True))
                break

        # Weekly stars: span with text like "234 stars this week" or "234 stars today"
        delta = 0
        for span in article.select("span"):
            txt = span.get_text(" ", strip=True)
            m = re.search(r"([\d,]+)\s+stars\s+this\s+week", txt)
            if m:
                delta = parse_int(m.group(1))
                break

        repos.append({
            "full_name": full,
            "name": full.split("/", 1)[1],
            "description": description,
            "language": language,
            "total_stars": total_stars,
            "delta": delta,
            "topics": [],
        })
    return repos


def scrape_all() -> dict[str, dict]:
    """Scrape overall + per-language trending pages. Return deduped {full_name: repo}."""
    print("Scraping overall trending...")
    all_repos: dict[str, dict] = {}
    for r in parse_trending(fetch_page()):
        all_repos[r["full_name"]] = r
    time.sleep(1)

    for lang in LANG_BUCKETS:
        print(f"Scraping {lang}...")
        try:
            for r in parse_trending(fetch_page(lang)):
                existing = all_repos.get(r["full_name"])
                if not existing or r["delta"] > existing["delta"]:
                    all_repos[r["full_name"]] = r
        except Exception as e:
            print(f"  {lang} failed: {e}", file=sys.stderr)
        time.sleep(1)

    return all_repos


def enrich_topics(repos: dict[str, dict]):
    """Fetch GitHub Topics for each repo via API. Best effort — silent failure."""
    if not TOKEN:
        print("No GITHUB_TOKEN, skipping topic enrichment (classification will be weaker).")
        return
    print(f"Enriching topics for {len(repos)} repos via API...")
    for i, (full, r) in enumerate(repos.items()):
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{full}/topics",
                headers={**API_HEADERS, "Accept": "application/vnd.github.mercy-preview+json"},
                timeout=15,
            )
            if resp.status_code == 200:
                r["topics"] = resp.json().get("names", [])
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"  enriched {i+1}/{len(repos)}")


def fmt_stars(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def truncate(s: str | None, n: int) -> str:
    if not s:
        return "—"
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_table(rows: list[dict], show_category: bool = False) -> list[str]:
    if not rows:
        return ["_No data._", ""]
    if show_category:
        out = [
            "| Rank | Repository | +Week | Total | Language | Category | Description |",
            "|:---:|:---|:---:|:---:|:---:|:---:|:---|",
        ]
    else:
        out = [
            "| Rank | Repository | +Week | Total | Language | Description |",
            "|:---:|:---|:---:|:---:|:---:|:---|",
        ]
    for i, r in enumerate(rows, 1):
        link = f"[{r['full_name']}](https://github.com/{r['full_name']})"
        lang = f"`{r['language']}`" if r['language'] else "—"
        desc = truncate(r['description'], 70).replace("|", "\\|")
        delta = f"+{r['delta']}" if r['delta'] > 0 else "—"
        total = fmt_stars(r['total_stars'])
        if show_category:
            out.append(f"| {i} | {link} | {delta} | {total} | {lang} | {r['category']} | {desc} |")
        else:
            out.append(f"| {i} | {link} | {delta} | {total} | {lang} | {desc} |")
    out.append("")
    return out


def build_readme(repos: list[dict]) -> str:
    # Classify each
    for r in repos:
        r["category"] = classify(r)

    # Sort by weekly delta desc
    repos.sort(key=lambda x: x["delta"], reverse=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L: list[str] = []
    L.append("# GitHub Weekly Trending")
    L.append("")
    L.append("[![Update](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/update.yml/badge.svg)](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/update.yml)")
    L.append("[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)")
    L.append("")
    L.append(f"> **Last updated**: {now}  ")
    L.append("> Top GitHub repositories by **stars gained in the past week**, ranked overall, by language, and by project type.")
    L.append("")
    L.append(f"Sourced from `github.com/trending?since=weekly` (overall + {len(LANG_BUCKETS)} language pages). Updated daily by GitHub Actions. Methodology in [docs/how-it-works.md](docs/how-it-works.md).")
    L.append("")

    # Navigation
    L.append("## Navigation")
    L.append("")
    L.append(f"- [Top {TOP_N_OVERALL} Overall](#top-{TOP_N_OVERALL}-overall)")
    L.append("- [By Language](#by-language)")
    L.append("- [By Project Type](#by-project-type)")
    L.append("- [About / Caveats](#about--caveats)")
    L.append("")
    L.append("---")
    L.append("")

    L.append(f"## Top {TOP_N_OVERALL} Overall")
    L.append("")
    L.extend(render_table(repos[:TOP_N_OVERALL], show_category=True))

    L.append("## By Language")
    L.append("")
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in repos:
        if r["language"]:
            by_lang[r["language"]].append(r)
    for slug in LANG_BUCKETS:
        display = LANG_DISPLAY[slug]
        rows = by_lang.get(display, [])[:TOP_N_PER_LANG]
        if not rows:
            continue
        L.append(f"### {display}")
        L.append("")
        L.extend(render_table(rows))

    L.append("## By Project Type")
    L.append("")
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in repos:
        by_cat[r["category"]].append(r)
    for cat in CATEGORY_ORDER:
        rows = by_cat.get(cat, [])[:TOP_N_PER_CATEGORY]
        if not rows:
            continue
        L.append(f"### {cat}")
        L.append("")
        L.extend(render_table(rows))

    L.append("## About / Caveats")
    L.append("")
    L.append("- Data source is `github.com/trending?since=weekly` — same weekly star count GitHub itself shows on its trending page.")
    L.append("- Coverage: overall page + 14 language pages, ~20 repos per page. Total uniques typically 150-250.")
    L.append("- **Project type** classification is rule-based (GitHub topics + name/description keywords). Edit `data/categories.yaml` to add or refine categories.")
    L.append("- Topic enrichment runs when `GITHUB_TOKEN` is available (always true in CI). Without it, classification falls back to name + description only.")
    L.append("- Star count is a popularity proxy, not a quality measure.")
    L.append("")
    L.append("## License")
    L.append("")
    L.append("[MIT](LICENSE)")
    L.append("")
    return "\n".join(L)


def main():
    repos_map = scrape_all()
    print(f"Scraped {len(repos_map)} unique repos.")
    enrich_topics(repos_map)
    readme = build_readme(list(repos_map.values()))
    README_PATH.write_text(readme, encoding="utf-8")
    print(f"Wrote {README_PATH} ({README_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
