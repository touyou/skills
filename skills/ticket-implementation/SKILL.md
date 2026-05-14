---
name: ticket-implementation
description: チケット URL またはチケット本文を渡されたら、内容を読み取って実装計画 → ブランチ作成 → 実装 → テスト → コミット → PR 作成まで一気通貫で実行する。Notion / Linear / GitHub Issue / plain text の各 source に対応。「結論 → 要件 → コメント → 概要」の優先順位で読み取り、チケット記述を鵜呑みにせずコード実態を Grep で検証してから実装に入る。ユーザーが「チケットを実装して」「このチケット対応して」「チケットからPR作って」「Notionチケットを実装」「Linear のissue やって」「issue #123 着手」と依頼した時、または `/ticket <URL or 本文>` を実行した時に発動する。
license: MIT
metadata:
  author: touyou
  version: "0.1.0"
---

# チケット → 実装 → PR

チケットを渡されたら、実装計画 → 実装 → PR 作成まで一気通貫で実行する。

「チケット」のソースは複数あり得る:

| Source | 判別 | 読み取り手段 |
|--------|------|-------------|
| **Notion** | URL に `notion.so` / `notion.com` | Notion MCP (`mcp__notion-api__*`) |
| **Linear** | URL に `linear.app` | Linear MCP (例: `linear` plugin) または Linear CLI |
| **GitHub Issue** | URL に `github.com/.../issues/N` | `gh issue view N --json title,body,comments,labels` |
| **Plain text** | URL なし、本文がそのまま渡される | 受け取った本文をそのまま使う |

Source 別の細かい手順 (ページ ID 抽出、ステータス遷移、コメント取得) は「Source 別補足」を参照。コア手順は source によらず同じ。

## 設定 (project ごと)

リポジトリのルートに `.claude/ticket-implementation.local.md` を置くと挙動を調整できる。

```markdown
---
# ブランチ命名 prefix のマッピング (チケット種別 → prefix)
branch_prefix_rules:
  feature: "feat/"
  fix: "fix/"
  ui: "ui/"
  bug: "bug/"
  refactor: "refact/"
  default: "feat/"

# ブランチ名フォーマット: <prefix><英語ケバブケース要約>
# 規約ファイル (例: docs/BRANCH_RULE.md) に詳細があるならここで指定
branch_naming_doc: "docs/BRANCH_RULE.md"

# テスト・フォーマット・コード生成
test_command: "make test"
format_command: "make format"
codegen_command: "make codegen"           # 任意。API 定義 / Freezed / Riverpod 等の生成が必要なときに
codegen_triggers:                         # この path 配下に変更があれば codegen 実行
  - "openapi/"
  - "lib/**/*.dart"  # @freezed / @riverpod アノテーションを含む可能性

# 規約・テスト方針の参照先
conventions_file: "AGENTS.md"             # AGENTS.md / CLAUDE.md / CONTRIBUTING.md
testing_policy: "仕様ベース"              # "仕様ベース" or "実装ベース"

# PR テンプレートとレビュアー
pr_template: ".github/PULL_REQUEST_TEMPLATE.md"
reviewer_rules:
  # 作成者 → 自動アサインするレビュアー (互いに見合いするペア)
  - if_author: "touyou"
    add_reviewer: "mnkd"
  - if_author: "mnkd"
    add_reviewer: "touyou"
  # マッチしない場合はユーザー確認

# Notion 専用 (Notion source のとき)
notion:
  status_property: "Status"
  status_in_progress: "着手中"
  status_review: "レビュー"
  status_done: "完了"

# 編集禁止ディレクトリ (生成物等)
forbidden_paths:
  - "lib/gen"
  - "lib/api_definitions"
  - "openapi/"

# 実装後に他スキルを起動するか
post_merge_hooks:
  - skill: "update-spec"
    when_changed: ["lib/app/pages/"]
---

# プロジェクト固有の注意点
（任意のメモ）
```

