#!/usr/bin/env python3
"""Dart / Flutter プロジェクトに対する Tier 1 メトリクスを収集する。

使い方:
    python run_tier1_dart_flutter.py [--repo PATH] [--out tier1.json]

出力フォーマットは TS Web の tier1.json と互換。aggregate.py が同じスキーマを期待する。
不在ツールは null + warnings に記録（0埋めしない）。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


GENERATED_DART_SUFFIXES = (".g.dart", ".freezed.dart", ".intent.dart", ".chopper.dart", ".gr.dart")
EXCLUDE_DIRS = {".dart_tool", "build", ".pub-cache", ".symlinks", "ios", "android", "macos", "linux", "windows", "web"}


def run(cmd, cwd, timeout=600):
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), shell=isinstance(cmd, str),
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout}s", 124
    except FileNotFoundError as e:
        return "", str(e), 127


def parse_pubspec(repo):
    """Best-effort YAML extraction without pyyaml.

    We only need: name, dependencies (as a key set), dev_dependencies (key set),
    dependency_overrides (key set), and the names of any path: deps. This is
    parseable with a simple line scanner since Flutter pubspec.yaml files are
    consistently formatted (2-space indent, no exotic anchors).
    """
    p = repo / "pubspec.yaml"
    if not p.exists():
        return {}
    text = p.read_text()
    result = {"name": None, "dependencies": set(), "dev_dependencies": set(),
              "dependency_overrides": set(), "path_deps": set()}
    section = None
    pending_dep = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # top-level keys (no leading space)
        if not line.startswith(" "):
            stripped = line.split("#", 1)[0].rstrip()
            if stripped.startswith("name:"):
                result["name"] = stripped.split(":", 1)[1].strip().strip("'\"")
                section = None
                pending_dep = None
                continue
            if stripped.rstrip(":") in ("dependencies", "dev_dependencies", "dependency_overrides"):
                section = stripped.rstrip(":")
                pending_dep = None
                continue
            section = None
            pending_dep = None
            continue
        if section is None:
            continue
        # depth-based: 2-space indent -> dep name; 4-space -> dep config (e.g. path:)
        indent = len(line) - len(line.lstrip())
        content = line.strip().split("#", 1)[0].rstrip()
        if not content:
            continue
        if indent == 2:
            # Either `pkg:` or `pkg: ^1.0.0` form
            key_part = content.split(":", 1)[0].strip()
            if key_part:
                result[section].add(key_part)
                pending_dep = key_part
        elif indent >= 4 and pending_dep:
            if content.startswith("path:"):
                result["path_deps"].add(pending_dep)
    return result


def find_dart_files(repo):
    """Enumerate non-generated .dart source files (lib/ + monorepo packages/*/lib/)."""
    repo = Path(repo)
    candidates = []
    for base in (repo / "lib", repo / "packages"):
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            # under packages/, only descend into <pkg>/lib/
            rel = Path(root).relative_to(base)
            if base.name == "packages":
                parts = rel.parts
                if len(parts) >= 2 and parts[1] != "lib":
                    # We're inside a package's subdir that isn't lib/ — skip its contents.
                    if len(parts) > 1 and "lib" not in parts:
                        dirs[:] = []
                        continue
            for f in files:
                if f.endswith(".dart") and not f.endswith(GENERATED_DART_SUFFIXES):
                    if any(part in {"test", "tests"} for part in Path(root).parts):
                        continue
                    candidates.append(Path(root) / f)
    return candidates


def count_loc(repo):
    total = 0
    for path in find_dart_files(repo):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return total


def measure_coverage(repo, warnings, tooling_used):
    """Run flutter test --coverage and parse coverage/lcov.info ourselves.

    Branch coverage isn't emitted by Dart's coverage backend in practice, so
    branches stay None even on success.
    """
    if shutil.which("flutter") is None:
        warnings.append("flutter SDK not on PATH; coverage disabled")
        return None, None
    out, err, rc = run("flutter test --coverage", cwd=repo, timeout=900)
    lcov = repo / "coverage" / "lcov.info"
    if not lcov.exists():
        tail = (err or out).splitlines()[-3:]
        warnings.append(f"flutter test --coverage did not produce coverage/lcov.info; rc={rc}; {' | '.join(tail)[:200]}")
        return None, None
    lines_found = 0
    lines_hit = 0
    try:
        for raw in lcov.read_text(errors="ignore").splitlines():
            if raw.startswith("LF:"):
                lines_found += int(raw[3:])
            elif raw.startswith("LH:"):
                lines_hit += int(raw[3:])
    except (OSError, ValueError) as e:
        warnings.append(f"failed to parse lcov.info: {e}")
        return None, None
    if lines_found == 0:
        warnings.append("lcov.info has no LF records; coverage is null")
        return None, None
    tooling_used["coverage"] = "flutter test --coverage (lcov.info)"
    return round(lines_hit / lines_found, 4), None


def run_dart_analyze(repo, warnings):
    """Run `dart analyze --format=machine`. Returns the raw output text or None.

    `dart analyze` exits with rc=1 when issues exist (which is the normal case),
    so we treat 0 and 1 as success. rc>=2 is genuine failure.
    """
    if shutil.which("dart") is None and shutil.which("flutter") is None:
        warnings.append("neither `dart` nor `flutter` on PATH; analyze disabled")
        return None
    cmd = "dart analyze --format=machine" if shutil.which("dart") else "flutter analyze --format=machine"
    out, err, rc = run(cmd, cwd=repo, timeout=600)
    if rc not in (0, 1):
        warnings.append(f"`{cmd}` failed; rc={rc}; tail={(err or out).splitlines()[-3:]}")
        return None
    return out


# Format: SEVERITY|TYPE|CODE|FILE|LINE|COL|LENGTH|MESSAGE
ANALYZE_LINE_RE = re.compile(r"^(INFO|WARNING|ERROR)\|[^|]+\|([^|]+)\|([^|]+)\|")


def parse_analyze_lines(text):
    rows = []
    for line in (text or "").splitlines():
        m = ANALYZE_LINE_RE.match(line)
        if m:
            severity, code, file_path = m.group(1), m.group(2), m.group(3)
            rows.append((severity, code, file_path, line))
    return rows


def measure_lint(rows, kloc, warnings, tooling_used, has_analysis_options):
    if rows is None:
        return None
    if not has_analysis_options:
        warnings.append("analysis_options.yaml not found; lint counts use Dart default rules (may diverge from project intent)")
    total = len(rows)
    tooling_used["lint"] = "dart analyze --format=machine"
    return round(total / max(kloc / 1000, 0.1), 2) if kloc > 0 else None


DEAD_CODE_RULES = {"dead_code", "unused_element", "unused_field", "unused_local_variable",
                   "unused_import", "unused_label", "unused_shown_name", "unused_catch_clause",
                   "unused_catch_stack"}


def measure_dead_code(rows, warnings, tooling_used):
    if rows is None:
        return None
    count = sum(1 for r in rows if r[1] in DEAD_CODE_RULES)
    tooling_used["dead_code"] = "dart analyze (unused_*/dead_code rules)"
    return count


