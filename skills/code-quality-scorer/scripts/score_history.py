#!/usr/bin/env python3
"""コミット履歴を辿って各コミットを採点する。

git worktree を使って各コミットを一時 checkout し、Tier 1 + Tier 3 (snapshot) を
収集する。本流のワーキングツリーは一切触らない。Tier 2 (LLM 判定) はコストが
高いので履歴 walk では実行しない（HEAD スコアリングのみ）。

使い方:
    python score_history.py --repo PATH --from REF --to REF \\
        [--strategy daily|merges-only|every-nth|all] \\
        [--every-nth N] [--out-dir DIR] [--profile typescript-web] \\
        [--skip-install]

戦略:
    daily        各日の最新コミット 1 つ（デフォルト）
    merges-only  マージコミットのみ
    every-nth    N コミットごと（--every-nth で N 指定、デフォルト 10）
    all          範囲内の全コミット（小規模範囲のみ推奨）

出力:
    <out-dir>/<sha>.json   各コミットのスコア
    <out-dir>/index.json   全コミットのインデックス + メタデータ

キャッシュ: <out-dir>/<sha>.json が同じ skill_version で既に存在すれば skip。
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_VERSION = "0.4"


PROFILE_CONFIG = {
    "typescript-web": {
        "tier1_script": "run_tier1_typescript_web.py",
        "tier3_script": "run_tier3_ui_logic.py",
        "install_timeout": 600,
        "tier1_timeout": 900,
    },
    "dart-flutter": {
        "tier1_script": "run_tier1_dart_flutter.py",
        "tier3_script": "run_tier3_flutter_ui.py",
        "install_timeout": 300,
        "tier1_timeout": 1200,  # flutter test --coverage can be slow
    },
    "swift-ios": {
        "tier1_script": "run_tier1_swift_ios.py",
        "tier3_script": "run_tier3_swift_ui.py",
        "install_timeout": 600,
        "tier1_timeout": 1500,  # swift build * N SPM packages
    },
    "kotlin-android": {
        # Skeleton — not dogfooded. See references/kotlin-android.md.
        "tier1_script": "run_tier1_kotlin_android.py",
        "tier3_script": "run_tier3_compose_ui.py",
        "install_timeout": 60,  # gradle wrapper download only
        "tier1_timeout": 1800,  # gradle is slow
    },
}


def git(args, cwd, check=False, timeout=120):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd),
        capture_output=True, text=True, timeout=timeout,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def select_commits(repo, from_ref, to_ref, strategy, every_nth):
    """Returns ordered list of (sha, date_iso) tuples (newest first)."""
    out = git(
        ["log", "--format=%H %cs", f"{from_ref}..{to_ref}"],
        cwd=repo, check=True,
    ).stdout
    all_commits = [tuple(line.split(" ", 1)) for line in out.splitlines() if line.strip()]
    if not all_commits:
        return []

    if strategy == "all":
        return all_commits

    if strategy == "daily":
        # Pick the newest commit for each calendar date.
        # all_commits is newest-first; for a given date, the first one we see is the newest.
        seen = set()
        picked = []
        for sha, date in all_commits:
            if date not in seen:
                seen.add(date)
                picked.append((sha, date))
        return picked

    if strategy == "merges-only":
        out2 = git(
            ["log", "--merges", "--format=%H %cs", f"{from_ref}..{to_ref}"],
            cwd=repo, check=True,
        ).stdout
        return [tuple(line.split(" ", 1)) for line in out2.splitlines() if line.strip()]

    if strategy == "every-nth":
        return [c for i, c in enumerate(all_commits) if i % every_nth == 0]

    raise SystemExit(f"unknown strategy: {strategy}")


def detect_install_cmd(worktree, profile):
    """Return (cmd_list, cwd) or (None, None). cwd lets us point Flutter monorepos
    at the right sub-directory (e.g. <repo>/app/) without changing the worktree."""
    if profile == "typescript-web":
        if (worktree / "pnpm-lock.yaml").exists():
            return ["pnpm", "install", "--frozen-lockfile", "--prefer-offline"], worktree
        if (worktree / "yarn.lock").exists():
            return ["yarn", "install", "--frozen-lockfile"], worktree
        if (worktree / "package-lock.json").exists():
            return ["npm", "ci"], worktree
        return None, None
    if profile == "dart-flutter":
        target = worktree if (worktree / "pubspec.yaml").exists() else (worktree / "app" if (worktree / "app" / "pubspec.yaml").exists() else None)
        if target is None:
            return None, None
        return ["flutter", "pub", "get"], target
    if profile == "swift-ios":
        # swift package resolve at every Package.swift root; for monorepos we run
        # the root one and let SPM walk path: deps. If only Xcode (no Package.swift),
        # there's nothing to resolve at this layer — Xcode handles it on build.
        if (worktree / "Package.swift").exists():
            return ["swift", "package", "resolve"], worktree
        # monorepo: try the root anyway, swift will discover packages via path: deps
        return None, None
    if profile == "kotlin-android":
        # Gradle handles dependency resolution lazily on the first task run; no
        # explicit "install" step. The wrapper download itself is fast.
        if (worktree / "gradlew").exists():
            return ["./gradlew", "--version"], worktree  # warms wrapper cache only
        return None, None
    return None, None


def run_helper(script_path, worktree, out_path, timeout):
    """Run a helper Python script, return parsed JSON output or (None, error)."""
    proc = subprocess.run(
        ["python3", str(script_path), "--repo", str(worktree), "--out", str(out_path)],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        return None, f"{script_path.name} failed (rc={proc.returncode}): {proc.stderr[-200:]}"
    if not out_path.exists():
        return None, f"{script_path.name} produced no output"
    try:
        return json.loads(out_path.read_text()), None
    except Exception as e:
        return None, f"{script_path.name} output unparseable: {e}"


def score_one_commit(repo, sha, date_iso, profile, out_dir, skip_install):
    cached = out_dir / f"{sha}.json"
    if cached.exists():
        try:
            data = json.loads(cached.read_text())
            if data.get("skill_version") == SKILL_VERSION:
                return data, "cached"
        except Exception:
            pass

    if profile not in PROFILE_CONFIG:
        return None, f"profile '{profile}' not supported (known: {sorted(PROFILE_CONFIG)})"
    pcfg = PROFILE_CONFIG[profile]

    # Create the worktree under /tmp to avoid touching the user's filesystem.
    wt_dir = Path(tempfile.mkdtemp(prefix=f"_scorer_wt_{sha[:8]}_"))
    # git worktree wants the target path to NOT exist; remove the empty mkdtemp dir.
    wt_dir.rmdir()
    git_result = git(["worktree", "add", str(wt_dir), sha], cwd=repo)
    if git_result.returncode != 0:
        return None, f"worktree add failed: {git_result.stderr.strip()}"

    warnings = []
    tier1_data = None
    tier3_data = None
    try:
        if not skip_install:
            install_cmd, install_cwd = detect_install_cmd(wt_dir, profile)
            if install_cmd:
                proc = subprocess.run(
                    install_cmd, cwd=str(install_cwd),
                    capture_output=True, text=True, timeout=pcfg["install_timeout"],
                )
                if proc.returncode != 0:
                    warnings.append(
                        f"install failed (cmd={install_cmd[0]}, rc={proc.returncode}); "
                        f"some tools may produce nulls"
                    )
            else:
                warnings.append(f"no install command configured for profile {profile}; skipping install")

        t1_path = Path(tempfile.mktemp(prefix=f"_scorer_t1_{sha[:8]}_", suffix=".json"))
        tier1_data, err = run_helper(
            SCRIPT_DIR / pcfg["tier1_script"],
            wt_dir, t1_path, timeout=pcfg["tier1_timeout"],
        )
        if err:
            warnings.append(err)

        t3_path = Path(tempfile.mktemp(prefix=f"_scorer_t3_{sha[:8]}_", suffix=".json"))
        tier3_data, err = run_helper(
            SCRIPT_DIR / pcfg["tier3_script"],
            wt_dir, t3_path, timeout=180,
        )
        if err:
            warnings.append(err)

        # Cleanup helper output files
        for p in (t1_path, t3_path):
            if p.exists():
                p.unlink()
    finally:
        # Always remove the worktree (this is safe even if `git worktree add` partially failed)
        git(["worktree", "remove", "--force", str(wt_dir)], cwd=repo)

    score = {
        "schema_version": "1",
        "skill_version": SKILL_VERSION,
        "commit_sha": sha,
        "commit_date": date_iso,
        "language_profile": profile,
        "tier1_metrics": tier1_data.get("tier1_metrics") if tier1_data else None,
        "tier1_tooling_used": tier1_data.get("tooling_used") if tier1_data else None,
        "tier1_warnings": tier1_data.get("warnings", []) if tier1_data else [],
        "tier3_ui_logic": tier3_data.get("tier3_ui_logic") if tier3_data else None,
        "tier3_meta": tier3_data.get("tier3_meta") if tier3_data else None,
        "loc": tier1_data.get("loc") if tier1_data else None,
        # Carry forward v0.3+ fields needed for security delta classification.
        "dep_snapshot": tier1_data.get("dep_snapshot") if tier1_data else None,
        "warnings": warnings,
    }
    cached.write_text(json.dumps(score, indent=2))
    return score, "scored"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Path to git repository")
    ap.add_argument("--from", dest="from_ref", help="Start ref (use with --to and --strategy)")
    ap.add_argument("--to", dest="to_ref", help="End ref (use with --from and --strategy)")
    ap.add_argument("--commits", help="Explicit comma-separated SHA list (overrides --from/--to)")
    ap.add_argument("--strategy", default="daily",
                    choices=["daily", "merges-only", "every-nth", "all"])
    ap.add_argument("--every-nth", type=int, default=10)
    ap.add_argument("--out-dir", default=".code-quality-scorer-cache")
    ap.add_argument("--profile", default="typescript-web")
    ap.add_argument("--skip-install", action="store_true",
                    help="Skip pnpm/yarn/npm install in each worktree (faster if deps unchanged)")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"error: {repo} is not a git repository", file=sys.stderr)
        sys.exit(1)

    out_dir = repo / args.out_dir
    out_dir.mkdir(exist_ok=True)

    if args.commits:
        # Explicit list: resolve each SHA to its date.
        shas = [s.strip() for s in args.commits.split(",") if s.strip()]
        commits = []
        for sha in shas:
            r = git(["log", "-1", "--format=%H %cs", sha], cwd=repo)
            if r.returncode == 0 and r.stdout.strip():
                commits.append(tuple(r.stdout.strip().split(" ", 1)))
            else:
                print(f"warning: skipping unresolvable ref {sha}", file=sys.stderr)
    else:
        if not args.from_ref or not args.to_ref:
            print("error: must provide --commits OR (--from and --to)", file=sys.stderr)
            sys.exit(1)
        commits = select_commits(repo, args.from_ref, args.to_ref, args.strategy, args.every_nth)

    if not commits:
        print("no commits found", file=sys.stderr)
        sys.exit(0)

    print(f"scoring {len(commits)} commits ({args.strategy} strategy)")
    print(f"out_dir: {out_dir}")
    index = {
        "skill_version": SKILL_VERSION,
        "from_ref": args.from_ref,
        "to_ref": args.to_ref,
        "strategy": args.strategy,
        "profile": args.profile,
        "commits": [],
    }
    for i, (sha, date) in enumerate(commits, 1):
        prefix = f"[{i}/{len(commits)}] {sha[:8]} ({date})"
        try:
            score, status = score_one_commit(
                repo, sha, date, args.profile, out_dir, args.skip_install,
            )
            if score is None:
                print(f"{prefix}  ERROR: {status}", flush=True)
                index["commits"].append({
                    "sha": sha, "date": date, "status": "error", "error": status,
                })
                continue
            print(
                f"{prefix}  {status}: warnings={len(score['warnings'])}, "
                f"tier1={'yes' if score['tier1_metrics'] else 'no'}, "
                f"tier3={'yes' if score['tier3_ui_logic'] else 'no'}",
                flush=True,
            )
            index["commits"].append({
                "sha": sha, "date": date, "status": status,
                "tier1_complete": score["tier1_metrics"] is not None,
                "tier3_complete": score["tier3_ui_logic"] is not None,
                "warnings_count": len(score["warnings"]),
            })
        except Exception as e:
            print(f"{prefix}  EXCEPTION: {e}", flush=True)
            index["commits"].append({"sha": sha, "date": date, "status": "exception", "error": str(e)})

    (out_dir / "index.json").write_text(json.dumps(index, indent=2))
    print(f"\nindex written: {out_dir}/index.json")


if __name__ == "__main__":
    main()
