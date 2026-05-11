#!/usr/bin/env python3
"""Tier 2 LLM judgment via N=3 independent sub-agents.

Spawns the `claude` CLI as N independent processes per dimension, each receiving
the rubric markdown plus a SHA-seeded sample of source files. Each returns a
1-5 score + rationale; we take the median and report a confidence level based
on agreement between the N runs.

This addresses the v0.2 SKILL.md disclaimer: "1 turn → 3 judgments anchors on
the first one and isn't really independent." Spawning separate `claude -p`
processes IS independent — they don't share context.

Cost note: each `claude -p` call pays once for cache creation (~$0.28 with
opus 4.7 1M ctx) and subsequent calls within the 5-minute prompt-cache TTL
hit cache_read (much cheaper). 4 dimensions × 3 samples = 12 calls. Best
case (run all 12 within 5 min, single dim's prompt re-used across N=3):
~$0.50-$1.00. Worst case (gaps over 5 min, every call rebuilds cache):
~$1.50-$3.00. Pass `--judge-model haiku` to drop cost ~10x at the price of
weaker rubric application.

Monorepo note: pass `--repo` pointing at the directory containing the
language's manifest (pubspec.yaml for Flutter app/, Package.swift for SPM,
package.json for TS Web). For Flutter monorepos like flutter_intents/, that
means `--repo flutter_intents/app` not `--repo flutter_intents`.

Usage:
    python judge.py --repo PATH --rubrics-dir REFERENCES_DIR \\
        --profile typescript-web --commit-sha SHA \\
        [--samples 3] [--max-files 20] [--max-lines 4000] \\
        [--dimensions cohesion,dry,bug_prone_patterns,test_effectiveness] \\
        [--out tier2.json] [--judge-model sonnet|haiku]
"""

import argparse
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
from pathlib import Path

DIMENSION_RUBRIC_FILES = {
    "cohesion": "rubric-cohesion.md",
    "dry": "rubric-dry.md",
    "bug_prone_patterns": "rubric-bug-prone.md",
    "test_effectiveness": "rubric-test-effectiveness.md",
}

PROFILE_SAMPLE_RULES = {
    "typescript-web": {
        "include_dirs": ["src", "app", "lib"],
        "extensions": (".ts", ".tsx", ".js", ".jsx"),
        "exclude_suffixes": (".d.ts", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".gen.ts"),
        "exclude_dirs": {"node_modules", "dist", "build", ".next", ".turbo", "__generated__"},
    },
    "dart-flutter": {
        "include_dirs": ["lib", "packages"],
        "extensions": (".dart",),
        "exclude_suffixes": (".g.dart", ".freezed.dart", ".intent.dart", ".gr.dart", ".chopper.dart",
                            ".gen.dart", ".config.dart", ".mocks.dart"),
        "exclude_dirs": {".dart_tool", "build", "test", "tests", "ios", "android", "macos", "linux", "windows", "web"},
    },
    "swift-ios": {
        "include_dirs": ["Sources", "Packages", ""],  # "" = whole repo (Xcode projects without Sources/)
        "extensions": (".swift",),
        "exclude_suffixes": ("Tests.swift",),
        "exclude_dirs": {".build", ".swiftpm", "DerivedData", "Pods", "Generated", "Tests"},
    },
}

# test_effectiveness needs test files, not source files.
TEST_FILE_RULES = {
    "typescript-web": {
        "extensions": (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".test.js", ".spec.js"),
        "include_dirs": ["src", "app", "lib", "test", "tests", "__tests__"],
        "exclude_dirs": {"node_modules", "dist", "build", ".next"},
    },
    "dart-flutter": {
        "extensions": ("_test.dart",),
        "include_dirs": ["test", "tests", "integration_test"],
        "exclude_dirs": {".dart_tool", "build"},
    },
    "swift-ios": {
        "extensions": ("Tests.swift",),
        "include_dirs": ["Tests", "Packages"],  # SPM tests live under Packages/<X>/Tests
        "exclude_dirs": {".build", ".swiftpm", "DerivedData"},
    },
}


def collect_files(repo, rule, exclude_paths=None):
    """Walk repo gathering files that match `rule`. Returns list[(path, lines)].

    `exclude_paths` (resolved absolute Path のリスト) を渡すと、その配下のファイルを除外する。
    プロジェクト固有の generated location (例: lib/gen, lib/api_definitions) を Tier 2 から
    取り除くために使う。
    """
    exclude_paths = exclude_paths or []
    out = []
    seen = set()
    bases = [repo / d for d in rule["include_dirs"]] if rule["include_dirs"] != [""] else [repo]
    for base in bases:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in rule["exclude_dirs"] and not d.startswith(".")]
            root_path = Path(root)
            if _is_under_any(root_path, exclude_paths):
                dirs[:] = []
                continue
            for f in files:
                p = Path(root) / f
                if p in seen:
                    continue
                if not f.endswith(rule["extensions"]):
                    continue
                if any(f.endswith(suf) for suf in rule.get("exclude_suffixes", ())):
                    continue
                if _is_under_any(p, exclude_paths):
                    continue
                try:
                    with open(p, encoding="utf-8", errors="ignore") as fh:
                        lines = sum(1 for _ in fh)
                except OSError:
                    continue
                if lines == 0:
                    continue
                seen.add(p)
                out.append((p, lines))
    return out


