# プロジェクト設定

リポジトリのルートに `.claude/ai-bot-pr-review.local.md` を置くと挙動を調整できる。無くてもデフォルトで動く。

```markdown
---
# bot author の許可リスト (どの author の PR を「bot 由来」として扱うか)
bot_authors:
  - app/github-actions
  - copilot-swe-agent[bot]
  - coderabbitai[bot]
  - dependabot[bot]

# ブランチ prefix の許可リスト (このスキルで対象にする)
branch_prefixes:
  - chore/codex-refactor-
  - copilot/
  - coderabbit/
  - dependabot/

# 対象外にする branch prefix (リリース PR / バックポート PR 等)
exclude_branch_prefixes:
  - release/
  - backport/

test_command: "make test"            # CI 確認用、未設定なら package.json/Makefile/pubspec.yaml から推測
format_command: "make format"        # フォーマット差分確認用 (auto-fix 用ではない)
merge_method: "auto"                 # auto / merge / squash / rebase
ci_check_name: ""                    # 例: "Flutter Tests" / "ci/test" / 空なら全 check 集約
conventions_file: "AGENTS.md"        # テスト方針との照らし合わせに使う規約ファイル
allow_dependency_only_merges: true   # Dependabot 等の lockfile-only PR を自動マージしてよいか
---

# プロジェクト固有の注意点
（任意のメモ）
```

各キーの意味:

- **`bot_authors`** — `gh pr view --json author --jq '.author.login'` の値と完全一致で判定。未設定時のデフォルトは[SKILL.md の bot 表](../SKILL.md) のすべての login。
- **`branch_prefixes`** — このリストのいずれかで始まるブランチ名の PR のみ対象。未設定時は `chore/codex-refactor-`, `copilot/`, `coderabbit/`, `dependabot/`, `renovate/`。
- **`exclude_branch_prefixes`** — `release/` / `backport/` 等、bot 由来でも対象外にしたい prefix。
- **`test_command` / `format_command`** — 未設定なら `package.json` の `scripts.test` / `Makefile` の `test` ターゲット / `pubspec.yaml` 周辺 (`flutter test` or `fvm flutter test`) を自動推測。
- **`merge_method: auto`** — `gh api repos/{owner}/{repo}` の `allow_squash_merge` / `allow_merge_commit` / `allow_rebase_merge` を読んで、squash → merge → rebase の優先順で有効なものを使う。
- **`ci_check_name`** — 判定に使う CI チェック名。未指定なら `gh pr view --json statusCheckRollup` の全 check を集約。
- **`conventions_file`** — テスト方針との照らし合わせで参照するプロジェクト規約ファイル (`AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md`)。
- **`allow_dependency_only_merges`** — Dependabot / Renovate のように **lockfile + manifest のみ変更**する PR をどう扱うか。`true` で、minor/patch・必須 CI 成功・レビュー通過・マージ許可があればマージ。`false` なら自動マージせず保留として報告する。

