"""Generate the weekly trending README from snapshots.

Strategy:
  1. Find today's snapshot and the one closest to 7 days ago.
  2. For each repo present in both, compute delta = today.stars - past.stars.
  3. Filter out non-positive deltas (we want gainers).
  4. Sort by delta descending.
  5. Produce three views in README:
       - Top 100 Overall (Weekly)
       - By Language (top per language)
       - By Project Type (top per category)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import classify  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO_ROOT / "snapshots"
README_PATH = REPO_ROOT / "README.md"

LANG_BUCKETS = [
    "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++", "C", "C#",
    "Ruby", "PHP", "Swift", "Kotlin", "Shell",
]
TOP_N_OVERALL = 100
TOP_N_PER_LANG = 20
TOP_N_PER_CATEGORY = 20
MIN_DELTA = 5  # ignore repos that gained fewer than this many stars (noise)


def list_snapshots() -> list[Path]:
    return sorted(SNAPSHOT_DIR.glob("*.json"))


def load_snapshot(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def find_pair() -> tuple[Path | None, Path | None]:
    """Return (today_snapshot, snapshot_closest_to_7_days_ago) or (today, None) if not enough history."""
    snaps = list_snapshots()
    if not snaps:
        return None, None
    today = snaps[-1]
    target = datetime.strptime(today.stem, "%Y-%m-%d") - timedelta(days=7)
    best = None
    best_diff = None
    for s in snaps[:-1]:
        d = datetime.strptime(s.stem, "%Y-%m-%d")
        diff = abs((d - target).days)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best = s
    return today, best


def compute_deltas(today_data: dict, past_data: dict) -> list[dict]:
    """For each repo in today's snapshot, compute delta vs past snapshot."""
    deltas = []
    past_repos = past_data["repos"]
    for full, info in today_data["repos"].items():
        if full not in past_repos:
            continue
        delta = info["stars"] - past_repos[full]["stars"]
        if delta < MIN_DELTA:
            continue
        deltas.append({
            "full_name": full,
            "delta": delta,
            "total_stars": info["stars"],
            "language": info.get("language"),
            "topics": info.get("topics", []),
            "description": info.get("description"),
            "name": full.split("/", 1)[1],
        })
    deltas.sort(key=lambda r: r["delta"], reverse=True)
    return deltas


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
        return ["_No data yet._", ""]
    if show_category:
        out = ["| Rank | Repository | +Week | Total | Language | Category | Description |",
               "|:---:|:---|:---:|:---:|:---:|:---:|:---|"]
    else:
        out = ["| Rank | Repository | +Week | Total | Language | Description |",
               "|:---:|:---|:---:|:---:|:---:|:---|"]
    for i, r in enumerate(rows, 1):
        link = f"[{r['full_name']}](https://github.com/{r['full_name']})"
        lang = f"`{r['language']}`" if r['language'] else "—"
        desc = truncate(r['description'], 70).replace("|", "\\|")
        if show_category:
            out.append(f"| {i} | {link} | +{r['delta']} | {fmt_stars(r['total_stars'])} | {lang} | {r['category']} | {desc} |")
        else:
            out.append(f"| {i} | {link} | +{r['delta']} | {fmt_stars(r['total_stars'])} | {lang} | {desc} |")
    out.append("")
    return out


def slugify(text: str) -> str:
    s = text.lower()
    s = s.replace(" / ", "-").replace(" ", "-")
    s = re.sub(r"[^\w\-]", "", s)
    return s


