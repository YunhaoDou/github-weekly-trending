# How It Works

## Why "weekly delta", not absolute stars

Lists like [Awesome-List-github-stars-ranking](https://github.com/YunhaoDou/Awesome-List-github-stars-ranking) rank by total stars — that surfaces the same titans every week (freeCodeCamp, React, Linux kernel) because their absolute lead is enormous. The "what's hot this week" question is answered by **weekly delta**: which repos picked up the most new stars in the past 7 days.

## The pipeline

```
┌────────────────┐         daily 00:00 UTC          ┌──────────────────────┐
│  GitHub Search │ ────────────────────────────────▶│  snapshots/<date>.json│
│      API       │  scripts/snapshot.py             │  top ~3000 repos     │
└────────────────┘                                  └──────────┬───────────┘
                                                               │
                                                               │  weekly Mon 02:00 UTC
                                                               ▼
                                                   ┌──────────────────────┐
                                                   │  scripts/ranking.py   │
                                                   │  diff vs ~7-day-old   │
                                                   │  snapshot → README    │
                                                   └──────────────────────┘
```

## Snapshot details

The GitHub Search API has a **1000-result cap per query**, so we slice by star buckets (`stars:>100000`, `stars:50000..100000`, …) and paginate within each bucket until we have ~3000 repos. This sidesteps the cap without sacrificing coverage of the long tail above 1000 stars.

Each snapshot is a compact JSON:
```json
{
  "captured_at": "2026-06-06T00:01:23Z",
  "repos": {
    "owner/name": {
      "stars": 12345,
      "language": "Python",
      "topics": ["llm", "agent"],
      "description": "..."
    }
  }
}
```

Snapshots older than 90 days are auto-pruned to keep the repo small.

## Project type classification

Two-tier rule-based:

1. **GitHub Topics** (weight 2): authoritative — when a repo declares itself as `topic: machine-learning`, that's a strong signal.
2. **Keyword match in name + description** (weight 1): catches repos that don't bother with topics.

Categories are defined in `data/categories.yaml`. Adding a category is a one-line YAML edit; no code change.

Order in the YAML file is the tie-break priority — earlier categories win ties. That's why `LLM / Agent` is listed before `AI / ML`: a project tagged with both `llm` and `machine-learning` should land in the more specific bucket.

## Caveats (read these before drawing conclusions)

- **First-week problem**: when a repo enters the top-3000 fresh this week but wasn't there 7 days ago, we have no baseline. It will be skipped this cycle and surface next week.
- **Top-3000 cutoff**: repos outside the top-3000 by total stars are not tracked. A repo at 800 stars exploding to 1500 in a week will not show up. We may raise this in future.
- **Star count is noisy**: a single viral tweet can spike a repo. Stars do not equal quality, longevity, or even usefulness. Treat the list as "what GitHub paid attention to this week", nothing more.
- **Classification is approximate**: rule-based heuristics work ~80% of the time. If you see something miscategorized, PRs to `data/categories.yaml` welcome.
- **Snapshot timing**: snapshot runs at 00:00 UTC. The "week" boundary is whichever pair the script picks (today + closest to today-7d). Usually a clean 7-day window; occasionally 6 or 8 if a snapshot run was missed.

## Extending

- **Add a category**: edit `data/categories.yaml`. No code.
- **Add a language bucket**: edit `LANG_BUCKETS` at the top of `scripts/ranking.py`.
- **Change top-N counts**: edit `TOP_N_*` constants in `scripts/ranking.py`.
- **Different time window**: tweak `find_pair()` in `scripts/ranking.py` to target N days instead of 7.

## Why not just scrape github.com/trending?

GitHub Trending only shows ~25 repos per page and the "weekly" view is officially capped. Our snapshot diff gives a much deeper view (top 3000 → top 100 by delta) and is reproducible — anyone can run the scripts locally and get the same numbers.
