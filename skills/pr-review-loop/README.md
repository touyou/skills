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

## モード切替

| モード | 用途 | 既定で選ばれる条件 |
|---|---|---|
| **auto-fix** | 指摘を自動修正して push まで | PR author が自分 (= `gh api user` の login) |
| **comment-only** | インラインコメント付きで Pull Request Review を投稿。コードは編集しない | PR author が他人 / bot |

投稿・push は依頼で許可された範囲だけ行います。レビュー結果だけの依頼ならローカルに返します。判定表の正本は [SKILL.md](SKILL.md)、投稿方法は [references/github-review.md](references/github-review.md) にあります。未確認の観点や重要な懸念が残る場合は APPROVE しません。

## 鉄則

- 他人 / bot の PR に勝手に commit を乗せない (既定 auto-fix は author が自分のときだけ)
- 同一指摘が 2 回失敗したら Discussion に格上げ → 無限ループを構造的に防ぐ
- push 失敗時に `--force` は使わない。rebase 競合は `git rebase --abort` でクリーンに戻す
- resolved は現在コードで解消を確認して再投稿を避ける。未修正・再発は隠さない

## プロジェクト固有設定 (`.claude/pr-review-loop.local.md`)

設定の完全版は [references/configuration.md](references/configuration.md) を参照。

## 依存

- 専門レビューアは任意。利用できなければ同じ観点を直接レビュー
- `gh` CLI と GitHub 認証 (`gh auth login`)

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。habee-app (Flutter) で運用していた `review-loop` スキルを汎用化したもの。
