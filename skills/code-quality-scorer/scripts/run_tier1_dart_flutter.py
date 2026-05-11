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


GENERATED_DART_SUFFIXES = (".g.dart", ".freezed.dart", ".intent.dart", ".chopper.dart", ".gr.dart", ".gen.dart", ".config.dart", ".mocks.dart")
EXCLUDE_DIRS = {".dart_tool", "build", ".pub-cache", ".symlinks", "ios", "android", "macos", "linux", "windows", "web"}


def detect_fvm(repo):
    """FVM プロジェクトかを検出する。

    `.fvmrc` または `.fvm/fvm_config.json` (旧形式) があれば fvm 経由で動かす。
    プロジェクトが FVM で SDK をピンしているのに素の flutter/dart を呼ぶと、
    シャドウされた別バージョンが走って analyze や coverage が乖離するため。
    """
    return (repo / ".fvmrc").exists() or (repo / ".fvm").is_dir()


def flutter_cmd(repo):
    return "fvm flutter" if detect_fvm(repo) and shutil.which("fvm") else "flutter"


def dart_cmd(repo):
    # fvm dart は fvm 1.3+ でサポート。fvm が無い場合は素の dart にフォールバック。
    return "fvm dart" if detect_fvm(repo) and shutil.which("fvm") else "dart"


def parse_exclude_paths(repo, raw):
    """--exclude-source-paths のカンマ区切り入力を絶対 Path のリストに正規化する。"""
    if not raw:
        return []
    paths = []
    for chunk in raw.split(","):
        s = chunk.strip()
        if not s:
            continue
        p = (repo / s).resolve()
        paths.append(p)
    return paths


def is_excluded(path, exclude_paths):
    """`path` が exclude_paths のいずれかの配下なら True。"""
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


def find_dart_files(repo, exclude_paths=None):
    """Enumerate non-generated .dart source files (lib/ + monorepo packages/*/lib/).

    `exclude_paths` を渡すと、その配下のファイルを除外する (lib/gen, lib/api_definitions など
    プロジェクト固有の generated location 対策)。
    """
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
            root_path = Path(root)
            if is_excluded(root_path, exclude_paths or []):
                dirs[:] = []
                continue
            for f in files:
                if f.endswith(".dart") and not f.endswith(GENERATED_DART_SUFFIXES):
                    if any(part in {"test", "tests"} for part in root_path.parts):
                        continue
                    full = root_path / f
                    if is_excluded(full, exclude_paths or []):
                        continue
                    candidates.append(full)
    return candidates


def count_loc(repo, exclude_paths=None):
    total = 0
    for path in find_dart_files(repo, exclude_paths=exclude_paths):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return total


def measure_coverage(repo, warnings, tooling_used):
    """Run flutter test --coverage and parse coverage/lcov.info ourselves.

    Branch coverage isn't emitted by Dart's coverage backend in practice, so
    branches stay None even on success. macOS/Linux では `flutter test --coverage` が
    file descriptor を大量に開くので、ulimit を一時的に上げてから実行する。
    """
    fvm = detect_fvm(repo) and shutil.which("fvm")
    has_flutter = shutil.which("flutter") is not None
    if not fvm and not has_flutter:
        warnings.append("flutter SDK not on PATH (no fvm and no bare flutter); coverage disabled")
        return None, None
    cmd = f"{flutter_cmd(repo)} test --coverage"
    # ulimit はサブシェル内なので親 shell には影響しない。macOS Catalina 以降だと
    # デフォルト 256 で coverage 中に "Too many open files" が頻発する。
    cmd = f"ulimit -n 10240 && {cmd}"
    out, err, rc = run(cmd, cwd=repo, timeout=1800)
    lcov = repo / "coverage" / "lcov.info"
    if not lcov.exists():
        combined = err or out
        tail = combined.splitlines()[-3:]
        # 「git worktree や CI で .env が無いせいで asset build が落ちる」よくあるケースを
        # 一般的な warning ではなく具体メッセージで区別する。再現する人がドキュメントを
        # 読まなくても原因に気づける程度に書く。
        hint = ""
        if "No file or variants found for asset" in combined or "Failed to build asset bundle" in combined:
            hint = (
                " hint: pubspec.yaml で参照しているアセット (.env や fonts 等) が見つからない可能性。"
                " worktree や clean checkout 上では .env が gitignore で消えていることが多い。"
                " `.env.sample` を `.env` に cp してから再実行するか、pubspec.yaml で該当アセットを optional 化してください。"
            )
        warnings.append(f"flutter test --coverage did not produce coverage/lcov.info; rc={rc}; {' | '.join(tail)[:200]}{hint}")
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
    tooling_used["coverage"] = f"{flutter_cmd(repo)} test --coverage (ulimit -n 10240, lcov.info)"
    return round(lines_hit / lines_found, 4), None


