#!/usr/bin/env python3
"""TypeScript Web プロジェクトに対する Tier 1 メトリクスを収集する。

使い方:
    python run_tier1_typescript_web.py [--repo PATH] [--out tier1.json]

出力: tier1_metrics + warnings + tooling_used を含む JSON。
不在ツールは null + warnings に記録（0埋めしない）。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd, timeout=300):
    """Return (stdout, stderr, returncode). Captures both."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout}s", 124
    except FileNotFoundError as e:
        return "", str(e), 127


def detect_package_manager(repo):
    if (repo / "pnpm-lock.yaml").exists():
        return "pnpm", "pnpm-lock.yaml"
    if (repo / "yarn.lock").exists():
        return "yarn", "yarn.lock"
    if (repo / "package-lock.json").exists():
        return "npm", "package-lock.json"
    return None, None


def read_package_json(repo):
    p = repo / "package.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def has_dep(pkg_json, name):
    deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
    return name in deps


def count_loc(repo):
    """Rough KLOC count: TS/TSX source lines, excluding generated/dist/node_modules."""
    excludes = ["node_modules", "dist", "build", ".next", ".turbo", "coverage", "__generated__"]
    total = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in excludes and not d.startswith(".")]
        for f in files:
            if f.endswith((".ts", ".tsx")) and not f.endswith((".d.ts",)):
                if any(p in f for p in (".test.", ".spec.")):
                    continue
                try:
                    with open(Path(root) / f, encoding="utf-8", errors="ignore") as fh:
                        total += sum(1 for _ in fh)
                except Exception:
                    pass
    return total


def measure_coverage(repo, pkg_json, npx, warnings, tooling_used):
    """Try to run coverage. Returns (lines, branches) as 0-1 floats or (None, None).

    Detects the coverage provider plugin (e.g. @vitest/coverage-v8) before
    running, and skips with a useful warning if the project hasn't installed
    one. Saves several minutes of runtime that would otherwise produce nothing.
    """
    scripts = pkg_json.get("scripts", {})
    test_script = " ".join(scripts.values())
    if has_dep(pkg_json, "vitest") or "vitest" in test_script:
        if not (has_dep(pkg_json, "@vitest/coverage-v8") or has_dep(pkg_json, "@vitest/coverage-istanbul")):
            warnings.append("vitest detected but no @vitest/coverage-* provider in deps; skipping coverage")
            return None, None
        cmd = f"{npx} vitest run --coverage --coverage.reporter=json-summary --coverage.reporter=text-summary"
        tool_label = "vitest --coverage"
    elif has_dep(pkg_json, "jest") or "jest" in test_script:
        cmd = f"{npx} jest --coverage --coverageReporters=json-summary"
        tool_label = "jest --coverage"
    elif has_dep(pkg_json, "nyc"):
        cmd = f"{npx} nyc --reporter=json-summary mocha"
        tool_label = "nyc + mocha"
    else:
        warnings.append("no test runner with coverage detected")
        return None, None

    out, err, rc = run(cmd, cwd=repo, timeout=900)
    summary = repo / "coverage" / "coverage-summary.json"
    if not summary.exists():
        warnings.append(f"coverage tool ran ({tool_label}) but coverage-summary.json not produced; rc={rc}")
        return None, None
    try:
        data = json.loads(summary.read_text())
        total = data.get("total", {})
        lines = total.get("lines", {}).get("pct")
        branches = total.get("branches", {}).get("pct")
        tooling_used["coverage"] = tool_label
        return (lines / 100 if lines is not None else None,
                branches / 100 if branches is not None else None)
    except Exception as e:
        warnings.append(f"failed to parse coverage-summary.json: {e}")
        return None, None


