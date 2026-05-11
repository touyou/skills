#!/usr/bin/env python3
"""Tier 3: Flutter UI に露出するロジックの量を観測する。

定義詳細は references/dart-flutter.md の Tier 3 セクション参照。
"""

import argparse
import json
import os
import re
from pathlib import Path

EXCLUDE_DIRS = {".dart_tool", "build", ".pub-cache", ".symlinks", ".git",
                "ios", "android", "macos", "linux", "windows", "web", "test", "tests"}
GENERATED_SUFFIXES = (".g.dart", ".freezed.dart", ".intent.dart", ".chopper.dart", ".gr.dart",
                     ".gen.dart", ".config.dart", ".mocks.dart")


def parse_exclude_paths(repo, raw):
    if not raw:
        return []
    out = []
    for chunk in raw.split(","):
        s = chunk.strip()
        if s:
            out.append((repo / s).resolve())
    return out


def is_excluded(path, exclude_paths):
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

# routing declarations
GOROUTE_RE = re.compile(r"\bGoRoute\s*\(")
ROUTEBASE_RE = re.compile(r"\bRouteBase\s*\(")
AUTOROUTE_RE = re.compile(r"\bAutoRoute\s*\(")
# type-safe go_router: `@TypedGoRoute<RouteData>(path: ..., routes: [...])` — generated
# into actual `GoRoute(...)` inside .g.dart, which we exclude. Without this regex, projects
# using go_router_builder would report routes_count=0 despite having dozens of routes.
# 外側は `@TypedGoRoute<` だが nested は `TypedGoRoute<` (annotation の引数の中で
# constructor として呼ばれる) なので両方拾う。
TYPED_GOROUTE_RE = re.compile(r"\bTypedGoRoute\s*<")
# `routes:` map literal: count string keys inside the next {...}
ROUTES_MAP_BLOCK_RE = re.compile(r"routes\s*:\s*\{([^{}]*)\}", re.DOTALL)
ROUTE_KEY_RE = re.compile(r"['\"]([^'\"]+)['\"]\s*:")
# MaterialApp(home: ...) / CupertinoApp(home: ...) — the implicit "/" route.
# Excludes MaterialApp.router(...) which uses declarative routing handled by
# the GoRoute / RouteBase counters.
MATERIAL_APP_HOME_RE = re.compile(r"\b(?:MaterialApp|CupertinoApp)\s*\(")

# named-arg style callbacks: onPressed:, onTap:, onChanged:, ...
HANDLER_RE = re.compile(r"\bon[A-Z]\w*\s*:\s*[\(\[<\w]")
NAVIGATOR_CALL_RE = re.compile(r"\bNavigator\.(?:push(?:Named|Replacement|ReplacementNamed)?|pop|popUntil)\s*\(")

# state primitives
SETSTATE_RE = re.compile(r"\bsetState\s*\(")
USESTATE_RE = re.compile(r"\buseState\s*\(")
USEEFFECT_RE = re.compile(r"\buseEffect\s*\(")
VALUE_NOTIFIER_RE = re.compile(r"\bValueNotifier\s*<")
CHANGE_NOTIFIER_INHERIT_RE = re.compile(r"\bextends\s+ChangeNotifier\b|\bwith\s+ChangeNotifier\b")

# rough cyclomatic
BRANCH_TOKENS = re.compile(r"\b(if|else if|case|catch|for|while|do)\b|\?\s*[^:?]+\s*:|&&|\|\|")


def is_dart_source(name):
    return name.endswith(".dart") and not name.endswith(GENERATED_SUFFIXES)


def walk_dart(repo, exclude_paths=None):
    for base in (repo / "lib", repo / "packages"):
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            root_path = Path(root)
            if is_excluded(root_path, exclude_paths or []):
                dirs[:] = []
                continue
            for f in files:
                if is_dart_source(f):
                    full = root_path / f
                    if is_excluded(full, exclude_paths or []):
                        continue
                    yield full


def count_routes(repo, warnings, exclude_paths=None):
    """Sum of GoRoute(/RouteBase(/AutoRoute(/MaterialApp routes-map keys."""
    total = 0
    for path in walk_dart(repo, exclude_paths=exclude_paths):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        total += len(GOROUTE_RE.findall(content))
        total += len(ROUTEBASE_RE.findall(content))
        total += len(AUTOROUTE_RE.findall(content))
        total += len(TYPED_GOROUTE_RE.findall(content))
        # Each MaterialApp(...)/CupertinoApp(...) — that is the "/" route via
        # `home:`. MaterialApp.router(...) uses GoRoute and is captured above.
        total += len(MATERIAL_APP_HOME_RE.findall(content))
        for block in ROUTES_MAP_BLOCK_RE.findall(content):
            total += len(ROUTE_KEY_RE.findall(block))
    if total == 0:
        warnings.append("no routing declarations found (GoRoute/AutoRoute/MaterialApp routes); routes_count is 0")
    return total


def count_handlers_state_complexity(repo, exclude_paths=None):
    handlers = 0
    state = 0
    complexity = 0
    files_seen = 0
    for path in walk_dart(repo, exclude_paths=exclude_paths):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_seen += 1
        handlers += len(HANDLER_RE.findall(content))
        handlers += len(NAVIGATOR_CALL_RE.findall(content))
        state += len(SETSTATE_RE.findall(content))
        state += len(USESTATE_RE.findall(content))
        state += len(USEEFFECT_RE.findall(content))
        state += len(VALUE_NOTIFIER_RE.findall(content))
        state += len(CHANGE_NOTIFIER_INHERIT_RE.findall(content))
        complexity += len(BRANCH_TOKENS.findall(content))
    return handlers, state, complexity, files_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="tier3.json")
    ap.add_argument(
        "--exclude-source-paths", default="",
        help="repo 相対パスのカンマ区切り。指定した配下を Tier 3 集計から除外 (例: 'lib/gen,lib/api_definitions')",
    )
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / "pubspec.yaml").exists() and (repo / "app" / "pubspec.yaml").exists():
        repo = repo / "app"

    exclude_paths = parse_exclude_paths(repo, args.exclude_source_paths)
    warnings = []
    routes = count_routes(repo, warnings, exclude_paths=exclude_paths)
    handlers, state, complexity, files_seen = count_handlers_state_complexity(repo, exclude_paths=exclude_paths)

    if files_seen == 0:
        warnings.append("no .dart source files found under lib/ or packages/*/lib/; Tier 3 metrics may not be meaningful")

    result = {
        "tier3_ui_logic": {
            "routes_count": routes,
            "interactive_handlers_count": handlers,
            "state_hooks_count": state,
            "ui_complexity_sum": complexity,
        },
        "tier3_meta": {
            "framework": "flutter",
            "dart_files_scanned": files_seen,
            "scan_root": str(repo),
            "excluded_source_paths": [
                str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p)
                for p in exclude_paths
            ],
        },
        "warnings": warnings,
    }

    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier3_ui_logic"], indent=2))


if __name__ == "__main__":
    main()