def run_dart_analyze(repo, warnings):
    """Run `dart analyze --format=machine`. Returns the raw output text or None.

    `dart analyze` exits with rc=1 when issues exist (which is the normal case),
    so we treat 0 and 1 as success. rc>=2 is genuine failure.
    """
    fvm = detect_fvm(repo) and shutil.which("fvm")
    has_dart = shutil.which("dart") is not None
    has_flutter = shutil.which("flutter") is not None
    if not fvm and not has_dart and not has_flutter:
        warnings.append("neither `dart` nor `flutter` on PATH (and no fvm); analyze disabled")
        return None
    if fvm:
        cmd = f"{dart_cmd(repo)} analyze --format=machine"
    elif has_dart:
        cmd = "dart analyze --format=machine"
    else:
        cmd = "flutter analyze --format=machine"
    out, err, rc = run(cmd, cwd=repo, timeout=600)
    # rc 規則 (dart CLI):
    #   0 = no issues
    #   1 = INFO/WARNING のみ
    #   2 = ERROR レベル issue が存在 (= 出力は valid)
    #   3+ = analyzer 自体が異常終了 (custom_lint plugin の起動失敗など) だが、
    #        多くの場合 stdout には先に書き込まれた INFO|...| 行が残っている。
    # rc=2 は ERROR があったというだけで出力を捨てる理由にならない。
    # rc>=3 でも先に出ている INFO|... 行は信用してよいので、出力が parseable な分は使う。
    if rc not in (0, 1, 2):
        # 行が parseable で 1 行以上得られているなら、partial として使う + warning。
        partial_rows = parse_analyze_lines(out)
        if partial_rows:
            warnings.append(
                f"`{cmd}` rc={rc} (analyzer crashed mid-run); using {len(partial_rows)} pre-crash rows. "
                f"tail={(err or out).splitlines()[-3:]}"
            )
            return out
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
    # dart analyze --format=machine の CODE 列は built-in 系 (STATIC_WARNING) では UPPERCASE
    # (`UNUSED_IMPORT`) で、lint 系 (TYPE=LINT) では snake_case lowercase (`unused_local_variable`)
    # で出る。両方拾えるよう lowercase 比較する。
    count = sum(1 for r in rows if r[1].lower() in DEAD_CODE_RULES)
    tooling_used["dead_code"] = "dart analyze (unused_*/dead_code rules, case-insensitive)"
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
        # built-in 系では `URI_DOES_NOT_EXIST` (UPPER) / lint 系では `uri_does_not_exist` (lower) で出る
        if code.lower() != "uri_does_not_exist":
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
    fvm = detect_fvm(repo) and shutil.which("fvm")
    has_dart = shutil.which("dart") is not None
    if not fvm and not has_dart:
        warnings.append("dart SDK not on PATH (and no fvm); security audit disabled")
        return None
    dart = dart_cmd(repo) if fvm else "dart"
    out, err, rc = run(f"{dart} pub audit --json", cwd=repo, timeout=180)
    if not out or 'Could not find a subcommand named "audit"' in (out + err):
        out, err, rc = run(f"{dart} pub audit", cwd=repo, timeout=180)
    if not out and 'Could not find a subcommand named "audit"' in err:
        warnings.append("`dart pub audit` not available in this SDK (Dart <3.x or stripped build); security null")
        return None
    if not out:
        warnings.append(f"dart pub audit produced no output; rc={rc}")
        return None
    if 'Could not find a subcommand named "audit"' in out:
        warnings.append("`dart pub audit` subcommand missing; security null")
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


