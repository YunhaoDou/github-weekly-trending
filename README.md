# GitHub Weekly Trending

[![Snapshot](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/snapshot.yml/badge.svg)](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/snapshot.yml)
[![Ranking](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/ranking.yml/badge.svg)](https://github.com/YunhaoDou/github-weekly-trending/actions/workflows/ranking.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Top 100 GitHub repositories by **stars gained in the past week**, ranked overall and by language and by project type.

Auto-refreshed weekly via GitHub Actions. Methodology in [docs/how-it-works.md](docs/how-it-works.md).

## Status

Bootstrapping. **Ranking populates after we have at least 7 days of snapshots.**

- Daily snapshot runs at 00:00 UTC (top ~3000 repos by total stars).
- Weekly ranking generates Monday 02:00 UTC by diffing today vs ~7 days ago.

Once the first weekly run produces a ranking, this README is auto-replaced with the actual table.

## What makes this different

| | Awesome-List-github-stars-ranking | github-weekly-trending |
|---|---|---|
| Metric | total stars | **weekly delta** |
| Surfaces | the same giants every week | **what got hot this week** |
| By language | yes | yes |
| **By project type** | no | **yes** (LLM/Agent, AI/ML, Web Framework, CLI, DevOps, Security, ...) |
| Update cadence | every 6h | daily snapshot, weekly ranking |
| Categorization method | n/a | rule-based topics + keywords (`data/categories.yaml`) |

## Project type categories

Defined in [`data/categories.yaml`](data/categories.yaml). Adding one is a YAML edit:

- LLM / Agent
- AI / ML
- Web Framework
- CLI / DevTool
- DevOps / Infra
- Database / Storage
- Security
- Data / Analytics
- Mobile
- Game / Graphics
- Learning Resource
- Other

## Run locally

```bash
git clone https://github.com/YunhaoDou/github-weekly-trending
cd github-weekly-trending
pip install -r requirements.txt

# Take a snapshot (use a token to avoid rate limits)
GITHUB_TOKEN=ghp_yourtoken python scripts/snapshot.py

# Generate the ranking from existing snapshots (needs ≥ 2)
python scripts/ranking.py
```

## License

[MIT](LICENSE)
