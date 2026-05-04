#!/usr/bin/env python3
"""Swift / SwiftUI iOS プロジェクトに対する Tier 1 メトリクスを収集する。

ツールチェーン方針 (advisor 警告に従う):
- 「壊れない固いところ」: SwiftLint + Periphery + swift build / swift package
- xcodebuild 系 (coverage / 全体ビルド) は scheme/destination 依存で頻繁に壊れるので、
  デフォルトは null + warning。trend 安定性を優先する。

使い方:
    python run_tier1_swift_ios.py [--repo PATH] [--out tier1.json]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


EXCLUDE_DIRS = {".build", ".swiftpm", "DerivedData", "Pods", ".git", "Generated"}

# Apple frameworks shipped with the SDK — used to filter hallucinated_imports.
# Keep in sync with references/swift-ios.md appendix.
APPLE_FRAMEWORKS = {
    "Foundation", "Combine", "SwiftUI", "UIKit", "AppKit", "WatchKit", "WidgetKit",
    "SwiftData", "CoreData", "CloudKit",
    "Observation",
    "os", "Logging",
    "XCTest", "Testing",
    "Network", "URLSession",
    "CoreLocation", "MapKit",
    "AVFoundation", "AVKit", "Photos", "PhotosUI",
    "StoreKit",
    "HealthKit", "HomeKit",
    "ARKit", "RealityKit", "SceneKit", "SpriteKit",
    "Vision", "CoreML", "CreateML", "NaturalLanguage", "Speech", "Sound",
    "GameKit",
    "Intents", "AppIntents", "UserNotifications",
    "ActivityKit",
    "LocalAuthentication", "CryptoKit", "Security",
    "MetricKit",
    "Compression", "Accelerate", "Metal", "MetalKit",
    "QuickLook", "QuickLookThumbnailing",
    "DeveloperToolsSupport",
    # implicit imports
    "Swift", "_Concurrency",
}


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


def find_swift_files(repo, include_tests=False):
    repo = Path(repo)
    found = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in files:
            if not f.endswith(".swift"):
                continue
            if not include_tests and (f.endswith("Tests.swift") or "UITest" in str(root) or "/Tests/" in str(Path(root))):
                continue
            found.append(Path(root) / f)
    return found


def count_loc(repo):
    total = 0
    for path in find_swift_files(repo, include_tests=False):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return total


def find_spm_packages(repo):
    """Locate every Package.swift in the repo (root + Packages/* + ios-spm/* etc.)
    and parse out their `name:` declarations. Used as the monorepo allowlist for
    hallucinated_imports filtering and as the iteration set for swift build.
    """
    name_re = re.compile(r"name:\s*\"([^\"]+)\"")
    packages = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        if "Package.swift" in files:
            pkg_path = Path(root) / "Package.swift"
            try:
                content = pkg_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # First name: in the file is the package name. dependencies have name:
            # too but those are usually in target sections — we accept the first
            # match as the canonical package name.
            m = name_re.search(content)
            if m:
                packages.append({"path": pkg_path, "name": m.group(1)})
    return packages


def extract_external_spm_deps(packages):
    """Scan all Package.swift files for `.package(url: "...")` declarations.
    Returns the set of imported module names declared as targets within those
    external packages (best-effort: we only have the URL, so we extract the
    last URL segment as the canonical module name guess).

    A more accurate approach would be to call `swift package show-dependencies
    --format json`, but that requires `swift package resolve` first. We keep
    this pure-text for offline analysis and let `swift build` errors catch
    misses.
    """
    url_re = re.compile(r"\.package\(\s*url:\s*\"([^\"]+)\"")
    product_re = re.compile(r"\.product\(\s*name:\s*\"([^\"]+)\"")
    deps = set()
    for pkg in packages:
        try:
            content = pkg["path"].read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in url_re.finditer(content):
            url = m.group(1)
            base = url.rstrip("/").split("/")[-1].removesuffix(".git")
            # Heuristic: GitHub repo names often map directly to module names
            # (e.g. swift-collections -> Collections). We add both the raw repo
            # name and a CamelCased form.
            deps.add(base)
            parts = re.split(r"[-_]", base)
            if len(parts) > 1:
                deps.add("".join(p.capitalize() for p in parts))
            deps.add(base.replace("swift-", "").capitalize())
        for m in product_re.finditer(content):
            deps.add(m.group(1))
    return deps


def measure_lint_and_complexity(repo, kloc, warnings, tooling_used):
    """Single SwiftLint pass; returns (lint_density, complexity_avg, complexity_p95).

    We extract complexity from the same pass to avoid invoking SwiftLint twice
    (it can be slow on large monorepos like IntentTodo).
    """
    if shutil.which("swiftlint") is None:
        warnings.append("swiftlint not installed; install via `brew install swiftlint`")
        return None, None, None
    out, err, rc = run("swiftlint lint --reporter json --quiet", cwd=repo, timeout=900)
    # SwiftLint exits 2 when violations exist (warnings) and 3 with errors;
    # we consider it successful as long as we got JSON.
    if not out:
        warnings.append(f"swiftlint produced no output; rc={rc}")
        return None, None, None
    try:
        violations = json.loads(out)
    except json.JSONDecodeError as e:
        warnings.append(f"failed to parse swiftlint output: {e}")
        return None, None, None
    total = len(violations)
    tooling_used["lint"] = "swiftlint lint --reporter json"
    density = round(total / max(kloc / 1000, 0.1), 2) if kloc > 0 else None

    # complexity extraction: rule_id == cyclomatic_complexity, "currently complexity is N"
    cx_re = re.compile(r"currently complexity is (\d+)")
    scores = []
    for v in violations:
        if v.get("rule_id") == "cyclomatic_complexity":
            m = cx_re.search(v.get("reason", "") or "")
            if m:
                scores.append(int(m.group(1)))
    if scores:
        scores.sort()
        avg = round(sum(scores) / len(scores), 2)
        p95 = scores[max(0, int(len(scores) * 0.95) - 1)]
        tooling_used["complexity"] = "swiftlint cyclomatic_complexity rule"
        tooling_used["complexity_caveat"] = "SwiftLint reports only over-threshold functions; avg/p95 are over-threshold subset"
        return density, avg, p95
    warnings.append("no swiftlint cyclomatic_complexity violations; avg/p95 reflect only over-threshold subset (here: empty)")
    return density, None, None


def measure_dead_code(repo, warnings, tooling_used):
    if shutil.which("periphery") is None:
        warnings.append("periphery not installed; dead_code_count is null")
        return None
    out, err, rc = run("periphery scan --format json --skip-build --quiet", cwd=repo, timeout=900)
    if not out:
        warnings.append(f"periphery produced no output; rc={rc}; tail={(err or '').splitlines()[-2:]}")
        return None
    try:
        data = json.loads(out)
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict):
            count = sum(len(v) if isinstance(v, list) else 0 for v in data.values())
        else:
            count = 0
        tooling_used["dead_code"] = "periphery scan --format json --skip-build"
        return count
    except json.JSONDecodeError as e:
        warnings.append(f"failed to parse periphery output: {e}")
        return None


SWIFT_BUILD_ERROR_RE = re.compile(r"^.+?:\d+:\d+:\s*error:", re.MULTILINE)
NO_MODULE_RE = re.compile(r"no such module ['\"]([^'\"]+)['\"]")


def measure_swift_build(packages, repo, warnings, tooling_used):
    """Run swift build across each Package.swift; return (type_errors, hallucinated_set).

    swift build naturally returns non-zero when there are errors — which is
    the whole point of this measurement. Treat any exit code as informational
    and parse stdout/stderr.
    """
    if shutil.which("swift") is None:
        warnings.append("swift toolchain not on PATH; type_errors and hallucinated_imports are null")
        return None, None
    if not packages:
        warnings.append("no Package.swift found in repo; swift build skipped")
        return None, None
    error_count = 0
    missing_modules = set()
    for pkg in packages:
        out, err, rc = run("swift build 2>&1", cwd=pkg["path"].parent, timeout=900)
        combined = (out or "") + "\n" + (err or "")
        error_count += len(SWIFT_BUILD_ERROR_RE.findall(combined))
        for m in NO_MODULE_RE.finditer(combined):
            missing_modules.add(m.group(1))
    tooling_used["type_check"] = "swift build (errors)"
    return error_count, missing_modules


def classify_hallucinated(missing_modules, packages, external_deps, warnings, tooling_used):
    if missing_modules is None:
        return None
    monorepo_names = {pkg["name"] for pkg in packages}
    hallucinated = set()
    for mod in missing_modules:
        if mod in monorepo_names:
            continue
        if mod in APPLE_FRAMEWORKS:
            continue
        if mod in external_deps:
            continue
        hallucinated.add(mod)
    tooling_used["hallucinated_imports"] = "swift build + Package.swift cross-check + Apple framework allowlist + monorepo SPM filter"
    return len(hallucinated)


def measure_security(repo, warnings, tooling_used):
    if shutil.which("osv-scanner") is None:
        warnings.append("osv-scanner not installed (`brew install osv-scanner`); security_vulnerabilities is null")
        return None
    resolved_files = list(repo.rglob("Package.resolved"))
    resolved_files = [p for p in resolved_files if not any(x in p.parts for x in EXCLUDE_DIRS)]
    if not resolved_files:
        warnings.append("no Package.resolved found; run `swift package resolve` first; security null")
        return None
    counts = {"high": 0, "medium": 0, "low": 0}
    for resolved in resolved_files:
        out, err, rc = run(f"osv-scanner --lockfile=Package.resolved --json", cwd=resolved.parent, timeout=180)
        if not out:
            continue
        try:
            data = json.loads(out)
            for result in data.get("results", []):
                for pkg in result.get("packages", []):
                    for v in pkg.get("vulnerabilities", []):
                        sev_list = v.get("database_specific", {}).get("severity", "") or ""
                        sev_text = sev_list.lower() if isinstance(sev_list, str) else ""
                        if "critical" in sev_text or "high" in sev_text:
                            counts["high"] += 1
                        elif "moderate" in sev_text or "medium" in sev_text:
                            counts["medium"] += 1
                        else:
                            counts["low"] += 1
        except json.JSONDecodeError:
            continue
    tooling_used["security"] = "osv-scanner --lockfile=Package.resolved"
    return counts


def measure_duplication(repo, warnings, tooling_used):
    if shutil.which("npx") is None:
        warnings.append("npx not on PATH; jscpd unavailable for code_duplication_pct")
        return None
    cmd = (
        "npx --yes jscpd --silent --reporters json --output /tmp/jscpd-swift "
        "--pattern '**/*.swift' "
        "--ignore '**/.build/**,**/.swiftpm/**,**/DerivedData/**,**/Pods/**,**/Tests/**' "
        "."
    )
    out, err, rc = run(cmd, cwd=repo, timeout=600)
    candidates = [
        Path("/tmp/jscpd-swift/jscpd-report.json"),
        repo / "report" / "jscpd-report.json",
        repo / "jscpd-report.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                pct = json.loads(p.read_text()).get("statistics", {}).get("total", {}).get("percentage")
                tooling_used["duplication"] = "jscpd --pattern **/*.swift"
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
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="tier1.json")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    has_pkg = (repo / "Package.swift").exists()
    has_xcode = any(repo.glob("*.xcodeproj")) or any(repo.glob("*.xcworkspace"))
    has_monorepo_pkgs = (repo / "Packages").exists()
    if not (has_pkg or has_xcode or has_monorepo_pkgs):
        print(f"error: no Package.swift / *.xcodeproj / *.xcworkspace / Packages/ found at {repo}", file=sys.stderr)
        sys.exit(1)

    packages = find_spm_packages(repo)
    external_deps = extract_external_spm_deps(packages)
    warnings = []
    tooling_used = {
        "package_manager": "swiftpm",
        "spm_packages": [pkg["name"] for pkg in packages],
        "has_xcode": has_xcode,
    }

    kloc = count_loc(repo)
    lint_density, avg_cx, p95_cx = measure_lint_and_complexity(repo, kloc, warnings, tooling_used)
    dead_code = measure_dead_code(repo, warnings, tooling_used)
    type_errors, missing_modules = measure_swift_build(packages, repo, warnings, tooling_used)
    hallucinated = classify_hallucinated(missing_modules, packages, external_deps, warnings, tooling_used)
    security = measure_security(repo, warnings, tooling_used)
    duplication = measure_duplication(repo, warnings, tooling_used)

    warnings.append("xcodebuild coverage skipped; pass --xcode-scheme to enable (not yet implemented in v0.3)")
    warnings.append("cognitive_complexity unavailable (SwiftLint analyzer rule requires compiler args); value is null")
    warnings.append("cyclic_dependencies_count unavailable on Swift standard tooling; value is null")

    dep_snapshot = sorted(external_deps | {pkg["name"] for pkg in packages})

    result = {
        "tier1_metrics": {
            "test_coverage_lines": None,
            "test_coverage_branches": None,
            "lint_violations_per_kloc": lint_density,
            "dead_code_count": dead_code,
            "avg_cyclomatic_complexity": avg_cx,
            "p95_cyclomatic_complexity": p95_cx,
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