def build_readme(deltas: list[dict], window_days: int, today_date: str, past_date: str) -> str:
    # Annotate categories
    for r in deltas:
        r["category"] = classify(r)

    lines: list[str] = []
    lines.append("# GitHub Weekly Trending")
    lines.append("")
    lines.append("[![Snapshot](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/snapshot.yml/badge.svg)](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/snapshot.yml)")
    lines.append("[![Ranking](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/ranking.yml/badge.svg)](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/ranking.yml)")
    lines.append("[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)")
    lines.append("")
    lines.append(f"> **Period**: {past_date} → {today_date} ({window_days} days)  ")
    lines.append("> Top 100 GitHub repositories by **stars gained in the past week**, ranked overall and by language and by project type.")
    lines.append("")
    lines.append("Auto-refreshed weekly via GitHub Actions. Methodology in [docs/how-it-works.md](docs/how-it-works.md).")
    lines.append("")

    # Navigation
    lines.append("## Navigation")
    lines.append("")
    lines.append(f"- [Top {TOP_N_OVERALL} Overall](#top-{TOP_N_OVERALL}-overall)")
    lines.append("- [By Language](#by-language)")
    lines.append("- [By Project Type](#by-project-type)")
    lines.append("- [About / Caveats](#about--caveats)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Overall
    lines.append(f"## Top {TOP_N_OVERALL} Overall")
    lines.append("")
    lines.extend(render_table(deltas[:TOP_N_OVERALL], show_category=True))

    # By Language
    lines.append("## By Language")
    lines.append("")
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in deltas:
        if r["language"]:
            by_lang[r["language"]].append(r)
    for lang in LANG_BUCKETS:
        rows = by_lang.get(lang, [])[:TOP_N_PER_LANG]
        if not rows:
            continue
        lines.append(f"### {lang}")
        lines.append("")
        lines.extend(render_table(rows))

    # By Project Type
    lines.append("## By Project Type")
    lines.append("")
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in deltas:
        by_cat[r["category"]].append(r)
    cat_order = [
        "LLM / Agent", "AI / ML", "Web Framework", "CLI / DevTool",
        "DevOps / Infra", "Database / Storage", "Security",
        "Data / Analytics", "Mobile", "Game / Graphics", "Learning Resource", "Other",
    ]
    for cat in cat_order:
        rows = by_cat.get(cat, [])[:TOP_N_PER_CATEGORY]
        if not rows:
            continue
        lines.append(f"### {cat}")
        lines.append("")
        lines.extend(render_table(rows))

    # About
    lines.append("## About / Caveats")
    lines.append("")
    lines.append("- **Weekly delta** = stars on `today` − stars on closest snapshot ~7 days earlier. We snapshot the top ~3000 repos by total stars daily.")
    lines.append("- **Project type** classification is rule-based (keywords + GitHub topics). It is not perfect; expect occasional miscategorization.")
    lines.append("- Repos that appear in this week's top-3000 but not 7 days ago are skipped (no baseline). They will surface in later weeks.")
    lines.append("- Star count is a popularity proxy, not a quality measure.")
    lines.append("- Snapshots older than 90 days are auto-pruned to keep the repo small.")
    lines.append("")
    lines.append("## License")
    lines.append("")
    lines.append("[MIT](LICENSE)")
    lines.append("")
    return "\n".join(lines)


def main():
    today, past = find_pair()
    if today is None:
        print("No snapshots found. Run scripts/snapshot.py first.", file=sys.stderr)
        sys.exit(1)
    if past is None:
        print(
            f"Only one snapshot ({today.stem}) — need at least two with a ~7 day gap. "
            "Re-run after enough snapshots accumulate.",
            file=sys.stderr,
        )
        sys.exit(1)

    today_data = load_snapshot(today)
    past_data = load_snapshot(past)
    window = (datetime.strptime(today.stem, "%Y-%m-%d") - datetime.strptime(past.stem, "%Y-%m-%d")).days

    deltas = compute_deltas(today_data, past_data)
    print(f"Computed {len(deltas)} deltas (window {window} days).")

    readme = build_readme(deltas, window_days=window, today_date=today.stem, past_date=past.stem)
    README_PATH.write_text(readme, encoding="utf-8")
    print(f"Wrote {README_PATH} ({README_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