`test_command` / `format_command` / `codegen_command` 未設定時の自動推測は `ai-bot-pr-review` / `pr-review-loop` と同じ。

## ワークフロー

### 0. 入力の解釈

引数を解釈して **source** と **チケット識別子** を決める:

- 引数が URL → ドメインで source 判別
- 引数が `#NNN` または数値のみ → GitHub Issue (現在のリポジトリ)
- 引数なし or 本文っぽいテキスト → Plain text
- 複数の URL がスペース区切り → **バッチモード** (後述)

### 1. チケット読み取り

Source 別に並列で取得 (各ステップは並列実行可、一部失敗しても取れた情報で続行)。

#### Notion

```text
1) URL 末尾 32 文字からページ ID を抽出
2) 並列実行:
   - mcp__notion-api__API-retrieve-a-page  (プロパティ)
   - mcp__notion-api__API-get-block-children (本文)
   - mcp__notion-api__API-retrieve-a-comment (コメント)
3) サブアイテム (relation) を持つなら親チケットとして扱う (後述)
```

#### Linear

```text
1) URL から issue identifier (例: TEAM-123) を抽出
2) Linear MCP または `linear` CLI で issue / comments / sub-issues を取得
3) sub-issues があれば親チケットとして扱う
```

#### GitHub Issue

```bash
gh issue view <number> --json title,body,comments,labels,assignees,milestone
```

GitHub Issue の sub-issue (task list) は body の `- [ ]` チェックリストで擬似的に表現される。これも親チケット扱いの対象 (該当する場合)。

#### Plain text

ユーザーから渡された本文をそのままチケット内容として扱う。コメント・ステータスは無いものとして進める。

### 2. ステータスを「着手中」に更新

Source 別 (失敗しても処理は続行、ベストエフォート):

| Source | 操作 |
|--------|------|
| Notion | `mcp__notion-api__API-update-page` で `<status_property>` を `<status_in_progress>` に |
| Linear | Linear MCP で issue state を `In Progress` 相当に |
| GitHub Issue | `gh issue edit <N> --add-label in-progress` (label がプロジェクトにあれば) |
| Plain text | 何もしない |

### 3. タスク分析

取得情報から「**このプロジェクトで何を変更すべきか**」を特定する。

優先順位:

1. **結論** (チケットで明示されている「やること」)
2. **要件** (受け入れ条件 / 仕様)
3. **コメント** (新しい順で読む、後出しの仕様変更を見落とさないため)
4. **概要** (背景情報)
5. **備考**

判断ルール:

- **不明な点があれば実装前にユーザー確認** (勝手に判断しない)
- 自分側 (このプロジェクト側) の変更対象を特定する。バックエンド側 / 他プロジェクト側の変更は対象外として明示
- 親チケットの場合はサブチケットを一覧して、ユーザーが選んだものをバッチモードで実行 (勝手に着手しない)

### 4. コード実態の検証

**チケットの記述を鵜呑みにしない**。現在のコードベースを Grep / Read で実際に検証して、チケットと乖離があれば**現在のコードを正とする** (乖離があったらコメントで指摘してから進める)。

```bash
# チケットで言及されたシンボル / ファイルパスが実在するか
grep -rn "<symbol>" <relevant_dirs>
```

`<conventions_file>` (例: `AGENTS.md`) に「探索の起点」が書かれている場合はそれに従う。

### 5. 実装計画の決定

- **ブランチ名**: `<branch_prefix_rules>` のマッピングに従って prefix を決定、末尾は英語ケバブケースで簡潔に。`<branch_naming_doc>` があれば最終確認に使う。
- **変更対象ファイル**: コードベースを Grep / Glob で探索して列挙。`<forbidden_paths>` 配下は変更しない。
- **親チケットの場合**: 未対応のサブチケットを一覧提示し、ユーザーが選択したものをバッチモードで処理する。**勝手にサブの実装を始めない**。