def measure_duplication(repo, warnings, tooling_used, exclude_paths=None):
    if shutil.which("npx") is None:
        warnings.append("npx not on PATH; jscpd unavailable for code_duplication_pct")
        return None
    target = "lib" if (repo / "lib").exists() else "."
    # exclude_paths は repo 相対 glob に変換 (lib/gen → **/lib/gen/**) して jscpd の --ignore に渡す。
    extra_ignores = []
    for p in (exclude_paths or []):
        try:
            rel = p.relative_to(repo)
            extra_ignores.append(f"**/{rel.as_posix()}/**")
        except ValueError:
            continue
    ignore_globs = (
        "**/.dart_tool/**,**/build/**,**/*.g.dart,**/*.freezed.dart,**/*.intent.dart,"
        "**/*.gr.dart,**/*.gen.dart,**/*.config.dart,**/*.mocks.dart"
    )
    if extra_ignores:
        ignore_globs = ignore_globs + "," + ",".join(extra_ignores)
    cmd = (
        "npx --yes jscpd --silent --reporters json --output /tmp/jscpd-flutter "
        "--pattern '**/*.dart' "
        f"--ignore '{ignore_globs}' "
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
    ap.add_argument(
        "--exclude-source-paths", default="",
        help="repo 相対パスのカンマ区切り。指定した配下を LOC/lint/duplication 集計から除外する (例: 'lib/gen,lib/api_definitions')",
    )
    ap.add_argument(
        "--skip-coverage", action="store_true",
        help="coverage 計測 (`flutter test --coverage`) をスキップ。スモークテストや CI 短縮用",
    )
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
    exclude_paths = parse_exclude_paths(repo, args.exclude_source_paths)
    fvm_active = detect_fvm(repo) and shutil.which("fvm") is not None
    tooling_used = {
        "package_manager": "pub",
        "pubspec": "pubspec.yaml",
        "monorepo_self_name": pubspec_info.get("name"),
        "monorepo_path_deps": sorted(pubspec_info.get("path_deps", [])),
        "fvm_detected": detect_fvm(repo),
        "fvm_active": fvm_active,
        "excluded_source_paths": [str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p) for p in exclude_paths],
    }

    kloc = count_loc(repo, exclude_paths=exclude_paths)
    if args.skip_coverage:
        cov_lines, cov_branches = None, None
        warnings.append("coverage skipped via --skip-coverage")
    else:
        cov_lines, cov_branches = measure_coverage(repo, warnings, tooling_used)
    analyze_text = run_dart_analyze(repo, warnings)
    rows = parse_analyze_lines(analyze_text)
    # exclude_paths 配下からの違反/dead は除外する (LOC からも除いているので一貫性を保つ)
    if exclude_paths:
        def keep(row):
            file_path = Path(row[2])
            if not file_path.is_absolute():
                file_path = repo / file_path
            return not is_excluded(file_path, exclude_paths)
        rows = [r for r in rows if keep(r)]
    lint_density = measure_lint(rows, kloc, warnings, tooling_used, has_analysis_options)
    dead_code = measure_dead_code(rows, warnings, tooling_used)
    type_errors = measure_type_errors(rows, warnings, tooling_used)
    hallucinated = measure_hallucinated_imports(rows, pubspec_info, warnings, tooling_used)
    security = measure_security(repo, warnings, tooling_used)
    duplication = measure_duplication(repo, warnings, tooling_used, exclude_paths=exclude_paths)

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
