# Repository Guidelines

このリポジトリの開発・運用ルール。Claude Code (`CLAUDE.md` → このファイルへの symlink) と OpenAI Codex (`AGENTS.md` 直接) の両方が読む。

## 何のリポジトリか

touyou 個人の **Agent Skills 集** を Claude Code と Codex の両方の marketplace で配布するリポジトリ。スキル本体は `skills/<name>/SKILL.md` 中心の共通フォーマット ([Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview))。同じ `skills/` を 2 つの marketplace 設定 (`.claude-plugin/marketplace.json` / `.agents/plugins/marketplace.json` + `.codex-plugin/plugin.json`) から指すことで、片方のフォークやコピーを作らずに済ませる。

## ディレクトリ構造

```
skills/                       ← 単一のソース。スキル本体はすべてここ
├── proofread-touyou/
│   └── SKILL.md
└── code-quality-scorer/
    ├── SKILL.md              ← 使い方 / 設計 / 動作モード
    ├── ROADMAP.md            ← 開発者向け引き継ぎ文書
    ├── references/           ← 言語別プロファイル + ルーブリック
    ├── scripts/              ← Tier 1 / 2 / 3 / aggregate / trend / bus_factor
    └── evals/                ← eval ハーネス (将来用)

.claude-plugin/
└── marketplace.json          ← Claude Code 用 (writing-pack / quality-pack の 2 plugin に分離)

.codex-plugin/
└── plugin.json               ← Codex 用 (touyou-skills 1 plugin として全 skill を提供)

.agents/
└── plugins/
    └── marketplace.json      ← Codex 用 marketplace 定義 (リポジトリ単独で publish 可能にする)

AGENTS.md                     ← この文書 (実体)
CLAUDE.md                     ← AGENTS.md への symlink
README.md                     ← 公開向け (インストール案内 + スキル一覧)
```

スキルによっては `SKILL.md` 1 枚で完結するものと、`scripts/` や `references/` を持つ複合スキルがある。後者でも entry point は `SKILL.md` なので、エージェントは `SKILL.md` を起点に必要なリソースを参照する。

## ローカル開発（symlink での読み込み）

開発しながら直接 Claude Code に読ませたいときは、`~/.agents/skills/` 配下にシンボリックリンクを張る:

```sh
ln -s ~/Developer/Private/skills/skills/<skill-name> ~/.agents/skills/<skill-name>
ln -s ../../.agents/skills/<skill-name> ~/.claude/skills/<skill-name>
```

(`.claude/skills` は `.agents/skills` を経由する間接参照。touyou の既存セットアップに合わせている)

Codex 側もデフォルトで `~/.agents/skills/` を読むので、上記 1 段目のリンクだけで Codex 用にも有効化される。

## 新しいスキルを追加するときの手順

1. `skills/<skill-name>/SKILL.md` を作成
   - YAML frontmatter 必須: `name`, `description`
   - 推奨: `license`, `metadata.author`, `metadata.version`
   - **description は invocation trigger になる** ので、ユーザーがこのスキルを呼びたくなる時の言い回しを複数含める
2. 必要に応じて `scripts/` / `references/` / `evals/` などの補助ディレクトリを追加。SKILL.md から相対パスで参照する
3. **Claude Code 側** (`.claude-plugin/marketplace.json`):
   - 既存プラグインの description と一致するなら、対応する plugin の `skills` 配列に `./skills/<skill-name>` を追加
   - **目的が既存プラグインと違うなら新プラグインを切る** (例: `writing-pack` = ライティング系 / `quality-pack` = コード品質計測系)
4. **Codex 側** (`.codex-plugin/plugin.json`):
   - `skills` フィールドが `./skills/` を指していれば自動で拾われるので、通常は何もしない
   - 新規スキルが `mcpServers` / `apps` / `hooks` を持つ場合は plugin.json 側にも追記
5. README のスキル一覧テーブルに行を追加
6. ローカルで symlink を張って動作確認
7. コミット

## プラグイン切り分けの方針 (Claude Code 側)

1 プラグイン = 1 つの目的領域、を緩く守る:

- **writing-pack**: 文章・コンテンツ系 (校正、リライト、翻訳)
- **quality-pack**: コード品質計測・分析系 (スコアリング、トレンド、bus factor)

新しい skill を追加するときは、既存プラグインの description と一致するなら同居 OK、ズレるなら別プラグインを切る判断を README / marketplace.json と一緒に行う。

Codex 側は `.codex-plugin/plugin.json` が「1 リポジトリ = 1 plugin」前提のため、現状は `touyou-skills` 1 plugin にすべての skill をまとめている (Codex でプラグイン分割が必要になったら、subdirectory に plugin.json を分けて `source.source = "git-subdir"` で marketplace から指す方式を検討)。

## バージョン管理

- 各 skill の `SKILL.md` frontmatter にある `metadata.version` は **skill 単位の semver** (例: code-quality-scorer は `"0.4.1"`)
- `.claude-plugin/marketplace.json` の `metadata.version` は **marketplace 全体の semver**
- `.codex-plugin/plugin.json` の `version` は **Codex plugin 全体の semver** (Claude marketplace と歩調を合わせる)
- 新規 skill 追加・plugin 構成変更は marketplace 側 minor bump、skill 内部の機能追加は skill 側 minor bump

## コミット / プルリクの方針

- 個人リポジトリなので main 直 push 可。ただし広範な構造変更や互換破壊は事前にメモを残す
- コミットメッセージは「変更の why」を 1〜3 文。長くなる場合は箇条書きの body を付ける
- Co-Authored-By trailer は AI と協働した場合に付ける

## このリポジトリで読むべきドキュメント

- スキル個別の仕様: `skills/<name>/SKILL.md` (常に entry point)
- スキル開発者引き継ぎ: 各 skill の `ROADMAP.md` (存在する場合)
- 公開向け: `README.md`
