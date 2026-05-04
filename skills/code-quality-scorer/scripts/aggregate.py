#!/usr/bin/env python3
"""Tier 1 メトリクス + Tier 2 観察を合成し、composite_score を計算する。

使い方:
    python aggregate.py --tier1 tier1.json [--tier2 tier2.json] \\
        --commit-sha SHA --commit-date ISO --profile typescript-web \\
        --skill-version 0.1 [--weights weights.json] --out score.json
"""

import argparse
import json
from pathlib import Path


DEFAULT_WEIGHTS = {
    "test_coverage": 15,
    "test_effectiveness": 15,
    "lint_density": 10,
    "dead_code": 5,
    "complexity": 10,
    "type_safety": 10,
    "security": 15,
    "cohesion": 5,
    "dry": 5,
    "bug_prone_patterns": 10,
}


def lerp(x, points):
    """Piecewise linear interpolation. points: list of (x, y) sorted by x."""
    if x is None:
        return None
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return None


def normalize_coverage(v):
    if v is None:
        return None
    return lerp(v * 100, [(0, 0), (50, 60), (70, 80), (80, 90), (90, 100), (100, 100)])


def normalize_lint_density(v):
    return lerp(v, [(0, 100), (1, 90), (5, 70), (10, 50), (30, 20), (50, 0), (1000, 0)])


def normalize_dead_code(count, kloc):
    if count is None or kloc is None or kloc == 0:
        return None
    density = count / (kloc / 1000)
    return lerp(density, [(0, 100), (0.5, 90), (2, 70), (5, 40), (10, 10), (20, 0), (1000, 0)])


def normalize_complexity(v):
    return lerp(v, [(1.0, 100), (3.0, 90), (5.0, 75), (8.0, 50), (12.0, 20), (20.0, 0), (1000, 0)])


def normalize_type_errors(v):
    return lerp(v, [(0, 100), (1, 70), (5, 40), (20, 10), (50, 0), (10000, 0)])


def normalize_security(vulns):
    if vulns is None:
        return None
    score = vulns.get("high", 0) * 10 + vulns.get("medium", 0) * 3 + vulns.get("low", 0)
    return lerp(score, [(0, 100), (3, 80), (10, 50), (30, 20), (100, 0), (10000, 0)])


def normalize_tier2(score_1_to_5):
    if score_1_to_5 is None:
        return None
    return (score_1_to_5 - 1) * 25  # 1->0, 2->25, 3->50, 4->75, 5->100


def compute_composite(tier1, tier2, kloc, weights):
    """Returns (composite, partial_composite, missing_keys)."""
    contributions = {
        "test_coverage": normalize_coverage(tier1.get("test_coverage_lines")),
        "lint_density": normalize_lint_density(tier1.get("lint_violations_per_kloc")),
        "dead_code": normalize_dead_code(tier1.get("dead_code_count"), kloc),
        "complexity": normalize_complexity(tier1.get("avg_cyclomatic_complexity")),
        "type_safety": normalize_type_errors(tier1.get("type_errors")),
        "security": normalize_security(tier1.get("security_vulnerabilities")),
        "cohesion": normalize_tier2((tier2.get("cohesion") or {}).get("score")),
        "dry": normalize_tier2((tier2.get("dry") or {}).get("score")),
        "bug_prone_patterns": normalize_tier2((tier2.get("bug_prone_patterns") or {}).get("score")),
        "test_effectiveness": normalize_tier2((tier2.get("test_effectiveness") or {}).get("score")),
    }

    available = {k: v for k, v in contributions.items() if v is not None}
    missing = [k for k, v in contributions.items() if v is None]

    full_total_weight = sum(weights[k] for k in contributions)
    available_weight = sum(weights[k] for k in available)

    composite = None
    if not missing:
        composite = round(sum(weights[k] * v for k, v in available.items()) / full_total_weight, 1)

    partial_composite = None
    if available_weight > 0:
        partial_composite = round(sum(weights[k] * v for k, v in available.items()) / available_weight, 1)

    return composite, partial_composite, missing, contributions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier1", required=True, help="tier1.json path")
    ap.add_argument("--tier2", help="tier2.json path (optional)")
    ap.add_argument("--tier3", help="tier3.json path (optional, observation only)")
    ap.add_argument("--commit-sha", required=True)
    ap.add_argument("--commit-date", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--skill-version", default="0.1")
    ap.add_argument("--weights", help="Custom weights JSON")
    ap.add_argument("--out", default="score.json")
    args = ap.parse_args()

    tier1_data = json.loads(Path(args.tier1).read_text())
    tier1 = tier1_data["tier1_metrics"]
    warnings = list(tier1_data.get("warnings", []))
    tooling = dict(tier1_data.get("tooling_used", {}))
    kloc = tier1_data.get("loc", 0)
    dep_snapshot = tier1_data.get("dep_snapshot")

    tier2 = {}
    if args.tier2 and Path(args.tier2).exists():
        tier2_data = json.loads(Path(args.tier2).read_text())
        tier2 = tier2_data.get("tier2_observations", {})
        warnings.extend(tier2_data.get("warnings", []))

    tier3 = {}
    tier3_meta = {}
    if args.tier3 and Path(args.tier3).exists():
        tier3_data = json.loads(Path(args.tier3).read_text())
        tier3 = tier3_data.get("tier3_ui_logic", {})
        tier3_meta = tier3_data.get("tier3_meta", {})
        warnings.extend(tier3_data.get("warnings", []))

    weights = DEFAULT_WEIGHTS.copy()
    if args.weights:
        weights.update(json.loads(Path(args.weights).read_text()))

    composite, partial, missing, contributions = compute_composite(tier1, tier2, kloc, weights)

    primary_score = composite if composite is not None else partial
    score = {
        "schema_version": "1",
        "skill_version": args.skill_version,
        "commit_sha": args.commit_sha,
        "commit_date": args.commit_date,
        "language_profile": args.profile,
        "tier1_metrics": tier1,
        "tier2_observations": tier2,
        "tier3_ui_logic": tier3,
        "tier3_meta": tier3_meta,
        "primary_score": primary_score,
        "primary_score_kind": "complete" if composite is not None else "partial",
        "composite_score": composite,
        "partial_composite_score": partial,
        "composite_status": "complete" if not missing else f"partial: missing {', '.join(missing)}",
        "normalized_contributions": {k: round(v, 1) if v is not None else None for k, v in contributions.items()},
        "weights_used": weights,
        "warnings": warnings,
        "tooling_used": tooling,
        "loc": kloc,
        "dep_snapshot": dep_snapshot,
    }

    Path(args.out).write_text(json.dumps(score, indent=2))
    print(f"wrote {args.out}")
    print(f"primary_score: {primary_score} ({'complete' if composite is not None else 'partial'})")
    print(f"composite_score: {composite}")
    print(f"partial_composite_score: {partial}")
    if missing:
        print(f"missing dimensions: {', '.join(missing)}")


if __name__ == "__main__":
    main()
