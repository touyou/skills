---
name: ai-bot-pr-review
description: AI bot が作った PR を一括レビューし、マージ・クローズ・保留を判定する。「bot の PR をレビュー」「Dependabot をまとめて処理」「自動生成 PR をマージ」の依頼に使う。実際の投稿・マージ・クローズは依頼で許可された範囲に限る。単一 PR の修正ループは pr-review-loop が担当する。
license: MIT
metadata:
  author: touyou
  version: "0.2.1"
---

# AI bot が生成した PR の一括レビュー

GitHub Actions / GitHub Apps 経由で自動生成された PR を一括処理する。妥当なものは approve → マージ、問題があるものはクローズする。

投稿・approve・マージ・クローズは、今回の依頼と既存の許可に含まれる操作だけ行う。「レビューして」だけなら判定を返し、外部操作が必要な場合は対象 PR と完成した理由文を提示して確認する。マージまで依頼済みなら再確認しない。設定ファイルは操作の許可を追加しない。

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

## 設定

既存の `.claude/ai-bot-pr-review.local.md` を両エージェント共通で読む。設定ファイルを作成する場合や既定値を調べる場合だけ、[references/configuration.md](references/configuration.md) の完全版を読む。コマンド例は設定例であり、対象リポジトリの規約・CI・利用可能なツールから実行コマンドを決める。

## 対象 PR の特定

```bash
# bot_authors の各 author について open PR を取得し、merge する
gh pr list --state open --limit 1000 --json number,title,headRefName,body,author,labels \
  --search "is:open is:pr" \
  | jq --argjson allowed_authors "$BOT_AUTHORS_JSON" \
       --argjson allowed_prefixes "$BRANCH_PREFIXES_JSON" \
       --argjson exclude_prefixes "$EXCLUDE_PREFIXES_JSON" \
       'map(select(
          (.author.login | IN($allowed_authors[]))
          and ([.headRefName | startswith($allowed_prefixes[])] | any)
          and ([.headRefName | startswith($exclude_prefixes[])] | any | not)
        ))'
```

prefix 判定は `[... | startswith($prefixes[])] | any` の形にする (`startswith($prefixes[])` を裸で `select` に渡すとストリーム展開で PR が重複したり、除外判定が「1つでも不一致なら通過」の意味になる)。`exclude_prefixes` が空のときは `any` が `false` → `not` で `true` になり、全 PR が通過する (意図通り)。

取得件数が上限に達した場合は検索範囲を分割するか API をページングし、未取得があるまま「全件」と報告しない。

**判別優先順**:

0. **exclude_branch_prefixes に一致** → 常に対象外（補助マッチより優先）
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
- **対象 CI の結果が不明 / PENDING / 未登録** → 保留して報告。ローカルテストは原因調査の補助であり、必須 CI の代替にしない。自分がテストした SHA を記録する

`ci_check_name` を指定していても、リポジトリの他の必須チェックを省略しない。チェック 0 件を成功扱いしない。

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

### マージ前ゲート: mergeStateStatus

CI が緑でも、それは**その PR のベースコミット時点の main に対する保証**でしかない。CI 緑の PR を複数連続でマージすると、コンフリクトマーカーは出ないのに組み合わせるとコンパイル不能・挙動不整合になるセマンティックコンフリクトが起きうる。approve 後、`gh pr merge` を実行する**直前**に必ず確認する:

```bash
gh pr view <number> --json mergeStateStatus --jq '.mergeStateStatus'
```

| mergeStateStatus | 対応 |
|---|---|
| `CLEAN` | レビュー済み SHA・必須 CI・許可を満たす場合にマージ可。意味上の競合がない保証ではない |
| `BEHIND` | `gh pr update-branch <number>` → CI 再完走を待ってから再判定 |
| `DIRTY` | コンフリクト解消が必要。スキップしてユーザーに戻す |
| `BLOCKED` / `UNSTABLE` | CI・レビュー要件が未完。完了を待つか、スキップして報告 |
| `UNKNOWN` / 未知の状態 | 最大 2 回再取得。それでも未確定なら保留 |

複数 PR を処理するときは**マージを直列に行う**: 1 件マージ → 次の PR の `mergeStateStatus` を再取得 → 判定、の順で進める。並列にマージするとこのゲートをすり抜ける (先にマージした PR によって残りの PR が `BEHIND` になるのを検出できない)。

### マージ方法

`merge_method=auto` の場合、リポジトリの merge 許可設定を読んで `gh pr merge` のフラグを切り替える:

```bash
SETTINGS=$(gh api repos/<owner>/<repo> --jq '{squash: .allow_squash_merge, merge: .allow_merge_commit, rebase: .allow_rebase_merge}')
# squash → merge → rebase の優先順で、有効なものを使う
```

```bash
gh pr review <number> --approve --body "LGTM — <カテゴリ> として確認済み。"
gh pr merge <number> <--squash|--merge|--rebase> --match-head-commit "$REVIEWED_HEAD"
```

レビュー開始時の head SHA を `REVIEWED_HEAD` に記録する。branch 更新や他者の push で SHA が変わった場合は新差分と CI を確認してから判定を更新する。自分が author の PR は自己 approve を試みず、承認要件を別途満たす。マージ後は PR の実状態を取得し、キュー登録をマージ済みと報告しない。`--match-head-commit` の詳細は [GitHub CLI](https://cli.github.com/manual/gh_pr_merge) を参照する。

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
