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
| **Notion** | URL に `notion.so` / `notion.com` | 利用可能な Notion コネクタ / MCP |
| **Linear** | URL に `linear.app` | Linear MCP / CLI |
| **GitHub Issue** | URL に `github.com/.../issues/N` | `gh issue view` |
| **Plain text** | URL なし、本文を直接 | そのまま使う (ステータス更新は対象外) |

## ワークフローの核

1. **チケット読み取り** (Source 別、並列実行)
2. **ステータスを「着手中」に更新** (依頼・運用で許可されている場合。失敗は報告)
3. **タスク分析**: 結論 → 要件 → コメント (新しい順) → 概要 → 備考 の優先順位
4. **コード実態の検証**: チケット記述を鵜呑みにせず 検索・参照 で実コード確認。構造は現在コード、期待動作は合意済み要件を基準にする
5. **実装計画**: ブランチ名 / 変更対象ファイル / 親チケットならサブと依頼範囲を照合
6. **実装 + テスト** (`<testing_policy>` に従う)
7. **コミット + PR 作成** (`<pr_template>` + assignee + reviewer)
8. **完了報告**: PR・テスト・状態更新を報告。マージ後のフックは実際のマージと追加作業の依頼がある場合のみ

## バッチモード / 親チケット

- 複数 URL をスペース区切りで渡すと並列 (独立) or 直列 (依存チェーン) で処理
- 親チケットは未着手サブと依頼範囲を照合し、対象が曖昧な場合だけ選択を求める

## 仕様ベースのテスト

実装コードを正にして「実装と一致するだけ」のテストは実装のバグもテストに組み込んで検出能力を失う。代わりに:

- テストケースは **仕様 (チケット要件 / API 仕様 / 合意事項) から導出**
- 期待値は実装から読み取らない
- テスト記述は仕様の言葉で書く (例: `test('広告クリック時に creativeId と slotSlug が API に送信される')` ← OK、`test('postCreativeClick が呼ばれる')` ← NG)
- 仕様とコードの不一致を発見したら **テストは仕様通り、失敗したら実装のバグとして修正**

## プロジェクト固有設定 (`.claude/ticket-implementation.local.md`)

設定の完全版は [references/configuration.md](references/configuration.md) を参照。

## 依存

- `gh` CLI と GitHub 認証
- Source に応じた MCP / CLI (Notion MCP / Linear MCP 等)

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。habee-app (Flutter + Notion 運用) で運用していた `ticket` スキルを汎用化し、Source を pluggable な構造に再設計したもの。