def measure_type_errors(rows, warnings, tooling_used):
    if rows is None:
        return None
    count = sum(1 for r in rows if r[0] == "ERROR")
    tooling_used["type_check"] = "dart analyze (severity=ERROR)"
    return count


def measure_hallucinated_imports(rows, pubspec_info, warnings, tooling_used):
    if rows is None:
        return None
    deps = pubspec_info.get("dependencies", set()) | pubspec_info.get("dev_dependencies", set()) | pubspec_info.get("dependency_overrides", set())
    self_name = pubspec_info.get("name")
    monorepo_packages = pubspec_info.get("path_deps", set())
    if self_name:
        monorepo_packages = monorepo_packages | {self_name}
    hallucinated = set()
    uri_re = re.compile(r"['\"]package:([^/'\"]+)/")
    for severity, code, file_path, full_line in rows:
        if code != "uri_does_not_exist":
            continue
        m = uri_re.search(full_line)
        if not m:
            continue
        pkg = m.group(1)
        if pkg in monorepo_packages or pkg in deps:
            continue
        hallucinated.add(pkg)
    tooling_used["hallucinated_imports"] = "dart analyze + pubspec cross-check + monorepo path-deps filter"
    return len(hallucinated)


def measure_security(repo, warnings, tooling_used):
    if shutil.which("dart") is None:
        warnings.append("dart SDK not on PATH; security audit disabled")
        return None
    out, err, rc = run("dart pub audit --json", cwd=repo, timeout=180)
    if not out:
        out, err, rc = run("dart pub audit", cwd=repo, timeout=180)
    if not out:
        warnings.append(f"dart pub audit produced no output; rc={rc}")
        return None
    counts = {"high": 0, "medium": 0, "low": 0}
    parsed_json = False
    try:
        data = json.loads(out)
        parsed_json = True
        for adv in data.get("advisories", []) or data.get("vulnerabilities", []) or []:
            sev = (adv.get("severity") or "").lower()
            if sev in ("critical", "high"):
                counts["high"] += 1
            elif sev in ("moderate", "medium"):
                counts["medium"] += 1
            elif sev == "low":
                counts["low"] += 1
    except json.JSONDecodeError:
        # Plain-text fallback: scan lines for severity tags. dart pub audit is young,
        # the format is still in flux; this gives at least directional signal.
        for line in out.splitlines():
            line_lower = line.lower()
            if "critical" in line_lower or " high " in line_lower:
                counts["high"] += 1
            elif "moderate" in line_lower or "medium" in line_lower:
                counts["medium"] += 1
            elif " low " in line_lower:
                counts["low"] += 1
    if counts == {"high": 0, "medium": 0, "low": 0} and not parsed_json:
        warnings.append("dart pub audit returned data but couldn't be parsed; security may be undercounted")
    tooling_used["security"] = "dart pub audit"
    return counts


