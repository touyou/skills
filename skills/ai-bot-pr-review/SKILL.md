---
name: ai-bot-pr-review
description: AI bot (Codex / Copilot / CodeRabbit / Devin / Dependabot 系 / 任意の GitHub Actions bot) が自動生成した PR を一括レビューして、安全なものは approve→マージ、ロジックを壊しているものはクローズする。テストカバレッジ向上 PR / 依存アップデート PR / 自動修正 PR などを対象に、本体ファイルの改変が安全か / テストの妥当性 / CI 状態を確認して判定する。ユーザーが「bot の PR をレビューして」「自動生成 PR を一括処理して」「codex の PR お願い」「copilot PR マージして」「dependabot まとめて」「automated PR triage」と依頼した時、または `/ai-bot-pr-review` を実行した時に発動する。
license: MIT
metadata:
  author: touyou
  version: "0.1.0"
---

# AI bot が生成した PR の一括レビュー

GitHub Actions / GitHub Apps 経由で自動生成された PR を一括処理する。妥当なものは approve → マージ、問題があるものはクローズする。

主要な想定 bot:

| Bot | author (GitHub) | 典型用途 | ブランチ prefix の例 |
|---|---|---|---|
| Codex (GitHub Actions) | `app/github-actions` | テストカバレッジ向上 | `chore/codex-refactor-` |
| Copilot Workspace / SWE Agent | `copilot-swe-agent[bot]` / `app/github-actions` | 自動修正・テスト | `copilot/` |
| CodeRabbit (auto-fix) | `coderabbitai[bot]` | レビュー指摘の自動反映 | `coderabbit/` |
| Devin | `devin-ai-integration[bot]` | チケット → 実装 | 任意 |
| Dependabot | `dependabot[bot]` | 依存更新 | `dependabot/` |
| Renovate | `renovate[bot]` | 依存更新 | `renovate/` |
| 自作 Actions | `app/github-actions` | 何でも | 任意 |

「どの bot を対象にするか」「どんな PR が `bot` 由来か」はリポジトリごとに異なるので、**bot author の許可リスト**と**ブランチ prefix の許可リスト**で絞り込む設計にしてある。

## 設定 (project ごと)

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

- **`bot_authors`** — `gh pr view --json author --jq '.author.login'` の値と完全一致で判定。未設定時のデフォルトは上の表のすべての login。
- **`branch_prefixes`** — このリストのいずれかで始まるブランチ名の PR のみ対象。未設定時は `chore/codex-refactor-`, `copilot/`, `coderabbit/`, `dependabot/`, `renovate/`。
- **`exclude_branch_prefixes`** — `release/` / `backport/` 等、bot 由来でも対象外にしたい prefix。
- **`test_command` / `format_command`** — 未設定なら `package.json` の `scripts.test` / `Makefile` の `test` ターゲット / `pubspec.yaml` 周辺 (`flutter test` or `fvm flutter test`) を自動推測。
- **`merge_method: auto`** — `gh api repos/{owner}/{repo}` の `allow_squash_merge` / `allow_merge_commit` / `allow_rebase_merge` を読んで、squash → merge → rebase の優先順で有効なものを使う。
- **`ci_check_name`** — 判定に使う CI チェック名。未指定なら `gh pr view --json statusCheckRollup` の全 check を集約。
- **`conventions_file`** — テスト方針との照らし合わせで参照するプロジェクト規約ファイル (`AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md`)。
- **`allow_dependency_only_merges`** — Dependabot / Renovate のように **lockfile + manifest のみ変更**する PR をどう扱うか。`true` で、minor/patch かつ CI 成功なら自動マージ。`false` で、必ずユーザー確認。

## 対象 PR の特定

```bash
# bot_authors の各 author について open PR を取得し、merge する
gh pr list --state open --json number,title,headRefName,body,author,labels \
  --search "is:open is:pr" \
  | jq --argjson allowed_authors "$BOT_AUTHORS_JSON" \
       --argjson allowed_prefixes "$BRANCH_PREFIXES_JSON" \
       --argjson exclude_prefixes "$EXCLUDE_PREFIXES_JSON" \
       'map(select(
          (.author.login | IN($allowed_authors[]))
          and (.headRefName | startswith($allowed_prefixes[]))
          and (.headRefName | startswith($exclude_prefixes[]) | not)
        ))'
```

**判別優先順**:

1. **author × ブランチ prefix の両方マッチ** → 対象 (確実に bot 由来)
2. **author マッチ + prefix 不一致** → タイトル・body に `test` / `coverage` / `chore` / `deps` 等のキーワードがあれば「補助マッチ」としてユーザーに対象にしてよいか確認
3. **author 不一致** → スキップ

対象外の PR はスキップし、レビュー結果に「対象外 (リリース PR 等)」と報告する。

## 用途別カテゴリ判定

bot PR は中身がいくつかのタイプに分かれ、レビュー基準が変わる:

| カテゴリ | 判別シグナル | レビュー基準 |
|----------|--------------|--------------|
| **テスト追加** | テストファイルのみ変更 (`/test/` `__tests__/` `.test.` `.spec.` `_test.`) | テスタビリティ向上のリファクタは許容、本体ロジック変更は NG |
| **依存更新** | `package.json` / `pubspec.yaml` / `Cargo.toml` / `go.mod` などの manifest + lockfile のみ | minor/patch かつ CI 成功なら自動 OK、major bump は ユーザー確認 |
| **自動修正** | lint / format / typo / 自明な bug fix の変更 | 修正範囲が PR タイトル / body の宣言と一致しているか確認 |
| **大規模リファクタ** | 多数のファイル本体変更 | **このスキルでは扱わない**。人間レビュー必須としてスキップ |

