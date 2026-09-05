# プロジェクト設定

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
reviewer_rules: []                  # 必要なら if_author / add_reviewer の対応を設定
# マッチしない場合は未割当で作成し、その旨を報告

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

# マージが確認され、連携作業も依頼されている場合のみ実行する
post_merge_hooks: []                # 利用可能な skill / when_changed を必要に応じ指定
---

# プロジェクト固有の注意点
（任意のメモ）
```

`test_command` / `format_command` / `codegen_command` 未設定時の自動推測は プロジェクトの package.json / Makefile / pubspec.yaml と CI 定義から判断する。

