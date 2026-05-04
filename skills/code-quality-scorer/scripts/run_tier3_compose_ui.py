#!/usr/bin/env python3
"""Tier 3: Jetpack Compose UI に露出するロジックの量を観測する (v0.4 SKELETON).

⚠ ステータス: SKELETON. サンプルプロジェクトで dogfood していない。
   定義詳細は references/kotlin-android.md の Tier 3 セクション参照。
"""

import argparse
import json
import os
import re
from pathlib import Path

EXCLUDE_DIRS = {"build", ".gradle", ".idea", "Generated", "test", "androidTest", "tests"}
GENERATED_KT_SUFFIXES = (".g.kt",)

# routes
COMPOSABLE_RE = re.compile(r"\bcomposable\s*[\(<]")
DIALOG_RE = re.compile(r"\bdialog\s*\(")
BOTTOMSHEET_RE = re.compile(r"\bbottomSheet\s*\(")
FRAGMENT_RE = re.compile(r"\bfragment\s*\(")

# interactive handlers — Compose uses lambda parameter syntax
NAMED_HANDLER_RE = re.compile(
    r"\b(?:onClick|onLongClick|onValueChange|onCheckedChange|onChange|"
    r"onSubmit|onPress|onFocusChanged|onDismissRequest)\s*=\s*\{"
)
MODIFIER_INTERACTION_RE = re.compile(
    r"\bModifier\.(?:clickable|combinedClickable|toggleable|selectable|swipeable|draggable)\s*[\({]"
)

# state primitives
STATE_RE = re.compile(
    r"\b(?:remember(?:Saveable|CoroutineScope)?|mutableStateOf|"
    r"collectAsState(?:WithLifecycle)?|produceState|derivedStateOf)\s*[\({]"
)

# control flow — Kotlin adds when, Elvis (?:)
BRANCH_TOKENS = re.compile(r"\b(if|else if|when|case|catch|for|while|do)\b|\?:|&&|\|\|")


def is_kt_source(path):
    name = path.name
    if not name.endswith(".kt"):
        return False
    if name.endswith(GENERATED_KT_SUFFIXES):
        return False
    if name.endswith("Test.kt") or name.endswith("Tests.kt"):
        return False
    parts = path.parts
    return not any(p in EXCLUDE_DIRS for p in parts)


def walk_kt(repo):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            if is_kt_source(p):
                yield p


def count_routes(repo, warnings):
    total = 0
    for path in walk_kt(repo):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        total += len(COMPOSABLE_RE.findall(content))
        total += len(DIALOG_RE.findall(content))
        total += len(BOTTOMSHEET_RE.findall(content))
        total += len(FRAGMENT_RE.findall(content))
    if total == 0:
        warnings.append("no Compose composable()/dialog()/bottomSheet() declarations found; routes_count is 0")
    return total


def count_handlers_state_complexity(repo):
    handlers = 0
    state = 0
    complexity = 0
    files_seen = 0
    for path in walk_kt(repo):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_seen += 1
        handlers += len(NAMED_HANDLER_RE.findall(content))
        handlers += len(MODIFIER_INTERACTION_RE.findall(content))
        state += len(STATE_RE.findall(content))
        complexity += len(BRANCH_TOKENS.findall(content))
    return handlers, state, complexity, files_seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="tier3.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    warnings = ["[skeleton] Tier 3 for Compose has not been dogfooded; numbers may need calibration"]

    routes = count_routes(repo, warnings)
    handlers, state, complexity, files_seen = count_handlers_state_complexity(repo)

    if files_seen == 0:
        warnings.append("no .kt source files found; Tier 3 metrics may not be meaningful")

    result = {
        "tier3_ui_logic": {
            "routes_count": routes,
            "interactive_handlers_count": handlers,
            "state_hooks_count": state,
            "ui_complexity_sum": complexity,
        },
        "tier3_meta": {
            "framework": "jetpack-compose",
            "kt_files_scanned": files_seen,
            "scan_root": str(repo),
        },
        "warnings": warnings,
    }
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier3_ui_logic"], indent=2))


if __name__ == "__main__":
    main()
