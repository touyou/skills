# skills

touyou個人のClaude Code用スキル集。Claude Code marketplace として配布される。

## インストール（Claude Code）

```sh
/plugin marketplace add touyou/skills
/plugin install writing-pack@touyou-skills    # 日本語ライティング系
/plugin install quality-pack@touyou-skills    # コード品質計測系
```

プラグインは目的別に分かれているので、必要なものだけ入れて OK。

## プラグイン / スキル一覧

| Plugin | Skill | 用途 |
| --- | --- | --- |
| `writing-pack` | [`proofread-touyou`](./skills/proofread-touyou/SKILL.md) | touyouが書いた日本語の文章をAI臭を残さずに校正する |
| `quality-pack` | [`code-quality-scorer`](./skills/code-quality-scorer/SKILL.md) | コードベースの品質をコミット単位でスコアリングし、Tier 1 (決定論的ツール) / Tier 2 (LLM judge) / Tier 3 (UI ロジック量) を分けて報告する。TypeScript Web / Dart Flutter / Swift iOS が本実装、Kotlin Android は skeleton |

各スキルディレクトリは [Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) に準拠。`SKILL.md` の frontmatter にある `description` をもとに、Claude が自動でスキルを呼び出すかを判断する。

## リポジトリ構造

```
skills/
├── .claude-plugin/
│   └── marketplace.json    # marketplace metadata (touyou-skills)
├── skills/                 # スキル本体
│   ├── proofread-touyou/
│   │   └── SKILL.md
│   └── code-quality-scorer/
│       ├── SKILL.md        # 使い方 / 設計 / 動作モード
│       ├── ROADMAP.md      # 開発者向け引き継ぎ文書
│       ├── references/     # 言語別プロファイル + ルーブリック
│       ├── scripts/        # Tier 1 / 2 / 3 / aggregate / trend / bus_factor
│       └── evals/          # eval ハーネス (将来用)
├── .gitignore
└── README.md
```

スキルによっては `SKILL.md` 1 枚で完結するものと、`scripts/` や `references/` を持つ複合スキルがある。後者でも entry point は SKILL.md なので、Claude は SKILL.md を起点に必要なリソースを参照する。

## ローカル開発（symlinkでの読み込み）

このリポジトリを開発しながら直接Claude Codeに読ませたいときは、`~/.agents/skills/` 配下にシンボリックリンクを張る:

```sh
ln -s ~/Developer/Private/skills/skills/<skill-name> ~/.agents/skills/<skill-name>
ln -s ../../.agents/skills/<skill-name> ~/.claude/skills/<skill-name>
```

（`.claude/skills` は `.agents/skills` を経由する間接参照を採用。touyouの既存セットアップに合わせている）

## 新しいスキルを追加するときの手順

1. `skills/<skill-name>/SKILL.md` を作成（YAML frontmatter 必須: `name`, `description`、推奨: `license`, `metadata.author`, `metadata.version`）
2. 必要に応じて `scripts/`, `references/`, `evals/` などの補助ディレクトリを追加（SKILL.md から参照する形にする）
3. `.claude-plugin/marketplace.json` の対応する plugin の `skills` 配列に `./skills/<skill-name>` を追加。**目的が既存プラグインと違うなら新プラグインを切る**（例: `writing-pack` = ライティング系 / `quality-pack` = コード品質計測系）
4. このREADMEの一覧テーブルに行を追加
5. ローカルでシンボリックリンクを張って動作確認
6. コミット

## プラグイン切り分けの方針

1 プラグイン = 1 つの目的領域、を緩く守る:

- **writing-pack**: 文章・コンテンツ系 (校正、リライト、翻訳)
- **quality-pack**: コード品質計測・分析系 (スコアリング、トレンド、bus factor)

新しい skill を追加するときは、既存プラグインの description と一致するなら同居 OK、ズレるなら別プラグインを切る判断を README/marketplace.json と一緒に行う。
