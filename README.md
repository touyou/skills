# skills

touyou 個人の Agent Skills 集。**Claude Code** と **OpenAI Codex** の両方で同じスキル群を利用できる。

## インストール

### Claude Code

```sh
/plugin marketplace add touyou/skills
/plugin install writing-pack@touyou-skills    # 日本語ライティング系
/plugin install quality-pack@touyou-skills    # コード品質計測系
/plugin install dev-flow-pack@touyou-skills   # PR・チケット・bot 自動化系
```

プラグインは目的別に分かれているので、必要なものだけ入れて OK。

### OpenAI Codex

```sh
codex plugin marketplace add touyou/skills
# その後、Codex の `/plugins` から `touyou-skills` をインストール
```

Codex 側はプラグインを 1 つ (`touyou-skills`) に集約してあり、配下の全スキルが一括で有効になる。

## プラグイン / スキル一覧

| Claude Plugin | Codex Plugin | Skill | 用途 |
| --- | --- | --- | --- |
| `writing-pack` | `touyou-skills` | [`proofread-touyou`](./skills/proofread-touyou/SKILL.md) | touyou が書いた日本語の文章を AI 臭を残さずに校正する |
| `quality-pack` | `touyou-skills` | [`code-quality-scorer`](./skills/code-quality-scorer/SKILL.md) | コードベースの品質をコミット単位でスコアリングし、Tier 1 (決定論的ツール) / Tier 2 (LLM judge) / Tier 3 (UI ロジック量) を分けて報告する。TypeScript Web / Dart Flutter / Swift iOS が本実装、Kotlin Android は skeleton |
| `dev-flow-pack` | `touyou-skills` | [`ai-bot-pr-review`](./skills/ai-bot-pr-review/SKILL.md) | AI bot (Codex / Copilot / CodeRabbit / Devin / Dependabot 系) が自動生成した PR を一括レビューして approve→マージ or クローズ。`.claude/ai-bot-pr-review.local.md` で対象 bot author / ブランチ prefix / マージ方式を設定可能 |
| `dev-flow-pack` | `touyou-skills` | [`pr-review-loop`](./skills/pr-review-loop/SKILL.md) | PR に対してレビュー → 修正 → 再レビューを「指摘がなくなるまで」自動で繰り返す。自分の PR なら auto-fix、他人/bot の PR なら comment-only にモードを自動切替。レビューエージェントは `pr-review-toolkit` プラグイン互換 |
| `dev-flow-pack` | `touyou-skills` | [`ticket-implementation`](./skills/ticket-implementation/SKILL.md) | Notion / Linear / GitHub Issue / Plain text のチケットを渡したら、実装計画 → ブランチ作成 → 実装 → テスト → コミット → PR 作成まで一気通貫。reviewer ルール・ブランチ prefix・コード生成は `.claude/ticket-implementation.local.md` で設定 |

各スキルは [Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) に準拠した `SKILL.md` を持つ。frontmatter の `description` をエージェントが読んで、ユーザーの依頼に応じて自動で呼び出すかを判断する。

## 使い方の例

各スキルは、ユーザーが自然言語で依頼するか `/<skill-name>` で明示起動する。

### `proofread-touyou`

```
このesa記事の校正お願い
```
touyou 名義の日本語文章に AI 臭を入れずに誤字脱字・事実誤認だけ指摘する。文体・リズム・ゆらぎは保護対象。

### `code-quality-scorer`

```
このプロジェクトを採点して
品質トレンドを見たい
AIで書いたコードの質を測りたい
```
Tier 1 (決定論的ツール) / Tier 2 (LLM judge, N=3 独立判定) / Tier 3 (UI ロジック量) を分けて報告。`scripts/score_history.py` で履歴 walk、`scripts/run_bus_factor.py` で bus factor delta も取れる。

### `ai-bot-pr-review`

```
bot の PR をまとめてレビューして
dependabot のやつ approve していい？
codex の PR お願い
```
`gh pr list` から bot author の open PR を集めて、カテゴリ別 (テスト追加 / 依存更新 / 自動修正) にレビューしてマージ or クローズ。

リポジトリ固有の挙動は `.claude/ai-bot-pr-review.local.md` で設定:

```markdown
---
bot_authors:
  - app/github-actions
  - dependabot[bot]
branch_prefixes:
  - chore/codex-refactor-
  - dependabot/
test_command: "make test"
merge_method: "auto"
allow_dependency_only_merges: true
---
```

### `pr-review-loop`

```
/pr-review-loop 1234
このPRのレビュー回して
PR #1234 を指摘がなくなるまでレビューして
/pr-review-loop 1234 --comment-only   # auto-fix を無効化したい場合
```
PR author が自分なら **auto-fix** (修正 → push まで)、他人/bot なら **comment-only** (REQUEST_CHANGES / APPROVE をインラインコメント付きで投稿) を既定にする。同一指摘 2 回失敗で Discussion 格上げして無限ループを構造的に防止。

リポジトリ固有の挙動は `.claude/pr-review-loop.local.md` で設定:

```markdown
---
test_command: "make test"
format_command: "make format"
conventions_file: "AGENTS.md"
review_agents:
  required:
    - pr-review-toolkit:code-reviewer
    - pr-review-toolkit:silent-failure-hunter
---
```

### `ticket-implementation`

```
/ticket https://www.notion.so/team/...
/ticket https://linear.app/team/issue/TEAM-123
/ticket #1234                           # 現在のリポジトリの GitHub Issue
このチケットを実装して
```
チケット URL のドメインで Source (Notion / Linear / GitHub Issue) を自動判別、本文を貼り付けた場合は Plain text として読む。`結論 → 要件 → コメント → 概要` の優先順位で要件抽出 → コード実態を Grep で検証 → ブランチ作成 → 実装 → テスト → PR 作成。

リポジトリ固有の挙動は `.claude/ticket-implementation.local.md` で設定:

```markdown
---
branch_prefix_rules:
  feature: "feat/"
  fix: "fix/"
test_command: "make test"
codegen_command: "make codegen"
reviewer_rules:
  - if_author: "alice"
    add_reviewer: "bob"
  - if_author: "bob"
    add_reviewer: "alice"
forbidden_paths:
  - "lib/gen"
  - "openapi/"
post_merge_hooks:
  - skill: "update-spec"
    when_changed: ["lib/app/pages/"]
---
```

## 開発・運用ルール

開発手順、ディレクトリ構造の詳細、新しいスキルを追加するときの手順、プラグイン切り分けの方針などは [`AGENTS.md`](./AGENTS.md) を参照 (Claude Code は `CLAUDE.md` 経由で同じファイルを読む)。
