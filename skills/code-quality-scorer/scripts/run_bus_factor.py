#!/usr/bin/env python3
"""Knowledge concentration / bus factor の指標を git 履歴から計算する。

「特定の人しか触っていないファイルがどれくらいあるか」「コミット範囲で知識が
分散したか集中したか」を見る。AI 活用効果の文脈では「touyouさんが AI 支援で
書いたコードが、AI なしの時代より少人数で（あるいは 1 人で）成立しているか」を
読み取る軸になる。

使い方:
    python run_bus_factor.py --repo PATH [--from REF] [--to REF] [--out bus_factor.json]

引数なしの場合: 全履歴を対象にした現在の bus factor 状態を出す。
--from --to がある場合: その範囲での delta を計算する。

指標:
- knowledge_concentration_index: 0-1。各ファイルの "primary author share" の
  加重平均。1 に近いほど「各ファイルに圧倒的なメイン著者がいる」（サイロ化）。
- single_author_files_ratio: 全コミットを1人だけが書いたファイルの割合。
- author_count: ユニーク著者数。
- knowledge_concentration_delta: --from --to 指定時、期間前後の index の差。
  正の値 = サイロ化が進んだ、負の値 = 知識が分散した。
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def git(args, cwd, check=False, timeout=300):
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd),
        capture_output=True, text=True, timeout=timeout,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr}")
    return result


SOURCE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".dart", ".swift", ".kt", ".kts")
# 生成物 suffix (言語横断)。`.d.ts`, `.g.dart` 系などを除外。
GENERATED_SUFFIXES = (
    ".d.ts",
    ".g.dart", ".freezed.dart", ".gr.dart", ".intent.dart", ".chopper.dart",
    ".gen.dart", ".config.dart", ".mocks.dart",
)


def list_tracked_source_files(repo, ref, extra_exclude_prefixes=None):
    """List tracked source files at ref, excluding tests/generated/build.

    multi-language 対応: .ts/.tsx/.js/.jsx/.dart/.swift/.kt/.kts。`extra_exclude_prefixes`
    で repo 相対の prefix を追加除外できる (例: ['lib/gen/', 'lib/api_definitions/'])。
    """
    extra_exclude_prefixes = tuple(extra_exclude_prefixes or [])
    out = git(["ls-tree", "-r", "--name-only", ref], cwd=repo, check=True).stdout
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        if not line.endswith(SOURCE_EXTENSIONS):
            continue
        if line.endswith(GENERATED_SUFFIXES):
            continue
        if any(seg in line for seg in (
            ".test.", ".spec.", "_test.dart",
            "/__tests__/", "/__generated__/", "/node_modules/",
            "/test/", "/tests/",
        )):
            continue
        if any(line.startswith(seg) for seg in (
            "dist/", "build/", ".next/", "node_modules/",
            "openapi/",  # auto-generated SDK
            ".dart_tool/", ".symlinks/",
        )):
            continue
        if extra_exclude_prefixes and line.startswith(extra_exclude_prefixes):
            continue
        files.append(line)
    return files


def file_author_counts(repo, path, ref, use_mailmap=True):
    """Returns dict of author -> commit count for `path` up to `ref`. Empty if file missing.

    use_mailmap: `.mailmap` を尊重する (`%aE` 大文字 = mapped email)。同一人物が複数 email で
    コミットしているケース (例: GitHub noreply + 個人 email + 会社 email) を 1 人として扱える。
    `.mailmap` が無い場合は通常の %ae と同じ動作なので安全に true がデフォルト。
    """
    fmt = "%aE" if use_mailmap else "%ae"
    cmd = ["log", "--follow"]
    if use_mailmap:
        cmd.append("--use-mailmap")
    cmd.extend([f"--format={fmt}", ref, "--", path])
    out = git(cmd, cwd=repo, timeout=60).stdout
    counts = defaultdict(int)
    for line in out.splitlines():
        a = line.strip()
        if a:
            counts[a] += 1
    return counts


def compute_state(repo, ref, exclude_prefixes=None, use_mailmap=True):
    """Compute knowledge_concentration_index, single_author_files_ratio,
    author_count for the codebase as of `ref`."""
    files = list_tracked_source_files(repo, ref, extra_exclude_prefixes=exclude_prefixes)
    if not files:
        return {
            "files_analyzed": 0,
            "knowledge_concentration_index": None,
            "single_author_files_ratio": None,
            "author_count": 0,
            "top_authors": [],
        }

    primary_shares = []
    single_author_count = 0
    all_author_commits = defaultdict(int)
    for path in files:
        counts = file_author_counts(repo, path, ref, use_mailmap=use_mailmap)
        if not counts:
            continue
        total = sum(counts.values())
        primary = max(counts.values()) / total
        primary_shares.append(primary)
        if len(counts) == 1:
            single_author_count += 1
        for a, c in counts.items():
            all_author_commits[a] += c

    if not primary_shares:
        return {
            "files_analyzed": 0,
            "knowledge_concentration_index": None,
            "single_author_files_ratio": None,
            "author_count": 0,
            "top_authors": [],
        }

    kci = sum(primary_shares) / len(primary_shares)
    safr = single_author_count / len(primary_shares)
    top = sorted(all_author_commits.items(), key=lambda kv: -kv[1])[:5]
    return {
        "files_analyzed": len(primary_shares),
        "knowledge_concentration_index": round(kci, 3),
        "single_author_files_ratio": round(safr, 3),
        "author_count": len(all_author_commits),
        "top_authors": [{"author": a, "commits": c} for a, c in top],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--from", dest="from_ref")
    ap.add_argument("--to", dest="to_ref", default="HEAD")
    ap.add_argument("--out", default="bus_factor.json")
    ap.add_argument(
        "--exclude-source-paths", default="",
        help="repo 相対パスの prefix をカンマ区切り。指定した配下を bus factor 計算から除外する (例: 'lib/gen,lib/api_definitions')",
    )
    ap.add_argument(
        "--no-mailmap", action="store_true",
        help="`.mailmap` による author email 正規化を無効化。デフォルト ON。`.mailmap` が無いリポジトリでは on/off いずれも同じ結果。",
    )
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"error: {repo} is not a git repository", file=sys.stderr)
        sys.exit(1)

    exclude_prefixes = []
    for chunk in (args.exclude_source_paths or "").split(","):
        s = chunk.strip()
        if not s:
            continue
        # 末尾 / を付けて prefix マッチに使う
        exclude_prefixes.append(s.rstrip("/") + "/")

    use_mailmap = not args.no_mailmap
    state_to = compute_state(repo, args.to_ref, exclude_prefixes=exclude_prefixes, use_mailmap=use_mailmap)
    result = {
        "to_ref": args.to_ref,
        "to_state": state_to,
    }

    if args.from_ref:
        state_from = compute_state(repo, args.from_ref, exclude_prefixes=exclude_prefixes, use_mailmap=use_mailmap)
        result["from_ref"] = args.from_ref
        result["from_state"] = state_from
        delta = None
        if (state_from["knowledge_concentration_index"] is not None
                and state_to["knowledge_concentration_index"] is not None):
            delta = round(
                state_to["knowledge_concentration_index"]
                - state_from["knowledge_concentration_index"],
                3,
            )
        result["knowledge_concentration_delta"] = delta
        result["interpretation"] = interpret_delta(delta)

    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result, indent=2))


def interpret_delta(delta):
    if delta is None:
        return "delta unavailable"
    if abs(delta) < 0.02:
        return "concentration unchanged within noise"
    if delta > 0:
        return f"concentration increased (+{delta}); knowledge silos grew"
    return f"concentration decreased ({delta}); knowledge spread"


if __name__ == "__main__":
    main()