### 6. 実装実行

1. **ワーキングツリーチェック**: uncommitted な変更があればユーザーに確認
2. **起点ブランチ**:
   - 独立チケット: `git checkout main && git pull origin main`
   - 依存チケット (バッチモード): 先行チケットのブランチを起点に
3. **新ブランチ**: `git checkout -b <ブランチ名>`
4. **実装**: `<conventions_file>` のコーディング規約に従う
5. **テスト**: `<testing_policy>` に従って構築
   - `仕様ベース` (推奨): チケットの仕様を正に書く。実装が間違っていたらテストが検出する
   - `実装ベース`: 実装の挙動をスナップショットする (regression 防止用途)
6. **フォーマット**: `<format_command>`
7. **テスト実行**: `<test_command>` (失敗したら修正)
8. **コード生成**: `<codegen_triggers>` の path に変更があれば `<codegen_command>` を実行

#### 仕様ベースのテストとは

実装コードを正にして「実装と一致する」だけのテストは、実装のバグもテストに組み込んでしまい検出能力を失う。代わりに:

- **テストケースは仕様 (チケット要件 / API 仕様 / 合意事項) から導出**
- **期待値は実装から読み取らない**
- **テスト記述は仕様の言葉で書く** (例: `test('広告クリック時に creativeId と slotSlug が API に送信される')` ← OK、`test('postCreativeClick が呼ばれる')` ← NG)
- 仕様とコードの不一致を発見したら **テストは仕様通りに書き、失敗したら実装のバグとして修正**

詳細: `<conventions_file>` のテストガイドラインと整合させる。

### 7. コミット & PR 作成

#### コミット

`<conventions_file>` のコミット規約に従う。慣例:

- gitmoji + 日本語 (例: `:sparkles: 日替わりチャレンジの通知設定を追加`)
- 既存のコミット履歴のスタイルに合わせる

#### PR

`<pr_template>` (`.github/PULL_REQUEST_TEMPLATE.md`) があればそのテンプレートに従って本文を組み立てる。共通項目:

- **チケットリンク**: `Notion Ticket: <URL>` / `Linear Issue: <URL>` / `Closes #<N>` を必ず含める
- **概要**: 変更内容の箇条書き
- **As-Is / To-Be**: 変更前後が明確な場合はテーブル
- **動作確認手順**: 検証手順を具体的に
- **画像 / 動画**: UI 変更があれば before/after

#### assignee / reviewer

```bash
# 自分を assignee に
CURRENT_USER=$(gh api /user --jq '.login')

# reviewer は <reviewer_rules> のマッチングで決定
# マッチしない場合はユーザー確認
gh pr create ... --assignee "$CURRENT_USER" --reviewer "<reviewer>"
```

reviewer rule に該当するものがなければ、空のまま PR 作成 → ユーザーに「reviewer 誰にする?」と確認。

### 8. マージ後の連携 (`post_merge_hooks`)

PR がマージされたら、`<post_merge_hooks>` に従って関連スキルを起動する:

```yaml
post_merge_hooks:
  - skill: "update-spec"
    when_changed: ["lib/app/pages/"]
```

例: マージした PR の diff に `lib/app/pages/` 配下の変更があれば、`update-spec` スキルを自動起動して関連ドキュメントを更新する。Source が Notion なら、ついでにチケットのステータスを `<status_review>` または `<status_done>` に更新。

## バッチモード

複数のチケット URL をスペース区切りで渡すと、依存関係を分析して並列 or 直列で処理する。

### 実行戦略

- **独立チケット** (依存関係なし) → `Agent` の `isolation: "worktree"` で**並列実行**
  - 各 worktree で `.env` 等の untracked file を参照できるよう、シンボリックリンクを張る:
    ```bash
    ln -s /path/to/original/.env /path/to/worktree/.env
    ```
