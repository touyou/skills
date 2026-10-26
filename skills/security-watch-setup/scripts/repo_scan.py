#!/usr/bin/env python3
"""定期脆弱性チェック用のリポジトリ走査ツール（標準ライブラリのみ）。

サブコマンド:
  repos    ROOT 配下の git リポジトリを列挙する（node_modules と追加 worktree は除く）
  sync     各リポジトリで fetch し、クリーンなデフォルトブランチだけ ff-only で pull する
           （ネットワークを使う git は 1 リポ 180 秒で打ち切り、FETCHTIMEOUT / PULLTIMEOUT を出す）
  scan     各リポジトリの origin デフォルトブランチのロックファイル（Maven / Gradle は直接書かれた依存）から、指定パッケージの
           解決済みバージョンと悪性パッケージ名の一致を出す
  runtimes 各リポジトリの origin デフォルトブランチから、Dockerfile の FROM と
           ランタイム指定ファイル（.node-version 等）、CI の node-version、
           GitHub Actions で使っている action（uses:）を出す

出力は 1 行 1 件のタブ区切り（repo, 見た ref, 最終コミット日, 種別, 内容）。sync は結果と repo の 2 列。判定（脆弱な範囲に
入るか）はこのスクリプトでは行わない。範囲の読み方が勧告ごとに違うので、呼び出し側が
勧告の affected range と照らし合わせる。

使い方の例:
  repo_scan.py repos ~/Developer
  repo_scan.py sync ~/Developer
  repo_scan.py scan ~/Developer --npm storybook,dompurify --pip pillow --gem rexml \
      --maven com.squareup.okhttp3:okhttp \
      --malware @grabcad/,imgdecode
  repo_scan.py runtimes ~/Developer
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

SKIP_DIRS = {"node_modules", ".venv", "venv", "Pods", "DerivedData", ".build", "vendor"}

LOCKFILE_RE = re.compile(
    r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lock"
    r"|uv\.lock|poetry\.lock|Pipfile\.lock|requirements[^/]*\.txt"
    r"|Gemfile\.lock|Podfile\.lock|Package\.resolved|pubspec\.lock|composer\.lock"
    r"|go\.sum|Cargo\.lock|gradle\.lockfile|build\.gradle(?:\.kts)?|pom\.xml|libs\.versions\.toml)$"
)
RUNTIME_FILE_RE = re.compile(
    r"(^|/)(\.node-version|\.nvmrc|\.ruby-version|\.python-version|\.tool-versions"
    r"|mise\.toml|\.mise\.toml|\.bun-version|\.java-version|\.fvmrc)$"
)
DOCKERFILE_RE = re.compile(r"(^|/)(Dockerfile[^/]*|[^/]*\.Dockerfile)$")
WORKFLOW_RE = re.compile(r"(^|/)\.github/workflows/[^/]+\.ya?ml$")


def git(repo: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, env=env
    )


NETWORK_TIMEOUT = 180


def git_net(repo: str, *args: str, env: dict) -> subprocess.CompletedProcess | None:
    """ネットワークを使う git。時間切れなら None。

    subprocess.run の timeout は git しか殺さず、パイプを握った ssh が残ると待ち続けるので、
    プロセスグループごと止める。
    """
    proc = subprocess.Popen(
        ["git", "-C", repo, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=NETWORK_TIMEOUT)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.communicate()
        return None
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def find_repos(root: str, max_depth: int) -> list[str]:
    """`.git` がディレクトリのものだけ拾う（`.git` がファイルの追加 worktree は除く）。"""
    root = os.path.abspath(os.path.expanduser(root))
    repos = []
    base_depth = root.rstrip(os.sep).count(os.sep)
    for cur, dirs, _files in os.walk(root):
        depth = cur.count(os.sep) - base_depth
        if os.path.isdir(os.path.join(cur, ".git")):
            repos.append(cur)
        dirs[:] = [
            d for d in dirs if d not in SKIP_DIRS and d != ".git" and depth < max_depth
        ]
    return sorted(repos)


def default_ref(repo: str) -> str | None:
    for ref in ("origin/HEAD", "origin/main", "origin/master", "origin/develop"):
        if git(repo, "rev-parse", "--verify", "-q", ref).returncode == 0:
            return ref
    if git(repo, "rev-parse", "--verify", "-q", "HEAD").returncode == 0:
        return "HEAD"
    return None


def last_date(repo: str, ref: str) -> str:
    return git(repo, "log", "-1", "--format=%cs", ref).stdout.strip()


def tree_files(repo: str, ref: str) -> list[str]:
    out = git(repo, "ls-tree", "-r", "--name-only", ref).stdout.splitlines()
    return [f for f in out if not any(part in SKIP_DIRS for part in f.split("/"))]


def show(repo: str, ref: str, path: str) -> str:
    return git(repo, "show", f"{ref}:{path}").stdout


def rel(root: str, repo: str) -> str:
    # ROOT にリポ自体を渡したときも、どのリポの行か分かるようにフォルダ名を出す
    r = os.path.relpath(repo, root)
    return os.path.basename(os.path.abspath(repo)) if r == "." else r


# ---------------------------------------------------------------- sync

def sync_one(repo: str) -> str:
    if not git(repo, "remote").stdout.strip():
        return "NOREMOTE"
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # ConnectTimeout だけだと、つながった後に応答が止まった接続を待ち続ける
    env.setdefault(
        "GIT_SSH_COMMAND",
        "ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3",
    )
    fetched = git_net(repo, "fetch", "--all", "--prune", "-q", env=env)
    if fetched is None:
        return "FETCHTIMEOUT"
    if fetched.returncode != 0:
        return "FETCHFAIL"
    # origin/HEAD が無いクローンでは main / master の推測が外れる（既定が kotlin 等のリポがある）
    if git(repo, "rev-parse", "--verify", "-q", "origin/HEAD").returncode != 0:
        git_net(repo, "remote", "set-head", "origin", "--auto", env=env)
    ref = default_ref(repo)
    if not ref or not ref.startswith("origin/"):
        return "NODEFAULT"
    # origin/HEAD は origin/main などに解決してからブランチ名を取る
    default = git(repo, "rev-parse", "--abbrev-ref", ref).stdout.strip().split("/", 1)[-1]
    current = git(repo, "branch", "--show-current").stdout.strip()
    dirty = git(repo, "status", "--porcelain").stdout.strip()
    if current != default or dirty:
        return f"SKIP({current or 'detached'}{', dirty' if dirty else ''})"
    # 無人実行なので、取り込んだ内容由来のフック（husky の post-merge 等）は走らせない
    pulled = git_net(repo, "-c", "core.hooksPath=/dev/null", "pull", "--ff-only", "-q", env=env)
    if pulled is None:
        return "PULLTIMEOUT"
    if pulled.returncode != 0:
        return "PULLFAIL"
    return "PULLED"


# ---------------------------------------------------------------- scan

def _npm_versions(text: str, name: str) -> set[str]:
    e = re.escape(name)
    vs: set[str] = set()
    # package-lock.json / npm-shrinkwrap.json
    vs |= set(re.findall(r'"(?:[^"]*/)?node_modules/' + e + r'":\s*\{\s*"version":\s*"([^"]+)"', text))
    # pnpm-lock.yaml（v6〜v9 のキー形式）
    vs |= set(re.findall(r"(?m)^\s+/?'?" + e + r"@([0-9][^(:\s'/]*)", text))
    # bun.lock
    vs |= set(re.findall(r'"' + e + r'":\s*\["' + e + r'@([0-9][^"]*)"', text))
    # yarn.lock（classic / berry）
    vs |= set(re.findall(r'(?m)^"?' + e + r'@[^\n]*:\n\s+version:? "?([^"\n]+)"?', text))
    return vs


def _pip_versions(text: str, path: str, name: str) -> set[str]:
    n = name.lower().replace("_", "-")
    vs: set[str] = set()
    if path.endswith(("uv.lock", "poetry.lock")):
        for pkg, ver in re.findall(r'name = "([^"]+)"\nversion = "([^"]+)"', text):
            if pkg.lower().replace("_", "-") == n:
                vs.add(ver)
    elif path.endswith("Pipfile.lock"):
        try:
            data = json.loads(text)
            for section in ("default", "develop"):
                for pkg, meta in (data.get(section) or {}).items():
                    if pkg.lower().replace("_", "-") == n and "version" in meta:
                        vs.add(meta["version"].lstrip("="))
        except ValueError:
            pass
    else:  # requirements*.txt
        for pkg, ver in re.findall(r"(?im)^([a-z0-9_.-]+)\s*==\s*([0-9][^\s;#]*)", text):
            if pkg.lower().replace("_", "-") == n:
                vs.add(ver)
    return vs


def _gem_versions(text: str, name: str) -> set[str]:
    return set(re.findall(r"(?m)^    " + re.escape(name) + r" \(([^)]+)\)$", text))


def _pod_versions(text: str, name: str) -> set[str]:
    # DEPENDENCIES 節の「(from `path`)」「(~> 5.0)」は制約なので、数字で始まる解決済みの版だけ残す
    found = re.findall(r"(?m)^  - " + re.escape(name) + r" \(([^)]+)\)", text)
    return {v for v in found if re.match(r"\d", v)}


def _spm_versions(text: str, name: str) -> set[str]:
    vs: set[str] = set()
    try:
        data = json.loads(text)
    except ValueError:
        return vs
    pins = data.get("pins") or (data.get("object") or {}).get("pins") or []
    for pin in pins:
        ident = (pin.get("identity") or pin.get("package") or "").lower()
        if ident == name.lower():
            ver = (pin.get("state") or {}).get("version")
            if ver:
                vs.add(ver)
    return vs


def _pub_versions(text: str, name: str) -> set[str]:
    # DOTALL にすると後ろのパッケージの version まで読み進めるので、行単位で区切る
    return set(re.findall(r"(?m)^  " + re.escape(name) + r":\n(?:    [^\n]*\n)*?    version: \"([^\"]+)\"", text))


def _composer_versions(text: str, name: str) -> set[str]:
    vs: set[str] = set()
    try:
        data = json.loads(text)
    except ValueError:
        return vs
    for section in ("packages", "packages-dev"):
        for pkg in data.get(section) or []:
            if pkg.get("name", "").lower() == name.lower():
                vs.add(pkg.get("version", ""))
    return vs


def _go_versions(text: str, name: str) -> set[str]:
    return set(re.findall(r"(?m)^" + re.escape(name) + r" (v[^\s/]+?)(?:/go\.mod)? ", text))


def _cargo_versions(text: str, name: str) -> set[str]:
    return {v for n, v in re.findall(r'name = "([^"]+)"\nversion = "([^"]+)"', text) if n == name}


def _maven_versions(text: str, path: str, coord: str) -> set[str]:
    """group:artifact の、ファイルに直接書かれたバージョンだけを拾う（推移的な依存は出ない）。"""
    if ":" not in coord:
        return set()
    group, artifact = coord.split(":", 1)
    g, a = re.escape(group), re.escape(artifact)
    vs: set[str] = set()
    if path.endswith("pom.xml"):
        for m in re.finditer(r"<groupId>\s*" + g + r"\s*</groupId>\s*<artifactId>\s*" + a
                             + r"\s*</artifactId>\s*<version>\s*([^<\s]+)\s*</version>", text):
            vs.add(m.group(1))
    elif path.endswith("libs.versions.toml"):
        # [versions] の key = "x" を引けるようにしておき、version.ref を解決する
        refs: dict[str, str] = {}
        sec = re.search(r"(?ms)^\[versions\]\s*$(.*?)(?=^\[|\Z)", text)
        if sec:
            refs = dict(re.findall(r'(?m)^\s*([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"', sec.group(1)))
        for line in text.splitlines():
            if not (re.search(r'module\s*=\s*"' + g + ":" + a + '"', line)
                    or (re.search(r'group\s*=\s*"' + g + '"', line) and re.search(r'name\s*=\s*"' + a + '"', line))):
                continue
            m = re.search(r'version\.ref\s*=\s*"([^"]+)"', line)
            if m:
                vs.add(refs.get(m.group(1), f"ref:{m.group(1)}"))
                continue
            m = re.search(r'version\s*=\s*"([^"]+)"', line)
            if m:
                vs.add(m.group(1))
        for m in re.finditer(r'"' + g + ":" + a + r':([^"]+)"', text):
            vs.add(m.group(1))
    else:  # gradle.lockfile / build.gradle(.kts)
        vs |= set(re.findall(r"['\"]?" + g + ":" + a + r":([0-9][^'\"=\s)]*)", text))
    return vs


def scan_repo(root: str, repo: str, wants: dict[str, list[str]], malware: list[str]) -> list[str]:
    ref = default_ref(repo)
    if not ref:
        return []
    date = last_date(repo, ref)
    rows: set[str] = set()
    for f in tree_files(repo, ref):
        if not LOCKFILE_RE.search(f):
            continue
        text = show(repo, ref, f)
        low = text.lower()
        for m in malware:
            if m.lower() in low:
                rows.add(f"MALWARE?\t{m} in {f}")
        base = f.rsplit("/", 1)[-1]
        found: list[tuple[str, str, set[str]]] = []
        if base in ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock"):
            found += [("npm", n, _npm_versions(text, n)) for n in wants["npm"]]
        elif base in ("uv.lock", "poetry.lock", "Pipfile.lock") or base.startswith("requirements"):
            found += [("pip", n, _pip_versions(text, f, n)) for n in wants["pip"]]
        elif base == "Gemfile.lock":
            found += [("gem", n, _gem_versions(text, n)) for n in wants["gem"]]
        elif base == "Podfile.lock":
            found += [("pod", n, _pod_versions(text, n)) for n in wants["pod"]]
        elif base == "Package.resolved":
            found += [("spm", n, _spm_versions(text, n)) for n in wants["spm"]]
        elif base == "pubspec.lock":
            found += [("pub", n, _pub_versions(text, n)) for n in wants["pub"]]
        elif base == "composer.lock":
            found += [("composer", n, _composer_versions(text, n)) for n in wants["composer"]]
        elif base == "go.sum":
            found += [("go", n, _go_versions(text, n)) for n in wants["go"]]
        elif base in ("gradle.lockfile", "build.gradle", "build.gradle.kts", "pom.xml", "libs.versions.toml"):
            found += [("maven", n, _maven_versions(text, f, n)) for n in wants["maven"]]
        elif base == "Cargo.lock":
            found += [("cargo", n, _cargo_versions(text, n)) for n in wants["cargo"]]
        for eco, name, versions in found:
            for v in versions:
                rows.add(f"{eco}\t{name}@{v} ({f})")
    return [f"{rel(root, repo)}\t{ref}\t{date}\t{r}" for r in sorted(rows)]


# ---------------------------------------------------------------- runtimes

def runtimes_repo(root: str, repo: str) -> list[str]:
    ref = default_ref(repo)
    if not ref:
        return []
    date = last_date(repo, ref)
    rows: set[str] = set()
    for f in tree_files(repo, ref):
        if DOCKERFILE_RE.search(f):
            for line in show(repo, ref, f).splitlines():
                m = re.match(r"\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", line, re.I)
                if m:
                    rows.add(f"docker\t{m.group(1)} ({f})")
        elif RUNTIME_FILE_RE.search(f):
            body = " ".join(show(repo, ref, f).split())[:120]
            rows.add(f"runtime-file\t{body} ({f})")
        elif WORKFLOW_RE.search(f):
            body = show(repo, ref, f)
            for m in re.finditer(r"(node-version|ruby-version|python-version|go-version|bun-version|php-version|java-version|flutter-version|dotnet-version):\s*(\S[^\n#]*)", body):
                rows.add(f"ci\t{m.group(1)}: {m.group(2).strip()} ({f})")
            # 使っている action（侵害・勧告との照合用）。ローカルの action（./）と docker:// は除く
            for m in re.finditer(r"(?m)^[\s-]*uses:\s*['\"]?([A-Za-z0-9_.-]+/[^\s'\"#@]+@[^\s'\"#]+)", body):
                rows.add(f"action\t{m.group(1)} ({f})")
        elif f.endswith("package.json") and f.count("/") <= 2:
            try:
                data = json.loads(show(repo, ref, f))
            except ValueError:
                continue
            engines = (data.get("engines") or {}).get("node")
            if engines:
                rows.add(f"engines\tnode {engines} ({f})")
    return [f"{rel(root, repo)}\t{ref}\t{date}\t{r}" for r in sorted(rows)]


# ---------------------------------------------------------------- main

def csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["repos", "sync", "scan", "runtimes"])
    p.add_argument("roots", nargs="+", help="走査するディレクトリ（複数可）")
    p.add_argument("--depth", type=int, default=5, help="リポジトリを探す深さ（既定 5）")
    # GitHub は同時の SSH 接続が多いと詰まるので、sync だけ並列を絞る
    p.add_argument("--jobs", type=int, help="並列数（既定は sync が 4、それ以外が 8）")
    for eco in ("npm", "pip", "gem", "pod", "spm", "pub", "composer", "go", "cargo", "maven"):
        p.add_argument(f"--{eco}", help=f"{eco} のパッケージ名（カンマ区切り）")
    p.add_argument("--malware", help="悪性パッケージ名・スコープ（カンマ区切り。部分一致で探す）")
    a = p.parse_args()
    if a.jobs is None:
        a.jobs = 4 if a.command == "sync" else 8

    for root in a.roots:
        root = os.path.abspath(os.path.expanduser(root))
        repos = find_repos(root, a.depth)
        if a.command == "repos":
            for r in repos:
                print(rel(root, r))
            continue
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            if a.command == "sync":
                for r, status in zip(repos, ex.map(sync_one, repos)):
                    print(f"{status}\t{rel(root, r)}")
            elif a.command == "scan":
                wants = {eco: csv(getattr(a, eco)) for eco in ("npm", "pip", "gem", "pod", "spm", "pub", "composer", "go", "cargo", "maven")}
                malware = csv(a.malware)
                for rows in ex.map(lambda r: scan_repo(root, r, wants, malware), repos):
                    for row in rows:
                        print(row)
            else:
                for rows in ex.map(lambda r: runtimes_repo(root, r), repos):
                    for row in rows:
                        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
