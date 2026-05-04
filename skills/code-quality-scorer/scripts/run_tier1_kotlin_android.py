#!/usr/bin/env python3
"""Kotlin Android プロジェクトに対する Tier 1 メトリクス収集 (v0.4 SKELETON).

⚠ ステータス: SKELETON. サンプルプロジェクトで dogfood していない。
   実プロジェクトで動かす時に必ず動作確認すること。
   構造は run_tier1_dart_flutter.py / run_tier1_swift_ios.py と揃えている。

カバー範囲 (skeleton で実装):
- KLOC count
- Detekt (lint + complexity + dead_code を一発で)
- gradle wrapper の存在確認

カバー範囲外 (TODO, 実プロジェクトで dogfood しながら追加):
- JaCoCo coverage
- compileDebugKotlin による type_errors / hallucinated_imports / deprecated
- OWASP dependency-check / osv-scanner
- jscpd (.kt パターン)

詳細は references/kotlin-android.md を参照。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXCLUDE_DIRS = {"build", ".gradle", ".idea", "Generated"}
GENERATED_KT_SUFFIXES = (".g.kt",)


def run(cmd, cwd, timeout=900):
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


def find_kotlin_files(repo, include_tests=False):
    out = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            if not f.endswith(".kt"):
                continue
            if f.endswith(GENERATED_KT_SUFFIXES):
                continue
            if not include_tests and (f.endswith("Test.kt") or f.endswith("Tests.kt") or "/test/" in str(Path(root)).lower() or "/androidtest/" in str(Path(root)).lower()):
                continue
            out.append(Path(root) / f)
    return out


def count_loc(repo):
    total = 0
    for path in find_kotlin_files(repo, include_tests=False):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return total


def detect_modules(repo):
    """Read settings.gradle(.kts) for `include(":foo", ":bar:baz")` declarations.
    Returns set of module paths like "app", "core", "feature/auth".
    """
    modules = set()
    for name in ("settings.gradle.kts", "settings.gradle"):
        p = repo / name
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Match include(":a", ":b:c", ":d") possibly multiline.
        for m in re.finditer(r'include\s*\(([^)]*)\)', content, re.DOTALL):
            for q in re.findall(r'"([^"]+)"', m.group(1)):
                modules.add(q.lstrip(":").replace(":", "/"))
    return modules


def has_gradle_wrapper(repo):
    return (repo / "gradlew").exists() and os.access(repo / "gradlew", os.X_OK)


def measure_detekt(repo, kloc, warnings, tooling_used):
    """Run `./gradlew detekt`. Parse Checkstyle XML reports for violations,
    extract complexity from the CyclomaticComplexMethod messages, and identify
    dead-code rules.

    Returns dict with keys: lint_density, dead_code, avg_cx, p95_cx.
    """
    if not has_gradle_wrapper(repo):
        warnings.append("./gradlew not executable; detekt skipped")
        return {"lint_density": None, "dead_code": None, "avg_cx": None, "p95_cx": None}
    out, err, rc = run("./gradlew detekt --no-daemon --console=plain", cwd=repo, timeout=900)
    if rc not in (0, 1):  # detekt exits 1 when violations exist
        warnings.append(f"./gradlew detekt failed (rc={rc}); detekt-driven metrics are null. Tail: {(err or out).splitlines()[-3:]}")
        return {"lint_density": None, "dead_code": None, "avg_cx": None, "p95_cx": None}

    # Collect every detekt.xml under <module>/build/reports/detekt/
    reports = list(repo.rglob("build/reports/detekt/detekt.xml"))
    if not reports:
        warnings.append("detekt ran but no report XML found at <module>/build/reports/detekt/detekt.xml")
        return {"lint_density": None, "dead_code": None, "avg_cx": None, "p95_cx": None}

    total_violations = 0
    dead_code = 0
    cx_scores = []
    dead_code_rules = {"unused-import", "unused-private-class", "unused-private-member",
                       "unused-parameter", "UnusedImports", "UnusedPrivateMember"}
    cx_re = re.compile(r"complexity\D+(\d+)", re.IGNORECASE)
    for report in reports:
        try:
            root = ET.parse(report).getroot()
        except (ET.ParseError, OSError) as e:
            warnings.append(f"failed to parse {report}: {e}")
            continue
        for file_el in root.findall(".//file"):
            for err_el in file_el.findall("error"):
                total_violations += 1
                source = err_el.get("source") or ""
                msg = err_el.get("message") or ""
                # Dead-code style rules
                if any(rule in source for rule in dead_code_rules):
                    dead_code += 1
                # Complexity rule emits "Cyclomatic complexity: N" or similar
                if "CyclomaticComplexMethod" in source or "cyclomatic" in msg.lower():
                    m = cx_re.search(msg)
                    if m:
                        cx_scores.append(int(m.group(1)))

    tooling_used["lint"] = "detekt (gradle)"
    tooling_used["dead_code"] = "detekt unused-* rules"
    density = round(total_violations / max(kloc / 1000, 0.1), 2) if kloc > 0 else None

    if cx_scores:
        cx_scores.sort()
        avg = round(sum(cx_scores) / len(cx_scores), 2)
        p95 = cx_scores[max(0, int(len(cx_scores) * 0.95) - 1)]
        tooling_used["complexity"] = "detekt CyclomaticComplexMethod"
        tooling_used["complexity_caveat"] = "Detekt reports only over-threshold methods; avg/p95 are over-threshold subset"
        return {"lint_density": density, "dead_code": dead_code, "avg_cx": avg, "p95_cx": p95}
    return {"lint_density": density, "dead_code": dead_code, "avg_cx": None, "p95_cx": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="tier1.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    has_gradle_files = any((repo / n).exists() for n in
                           ("build.gradle.kts", "build.gradle", "settings.gradle.kts", "settings.gradle"))
    if not has_gradle_files:
        print(f"error: no build.gradle / settings.gradle found at {repo}", file=sys.stderr)
        sys.exit(1)

    warnings = []
    modules = detect_modules(repo)
    tooling_used = {
        "package_manager": "gradle",
        "build_system": "gradle",
        "modules": sorted(modules),
        "has_gradle_wrapper": has_gradle_wrapper(repo),
    }

    kloc = count_loc(repo)
    detekt_result = measure_detekt(repo, kloc, warnings, tooling_used)

    # Skeleton stubs — extend in dogfood phase.
    warnings.append("[skeleton] coverage not implemented; pass --enable-coverage in future to run jacocoTestReport")
    warnings.append("[skeleton] type_errors / hallucinated_imports require ./gradlew compileDebugKotlin parsing — not implemented")
    warnings.append("[skeleton] security / outdated / deprecated require additional Gradle plugins — not implemented")
    warnings.append("[skeleton] code_duplication via jscpd not yet wired in for Kotlin")

    result = {
        "tier1_metrics": {
            "test_coverage_lines": None,
            "test_coverage_branches": None,
            "lint_violations_per_kloc": detekt_result["lint_density"],
            "dead_code_count": detekt_result["dead_code"],
            "avg_cyclomatic_complexity": detekt_result["avg_cx"],
            "p95_cyclomatic_complexity": detekt_result["p95_cx"],
            "avg_cognitive_complexity": None,
            "p95_cognitive_complexity": None,
            "deprecated_api_count": None,
            "outdated_dependencies_major": None,
            "type_errors": None,
            "security_vulnerabilities": None,
            "security_advisories": None,
            "code_duplication_pct": None,
            "cyclic_dependencies_count": None,
            "hallucinated_imports_count": None,
        },
        "dep_snapshot": None,
        "warnings": warnings,
        "tooling_used": tooling_used,
        "loc": kloc,
    }
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"wrote {args.out}")
    print(json.dumps(result["tier1_metrics"], indent=2))


if __name__ == "__main__":
    main()
