# skills

touyou 個人の Agent Skills 集。**Claude Code** と **OpenAI Codex** の両方で同じスキル群を利用できる。

## インストール

### Claude Code

```sh
/plugin marketplace add touyou/skills
/plugin install writing-pack@touyou-skills    # 日本語ライティング系
/plugin install quality-pack@touyou-skills    # コード品質計測系
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

各スキルは [Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) に準拠した `SKILL.md` を持つ。frontmatter の `description` をエージェントが読んで、ユーザーの依頼に応じて自動で呼び出すかを判断する。

## 開発・運用ルール

開発手順、ディレクトリ構造の詳細、新しいスキルを追加するときの手順、プラグイン切り分けの方針などは [`AGENTS.md`](./AGENTS.md) を参照 (Claude Code は `CLAUDE.md` 経由で同じファイルを読む)。