def _is_under_any(path, exclude_paths):
    if not exclude_paths:
        return False
    try:
        rp = path.resolve()
    except OSError:
        rp = path
    for ex in exclude_paths:
        try:
            rp.relative_to(ex)
            return True
        except ValueError:
            continue
    return False


def deterministic_sample(files, seed_str, max_files, max_lines):
    """Reproducible weighted sample. Same SHA + same dimension -> same files."""
    if not files:
        return []
    seed_int = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed_int)
    # Sort by path for stable ordering before shuffle (RNG state is what varies).
    sorted_files = sorted(files, key=lambda x: str(x[0]))
    rng.shuffle(sorted_files)
    picked = []
    total_lines = 0
    for path, lines in sorted_files:
        if len(picked) >= max_files or total_lines >= max_lines:
            break
        picked.append((path, lines))
        total_lines += lines
    return picked


def build_prompt(rubric_text, sample_files, dimension, repo):
    """Compose the prompt for a single judge run.

    The CRITICAL contract is the closing instruction: a JSON object on the
    LAST line of the response. claude often prefaces with prose; we discard
    everything except the last JSON-shaped line in the parser.
    """
    parts = [
        f"You are evaluating the **{dimension}** of a codebase using the rubric below.",
        "",
        "Read the rubric carefully. Then read each sample file. Output your judgment "
        "as a single JSON object on the LAST line of your response. Do NOT wrap the "
        "JSON in code fences. Do NOT add prose after the JSON.",
        "",
        "## Required output schema",
        "```",
        '{"score": <int 1..5>, "confidence": "high|medium|low", "rationale": "<string ≤200 chars; cite specific file paths/signals>", "files_observed": <int>}',
        "```",
        "",
        "Apply the rubric's 'sample-insufficient default' rule: if you saw fewer than the rubric's threshold, default to 3 with confidence:low.",
        "",
        "## Rubric",
        rubric_text.strip(),
        "",
        f"## Sample files (rooted at {repo})",
    ]
    for path, _lines in sample_files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(repo) if repo in path.parents else path
        parts.append(f"\n### File: `{rel}`")
        parts.append("```")
        parts.append(content)
        parts.append("```")
    parts.append("\nNow output the JSON judgment as the last line.")
    return "\n".join(parts)


def call_claude(prompt, model=None, timeout=300):
    """Invoke `claude -p <prompt> --output-format json`. Returns the result string
    (the model's text reply) or None on failure.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if model:
        cmd.extend(["--model", model])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except FileNotFoundError:
        return None, "claude CLI not found"
    if proc.returncode != 0:
        return None, f"rc={proc.returncode}: {proc.stderr[:300]}"
    try:
        envelope = json.loads(proc.stdout)
        return envelope.get("result"), None
    except json.JSONDecodeError as e:
        return None, f"failed to parse claude envelope: {e}"


def parse_judgment(text):
    """Extract the JSON judgment from the model's response. Returns dict or None."""
    if not text:
        return None
    # Strategy: find all balanced JSON objects with "score" key, take the last
    # (which the prompt asks for). Walk char-by-char to handle nested quotes.
    candidates = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        in_str = False
        esc = False
        for j in range(i, n):
            c = text[j]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"' and not esc:
                in_str = not in_str
            elif not in_str:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        if '"score"' in candidate:
                            candidates.append(candidate)
                        break
    if not candidates:
        return None
    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
            if isinstance(obj.get("score"), int) and 1 <= obj["score"] <= 5:
                return obj
        except json.JSONDecodeError:
            continue
    return None


def aggregate_runs(runs):
    """Take N judge results -> return single tier2_observation dict.

    The aggregate `confidence` is computed from agreement between the N runs
    — NOT the same as each sub-agent's self-rated confidence (which is preserved
    inside `raw_runs[*].confidence` for audit).

    - all N scores equal -> high  (the spawn-N-judges design IS working: independent
      readers converge -> the rubric application is reliable)
    - some agreement (e.g. 2 of 3) -> medium  (rubric line drawn between two adjacent
      scores; either is defensible)
    - all N different -> low  (judges can't agree -> rubric application is shaky on
      this codebase, treat the median as a soft signal)
    """
    successful = [r for r in runs if r is not None]
    if not successful:
        return {
            "score": None, "confidence": "low",
            "rationale": "all judge runs failed; see raw_runs for errors",
            "files_sampled": 0, "raw_runs": runs, "n_successful": 0,
        }
    scores = [r["score"] for r in successful]
    median = int(statistics.median(scores))
    distinct = len(set(scores))
    if distinct == 1:
        confidence = "high"
    elif distinct < len(scores):
        confidence = "medium"
    else:
        confidence = "low"
    files_sampled = max((r.get("files_observed", 0) for r in successful), default=0)
    rationale = " | ".join(
        f"[run {i + 1} score={r['score']}] {r.get('rationale', '')[:120]}"
        for i, r in enumerate(successful)
    )[:600]
    return {
        "score": median,
        "confidence": confidence,
        "rationale": rationale,
        "files_sampled": files_sampled,
        "raw_runs": successful,
        "n_successful": len(successful),
        "n_attempted": len(runs),
        "score_distribution": dict(sorted({s: scores.count(s) for s in set(scores)}.items())),
    }


