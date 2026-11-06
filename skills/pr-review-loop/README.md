# pr-review-loop

PR に対してレビュー → 修正 → 再レビューを「指摘がなくなるまで」自動で繰り返す。人間レビュアーに出す前にコード品質を底上げし、レビュー往復回数を減らすのが目的。

## いつ発動するか

```
/pr-review-loop 1234
このPRのレビュー回して
PR #1234 を指摘がなくなるまでレビューして
レビューループして
review loop
/pr-review-loop 1234 --comment-only   # auto-fix を無効化したい場合
/pr-review-loop 1234 --auto-fix       # 他人 PR でも編集を強制したい場合
```

## 何をするか

自分の PR では指摘を直して push まで進め、他人や bot の PR ではインラインコメント付きのレビューを投稿するだけにとどめる。どちらにするかは明示指定があればそれに従う。投稿・push は依頼で許可された範囲だけで、同じ問題への修正試行と全体の周回には上限がある。

## プロジェクト固有設定 (`.claude/pr-review-loop.local.md`)

設定の完全版は [references/configuration.md](references/configuration.md) を参照。

## 依存

- 専門レビューアは任意。利用できなければ同じ観点を直接レビュー
- `gh` CLI と GitHub 認証 (`gh auth login`)

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。Flutter アプリのリポジトリで運用していた `review-loop` スキルを汎用化したもの。
