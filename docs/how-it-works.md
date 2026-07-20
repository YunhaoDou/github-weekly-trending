# How It Works

## Why "weekly delta" instead of total stars

Lists like [Awesome-List-github-stars-ranking](https://github.com/YunhaoDou/Awesome-List-github-stars-ranking) rank by total stars — that surfaces the same titans every week (freeCodeCamp, React, Linux kernel) because their absolute lead is enormous. The "what's hot **this week**" question is answered by **weekly delta**: which repos picked up the most new stars in the past 7 days.

## The pipeline

```
┌──────────────────────────────┐
│  github.com/trending         │
│   ?since=weekly              │
│  (overall + 14 languages)    │
└──────────────┬───────────────┘
               │ daily 00:00 UTC
               ▼
┌──────────────────────────────┐
│  scripts/build.py            │
│   - HTML parse (BeautifulSoup)│
│   - Dedupe by full_name      │
│   - Enrich topics via API    │
│   - Classify (rule-based)    │
│   - Render README            │
└──────────────┬───────────────┘
               │ commit + push
               ▼
        README.md (auto-generated)
```

## Why scrape github.com/trending instead of computing our own delta

GitHub's `/trending?since=weekly` page already shows the per-repo weekly star count, computed and ranked by GitHub itself. Re-implementing this via daily snapshots and 7-day diffs adds complexity (storage, missing snapshots, repos entering/leaving the top-N) for no gain. We use the same data the GitHub UI shows.

The tradeoff: we depend on GitHub's HTML structure. If GitHub redesigns the trending page, the parser breaks. Mitigation: defensive parsing with CSS selectors that focus on the stable parts.

## Coverage

We scrape:
- `/trending?since=weekly` — overall page (~25 repos)
- `/trending/<lang>?since=weekly` for 14 languages: python, javascript, typescript, go, rust, java, c++, c, c#, ruby, php, swift, kotlin, shell

After deduplication, this typically yields 150-250 unique repos per run, ample for a top-100 table.

## Project type classification

Two-tier rule-based:

1. **GitHub Topics** (weight 2): authoritative — when a repo declares itself as `topic: machine-learning`, that's a strong signal.
2. **Keyword match in name + description** (weight 1): catches repos that don't bother with topics.

Categories live in [`data/categories.yaml`](../data/categories.yaml). Adding a category is a one-line YAML edit; no code change.

Order in the YAML file is tie-break priority — earlier wins. `LLM / Agent` is listed before `AI / ML` so a project tagged with both `llm` and `machine-learning` lands in the more specific bucket.

Topics are only available via the GitHub API (separate from the trending page HTML). The workflow runs with `GITHUB_TOKEN` so topic enrichment is automatic. Run locally without a token and classification falls back to name + description only — still works, just slightly noisier.

## Caveats

- **Star count is noisy**: a single viral tweet can spike a repo. Stars do not equal quality, longevity, or usefulness. Treat the list as "what GitHub paid attention to this week", nothing more.
- **Classification is approximate**: rule-based heuristics work ~80% of the time. If you see something miscategorized, edit `data/categories.yaml` and submit a PR.
- **Trending page selection bias**: GitHub's own algorithm decides what shows up in trending — we don't see anything below their threshold. That threshold is opaque.

## Extending

- **Add a category**: edit `data/categories.yaml`. No code.
- **Add a language bucket**: edit `LANG_BUCKETS` and `LANG_DISPLAY` at the top of `scripts/build.py`.
- **Change top-N counts**: edit `TOP_N_*` constants in `scripts/build.py`.
- **Change update frequency**: edit cron expression in `.github/workflows/update.yml`.
