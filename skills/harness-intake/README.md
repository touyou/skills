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

## ワークフロー

変更点を特定し、汎用性と既存スキル・Issue を照合してドラフトを作る。起票まで依頼されていれば Issue を作成し、下書きだけの依頼なら本文を返す。起票できない場合は失敗を報告し、一意な名前の保留ファイルに保存する。タイムアウト時は既存 Issue を照合して二重投稿を避ける。

既定の提案先は touyou/skills。実際のスキル実装や PR は別の作業として扱う。完全な手順は [SKILL.md](SKILL.md) を参照する。

## 関連

- 過去実例: [touyou/skills#5](https://github.com/touyou/skills/issues/5)
  （iOS実装から得た a11y パターンを Issue 起票 → PR #6 で `apple-accessibility` に取り込み）
