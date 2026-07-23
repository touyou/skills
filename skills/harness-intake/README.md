# harness-intake

実プロジェクトで磨いた AI エージェントハーネス（CLAUDE.md / AGENTS.md、`.claude/skills` ・
`agents` ・`hooks`、自動化スクリプト等）から汎用化できるパターンを見つけて、`touyou/skills`
リポジトリへの GitHub Issue として起票するスキル。取り込み（SKILL.md への実装・PR）は
`touyou/skills` 側で別途行う — このスキルは起票までを担当する。

`touyou/skills` の外、つまりハーネスを磨いている作業ディレクトリ（例: jt 配下の
habee-app / habee-app-codex / momentia-app-harness、sparkle 配下の sparkle-design /
sparkle-design-internal など）から呼び出す想定。

## いつ発動するか

```
このハーネス改善をskillsに提案して
touyou/skillsに起票して
この気づきをスキル側に取り込みたい
ハーネスの改善をIssue化して
/harness-intake
```

## 動くこと / 動かないこと

- **やる**: 変更点の特定 → 汎用性判定 → touyou/skills 側の既存スキルとの照合 → Issue ドラフト
  作成 → ユーザー確認 → `gh issue create --repo touyou/skills`
- **やらない**: touyou/skills への直接コミット・PR 作成、呼び出し元プロジェクトのファイル変更、
  ユーザー確認なしでの Issue 起票

## プロジェクト固有設定 (`.claude/harness-intake.local.md`)

省略可。よく使うハーネスプロジェクトの呼び名や、対象リポジトリを変えたい場合に設定する。

```markdown
---
target_repo: "touyou/skills"   # 既定値。fork先に提案したい場合などに上書き
known_harness_roots:
  - "~/Developer/Projects/jt"
  - "~/Developer/Internal/sparkle"
---
```

## 関連

- 過去実例: [touyou/skills#5](https://github.com/touyou/skills/issues/5)
  （iOS実装から得た a11y パターンを Issue 起票 → PR #6 で `apple-accessibility` に取り込み）
