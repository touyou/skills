#!/usr/bin/env python3
"""score_history.py が出した score-<sha>.json 群から trend レポートを生成する。

各 dimension について、時系列のスパークライン + 始点/終点/delta を markdown で出す。

使い方:
    python generate_trend.py --in-dir DIR [--out trend.md] [--repo PATH]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values, missing_char="·"):
    """Return an 8-block sparkline. None values become `missing_char`.

    All values equal -> middle block. Empty -> empty string.
    """
    nums = [v for v in values if v is not None]
    if not nums:
        return missing_char * len(values)
    if len(set(nums)) == 1:
        return "".join(SPARK_BLOCKS[3] if v is not None else missing_char for v in values)
    lo, hi = min(nums), max(nums)
    span = hi - lo
    chars = []
    for v in values:
        if v is None:
            chars.append(missing_char)
        else:
            idx = int((v - lo) / span * (len(SPARK_BLOCKS) - 1))
            chars.append(SPARK_BLOCKS[idx])
    return "".join(chars)


def fmt_value(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def fmt_delta(first, last):
    if first is None or last is None:
        return "—"
    delta = last - first
    if isinstance(delta, float):
        s = f"{delta:+.2f}"
    else:
        s = f"{delta:+d}"
    return s


def load_scores(in_dir):
    """Load all <sha>.json from in_dir, return list sorted by commit_date (oldest first)."""
    scores = []
    for p in in_dir.glob("*.json"):
        if p.name == "index.json":
            continue
        try:
            scores.append(json.loads(p.read_text()))
        except Exception:
            continue
    scores.sort(key=lambda s: s.get("commit_date", ""))
    return scores


TIER1_DIMS = [
    ("lint_violations_per_kloc", "lint density (per kloc)"),
    ("type_errors", "type errors"),
    ("code_duplication_pct", "code duplication %"),
    ("cyclic_dependencies_count", "cyclic dependencies"),
    ("hallucinated_imports_count", "hallucinated imports"),
    ("dead_code_count", "dead code count"),
    ("avg_cyclomatic_complexity", "avg cyclomatic complexity"),
    ("avg_cognitive_complexity", "avg cognitive complexity"),
    ("deprecated_api_count", "deprecated API uses"),
    ("outdated_dependencies_major", "outdated deps (major)"),
    ("test_coverage_lines", "test coverage (lines)"),
]


def get_tier1(score, key):
    if not score.get("tier1_metrics"):
        return None
    return score["tier1_metrics"].get(key)


def get_security_score(score):
    if not score.get("tier1_metrics"):
        return None
    sec = score["tier1_metrics"].get("security_vulnerabilities")
    if not sec:
        return None
    # Weighted: high*10 + medium*3 + low*1
    return sec.get("high", 0) * 10 + sec.get("medium", 0) * 3 + sec.get("low", 0)


TIER3_DIMS = [
    ("routes_count", "routes"),
    ("interactive_handlers_count", "interactive handlers"),
    ("state_hooks_count", "state hooks"),
    ("ui_complexity_sum", "UI complexity sum"),
]


def get_tier3(score, key):
    if not score.get("tier3_ui_logic"):
        return None
    return score["tier3_ui_logic"].get(key)


def render_table(scores, dims, getter, title):
    """Render a markdown table for a set of dimensions."""
    lines = [f"### {title}", "", "| Dimension | First | Last | Δ | Trend (oldest→newest) |", "|---|---|---|---|---|"]
    for key, label in dims:
        values = [getter(s, key) for s in scores]
        first_idx = next((i for i, v in enumerate(values) if v is not None), None)
        last_idx = next((i for i, v in enumerate(reversed(values)) if v is not None), None)
        first = values[first_idx] if first_idx is not None else None
        last = values[len(values) - 1 - last_idx] if last_idx is not None else None
        spark = sparkline(values)
        lines.append(f"| {label} | {fmt_value(first)} | {fmt_value(last)} | {fmt_delta(first, last)} | `{spark}` |")
    return "\n".join(lines)


def render_security(scores):
    lines = ["### Security vulnerabilities (high/medium/low)", "", "| Severity | First | Last | Δ | Trend |", "|---|---|---|---|---|"]
    for sev in ("high", "medium", "low"):
        values = []
        for s in scores:
            t1 = s.get("tier1_metrics") or {}
            sec = t1.get("security_vulnerabilities") or {}
            values.append(sec.get(sev) if sec else None)
        first_idx = next((i for i, v in enumerate(values) if v is not None), None)
        last_idx = next((i for i, v in enumerate(reversed(values)) if v is not None), None)
        first = values[first_idx] if first_idx is not None else None
        last = values[len(values) - 1 - last_idx] if last_idx is not None else None
        lines.append(f"| {sev} | {fmt_value(first)} | {fmt_value(last)} | {fmt_delta(first, last)} | `{sparkline(values)}` |")
    return "\n".join(lines)


def _advisory_set(score):
    """Return set of (package, severity) tuples from a score's advisories.
    Returns None if the score doesn't carry advisories (older runs)."""
    t1 = score.get("tier1_metrics") or {}
    advs = t1.get("security_advisories")
    if advs is None:
        return None
    return {(a.get("package"), a.get("severity")) for a in advs if a.get("package")}


