# harness-intake

実プロジェクトで磨いた AI エージェントハーネス（CLAUDE.md / AGENTS.md、`.claude/skills` ・
`agents` ・`hooks`、自動化スクリプト等）から汎用化できるパターンを見つけて、`touyou/skills`
リポジトリへの GitHub Issue として起票するスキル。取り込み（SKILL.md への実装・PR）は
`touyou/skills` 側で別途行う — このスキルは起票までを担当する。

`touyou/skills` の外、つまりハーネスを磨いている作業ディレクトリから呼び出す想定。

## いつ発動するか

```
このハーネス改善をskillsに提案して
touyou/skillsに起票して
この気づきをスキル側に取り込みたい
ハーネスの改善をIssue化して
/harness-intake
```

## 何をするか

変更点から汎用化できるパターンを見つけ、既存のスキルと Issue に照らしてから Issue の下書きを作る。起票まで頼まれたときだけ Issue を作る。既定の提案先は touyou/skills で、スキル本体への取り込みは別の作業として扱う。手順は [SKILL.md](SKILL.md) にある。

## 関連

- 過去実例: [touyou/skills#5](https://github.com/touyou/skills/issues/5)
  （iOS実装から得た a11y パターンを Issue 起票 → PR #6 で `apple-accessibility` に取り込み）
