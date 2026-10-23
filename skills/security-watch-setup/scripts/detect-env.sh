#!/usr/bin/env bash
# 定期脆弱性チェックのセットアップ用に、この環境の事実を集めて表示する。
# 何もインストール・変更しない。ただし runtimes_by_shell は各シェルの設定ファイル（.zshrc など）を
# 対話シェルとして実行するので、そこに書かれた処理は走る（20 秒で打ち切る）。macOS / Linux / WSL / Git Bash で動く。
#
# 使い方: bash detect-env.sh [リポジトリを探すディレクトリ ...]
# 出力は「## 見出し」と「key: value」の行。値が取れないものは出さない。

set -u

have() { command -v "$1" >/dev/null 2>&1; }
kv() { [ -n "${2:-}" ] && printf '%s: %s\n' "$1" "$2"; }
first_line() { "$@" 2>/dev/null | head -n 1; }

echo "## os"
kv os "$(uname -s)"
kv arch "$(uname -m)"
if have sw_vers; then kv macos "$(sw_vers -productVersion)"; fi
if [ -r /etc/os-release ]; then kv linux "$(. /etc/os-release; echo "${PRETTY_NAME:-}")"; fi
if grep -qi microsoft /proc/version 2>/dev/null; then kv wsl yes; fi
kv timezone "$(date +%Z)"

echo "## shell"
kv login_shell "${SHELL:-}"
for s in fish zsh bash pwsh; do have "$s" && kv "has_$s" "$(command -v "$s")"; done

echo "## agents"
have claude && kv claude_cli "$(first_line claude --version)"
[ -d /Applications/Claude.app ] && kv claude_desktop /Applications/Claude.app
[ -d "$HOME/.claude/scheduled-tasks" ] && kv claude_scheduled_tasks_dir "$HOME/.claude/scheduled-tasks"
[ -d "$HOME/.claude/skills" ] && kv claude_skills_dir "$HOME/.claude/skills"
have codex && kv codex_cli "$(first_line codex --version)"
[ -d "$HOME/.codex" ] && kv codex_home "$HOME/.codex"
[ -d /Applications/Codex.app ] && kv codex_desktop /Applications/Codex.app
[ -d "$HOME/.agents/skills" ] && kv agents_skills_dir "$HOME/.agents/skills"
have cursor-agent && kv cursor_agent "$(first_line cursor-agent --version)"
have gemini && kv gemini_cli "$(first_line gemini --version)"

echo "## schedulers"
have launchctl && kv launchd yes
have crontab && kv cron yes
if have systemctl && systemctl --user list-timers >/dev/null 2>&1; then kv systemd_user_timers yes; fi
have schtasks.exe && kv windows_task_scheduler yes

echo "## notify"
have osascript && kv osascript yes
have terminal-notifier && kv terminal_notifier yes
have notify-send && kv notify_send yes