def judge_dimension(dimension, rubric_text, sample_files, repo, n, model, warnings):
    runs = []
    prompt = build_prompt(rubric_text, sample_files, dimension, repo)
    for i in range(n):
        result, err = call_claude(prompt, model=model)
        if err:
            warnings.append(f"{dimension} run {i + 1} failed: {err}")
            runs.append(None)
            continue
        parsed = parse_judgment(result)
        if parsed is None:
            warnings.append(f"{dimension} run {i + 1}: could not parse JSON from response (head: {(result or '')[:120]})")
            runs.append(None)
            continue
        runs.append(parsed)
    return aggregate_runs(runs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--rubrics-dir", default=str(Path(__file__).resolve().parent.parent / "references"))
    ap.add_argument("--profile", required=True, choices=list(PROFILE_SAMPLE_RULES.keys()))
    ap.add_argument("--commit-sha", required=True, help="Used to seed sampling for reproducibility")
    ap.add_argument("--samples", type=int, default=3, help="Independent judge runs per dimension (N)")
    ap.add_argument("--max-files", type=int, default=20)
    ap.add_argument("--max-lines", type=int, default=4000)
    ap.add_argument("--dimensions", default=",".join(DIMENSION_RUBRIC_FILES.keys()))
    ap.add_argument("--judge-model", default=None, help="Override model; e.g. sonnet/haiku")
    ap.add_argument("--out", default="tier2.json")
    ap.add_argument(
        "--exclude-source-paths", default="",
        help="repo 相対パスのカンマ区切り。指定した配下のファイルを Tier 2 サンプリング対象から除外 (例: 'lib/gen,lib/api_definitions')",
    )
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    rubrics_dir = Path(args.rubrics_dir).resolve()
    dimensions = [d.strip() for d in args.dimensions.split(",") if d.strip()]
    warnings = []
    exclude_paths = []
    for chunk in (args.exclude_source_paths or "").split(","):
        s = chunk.strip()
        if s:
            exclude_paths.append((repo / s).resolve())

    rule_src = PROFILE_SAMPLE_RULES[args.profile]
    rule_test = TEST_FILE_RULES.get(args.profile)
    src_files = collect_files(repo, rule_src, exclude_paths=exclude_paths)
    test_files = collect_files(repo, rule_test, exclude_paths=exclude_paths) if rule_test else []
    if not src_files:
        warnings.append(f"no source files matched profile rules for {args.profile}; Tier 2 likely meaningless")

    observations = {}
    for dim in dimensions:
        rubric_path = rubrics_dir / DIMENSION_RUBRIC_FILES.get(dim, f"rubric-{dim}.md")
        if not rubric_path.exists():
            warnings.append(f"rubric not found for dimension '{dim}' at {rubric_path}; skipping")
            continue
        rubric_text = rubric_path.read_text()

        # test_effectiveness needs test files, others need source files
        files_to_sample = test_files if dim == "test_effectiveness" else src_files
        if not files_to_sample:
            warnings.append(f"no files matched for dimension '{dim}'; emitting low-confidence default")
            observations[dim] = {
                "score": 3, "confidence": "low",
                "rationale": f"no {'test' if dim == 'test_effectiveness' else 'source'} files matched profile rules",
                "files_sampled": 0,
            }
            continue

        seed_str = f"{args.commit_sha}|{dim}"
        picked = deterministic_sample(files_to_sample, seed_str, args.max_files, args.max_lines)
        print(f"[{dim}] sampling {len(picked)} files (seeded by {args.commit_sha[:8]}|{dim})", file=sys.stderr)
        observations[dim] = judge_dimension(dim, rubric_text, picked, repo, args.samples, args.judge_model, warnings)
        observations[dim]["files_in_sample"] = [str(p.relative_to(repo)) for p, _ in picked]

    result = {
        "tier2_observations": observations,
        "warnings": warnings,
        "judge_meta": {
            "n_samples_per_dimension": args.samples,
            "max_files": args.max_files,
            "max_lines": args.max_lines,
            "judge_model": args.judge_model or "default (claude CLI)",
            "profile": args.profile,
            "commit_sha": args.commit_sha,
        },
    }
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    for dim, obs in observations.items():
        if obs.get("score") is None:
            print(f"  {dim}: FAILED ({obs.get('rationale', '')[:80]})")
        else:
            print(f"  {dim}: score={obs['score']} confidence={obs['confidence']} (n={obs.get('n_successful', 0)}/{obs.get('n_attempted', 0)}, dist={obs.get('score_distribution', {})})")


if __name__ == "__main__":
    main()