def measure_lint(repo, pkg_json, npx, kloc, warnings, tooling_used):
    """Returns (lint_density, eslint_json_cache).

    eslint_json_cache is the parsed eslint JSON output, reused later by
    measure_complexity to avoid running eslint twice (which can take minutes
    on real projects).
    """
    eslint_config = any((repo / name).exists() for name in
                        [".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs",
                         ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"])
    has_eslint_in_pkg = "eslintConfig" in pkg_json
    if eslint_config or has_eslint_in_pkg or has_dep(pkg_json, "eslint"):
        out, err, rc = run(f"{npx} eslint . --format json", cwd=repo, timeout=600)
        if not out:
            warnings.append(f"eslint ran but no output; rc={rc}")
            return None, None
        try:
            results = json.loads(out)
            total = sum(r.get("errorCount", 0) + r.get("warningCount", 0) for r in results)
            tooling_used["lint"] = "eslint ."
            density = round(total / max(kloc / 1000, 0.1), 2) if kloc > 0 else None
            return density, results
        except Exception as e:
            warnings.append(f"failed to parse eslint output: {e}")
            return None, None
    if has_dep(pkg_json, "@biomejs/biome"):
        out, err, rc = run(f"{npx} biome check --reporter=json .", cwd=repo, timeout=300)
        try:
            data = json.loads(out)
            count = len(data.get("diagnostics", []))
            tooling_used["lint"] = "biome check"
            density = round(count / max(kloc / 1000, 0.1), 2) if kloc > 0 else None
            return density, None
        except Exception as e:
            warnings.append(f"failed to parse biome output: {e}")
            return None, None
    warnings.append("no lint config detected; skipping lint")
    return None, None


def measure_dead_code(repo, pkg_json, npx, warnings, tooling_used):
    if has_dep(pkg_json, "knip"):
        out, err, rc = run(f"{npx} knip --reporter=json", cwd=repo, timeout=300)
        try:
            data = json.loads(out)
            count = (
                len(data.get("files", []))
                + sum(len(f.get("exports", [])) for f in data.get("issues", []))
                + sum(len(f.get("types", [])) for f in data.get("issues", []))
            )
            tooling_used["dead_code"] = "knip"
            return count
        except Exception as e:
            warnings.append(f"failed to parse knip output: {e}")
            return None
    if has_dep(pkg_json, "ts-prune"):
        out, err, rc = run(f"{npx} ts-prune", cwd=repo, timeout=300)
        if rc in (0, 1):
            lines = [l for l in out.splitlines() if l.strip() and "(used in module)" not in l]
            tooling_used["dead_code"] = "ts-prune"
            return len(lines)
    warnings.append("knip/ts-prune not installed; dead_code_count is null")
    return None


def measure_type_errors(repo, pkg_json, npx, warnings, tooling_used):
    if not (repo / "tsconfig.json").exists():
        warnings.append("tsconfig.json not found")
        return None
    out, err, rc = run(f"{npx} tsc --noEmit --pretty false", cwd=repo, timeout=300)
    combined = out + err
    count = sum(1 for line in combined.splitlines() if " error TS" in line)
    tooling_used["type_check"] = "tsc --noEmit"
    return count


def _bucket_severity(sev):
    """Map npm/pnpm severity strings to {high,medium,low}. Returns None if unknown."""
    if sev in ("critical", "high"):
        return "high"
    if sev == "moderate":
        return "medium"
    if sev == "low":
        return "low"
    return None


def measure_security(repo, pm, warnings, tooling_used):
    """Run audit. Returns (counts_dict, advisories_list) or (None, None) on failure.

    advisories_list is per-vulnerable-package: [{package, severity, range}]. Saving
    these enables generate_trend.py to classify a security delta as either
    "newly-disclosed CVE on a pre-existing dependency" (ecosystem noise) or
    "vulnerability appeared with a newly-added package" (code-originated).
    """
    if pm is None:
        warnings.append("no lockfile detected; skipping security audit")
        return None, None
    cmd = {"npm": "npm audit --json", "pnpm": "pnpm audit --json", "yarn": "yarn npm audit --json"}.get(pm)
    if not cmd:
        return None, None
    out, err, rc = run(cmd, cwd=repo, timeout=300)
    if not out:
        warnings.append(f"{pm} audit produced no output; rc={rc}")
        return None, None
    try:
        data = json.loads(out.split("\n")[0] if pm == "yarn" else out)
        vulns = data.get("metadata", {}).get("vulnerabilities", {})
        counts = {
            "high": vulns.get("high", 0) + vulns.get("critical", 0),
            "medium": vulns.get("moderate", 0),
            "low": vulns.get("low", 0),
        }
        advisories = []
        per_pkg = data.get("vulnerabilities", {})
        if isinstance(per_pkg, dict):
            # npm 7+/pnpm: dict keyed by package name.
            for pkg_name, info in per_pkg.items():
                if not isinstance(info, dict):
                    continue
                bucket = _bucket_severity(info.get("severity"))
                if bucket is None:
                    continue
                advisories.append({
                    "package": pkg_name,
                    "severity": bucket,
                    "range": info.get("range"),
                })
        elif isinstance(per_pkg, list):
            # Legacy/alternative shape (some yarn versions).
            for v in per_pkg:
                bucket = _bucket_severity(v.get("severity"))
                if bucket is None:
                    continue
                advisories.append({
                    "package": v.get("module_name") or v.get("name"),
                    "severity": bucket,
                    "range": v.get("vulnerable_versions"),
                })
        tooling_used["security"] = f"{pm} audit"
        return counts, advisories
    except Exception as e:
        warnings.append(f"failed to parse {pm} audit: {e}")
        return None, None


def collect_dep_snapshot(pkg_json):
    """Capture top-level deps from package.json. Used by generate_trend.py to
    classify whether a new advisory landed on a pre-existing dependency
    (likely ecosystem noise) or alongside a newly-added package (code change).

    We only save names (not versions) to keep the comparison stable across
    range updates that don't change the dep set.
    """
    deps = set()
    for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps.update(pkg_json.get(k, {}).keys())
    return sorted(deps)


def measure_duplication(repo, npx, warnings, tooling_used):
    """Run jscpd if available. Returns duplication % as float (0-100) or None.

    Limited to typical source dirs to avoid scanning node_modules / build outputs.
    Larger projects may still time out at 600s; that's a documented limitation.
    """
    src_dirs = [d for d in ("src", "app", "lib", "components", "pages", "hooks", "store", "stores", "contexts") if (repo / d).exists()]
    targets = " ".join(src_dirs) if src_dirs else "."
    out, err, rc = run(
        f"{npx} jscpd --silent --reporters json --output /tmp/jscpd-report --pattern '**/*.{{ts,tsx}}' {targets}",
        cwd=repo, timeout=600,
    )
    report_path = repo / "report" / "jscpd-report.json"
    fallback_path = Path("/tmp/jscpd-report/jscpd-report.json")
    candidates = [report_path, fallback_path, repo / "jscpd-report.json"]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                pct = data.get("statistics", {}).get("total", {}).get("percentage")
                tooling_used["duplication"] = f"jscpd ({targets})"
                return pct
            except Exception as e:
                warnings.append(f"failed to parse jscpd report: {e}")
                return None
    if rc == 127:
        warnings.append("jscpd not installed; code_duplication_pct is null")
    elif rc == 124:
        warnings.append("jscpd timed out (>600s) on this project; code_duplication_pct is null. Consider running jscpd manually with narrower scope.")
    else:
        warnings.append(f"jscpd ran but report not found; rc={rc}")
    return None


def measure_cyclic_deps(repo, npx, warnings, tooling_used):
    """Run madge --circular --json. Returns count or None."""
    src_dirs = [d for d in ("src", "app", "lib", "components", "pages") if (repo / d).exists()]
    if not src_dirs:
        warnings.append("no source directory found for cyclic deps check")
        return None
    target = src_dirs[0]
    out, err, rc = run(
        f"{npx} madge --circular --extensions ts,tsx --json {target}",
        cwd=repo, timeout=300,
    )
    if rc == 127 or "command not found" in err.lower():
        warnings.append("madge not installed; cyclic_dependencies_count is null")
        return None
    try:
        cycles = json.loads(out) if out.strip() else []
        tooling_used["cyclic_deps"] = f"madge --circular {target}"
        return len(cycles)
    except Exception as e:
        warnings.append(f"failed to parse madge output: {e}")
        return None


def load_tsconfig_path_aliases(repo):
    """Read tsconfig.json's compilerOptions.paths. Returns list of alias prefixes.

    For `"@/*": ["./*"]`, the alias prefix is `@/` (matches any import starting
    with `@/`). For `"~components": ["./components"]` (no glob), the prefix is
    the literal alias.

    tsconfig.json sometimes contains // and /* */ comments, which standard JSON
    rejects. Try strict parse first; if that fails, strip comments carefully.
    The naive `/* */` strip MUST avoid eating path globs like `"@/*"` — restrict
    block-comment matches to start with `/*` followed by whitespace or newline,
    which paths like `@/*` don't match.
    """
    tsconfig = repo / "tsconfig.json"
    if not tsconfig.exists():
        return []
    raw = tsconfig.read_text()
    data = None
    try:
        data = json.loads(raw)
    except Exception:
        # Strict parse failed; try comment-tolerant pass.
        import re
        # Strip `//` line comments (but not URLs in strings, hopefully rare).
        cleaned = re.sub(r"(^|[^:\"])//[^\n]*", r"\1", raw)
        # Strip `/* */` block comments only when `/*` is followed by whitespace
        # or `*` (e.g. `/**`). This excludes path globs like `@/*` and `*/foo`.
        cleaned = re.sub(r"/\*[\s*][\s\S]*?\*/", "", cleaned)
        # Strip trailing commas before `}` or `]`.
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        try:
            data = json.loads(cleaned)
        except Exception:
            return []
    paths = data.get("compilerOptions", {}).get("paths", {}) or {}
    aliases = []
    for k in paths.keys():
        if "*" in k:
            aliases.append(k.replace("*", ""))
        else:
            aliases.append(k)
    return aliases


def measure_hallucinated_imports(repo, npx, pkg_json, warnings, tooling_used):
    """Count tsc 'Cannot find module' errors that reference imports which:
    - Are not relative (./ or ../ or absolute /),
    - Do NOT match a tsconfig path alias prefix,
    - Are NOT a Node.js builtin,
    - Are NOT in package.json deps.

    These are likely AI-hallucinated packages or stale imports to packages
    that no longer exist. Path-alias false positives (the most common cause
    of false hallucinations on Next.js projects) are explicitly filtered out
    by reading tsconfig paths.
    """
    if not (repo / "tsconfig.json").exists():
        return None
    out, err, rc = run(f"{npx} tsc --noEmit --pretty false", cwd=repo, timeout=600)
    combined = out + err
    deps = set()
    for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps.update(pkg_json.get(k, {}).keys())
    path_aliases = load_tsconfig_path_aliases(repo)

    BUILTINS = {
        "fs", "path", "os", "crypto", "http", "https", "stream", "util", "url",
        "child_process", "zlib", "events", "buffer", "querystring", "net", "dns",
        "tls", "process", "string_decoder", "assert", "constants", "module",
        "punycode", "readline", "repl", "tty", "vm", "v8", "worker_threads",
        "perf_hooks", "async_hooks", "cluster", "dgram", "domain", "inspector",
    }

    import re
    pattern = re.compile(r"Cannot find module ['\"]([^'\"]+)['\"]")
    hallucinated = set()
    for m in pattern.finditer(combined):
        mod = m.group(1)
        if mod.startswith(".") or mod.startswith("/"):
            continue
        if any(mod.startswith(a) for a in path_aliases):
            continue  # internal path alias (e.g. @/...), not a package
        parts = mod.split("/")
        if mod.startswith("@") and len(parts) >= 2:
            base = "/".join(parts[:2])
        else:
            base = parts[0]
        if base in BUILTINS or base.startswith("node:"):
            continue
        if base not in deps:
            hallucinated.add(mod)
    tooling_used["hallucinated_imports"] = "tsc + package.json cross-check + tsconfig paths filter"
    return len(hallucinated)


def measure_complexity(repo, npx, pkg_json, eslint_json_cache, warnings, tooling_used):
    """Extract complexity scores from already-run eslint JSON output.

    Reuses eslint_json_cache (populated by measure_lint) to avoid running eslint
    twice. Returns (avg, p95) or (None, None). Only works if the project has
    the `complexity` rule enabled — otherwise no `complexity` ruleId will appear
    in messages and we return None with a warning.
    """
    if eslint_json_cache is None:
        return None, None
    try:
        scores = []
        import re
        for r in eslint_json_cache:
            for msg in r.get("messages", []):
                if msg.get("ruleId") == "complexity":
                    m = re.search(r"complexity of (\d+)", msg.get("message", ""))
                    if m:
                        scores.append(int(m.group(1)))
        if not scores:
            warnings.append("eslint 'complexity' rule not enabled in project; complexity metrics are null")
            return None, None
        scores.sort()
        avg = sum(scores) / len(scores)
        p95 = scores[max(0, int(len(scores) * 0.95) - 1)]
        tooling_used["complexity"] = "eslint complexity rule (reused from lint pass)"
        return round(avg, 2), p95
    except Exception as e:
        warnings.append(f"failed to extract complexity: {e}")
        return None, None


def measure_deprecated_api_usage(eslint_json_cache, warnings, tooling_used):
    """Count `eslint-plugin-deprecation` violations from the cached eslint pass.

    This counts in-source uses of APIs flagged with @deprecated JSDoc — i.e. the
    project is calling functions that the upstream maintainer has marked as
    going away. AI-generated code commonly reaches for deprecated patterns
    because training data lags behind library evolution.

    Rule id: `deprecation/deprecation` (also tolerates `@typescript-eslint/no-deprecated`
    and bare `no-deprecated` from variant configurations).

    Returns count or None if eslint cache is missing. Returns 0 (not None)
    when eslint ran but the rule isn't enabled — emits a warning so users know
    to enable the plugin if they want this signal.
    """
    if eslint_json_cache is None:
        return None
    deprecated_rule_ids = {"deprecation/deprecation", "@typescript-eslint/no-deprecated", "no-deprecated"}
    seen_any_msg = False
    count = 0
    for r in eslint_json_cache:
        for msg in r.get("messages", []):
            seen_any_msg = True
            rid = msg.get("ruleId") or ""
            if rid in deprecated_rule_ids or rid.endswith("no-deprecated"):
                count += 1
    if not seen_any_msg:
        # No messages at all means we can't tell if rule is enabled. Stay null.
        return None
    if count == 0:
        # Most projects without the plugin land here. Surface the gap so the
        # user can opt in, but don't fail; 0 is a legitimate value for projects
        # that DO have the plugin but happen to be clean.
        warnings.append("deprecated_api_count is 0 — verify eslint-plugin-deprecation (or @typescript-eslint/no-deprecated) is enabled to confirm this isn't a false zero")
    tooling_used["deprecated_api"] = "eslint deprecation rule (reused from lint pass)"
    return count


def measure_outdated_dependencies(repo, pm, warnings, tooling_used):
    """Count direct deps with a major-version upgrade available.

    Uses `<pm> outdated --json`. Returns count of packages whose `current` major
    differs from their `latest` major. None if the command isn't available or
    the project has no lockfile.

    Major-version drift is the closest proxy we get for "this project is
    falling behind on its API surface" without per-package CVE/changelog
    inspection. Minor/patch drift is excluded — that's normal release cadence.
    """
    if pm is None:
        return None
    cmd = {
        "npm": "npm outdated --json",
        "pnpm": "pnpm outdated --format json",
        "yarn": "yarn outdated --json",
    }.get(pm)
    if not cmd:
        return None
    out, err, rc = run(cmd, cwd=repo, timeout=180)
    # `*outdated` exits non-zero (typically 1) when there ARE outdated packages.
    # Empty output means either an error or genuinely no outdated deps.
    if not out:
        if rc == 0:
            tooling_used["outdated_deps"] = f"{pm} outdated"
            return 0
        warnings.append(f"{pm} outdated produced no output; rc={rc}")
        return None

    def major(v):
        if not v:
            return None
        try:
            # Strip leading non-digit chars (e.g. "^", "~", "v") then take first segment.
            cleaned = v.lstrip("^~v=<>! ")
            return int(cleaned.split(".")[0].split("-")[0])
        except (ValueError, IndexError):
            return None

    count = 0
    try:
        if pm == "pnpm":
            # pnpm outdated --format json => dict keyed by package name
            data = json.loads(out)
            for _, info in (data or {}).items():
                cur_major = major(info.get("current"))
                latest_major = major(info.get("latest"))
                if cur_major is not None and latest_major is not None and latest_major > cur_major:
                    count += 1
        elif pm == "npm":
            data = json.loads(out)
            for _, info in (data or {}).items():
                cur_major = major(info.get("current"))
                latest_major = major(info.get("latest"))
                if cur_major is not None and latest_major is not None and latest_major > cur_major:
                    count += 1
        elif pm == "yarn":
            # yarn outdated --json emits NDJSON; the data row is the second line.
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "table":
                    continue
                # head: ["Package","Current","Wanted","Latest","Workspace","Package Type","URL"]
                head = obj.get("data", {}).get("head", [])
                rows = obj.get("data", {}).get("body", [])
                try:
                    cur_idx = head.index("Current")
                    latest_idx = head.index("Latest")
                except ValueError:
                    continue
                for row in rows:
                    cm = major(row[cur_idx]) if cur_idx < len(row) else None
                    lm = major(row[latest_idx]) if latest_idx < len(row) else None
                    if cm is not None and lm is not None and lm > cm:
                        count += 1
        tooling_used["outdated_deps"] = f"{pm} outdated"
        return count
    except Exception as e:
        warnings.append(f"failed to parse {pm} outdated: {e}")
        return None


def measure_cognitive_complexity(eslint_json_cache, warnings, tooling_used):
    """Extract cognitive complexity scores from sonarjs/cognitive-complexity messages.

    Cognitive complexity differs from cyclomatic by weighting nesting depth
    exponentially — a deeply nested `if/else` chain explodes while a flat switch
    stays low. Captures "hard-to-read complexity" rather than just "branch count".

    sonarjs message format: "Refactor this function to reduce its Cognitive
    Complexity from <N> to the <allowed> allowed." Extract the N.

    Reuses the eslint pass — no extra runtime. Returns (avg, p95) or (None, None).
    Pre-condition: project has eslint-plugin-sonarjs and the cognitive-complexity
    rule enabled.
    """
    if eslint_json_cache is None:
        return None, None
    try:
        import re
        # sonarjs/cognitive-complexity is the canonical id; some setups namespace it
        # as `@sonar/cognitive-complexity` etc. Match suffix to be tolerant.
        scores = []
        for r in eslint_json_cache:
            for msg in r.get("messages", []):
                rule = msg.get("ruleId") or ""
                if not rule.endswith("cognitive-complexity"):
                    continue
                m = re.search(r"Cognitive Complexity from (\d+)", msg.get("message", ""))
                if m:
                    scores.append(int(m.group(1)))
        if not scores:
            warnings.append("sonarjs/cognitive-complexity rule not enabled (or eslint-plugin-sonarjs not installed); cognitive complexity metrics are null")
            return None, None
        scores.sort()
        avg = sum(scores) / len(scores)
        p95 = scores[max(0, int(len(scores) * 0.95) - 1)]
        tooling_used["cognitive_complexity"] = "eslint sonarjs/cognitive-complexity (reused from lint pass)"
        return round(avg, 2), p95
    except Exception as e:
        warnings.append(f"failed to extract cognitive complexity: {e}")
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".", help="Repository path")
    ap.add_argument("--out", default="tier1.json", help="Output JSON path")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / "package.json").exists():
        print(f"error: {repo}/package.json not found", file=sys.stderr)
        sys.exit(1)

    pkg_json = read_package_json(repo)
    pm, lockfile = detect_package_manager(repo)

    # Always use npx for tool invocation. It works regardless of project
    # package manager and can fetch tools not installed locally (jscpd, madge).
    # `pnpm exec` only runs locally-installed binaries which fails for
    # tools not in devDeps. `yarn` v1 vs Berry has different invocation rules.
    if shutil.which("npx") is None:
        print("error: npx not found; install Node.js", file=sys.stderr)
        sys.exit(1)
    npx = "npx --yes"

    warnings = []
    tooling_used = {"package_manager": pm, "lockfile": lockfile}

    kloc = count_loc(repo)
    cov_lines, cov_branches = measure_coverage(repo, pkg_json, npx, warnings, tooling_used)
    lint_density, eslint_json = measure_lint(repo, pkg_json, npx, kloc, warnings, tooling_used)
    dead_code = measure_dead_code(repo, pkg_json, npx, warnings, tooling_used)
    type_errors = measure_type_errors(repo, pkg_json, npx, warnings, tooling_used)
    security, security_advisories = measure_security(repo, pm, warnings, tooling_used)
    dep_snapshot = collect_dep_snapshot(pkg_json)
    duplication = measure_duplication(repo, npx, warnings, tooling_used)
    cyclic = measure_cyclic_deps(repo, npx, warnings, tooling_used)
    hallucinated = measure_hallucinated_imports(repo, npx, pkg_json, warnings, tooling_used)
    avg_cx, p95_cx = measure_complexity(repo, npx, pkg_json, eslint_json, warnings, tooling_used)
    avg_cog, p95_cog = measure_cognitive_complexity(eslint_json, warnings, tooling_used)
    deprecated_count = measure_deprecated_api_usage(eslint_json, warnings, tooling_used)
    outdated_major = measure_outdated_dependencies(repo, pm, warnings, tooling_used)

    result = {
        "tier1_metrics": {
            "test_coverage_lines": cov_lines,
            "test_coverage_branches": cov_branches,
            "lint_violations_per_kloc": lint_density,
            "dead_code_count": dead_code,
            "avg_cyclomatic_complexity": avg_cx,
            "p95_cyclomatic_complexity": p95_cx,
            "avg_cognitive_complexity": avg_cog,
            "p95_cognitive_complexity": p95_cog,
            "deprecated_api_count": deprecated_count,
            "outdated_dependencies_major": outdated_major,
            "type_errors": type_errors,
            "security_vulnerabilities": security,
            "security_advisories": security_advisories,
            "code_duplication_pct": duplication,
            "cyclic_dependencies_count": cyclic,
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
