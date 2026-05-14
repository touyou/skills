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

## 開発・運用ルール

開発手順、ディレクトリ構造の詳細、新しいスキルを追加するときの手順、プラグイン切り分けの方針などは [`AGENTS.md`](./AGENTS.md) を参照 (Claude Code は `CLAUDE.md` 経由で同じファイルを読む)。
