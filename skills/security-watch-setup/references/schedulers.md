# 定期実行の登録手順

## どれを使うか

上から順に、当てはまる最初のものを使う。1・2 行目は detect-env.sh の結果（インストールの有無）だけで
なく、**今のセッションに定期タスクを作るツールがあるか**で判定する。アプリは入っているのに
ツールがない（CLI から呼ばれた）ときは、SKILL.md Step 2 の 7 で本人に選んでもらう。

| 条件 | 使う仕組み | 理由 |
|---|---|---|
| Claude Code のデスクトップアプリで、定期タスクのツール（`create_scheduled_task`）が使える | **Claude Code の定期タスク** | ローカルのファイル・シェル・gh がそのまま使え、結果がアプリに残る |
| Codex のデスクトップアプリで、Automations が使える | **Codex の Automations** | 同上 |
| `claude` CLI があり、macOS | **launchd + `claude -p`** | アプリを開いていなくても動く |
| `claude` CLI があり、Linux / WSL | **systemd ユーザータイマー（なければ cron）+ `claude -p`** | |
| `codex` CLI だけがある | **launchd / systemd / cron + `codex exec`** | |
| Windows ネイティブ | **タスクスケジューラ + `claude -p` または `codex exec`** | |

**使わないもの**:

- クラウドで動くルーチン（Claude Code の `/schedule` で作るリモートのルーチンなど）。手元の PC の
  ツール・ランタイム・未 push のリポジトリが見えないので、このチェックの目的に合わない。
  GitHub 上のリポジトリだけを見るチェックに絞るなら使えるが、その場合は 2 章（ローカルの最新化）を
  雛形から外し、`repo_scan.py` の代わりに `gh api` でロックファイルを取得するように書き換える
- セッションの中だけで回るループ（`/loop` など）。セッションを閉じると止まる

## Claude Code の定期タスク（デスクトップアプリ）

`create_scheduled_task` ツールで登録する。

- `taskId`: `security-watch`（使われていれば提案された別名）
- `title`: 本人の言葉で（例: 「セキュリティ定期チェック」）
- `description`: 1 行の説明
- `cronExpression`: **ローカル時刻**の 5 項目。平日 9:00 と 17:00 なら `0 9,17 * * 1-5`
- `prompt`: 組み立てたルーチン全文

プロンプトは `~/.claude/scheduled-tasks/<taskId>/SKILL.md` に保存される。あとから手順を直すときは
`update_scheduled_task` を使うか、このファイルを編集する。

伝えること:

- **アプリが開いている間だけ動く**。閉じていた時間の分は、次に開いたときに実行される
- 1 回目は `run_scheduled_task` で今すぐ動かせる（Step 4 の確認に使う）
- 権限モードがセッションの設定に従って保存されることがある。ツールの結果に保存された
  モードが出るので、そのまま伝える。別の端末やプロジェクトから作ったときなど、権限モードが
  保存されていないと、無人の実行がツールの承認待ちで止まる。その場合はアプリの「Scheduled」から
  タスクを開いて権限モード（`brew` / `git pull` / PR 作成まで止めずに進めるなら Auto）を選び、
  「Run now」で 1 回動かして出てきた承認を通してもらう
- 定期タスクの作成は、エージェントの安全判定で止められることがある。そのときは本人に
  作成してよいかを明示的に確かめてから作り直す（ファイルを直接書いて回避しない）

## Codex の Automations（デスクトップアプリ）

Codex アプリの Automations 画面（またはアプリが提供する自動化のツール）で、プロンプト・
スケジュール・作業ディレクトリを指定して登録する。項目名や設定場所はバージョンで変わるので、
**登録前にアプリの画面か `codex --help` で実際の項目を確かめ、決め打ちしない**。

- 作業ディレクトリ: リポジトリの置き場所（`{{REPO_ROOTS}}` の親）
- サンドボックス: ネットワークアクセスと、置き場所への書き込みが要る
- スクリプトは `~/.agents/skills/security-watch-setup/scripts/` など、Codex から読める場所の絶対パスで書く

## launchd + `claude -p`（macOS）

