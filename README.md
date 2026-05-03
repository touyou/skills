# skills

touyou個人のClaude Code用スキル集。

## 構造

```
skills/
  README.md
  <skill-name>/
    SKILL.md        # スキルの本体（YAML frontmatter + プロンプト）
    references/     # （任意）詳細ドキュメント
```

各スキルディレクトリは Claude Code の skill 仕様に準拠。`SKILL.md` の frontmatter にある `description` をもとに、Claude が自動でスキルを呼び出すかどうかを判断する。

## ローカルでの使い方

このリポジトリのスキルを Claude Code から使うには、`~/.agents/skills/` または `~/.claude/skills/` 配下にシンボリックリンクを張る:

```sh
ln -s ~/Developer/Private/skills/<skill-name> ~/.agents/skills/<skill-name>
ln -s ../../.agents/skills/<skill-name> ~/.claude/skills/<skill-name>
```

（`.claude/skills` は `.agents/skills` を経由する間接参照を採用している。touyouの既存セットアップに合わせている）

## スキル一覧

| Skill | 用途 |
| --- | --- |
| `proofread-touyou` | touyouが書いた日本語の文章をAI臭を残さずに校正する |

## 新しいスキルを追加するときの手順

1. `<skill-name>/SKILL.md` を作成（YAML frontmatter 必須: `name`, `description`）
2. このREADMEの「スキル一覧」テーブルに行追加
3. ローカルでシンボリックリンクを張って動作確認
4. コミット