def render_security_delta_classification(scores):
    """Classify security delta between first and last commit into:
    - "code-driven": new advisory whose package was NOT in baseline's deps
    - "newly-disclosed": new advisory whose package WAS already in baseline's deps
    - "resolved": advisory present in baseline but gone in head

    Requires both endpoints to carry security_advisories + dep_snapshot. Older
    score files (pre-v0.3) lack these — emit a note instead of failing.
    """
    if len(scores) < 2:
        return ""
    base, head = scores[0], scores[-1]
    base_set = _advisory_set(base)
    head_set = _advisory_set(head)
    if base_set is None or head_set is None:
        return (
            "### Security delta classification\n\n"
            "_Skipped: one of the endpoints predates v0.3 (no `security_advisories`). "
            "Re-run `score_history.py` to re-score those commits._\n"
        )
    appeared = head_set - base_set
    resolved = base_set - head_set
    base_deps = set(base.get("dep_snapshot") or [])
    code_driven = []
    newly_disclosed = []
    for pkg, sev in sorted(appeared):
        if pkg in base_deps:
            newly_disclosed.append((pkg, sev))
        else:
            code_driven.append((pkg, sev))

    def fmt_list(items, limit=10):
        if not items:
            return "(none)"
        head_items = ", ".join(f"`{p}` ({s})" for p, s in items[:limit])
        more = f" … +{len(items) - limit} more" if len(items) > limit else ""
        return head_items + more

    lines = [
        "### Security delta classification (head vs first commit)",
        "",
        f"- **Code-driven appearances**: {len(code_driven)} — package was not in baseline's direct deps. {fmt_list(code_driven)}",
        f"- **Newly-disclosed (ecosystem noise)**: {len(newly_disclosed)} — same package was already a dep, CVE was published since baseline. {fmt_list(newly_disclosed)}",
        f"- **Resolved**: {len(resolved)} — advisories present at baseline that are gone now. {fmt_list(sorted(resolved))}",
        "",
        "_Heuristic: 'code-driven' is approximated by package presence in the baseline's package.json deps. Transitive-only adds may misclassify; the goal is filtering out ecosystem CVE noise from the trend, not perfect attribution._",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="Directory containing score-<sha>.json files")
    ap.add_argument("--out", default="trend.md")
    ap.add_argument("--repo", help="Repository path (for resolving paths and metadata)")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.is_dir():
        print(f"error: {in_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    scores = load_scores(in_dir)
    if not scores:
        print(f"error: no score-*.json files found in {in_dir}", file=sys.stderr)
        sys.exit(1)

    first_date = scores[0].get("commit_date", "?")
    last_date = scores[-1].get("commit_date", "?")
    repo_label = args.repo or scores[0].get("language_profile", "unknown")

    out_lines = [
        f"# Code Quality Trend Report",
        "",
        f"**Project**: {repo_label}",
        f"**Period**: {first_date} → {last_date}",
        f"**Commits scored**: {len(scores)}",
        f"**Profile**: {scores[0].get('language_profile', '?')}",
        "",
        "## Tier 1 (deterministic code state)",
        "",
        render_table(scores, TIER1_DIMS, get_tier1, "Direct metrics"),
        "",
        render_security(scores),
        "",
        render_security_delta_classification(scores),
        "",
        "## Tier 3 (UI logic snapshot)",
        "",
        render_table(scores, TIER3_DIMS, get_tier3, "UI logic dimensions"),
        "",
        "## Reading guide",
        "",
        "- **Direction matters more than absolute values.** A drop in `lint density` from 6.7 → 5.8 is a stronger signal than the level itself.",
        "- **Tier 1 changes are deterministic** — same code → same score. Trends here are trustworthy.",
        "- **Tier 3 deltas track 'value delivered'** — handler/hook/complexity increases mean more UI logic shipped to users.",
        "- **Security delta can be noisy** — see the classification table; only the 'code-driven' bucket reflects code/dep choices, the 'newly-disclosed' bucket is ecosystem CVE publication noise.",
        "- **Sparklines use 8 levels** (`▁▂▃▄▅▆▇█`) normalized to the min-max range *within this period*. `·` indicates missing data.",
        "",
    ]

    out_path = Path(args.out)
    out_path.write_text("\n".join(out_lines))
    print(f"wrote {out_path}")
    print(f"  {len(scores)} commits, {first_date} → {last_date}")


if __name__ == "__main__":
    main()