- **依存チケット** → 直列処理し、先行ブランチを起点にチェーン
  - 例: チケット A → B (A の変更に依存)
    - A: main → branch-a → PR-A (base: main)
    - B: branch-a → branch-b → PR-B (base: branch-a)

### 依存判定

- B の要件が A の変更結果を前提としている
- 同じファイルを変更する可能性が高い
- チケット本文 / コメントで明示的に順序が指定されている

判断が難しければユーザー確認。

### エラーハンドリング

- 1 つのチケットが失敗しても残りは続行
- 依存チェーンで先行が失敗したら後続もスキップ
- 全完了後、結果をまとめて報告

## 親チケット

サブアイテムを持つ親チケットが渡された場合:

1. 親のサブアイテムを取得 (Notion `relation` プロパティ / Linear sub-issues / GitHub task list)
2. 各サブのステータス確認
3. 未着手・着手中のサブを一覧表示
4. ユーザーが選択したサブをバッチモードで実行

```
親チケット <ID> のサブチケット:
- [ ] <ID-1>: <タイトル>（未着手）
- [x] <ID-2>: <タイトル>（完了）
- [ ] <ID-3>: <タイトル>（未着手）

どのサブチケットを処理しますか？（スペース区切りで番号、または all で全未着手を処理）
```

**ユーザー確認なしに勝手にサブの実装を始めない**。

## 完了条件

- テストが全て通っている
- PR が作成されている
- PR 本文にチケットへのリンクがある
- assignee と reviewer が設定されている (reviewer は空の場合はユーザー確認済み)
- ステータスが適切に更新されている (Source 別)

## Source 別補足

### Notion

ページ ID 抽出 (URL 末尾 32 文字):

```bash
PAGE_ID=$(echo "$URL" | grep -oE '[0-9a-f]{32}' | tail -1)
```

ハイフンを 8-4-4-4-12 形式に整形してから API へ渡す (API が要求するため):

```bash
PAGE_ID_HYPHENATED=$(echo "$PAGE_ID" | sed -E 's/^(........)(....)(....)(....)(.{12})$/\1-\2-\3-\4-\5/')
```

### Linear

`linear` plugin が入っていれば MCP 経由、なければ `linear-cli` か web で手動取得。issue identifier (例: `TEAM-123`) の抽出は URL から:

```bash
ISSUE_ID=$(echo "$URL" | grep -oE '[A-Z]+-[0-9]+' | head -1)
```

### GitHub Issue

```bash
gh issue view <number> --json title,body,comments,labels,assignees,milestone,projectItems
```

Issue の task list (`- [ ]` チェックボックス) を sub-issue として扱う場合は body から正規表現で抽出。GitHub の "sub-issues" 機能 (Projects v2) は API で別途取得。

### Plain text

ユーザーが Notion / Linear / Jira / etc. の本文をそのまま貼り付けた場合。「結論 → 要件 → コメント → 概要 → 備考」の優先順位で抜き出すルールはそのまま使える。ステータス更新は対象外、コメント追加もできない (チケットシステムが分からないため)。

## 由来とブラッシュアップ方針

このスキルは habee-app (Flutter + Notion チケット運用) で運用していた `ticket` スキルを汎用化したもの。Notion API 特化だった読み取り処理を「Source 別の plugin 型」にし、reviewer ルール / branch prefix / `make codegen` / `lib/app/pages/` 等のプロジェクト固有要素を `.claude/ticket-implementation.local.md` に外出ししてある。

Notion 中心の運用は残しつつ、Linear / GitHub Issue / Plain text にも同じワークフローを適用できる構造。他プロジェクトで類似のチケット → PR ワークフローを動かしていたら、Source 別の読み取り処理と PR テンプレート連携の差分を集めてブラッシュアップする想定。

## 依存

- `gh` CLI と GitHub 認証
- Source に応じた MCP / CLI (Notion MCP / Linear MCP 等)