def measure_duplication(repo, warnings, tooling_used):
    if shutil.which("npx") is None:
        warnings.append("npx not on PATH; jscpd unavailable for code_duplication_pct")
        return None
    target = "lib" if (repo / "lib").exists() else "."
    cmd = (
        "npx --yes jscpd --silent --reporters json --output /tmp/jscpd-flutter "
        "--pattern '**/*.dart' "
        "--ignore '**/.dart_tool/**,**/build/**,**/*.g.dart,**/*.freezed.dart,**/*.intent.dart,**/*.gr.dart' "
        f"{target}"
    )
    out, err, rc = run(cmd, cwd=repo, timeout=600)
    candidates = [
        Path("/tmp/jscpd-flutter/jscpd-report.json"),
        repo / "report" / "jscpd-report.json",
        repo / "jscpd-report.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                pct = json.loads(p.read_text()).get("statistics", {}).get("total", {}).get("percentage")
                tooling_used["duplication"] = f"jscpd --pattern **/*.dart ({target})"
                return pct
            except (OSError, json.JSONDecodeError) as e:
                warnings.append(f"failed to parse jscpd report: {e}")
                return None
    if rc == 127:
        warnings.append("jscpd not installed; code_duplication_pct is null")
    elif rc == 124:
        warnings.append("jscpd timed out; code_duplication_pct is null")
    else:
        warnings.append(f"jscpd ran but report not found; rc={rc}")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".", help="Repository path")
    ap.add_argument("--out", default="tier1.json", help="Output JSON path")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / "pubspec.yaml").exists():
        # Fall back to looking at app/ subdir for monorepos like flutter_intents
        if (repo / "app" / "pubspec.yaml").exists():
            repo = repo / "app"
            print(f"info: using monorepo target {repo}", file=sys.stderr)
        else:
            print(f"error: {repo}/pubspec.yaml not found (also tried {repo}/app/)", file=sys.stderr)
            sys.exit(1)

    pubspec_info = parse_pubspec(repo)
    has_analysis_options = (repo / "analysis_options.yaml").exists()
    warnings = []
    tooling_used = {
        "package_manager": "pub",
        "pubspec": "pubspec.yaml",
        "monorepo_self_name": pubspec_info.get("name"),
        "monorepo_path_deps": sorted(pubspec_info.get("path_deps", [])),
    }

    kloc = count_loc(repo)
    cov_lines, cov_branches = measure_coverage(repo, warnings, tooling_used)
    analyze_text = run_dart_analyze(repo, warnings)
    rows = parse_analyze_lines(analyze_text)
    lint_density = measure_lint(rows, kloc, warnings, tooling_used, has_analysis_options)
    dead_code = measure_dead_code(rows, warnings, tooling_used)
    type_errors = measure_type_errors(rows, warnings, tooling_used)
    hallucinated = measure_hallucinated_imports(rows, pubspec_info, warnings, tooling_used)
    security = measure_security(repo, warnings, tooling_used)
    duplication = measure_duplication(repo, warnings, tooling_used)

    # Cyclomatic / cognitive complexity: Dart standard tooling can't produce these.
    # Stay null — keeps trend analysis honest (educated guesses would lie).
    warnings.append("cyclomatic / cognitive complexity unavailable on Dart standard tooling; values are null")

    # Cyclic dependencies: no madge equivalent for Dart yet.
    warnings.append("cyclic_dependencies_count unavailable on Dart standard tooling; value is null")

    dep_snapshot = sorted(
        pubspec_info.get("dependencies", set())
        | pubspec_info.get("dev_dependencies", set())
        | pubspec_info.get("dependency_overrides", set())
    )

    result = {
        "tier1_metrics": {
            "test_coverage_lines": cov_lines,
            "test_coverage_branches": cov_branches,
            "lint_violations_per_kloc": lint_density,
            "dead_code_count": dead_code,
            "avg_cyclomatic_complexity": None,
            "p95_cyclomatic_complexity": None,
            "avg_cognitive_complexity": None,
            "p95_cognitive_complexity": None,
            "deprecated_api_count": None,
            "outdated_dependencies_major": None,
            "type_errors": type_errors,
            "security_vulnerabilities": security,
            "security_advisories": None,
            "code_duplication_pct": duplication,
            "cyclic_dependencies_count": None,
            "hallucinated_imports_count": hallucinated,
        },
        "dep_snapshot": dep_snapshot,
        "warnings": warnings,
        "tooling_used": tooling_used,
        "loc": kloc,
    }

    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier1_metrics"], indent=2))


if __name__ == "__main__":
    main()
