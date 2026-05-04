#!/usr/bin/env python3
"""Tier 3: UI に露出するロジックの量を観測する。

「届いた価値の量」のプロキシとして、コミット履歴の質に依存しない指標を計算する:
- routes_count: ルーティング上のページ数
- interactive_handlers_count: イベントハンドラ総数
- state_hooks_count: useState/useReducer 使用数
- ui_complexity_sum: .tsx ファイルの関数の cyclomatic complexity 総和（簡易）

これは観測軸であり、評価軸ではない（多い/少ないが直接良し悪しではない）。
"""

import argparse
import json
import os
import re
from pathlib import Path

EXCLUDE_DIRS = {
    "node_modules", "dist", "build", ".next", ".turbo",
    "coverage", "__generated__", ".cache", "out",
}

# Event handler attribute names like onClick=, onChange=, onSubmit=, etc.
HANDLER_RE = re.compile(r"\bon[A-Z]\w*\s*=\s*[{\"]")
# State hook calls
STATE_HOOK_RE = re.compile(r"\buse(State|Reducer)\s*\(")
# Cyclomatic-ish branch markers (rough; for v0.1 a regex is enough)
BRANCH_TOKENS = re.compile(
    r"\b(if|else if|case|catch|for|while|do)\b|\?\s*[^:?]+\s*:|&&|\|\|"
)


def walk_files(repo, exts):
    repo = Path(repo)
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(exts):
                yield Path(root) / f


def is_test_file(path):
    name = path.name
    return any(s in name for s in (".test.", ".spec."))


def count_routes_next_app_router(repo):
    """Count Next.js App Router pages: app/**/page.{ts,tsx,js,jsx}"""
    count = 0
    for d in ("app", "src/app"):
        base = Path(repo) / d
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for f in files:
                if f in {"page.tsx", "page.ts", "page.jsx", "page.js"}:
                    count += 1
    return count


def count_routes_pages_router(repo):
    """Count Next.js Pages Router: pages/*.{ts,tsx,js,jsx} excluding _app, _document, _error, api/**"""
    count = 0
    base = Path(repo) / "pages"
    if not base.exists():
        return 0
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        # skip api routes (server, not UI)
        if Path(root).relative_to(base).parts and Path(root).relative_to(base).parts[0] == "api":
            continue
        for f in files:
            if f.endswith((".tsx", ".jsx", ".ts", ".js")):
                stem = f.rsplit(".", 1)[0]
                if stem.startswith("_"):
                    continue
                count += 1
    return count


def count_routes_react_router(repo):
    """Count <Route> declarations across .tsx/.jsx files. Crude but gives an idea."""
    count = 0
    for path in walk_files(repo, (".tsx", ".jsx")):
        if is_test_file(path):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        count += len(re.findall(r"<Route\b", content))
    return count


def detect_routes_count(repo, warnings):
    """Try Next.js first (more deterministic), then React Router fallback."""
    nx_app = count_routes_next_app_router(repo)
    nx_pages = count_routes_pages_router(repo)
    if nx_app or nx_pages:
        return nx_app + nx_pages, "next"
    rr = count_routes_react_router(repo)
    if rr > 0:
        return rr, "react-router"
    warnings.append("no recognized routing pattern; routes_count is 0")
    return 0, "none"


def count_handlers_and_hooks_and_complexity(repo):
    handlers = 0
    state_hooks = 0
    complexity = 0
    files_seen = 0
    for path in walk_files(repo, (".tsx", ".jsx")):
        if is_test_file(path):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        files_seen += 1
        handlers += len(HANDLER_RE.findall(content))
        state_hooks += len(STATE_HOOK_RE.findall(content))
        # cyclomatic-ish: 1 baseline + branch tokens
        # we count branch tokens; each .tsx file's contribution is len(matches)
        complexity += len(BRANCH_TOKENS.findall(content))
    return handlers, state_hooks, complexity, files_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="tier3.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    warnings = []

    routes_count, routing_kind = detect_routes_count(repo, warnings)
    handlers, hooks, complexity, files_seen = count_handlers_and_hooks_and_complexity(repo)

    if files_seen == 0:
        warnings.append("no .tsx/.jsx files found; Tier 3 metrics may not be meaningful")

    result = {
        "tier3_ui_logic": {
            "routes_count": routes_count,
            "interactive_handlers_count": handlers,
            "state_hooks_count": hooks,
            "ui_complexity_sum": complexity,
        },
        "tier3_meta": {
            "routing_kind": routing_kind,
            "tsx_jsx_files_scanned": files_seen,
        },
        "warnings": warnings,
    }

    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier3_ui_logic"], indent=2))


if __name__ == "__main__":
    main()
