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

## 何をするか

チケットを読み、現在のコードと突き合わせて計画を立て、実装・テスト・PR 作成まで進める。テストはチケットの仕様から書き、実装に合わせて期待値を決めない。複数のチケットや親チケットもまとめて扱える。

## プロジェクト固有設定 (`.claude/ticket-implementation.local.md`)

設定の完全版は [references/configuration.md](references/configuration.md) を参照。

## 依存

- `gh` CLI と GitHub 認証
- Source に応じた MCP / CLI (Notion MCP / Linear MCP 等)

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。Flutter + Notion 運用のリポジトリで使っていた `ticket` スキルを汎用化し、Source を pluggable な構造に再設計したもの。