echo "## shell_activation"
# バージョン管理ツールをどのシェルの設定で有効にしているか（ルーチンをどのシェルで動かすかの根拠）
for f in "$HOME/.config/fish/config.fish" "$HOME"/.config/fish/conf.d/*.fish \
         "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.zshenv" \
         "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
  [ -f "$f" ] || continue
  hits=$(grep -oE 'mise activate|rtx activate|nvm\.sh|asdf\.(sh|fish)|volta|fnm env|rbenv init|pyenv init|brew shellenv|\.bun/bin|direnv hook' "$f" 2>/dev/null | sort -u | tr '\n' ',' | sed 's/,$//')
  [ -n "$hits" ] && kv "$f" "$hits"
done

echo "## version_managers"
for t in brew mise asdf volta fnm pyenv rbenv uv pipx; do
  have "$t" && kv "$t" "$(first_line "$t" --version)"
done
[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ] && kv nvm "${NVM_DIR:-$HOME/.nvm}"

echo "## runtimes"
# シェルごとに PATH が違うことがあるので、見つかった実体をすべて出す
for t in node bun deno ruby python3 go php java swift; do
  have "$t" || continue
  for p in $(which -a "$t" 2>/dev/null | awk '!seen[$0]++'); do
    case "$t" in
      go) v="$("$p" version 2>/dev/null)" ;;
      # JAVA_TOOL_OPTIONS / JDK_JAVA_OPTIONS があると「(NOTE: )Picked up ...」の行が先に出る
      java) v="$("$p" -version 2>&1 | grep -v 'Picked up' | head -n 1)" ;;
      swift) v="$("$p" --version 2>/dev/null | head -n 1)" ;;
      *) v="$(first_line "$p" --version)" ;;
    esac
    kv "$t" "$p $v"
  done
done

echo "## runtimes_by_shell"
# 定期実行はユーザーの対話シェルとは別の PATH で動くことが多い。各シェルの設定を読んだ状態で
# どの実体・バージョンが選ばれるかを出す（mise / nvm の shim はここでしか見えないことがある）
# 遅延読み込み（zsh-nvm の NVM_LAZY_LOAD など）では command -v がパスでなく関数名を返すので function と出す
probe='for t in node bun deno ruby python3 go php; do p=$(command -v $t 2>/dev/null) || continue; case $p in /*) ;; *) p=function ;; esac; v=$($t --version 2>/dev/null | head -n 1); [ $t = go ] && v=$(go version 2>/dev/null); echo "$t $p $v"; done'
# mise activate / nvm は .zshrc・.bashrc に書くことが多く、-l だけでは読まれない（Debian 系の .bashrc は
# 非対話なら即 return する）ので -i も付ける。対話起動で出る余計な出力は、ランタイム名で始まる行だけ拾って除く
to=""; have timeout && to="timeout 20"; have gtimeout && to="gtimeout 20"
for s in zsh bash; do
  have "$s" || continue
  $to "$s" -ilc "$probe" 2>/dev/null </dev/null | grep -E '^(node|bun|deno|ruby|python3|go|php) (/|function)' \
    | while read -r t p v; do kv "${s}_$t" "$p $v"; done
done
if have fish; then
  fish -c 'for t in node bun deno ruby python3 go php
    set p (command -s $t); or continue
    if test $t = go; set v (go version 2>/dev/null); else; set v ($t --version 2>/dev/null | head -n 1); end
    echo "$t $p $v"
  end' 2>/dev/null </dev/null | while read -r t p v; do kv "fish_$t" "$p $v"; done
fi

echo "## tools"
for t in git docker pnpm yarn npm gh dart flutter xcodebuild; do
  have "$t" && kv "$t" "$(first_line "$t" --version)"
done
if have gh; then
  if gh auth status >/dev/null 2>&1; then
    kv gh_auth ok
    # 個人アカウントのリポ（<login>/*）は gh_orgs に出ないので別に出す
    kv gh_login "$(gh api user -q .login 2>/dev/null)"
    kv gh_orgs "$(gh api user/orgs -q '.[].login' 2>/dev/null | tr '\n' ' ')"
  else
    kv gh_auth none
  fi
fi
[ -d "/Applications/Docker.app" ] && kv docker_desktop "$(defaults read /Applications/Docker.app/Contents/Info.plist CFBundleShortVersionString 2>/dev/null)"
[ -d "/Applications/Google Chrome.app" ] && kv chrome "$(defaults read "/Applications/Google Chrome.app/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null)"

echo "## repo_roots"
roots=("$@")
if [ ${#roots[@]} -eq 0 ]; then
  roots=("$HOME/Developer" "$HOME/dev" "$HOME/src" "$HOME/code" "$HOME/projects" "$HOME/Projects" \
         "$HOME/work" "$HOME/repos" "$HOME/git" "$HOME/workspace" "$HOME/ghq")
fi
for r in "${roots[@]}"; do
  [ -d "$r" ] || continue
  n=$(find "$r" -maxdepth 5 -name node_modules -prune -o -type d -name .git -print 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] && kv "$r" "$n repos"
done

echo "## ecosystems"
# 見つかったロックファイルの種類と件数（どの情報源を毎回見るかを決める材料）
for r in "${roots[@]}"; do
  [ -d "$r" ] || continue
  find "$r" -maxdepth 6 \( -name node_modules -o -name .git -o -name Pods -o -name .venv \) -prune -o -type f \( \
    -name package-lock.json -o -name pnpm-lock.yaml -o -name yarn.lock -o -name bun.lock -o \
    -name uv.lock -o -name poetry.lock -o -name 'requirements*.txt' -o -name Pipfile.lock -o \
    -name Gemfile.lock -o -name Podfile.lock -o -name Package.resolved -o -name pubspec.lock -o \
    -name composer.lock -o -name go.sum -o -name Cargo.lock -o -name 'Dockerfile*' -o \
    -name gradle.lockfile -o -name build.gradle -o -name build.gradle.kts -o -name pom.xml \) -print 2>/dev/null
done | awk -F/ '{print $NF}' | sed -E 's/^requirements.*\.txt$/requirements.txt/; s/^Dockerfile.*/Dockerfile/; s/^build\.gradle(\.kts)?$/build.gradle/' \
  | sort | uniq -c | awk '{printf "%s: %s\n", $2, $1}'

echo "## docker_base_images"
# Dockerfile の FROM（作業ツリーの内容。どのディストリ・ランタイムの告知を見るかの材料）
for r in "${roots[@]}"; do
  [ -d "$r" ] || continue
  find "$r" -maxdepth 6 \( -name node_modules -o -name .git \) -prune -o -type f -name 'Dockerfile*' -print 2>/dev/null
done | while read -r f; do
  # マルチステージのステージ名（FROM x AS base → FROM base）は除く
  awk 'toupper($1) == "FROM" {
         i = 2; if ($i ~ /^--platform=/) i++
         img = $i; if (!(img in stage)) print img
         if (toupper($(i+1)) == "AS") stage[$(i+2)] = 1
       }' "$f" 2>/dev/null
done | grep -v '^\$' | sed -E 's/@sha256:.*$/@sha256/' | sort | uniq -c | sort -rn | awk '{printf "%s: %s\n", $2, $1}'
