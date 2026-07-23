# skills

touyou 個人の Agent Skills 集。**Claude Code** と **OpenAI Codex** の両方で同じスキル群を利用できる。

## インストール

### Claude Code

```sh
/plugin marketplace add touyou/skills
/plugin install writing-pack@touyou-skills    # 日本語ライティング系
/plugin install quality-pack@touyou-skills    # コード品質計測系
/plugin install dev-flow-pack@touyou-skills   # PR・チケット・bot 自動化系
/plugin install a11y-pack@touyou-skills       # Apple プラットフォームのアクセシビリティ対応
/plugin install meta-pack@touyou-skills       # このリポジトリ自体の運用・拡充支援
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
| `writing-pack` | `touyou-skills` | [`proofread-touyou`](./skills/proofread-touyou/) | touyou が書いた日本語の文章を AI 臭を残さずに校正する |
| `writing-pack` | `touyou-skills` | [`write-touyou`](./skills/write-touyou/) | touyou 名義で日本語の文章を新しく書く (生成・執筆・下書き)。本人の肉声で書き AI 臭を避ける |
| `quality-pack` | `touyou-skills` | [`code-quality-scorer`](./skills/code-quality-scorer/) | コードベース品質をコミット単位でスコアリング。Tier 1 (決定論的ツール) / Tier 2 (LLM judge) / Tier 3 (UI ロジック量) を分けて報告。TS Web / Dart Flutter / Swift iOS が本実装、Kotlin Android は skeleton |
| `dev-flow-pack` | `touyou-skills` | [`ai-bot-pr-review`](./skills/ai-bot-pr-review/) | AI bot (Codex / Copilot / CodeRabbit / Devin / Dependabot 系) が自動生成した PR を一括レビューして approve→マージ or クローズ |
| `dev-flow-pack` | `touyou-skills` | [`pr-review-loop`](./skills/pr-review-loop/) | PR にレビュー → 修正 → 再レビューを「指摘がなくなるまで」繰り返す。自分の PR=auto-fix / 他人=comment-only に自動切替 |
| `dev-flow-pack` | `touyou-skills` | [`review-followup`](./skills/review-followup/) | 過去に自分がレビューコメントを付けた PR を横断スキャンし、対応をコミット diff で裏取りしてから approve する |
| `dev-flow-pack` | `touyou-skills` | [`parallel-review-harness`](./skills/parallel-review-harness/) | 任意のレビュー観点を N 個の独立レビューアに割り当てて並列レビュー。実行環境を自己診断して二系統クロス / 単系統並列 / 逐次マルチパスに自動フォールバック |
| `dev-flow-pack` | `touyou-skills` | [`ticket-implementation`](./skills/ticket-implementation/) | Notion / Linear / GitHub Issue / Plain text のチケットから実装 → テスト → PR 作成まで一気通貫 |
| `dev-flow-pack` | `touyou-skills` | [`fresh-session-e2e`](./skills/fresh-session-e2e/) | 配布物の初回導入 UX を、/tmp の空ディレクトリ + 別プロセスのゼロコンテキストセッション + 固定再現プロンプトで E2E 検証する |
| `a11y-pack` | `touyou-skills` | [`apple-accessibility`](./skills/apple-accessibility/) | SwiftUI / UIKit のアクセシビリティ実装・レビュー。HIG の Vision / Mobility / Cognitive / Hearing / Speech チェックリストと実装パターン集 |
| `meta-pack` | `touyou-skills` | [`harness-intake`](./skills/harness-intake/) | 実プロジェクトで磨いた AI エージェントハーネスの汎用パターンを、touyou/skills への GitHub Issue として起票する |
| `meta-pack` | `touyou-skills` | [`retrospective`](./skills/retrospective/) | セッション失敗と PR 指摘の「繰り返し」を掘り起こし、AGENTS.md / スキル / memory への恒久ルール候補として提示する |

各スキルは [Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) に準拠した `SKILL.md` を持つ。スキルディレクトリの `README.md` には呼び出し例・`.local.md` の設定例など外向きの紹介、`SKILL.md` にはエージェント起動用の正式な仕様を書いている。

## 開発・運用ルール

開発手順、ディレクトリ構造の詳細、新しいスキルを追加するときの手順、プラグイン切り分けの方針などは [`AGENTS.md`](./AGENTS.md) を参照 (Claude Code は `CLAUDE.md` 経由で同じファイルを読む)。
