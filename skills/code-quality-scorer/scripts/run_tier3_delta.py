#!/usr/bin/env python3
"""Tier 3 delta: 2 ref 間で UI logic がどれだけ追加/削除されたかを別々に出す。

「機能整理（削除）= 不要機能を切る判断」「統合による隠蔽 = UX 改善」を読み取れるよう、
純増（net）ではなく added / removed を別々に保つ。

使い方:
    python run_tier3_delta.py --repo <path> --from <ref> --to <ref> --out tier3_delta.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


HANDLER_RE = re.compile(r"\bon[A-Z]\w*\s*=\s*[{\"]")
STATE_HOOK_RE = re.compile(r"\buse(State|Reducer)\s*\(")
BRANCH_TOKENS = re.compile(
    r"\b(if|else if|case|catch|for|while|do)\b|\?\s*[^:?]+\s*:|&&|\|\|"
)


def git(args, cwd):
    proc = subprocess.run(
        ["git"] + args, cwd=str(cwd),
        capture_output=True, text=True, check=False,
    )
    return proc.stdout, proc.stderr, proc.returncode


def collect_diff_lines(repo, from_ref, to_ref):
    """Returns (added_lines, removed_lines) for .tsx/.jsx files between refs."""
    out, err, rc = git(
        ["diff", "--unified=0", f"{from_ref}..{to_ref}", "--", "*.tsx", "*.jsx"],
        cwd=repo,
    )
    if rc != 0:
        raise SystemExit(f"git diff failed: {err}")
    added = []
    removed = []
    for line in out.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return "\n".join(added), "\n".join(removed)


def count_in_text(text):
    return {
        "handlers": len(HANDLER_RE.findall(text)),
        "hooks": len(STATE_HOOK_RE.findall(text)),
        "complexity": len(BRANCH_TOKENS.findall(text)),
    }


def is_route_path(path):
    """True if `path` looks like a routable page file in Next.js App or Pages Router.

    App Router: any `page.{tsx,ts,jsx,js}` file (typically nested under app/).
    Pages Router: files directly under `pages/` (or sub-dirs not under `api/`),
    excluding files prefixed with `_` (e.g. `_app.tsx`, `_document.tsx`).
    """
    name = Path(path).name
    if name in {"page.tsx", "page.ts", "page.jsx", "page.js"}:
        return True
    norm = f"/{path}"
    if "/pages/" in norm:
        if "/api/" in norm or name.startswith("_"):
            return False
        return path.endswith((".tsx", ".ts", ".jsx", ".js"))
    return False


def collect_route_changes(repo, from_ref, to_ref):
    """Detect added/removed Next.js routes (page.tsx etc.) and React Router <Route> declarations.

    For Next.js: page.{tsx,ts,jsx,js} file additions/deletions in app/ or pages/ (non-api).
    For React Router: scan added/removed <Route> in diff output.
    """
    out, err, rc = git(
        ["diff", "--name-status", f"{from_ref}..{to_ref}"],
        cwd=repo,
    )
    if rc != 0:
        raise SystemExit(f"git diff --name-status failed: {err}")
    added_routes = 0
    removed_routes = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        is_route_file = is_route_path(path)
        if is_route_file:
            if status == "A":
                added_routes += 1
            elif status == "D":
                removed_routes += 1

    # React Router: count <Route> token additions/removals from diff
    added_text, removed_text = collect_diff_lines(repo, from_ref, to_ref)
    rr_added = len(re.findall(r"<Route\b", added_text))
    rr_removed = len(re.findall(r"<Route\b", removed_text))

    return {
        "next_routes_added": added_routes,
        "next_routes_removed": removed_routes,
        "react_router_routes_added": rr_added,
        "react_router_routes_removed": rr_removed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--from", dest="from_ref", required=True)
    ap.add_argument("--to", dest="to_ref", required=True)
    ap.add_argument("--out", default="tier3_delta.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists() and not (repo.parent / ".git").exists():
        # try to find the git root
        out, err, rc = git(["rev-parse", "--show-toplevel"], cwd=repo)
        if rc != 0:
            print(f"error: not a git repository: {repo}", file=sys.stderr)
            sys.exit(1)
        repo = Path(out.strip())

    added_text, removed_text = collect_diff_lines(repo, args.from_ref, args.to_ref)
    added_counts = count_in_text(added_text)
    removed_counts = count_in_text(removed_text)
    routes = collect_route_changes(repo, args.from_ref, args.to_ref)

    routes_added_total = routes["next_routes_added"] + routes["react_router_routes_added"]
    routes_removed_total = routes["next_routes_removed"] + routes["react_router_routes_removed"]

    result = {
        "tier3_delta": {
            "from_ref": args.from_ref,
            "to_ref": args.to_ref,
            "routes_added": routes_added_total,
            "routes_removed": routes_removed_total,
            "handlers_added": added_counts["handlers"],
            "handlers_removed": removed_counts["handlers"],
            "hooks_added": added_counts["hooks"],
            "hooks_removed": removed_counts["hooks"],
            "complexity_added": added_counts["complexity"],
            "complexity_removed": removed_counts["complexity"],
        },
        "tier3_delta_meta": {
            "routes_breakdown": routes,
        },
    }

    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier3_delta"], indent=2))


if __name__ == "__main__":
    main()