## レビュー基準

### 1. 本体ファイル変更の安全性

```bash
gh pr diff <number> --name-only   # 変更ファイル一覧
gh pr diff <number>                # 差分の詳細
```

テスト追加カテゴリの場合:

- **テストファイルのみの変更** → OK
- **本体ファイルがフォーマット変更のみ** (改行位置・インデント) → OK
- **本体ファイルにテスタビリティ向上のリファクタ** (DI 追加、メソッド分割、可視性変更) → OK (元のロジックが保たれていれば許容)
- **本体ファイルのロジック変更** (条件分岐の変更、メソッド削除等) → NG (クローズ対象)

依存更新カテゴリの場合:

- **manifest + lockfile のみ** かつ **CI 成功** かつ **major bump なし** → OK
- **major bump** → ユーザー確認 (breaking change の可能性)
- **manifest + lockfile 以外のファイルが変更されている** → ユーザー確認 (典型的に CI 設定の追従が混ざる)

自動修正カテゴリの場合:

- PR タイトル / body の宣言 (例: 「未使用 import を削除」) と diff の内容が一致 → OK
- 宣言外の変更が混ざる → ユーザー確認

### 2. テストの妥当性 (テスト追加カテゴリのみ)

- テストが既存の stub / fixture パターン (`conventions_file` 参照) に従っているか
- **テストの期待値が仕様に基づいているか** (実装の丸写しではないか)
- 不要なテスト (自明すぎる / 重複する) が含まれていないか

実装コードを正にして「実装と一致する」だけのテストを書くと、実装のバグもテストに組み込まれて検出能力が失われる。**仕様を正に書かれているか**を見る。

### 3. CI 状態とテスト結果

```bash
gh pr checks <number>                                  # CI チェック状態
gh pr view <number> --json body --jq '.body'           # PR 説明からテスト結果
gh pr view <number> --json mergeable --jq '.mergeable' # コンフリクト確認
```

- **対象 CI (`ci_check_name`) が SUCCESS** → CI 確認 OK
- **対象 CI が FAILURE** → NG (クローズまたはスキップ)
- **対象 CI の結果が不明 / PENDING** → ローカルで `<test_command>` を実行して確認

PR 説明に bot の実行ログが含まれる場合、テスト結果 (pass/fail 件数) を読み取って参考にする。

## 判定とアクション

| 判定 | アクション |
|---|---|
| テスト追加 + テスト妥当 + 本体安全 + CI 通過 | approve → マージ |
| 依存更新 minor/patch + CI 通過 + `allow_dependency_only_merges=true` | approve → マージ |
| 依存更新 major bump | ユーザー確認 (skip → report) |
| 自動修正 + 宣言と diff 一致 + CI 通過 | approve → マージ |
| ロジックを壊している | クローズ + 具体的な理由コメント |
| テストの質が低い | クローズ + 理由コメント |
| CI 失敗で原因が PR 由来 | クローズ + 理由コメント |
| CI 失敗だが main 側の問題の可能性 | ローカルで `<test_command>` 実行して判断 |
| 大規模リファクタ / カテゴリ不明 | ユーザー確認 (skip → report) |
| リリース PR / バックポート等 | スキップ (対象外として報告) |

### マージ方法

`merge_method=auto` の場合、リポジトリの merge 許可設定を読んで `gh pr merge` のフラグを切り替える:

```bash
SETTINGS=$(gh api repos/<owner>/<repo> --jq '{squash: .allow_squash_merge, merge: .allow_merge_commit, rebase: .allow_rebase_merge}')
# squash → merge → rebase の優先順で、有効なものを使う
```

```bash
gh pr review <number> --approve --body "LGTM — <カテゴリ> として確認済み。"
gh pr merge <number> <--squash|--merge|--rebase>
```

approve コメントには「どのカテゴリ判定で、なぜ妥当と判断したか」を 1 行で書く (audit ログとして後で読める)。

### クローズ方法

```bash
gh pr close <number> --comment "クローズ理由: <具体的な理由>"
```

理由コメントには「どのファイルのどの行が問題か」を具体的に書く。bot が次回再生成する時の参考になる。

## レビュー結果の報告

全 PR のレビュー完了後、結果をテーブル形式で報告する:

| PR | author | カテゴリ | 内容 | 判定 | アクション |
|---|---|---|---|---|---|
| #1234 | app/github-actions | テスト追加 | XxxViewModel テスト追加 | OK | マージ済み |
| #1235 | dependabot[bot] | 依存更新 (patch) | bump foo 1.2.3 → 1.2.4 | OK | マージ済み |
| #1236 | app/github-actions | テスト追加 | △△ロジック変更あり | NG | クローズ |
| #1237 | dependabot[bot] | 依存更新 (major) | bump bar 2.x → 3.0 | — | スキップ (要確認) |
| #1238 | github-actions[bot] | リリース PR | — | — | 対象外 |

最後に**ユーザー確認待ち**の PR (major bump / カテゴリ不明 / 大規模リファクタ) をまとめて一覧する。

## 由来とブラッシュアップ方針

このスキルは habee-app (Flutter) で運用していた `codex-review` スキル (Codex GitHub Actions 専用) を、複数 bot 対応に汎用化したもの。`make test` / Flutter Tests / squash merge 無効 / `AGENTS.md` 等のプロジェクト固有要素を `.claude/ai-bot-pr-review.local.md` に外出ししてある。

他プロジェクトで類似の bot triage を運用していたら、`bot_authors` / `branch_prefixes` / カテゴリ判定の差分を集めて、このスキルの判定マトリクスをブラッシュアップする想定。
