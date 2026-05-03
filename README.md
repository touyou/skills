# skills

touyou個人のClaude Code用スキル集。Claude Code marketplace として配布される。

## インストール（Claude Code）

```sh
/plugin marketplace add touyou/skills
/plugin install writing-pack@touyou-skills
```

## スキル / プラグイン一覧

| Plugin | Skill | 用途 |
| --- | --- | --- |
| `writing-pack` | `proofread-touyou` | touyouが書いた日本語の文章をAI臭を残さずに校正する |

## リポジトリ構造

```
skills/
├── .claude-plugin/
│   └── marketplace.json    # marketplace metadata
├── skills/                 # スキル本体
│   └── proofread-touyou/
│       └── SKILL.md
├── .gitignore
└── README.md
```

各スキルディレクトリは [Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) に準拠。`SKILL.md` の frontmatter にある `description` をもとに、Claudeが自動でスキルを呼び出すかを判断する。

## ローカル開発（symlinkでの読み込み）

このリポジトリを開発しながら直接Claude Codeに読ませたいときは、`~/.agents/skills/` 配下にシンボリックリンクを張る:

```sh
ln -s ~/Developer/Private/skills/skills/<skill-name> ~/.agents/skills/<skill-name>
ln -s ../../.agents/skills/<skill-name> ~/.claude/skills/<skill-name>
```

（`.claude/skills` は `.agents/skills` を経由する間接参照を採用。touyouの既存セットアップに合わせている）

## 新しいスキルを追加するときの手順

1. `skills/<skill-name>/SKILL.md` を作成（YAML frontmatter 必須: `name`, `description`）
2. `.claude-plugin/marketplace.json` の対応する plugin の `skills` 配列に `./skills/<skill-name>` を追加（または新規 plugin として追加）
3. このREADMEの一覧テーブルに行追加
4. ローカルでシンボリックリンクを張って動作確認
5. コミット
