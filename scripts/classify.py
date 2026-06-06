"""Classify a repo into a project category by rule-based keyword + topic matching."""
from pathlib import Path
import re

import yaml

CATEGORIES_PATH = Path(__file__).resolve().parents[1] / "data" / "categories.yaml"


def load_categories() -> list[dict]:
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["categories"]


_CATEGORIES = load_categories()


def _normalize(text: str) -> str:
    return (text or "").lower()


def classify(repo: dict) -> str:
    """Return the best-matching category name for a repo dict.

    Expected repo fields: name, description, topics (list of strings).
    Strategy:
      - Tokenize name + description into words, hyphen-aware
      - For each category:
          score += 2 per topic hit (topics are more authoritative)
          score += 1 per keyword found anywhere
      - Highest score wins; ties broken by category order in YAML (earlier wins)
      - If no category scores > 0, return 'Other'
    """
    name = _normalize(repo.get("name", ""))
    desc = _normalize(repo.get("description", ""))
    topics = {_normalize(t) for t in repo.get("topics", []) if t}

    blob = f"{name} {desc} {' '.join(topics)}"
    # Extract tokens that may be hyphenated (react-native, machine-learning, etc.)
    tokens = set(re.findall(r"[a-z0-9][a-z0-9\-]*", blob))

    best_name = "Other"
    best_score = 0

    for cat in _CATEGORIES:
        score = 0
        for t in cat.get("topics", []):
            if t.lower() in topics:
                score += 2
        for kw in cat.get("keywords", []):
            kw_l = kw.lower()
            if kw_l in tokens or kw_l in blob:
                score += 1
        if score > best_score:
            best_score = score
            best_name = cat["name"]

    return best_name if best_score > 0 else "Other"


if __name__ == "__main__":
    # Quick self-test
    samples = [
        {"name": "langchain", "description": "Build LLM agents", "topics": ["llm", "agent"]},
        {"name": "react", "description": "UI library for the web", "topics": ["react", "frontend"]},
        {"name": "awesome-rust", "description": "A curated list of Rust resources", "topics": ["awesome-list", "rust"]},
        {"name": "kubectl", "description": "Kubernetes CLI", "topics": ["kubernetes", "cli"]},
        {"name": "mystery", "description": "what even is this", "topics": []},
    ]
    for s in samples:
        print(f"{s['name']:>20} -> {classify(s)}")
