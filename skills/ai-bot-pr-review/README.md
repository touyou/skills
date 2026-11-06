# ai-bot-pr-review

AI bot (Codex / Copilot / CodeRabbit / Devin / Dependabot / Renovate / 自作 Actions など) が自動生成した PR を一括レビューして、安全なものは approve→マージ、ロジックを壊しているものはクローズする。

## いつ発動するか

```
bot の PR をまとめてレビューして
自動生成 PR を一括処理して
codex の PR お願い
copilot PR マージして
dependabot まとめて
automated PR triage
```

または `/ai-bot-pr-review` で明示起動。

## 何をするか

PR の author とブランチ名の両方から bot 由来の PR を拾い、テスト追加・依存更新・自動修正のカテゴリごとに判定する。互換を壊しうる依存更新や大規模なリファクタはマージせず、要確認として報告に残す。結果は PR ごとの判定とアクションの表で返す。

## プロジェクト固有設定 (`.claude/ai-bot-pr-review.local.md`)

設定の完全版は [references/configuration.md](references/configuration.md) を参照。

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。Flutter アプリのリポジトリで運用していた `codex-review` スキルを複数 bot 対応に汎用化したもの。
