#!/usr/bin/env python3
"""Tier 3: SwiftUI UI に露出するロジックの量を観測する。

定義詳細は references/swift-ios.md の Tier 3 セクション参照。
"""

import argparse
import json
import os
import re
from pathlib import Path

EXCLUDE_DIRS = {".build", ".swiftpm", "DerivedData", "Pods", ".git", "Generated", "Tests"}

# routes
NAVIGATION_LINK_RE = re.compile(r"\bNavigationLink\s*[\(<{]")
NAV_DESTINATION_RE = re.compile(r"\.navigationDestination\s*\(")
TAB_RE = re.compile(r"\bTab\s*\(")
SHEET_RE = re.compile(r"\.sheet\s*\(")
FULLSCREEN_COVER_RE = re.compile(r"\.fullScreenCover\s*\(")
POPOVER_RE = re.compile(r"\.popover\s*\(")

# interactive handlers
BUTTON_RE = re.compile(r"\bButton\s*\(")
HANDLER_MOD_RE = re.compile(r"\.on[A-Z]\w*\s*[\({]")
GESTURE_RE = re.compile(r"\.gesture\s*\(")
SWIPE_ACTIONS_RE = re.compile(r"\.swipeActions\s*[\({]")
CONTEXT_MENU_RE = re.compile(r"\.contextMenu\s*\{")

# state
STATE_PROP_RE = re.compile(
    r"@(?:State(?:Object)?|ObservedObject|Binding|Environment(?:Object)?|Bindable|Query|AppStorage|SceneStorage)\b"
)

# rough cyclomatic — Swift adds `guard` and `??`
BRANCH_TOKENS = re.compile(r"\b(if|else if|case|catch|for|while|do|guard)\b|\?\?|&&|\|\|")


def is_swift_source(path):
    name = path.name
    if not name.endswith(".swift"):
        return False
    if name.endswith("Tests.swift") or "UITest" in str(path):
        return False
    parts = path.parts
    return not any(part in EXCLUDE_DIRS for part in parts)


def walk_swift(repo):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            if is_swift_source(p):
                yield p


def count_routes(repo, warnings):
    total = 0
    for path in walk_swift(repo):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        total += len(NAVIGATION_LINK_RE.findall(content))
        total += len(NAV_DESTINATION_RE.findall(content))
        total += len(TAB_RE.findall(content))
        total += len(SHEET_RE.findall(content))
        total += len(FULLSCREEN_COVER_RE.findall(content))
        total += len(POPOVER_RE.findall(content))
    if total == 0:
        warnings.append("no SwiftUI navigation/sheet/tab declarations found; routes_count is 0")
    return total


def count_handlers_state_complexity(repo):
    handlers = 0
    state = 0
    complexity = 0
    files_seen = 0
    for path in walk_swift(repo):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_seen += 1
        handlers += len(BUTTON_RE.findall(content))
        handlers += len(HANDLER_MOD_RE.findall(content))
        handlers += len(GESTURE_RE.findall(content))
        handlers += len(SWIPE_ACTIONS_RE.findall(content))
        handlers += len(CONTEXT_MENU_RE.findall(content))
        state += len(STATE_PROP_RE.findall(content))
        complexity += len(BRANCH_TOKENS.findall(content))
    return handlers, state, complexity, files_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="tier3.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    warnings = []
    routes = count_routes(repo, warnings)
    handlers, state, complexity, files_seen = count_handlers_state_complexity(repo)

    if files_seen == 0:
        warnings.append("no .swift source files found; Tier 3 metrics may not be meaningful")

    result = {
        "tier3_ui_logic": {
            "routes_count": routes,
            "interactive_handlers_count": handlers,
            "state_hooks_count": state,
            "ui_complexity_sum": complexity,
        },
        "tier3_meta": {
            "framework": "swiftui",
            "swift_files_scanned": files_seen,
            "scan_root": str(repo),
        },
        "warnings": warnings,
    }

    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier3_ui_logic"], indent=2))


if __name__ == "__main__":
    main()
