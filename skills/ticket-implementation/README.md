# ticket-implementation

チケット URL またはチケット本文を渡されたら、実装計画 → ブランチ作成 → 実装 → テスト → コミット → PR 作成まで一気通貫で実行する。

## いつ発動するか

```
/ticket https://www.notion.so/team/...
/ticket https://linear.app/team/issue/TEAM-123
/ticket https://github.com/owner/repo/issues/1234
/ticket #1234                 # 現在のリポジトリの GitHub Issue
このチケットを実装して
Linear のissue やって
issue #123 着手
```

引数なしでチケット本文を貼り付けて渡してもよい (Plain text mode)。

## 対応 Source

| Source | 判別 | 読み取り |
|--------|------|----------|
| **Notion** | URL に `notion.so` / `notion.com` | Notion MCP (`mcp__notion-api__*`) |
| **Linear** | URL に `linear.app` | Linear MCP / CLI |
| **GitHub Issue** | URL に `github.com/.../issues/N` | `gh issue view` |
| **Plain text** | URL なし、本文を直接 | そのまま使う (ステータス更新は対象外) |

## ワークフローの核

1. **チケット読み取り** (Source 別、並列実行)
2. **ステータスを「着手中」に更新** (Source が許せばベストエフォート)
3. **タスク分析**: 結論 → 要件 → コメント (新しい順) → 概要 → 備考 の優先順位
4. **コード実態の検証**: チケット記述を鵜呑みにせず Grep / Read で実コード確認。乖離があれば現在のコードを正にして指摘してから進める
5. **実装計画**: ブランチ名 / 変更対象ファイル / 親チケットならサブを一覧してユーザー選択
6. **実装 + テスト** (`<testing_policy>` に従う)
7. **コミット + PR 作成** (`<pr_template>` + assignee + reviewer)
8. **マージ後フック** (`post_merge_hooks`): path 条件付きで別スキルを起動

## バッチモード / 親チケット

- 複数 URL をスペース区切りで渡すと並列 (独立) or 直列 (依存チェーン) で処理
- サブアイテムを持つ親チケットは未着手サブを一覧表示 → ユーザー選択 → バッチ実行 (勝手に始めない)

## 仕様ベースのテスト

実装コードを正にして「実装と一致するだけ」のテストは実装のバグもテストに組み込んで検出能力を失う。代わりに:

- テストケースは **仕様 (チケット要件 / API 仕様 / 合意事項) から導出**
- 期待値は実装から読み取らない
- テスト記述は仕様の言葉で書く (例: `test('広告クリック時に creativeId と slotSlug が API に送信される')` ← OK、`test('postCreativeClick が呼ばれる')` ← NG)
- 仕様とコードの不一致を発見したら **テストは仕様通り、失敗したら実装のバグとして修正**

## プロジェクト固有設定 (`.claude/ticket-implementation.local.md`)

```markdown
---
branch_prefix_rules:
  feature: "feat/"
  fix: "fix/"
  ui: "ui/"
  bug: "bug/"
  refactor: "refact/"
  default: "feat/"
branch_naming_doc: "docs/BRANCH_RULE.md"

test_command: "make test"
format_command: "make format"
codegen_command: "make codegen"
codegen_triggers:
  - "openapi/"
  - "lib/**/*.dart"

conventions_file: "AGENTS.md"
testing_policy: "仕様ベース"     # "仕様ベース" or "実装ベース"
pr_template: ".github/PULL_REQUEST_TEMPLATE.md"

reviewer_rules:
  - if_author: "alice"
    add_reviewer: "bob"
  - if_author: "bob"
    add_reviewer: "alice"

notion:
  status_property: "Status"
  status_in_progress: "着手中"
  status_review: "レビュー"
  status_done: "完了"

forbidden_paths:
  - "lib/gen"
  - "lib/api_definitions"
  - "openapi/"

post_merge_hooks:
  - skill: "update-spec"
    when_changed: ["lib/app/pages/"]
---
```

## 依存

- `gh` CLI と GitHub 認証
- Source に応じた MCP / CLI (Notion MCP / Linear MCP 等)

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。habee-app (Flutter + Notion 運用) で運用していた `ticket` スキルを汎用化し、Source を pluggable な構造に再設計したもの。