1. ルーチン全文を `~/.local/share/security-watch/prompt.md` に保存する（スクリプトのコピー先 `scripts/` と同じ場所にまとめる。macOS でも同じパス）
2. 実行用のスクリプト `~/.local/share/security-watch/run.sh` を作る。
   **シェルは SKILL.md Step 1 で決めたもの（バージョン管理ツールを有効にしているシェル）**にする。
   そうしないと、定期実行で mise / nvm のランタイムが見えず、確認が抜ける。

   zsh・bash の例（ログインシェルとして起動して `.zprofile` / `.zshrc` を読ませる）:

   ```sh
   #!/bin/zsh -il
   cd "$HOME"
   exec claude -p "$(cat "$HOME/.local/share/security-watch/prompt.md")" \
     --permission-mode auto \
     --add-dir "$HOME/Developer" \
     >> "$HOME/Library/Logs/security-watch.log" 2>&1
   ```

   fish の例（fish は非対話でも `config.fish` を読む）:

   ```fish
   #!/opt/homebrew/bin/fish
   cd $HOME
   claude -p (cat "$HOME/.local/share/security-watch/prompt.md" | string collect) \
     --permission-mode auto \
     --add-dir $HOME/Developer \
     >> $HOME/Library/Logs/security-watch.log 2>&1
   ```

   - `--permission-mode` は無人で動かせるもの（`auto` か、必要なコマンドだけを `--allowedTools` で
     許可する形）にする。`bypassPermissions` は使わない
   - fish のパスは `command -s fish` の結果に合わせる
   - オプション名は `claude --help` で確かめてから書く
   - 1 回目の実行のあと、ログの冒頭でランタイムの実体が detect-env.sh の `runtimes_by_shell` と
     一致しているか確かめる
3. `~/Library/LaunchAgents/dev.security-watch.plist` を作る（平日 9:00 と 17:00 の例）:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>dev.security-watch</string>
     <key>ProgramArguments</key>
     <array><string>/Users/USERNAME/.local/share/security-watch/run.sh</string></array>
     <key>StartCalendarInterval</key>
     <array>
       <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
       <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
       <!-- Weekday 2〜5 も同じように並べる -->
     </array>
   </dict>
   </plist>
   ```

4. 登録して 1 回動かす:

   ```sh
   chmod +x "$HOME/.local/share/security-watch/run.sh"
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.security-watch.plist
   launchctl kickstart -k gui/$(id -u)/dev.security-watch
   ```

   止めるときは `launchctl bootout gui/$(id -u)/dev.security-watch`。スリープ中に予定時刻を
   過ぎた分は、起きたときに 1 回実行される。

## systemd ユーザータイマー / cron + `claude -p`（Linux・WSL）

run.sh は上と同じ考え方で `~/.local/share/security-watch/run.sh` に置く（シェルは Step 1 で決めたもの。bash なら `#!/bin/bash -l`）。

systemd:

```ini
# ~/.config/systemd/user/security-watch.service
[Service]
Type=oneshot
ExecStart=%h/.local/share/security-watch/run.sh

# ~/.config/systemd/user/security-watch.timer
[Timer]
OnCalendar=Mon..Fri 09,17:00
Persistent=true
[Install]
WantedBy=timers.target
```

```sh
systemctl --user daemon-reload
systemctl --user enable --now security-watch.timer
systemctl --user start security-watch.service   # 1 回動かす
```

cron（systemd が使えないとき）: `crontab -e` に `0 9,17 * * 1-5 $HOME/.local/share/security-watch/run.sh`。
cron は PATH が最小なので、run.sh をログインシェルで動かすことが特に大事。

## `codex exec` を使う場合

run.sh の `claude -p ...` を `codex exec` に置き換える。サンドボックスと承認のオプション名は
バージョンで変わるので、**`codex exec --help` で確かめてから**、ネットワークアクセスとリポジトリの
置き場所への書き込みができる最小の設定にする。危険なオプション（承認とサンドボックスを
両方外すもの）は使わない。

## タスクスケジューラ（Windows ネイティブ）

PowerShell のスクリプト（`run.ps1`）で `claude -p` を呼び、`Register-ScheduledTask` で登録する。
ルーチンのコマンド例は PowerShell の構文に、detect-env.sh・repo_scan.py の呼び出しは
`python` と Git for Windows の `bash` が使えるかを確かめてから書く。使えなければ WSL での
実行を勧める。

## 共通の確認

- 登録したら必ず 1 回動かし、ログとレポートを見る（SKILL.md の Step 4）
- ルーチンが gh を使うので、無人実行の環境でも `gh auth status` が通ることを確かめる
- 実行時間は 10〜30 分かかることがある。次の実行と重ならない間隔にする
