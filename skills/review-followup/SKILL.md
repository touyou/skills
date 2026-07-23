---
name: review-followup
description: 過去に自分がレビューコメントを付けた PR を横断スキャンし、著者側の対応をコード (コミット差分) で裏取りしてから approve するかを判断するフォローアップ専用スキル。新規レビューは行わず、「前回指摘した内容が実際に直っているか」の確認に特化する。ユーザーが「指摘した PR のフォローアップして」「レビュー済み PR の対応確認して」「直ってたら approve して」「review followup」「指摘対応の裏取りして」と依頼した時、または `/review-followup [PR番号]` を実行した時に発動する。
license: MIT
metadata:
  author: touyou
  version: "0.1.0"
---

# review-followup

過去に自分がレビューコメントを付けた PR について、著者の対応をコミット差分で裏取りし、対応済みと確認できたものだけ approve する。**新規の指摘は追加しない** — レビューそのものは `pr-review-loop` の担当で、このスキルは「指摘 → 対応 → 承認」のループを閉じる後段だけを受け持つ。

## 鉄則

- **フォローアップ専用**: 新規の指摘を見つけても投稿しない。気づいたことがあれば最終レポートに「参考」として書くに留める (必要ならユーザーが `pr-review-loop` を別途回す)。
- **裏取りなしで approve しない**: 著者の「直しました」コメントだけを根拠にしない。必ず対応コミットの diff を読んで、指摘の意図が満たされているかを確認する。
- **判断できないものはスキップ**: 対応が部分的・意図と違う・diff から判断不能な場合は approve せず、レポートに理由付きで残す。
- **CI 未通過の PR は approve しない**: 対応が正しくても CI が赤ならスキップして報告。

## 対象 PR の特定 (決定的パート)

引数の有無で分岐する:

- **PR 番号あり** (`/review-followup 123`): その PR のみ対象。
- **引数なし**: 自分がレビューコメントを付けた open PR を横断スキャン。

```bash
GH_USER=$(gh api user --jq '.login')

# 自分がレビューした open PR (自分が author のものは除外)
gh pr list --state open --json number,title,author,reviews \
  --jq --arg me "$GH_USER" '
    map(select(
      (.author.login != $me)
      and ([.reviews[].author.login] | index($me))
    )) | .[] | {number, title, author: .author.login}'
```

各対象 PR について、裏取りに使う材料を決定的に収集する:

```bash
# 1. 自分のレビューコメント一覧 (インライン + review body)。最後に自分がレビューした時刻も控える
gh api "repos/{owner}/{repo}/pulls/$PR_NUMBER/comments" \
  --jq --arg me "$GH_USER" 'map(select(.user.login == $me)) | .[] | {path, line, body, created_at}'
gh pr view "$PR_NUMBER" --json reviews \
  --jq --arg me "$GH_USER" '.reviews | map(select(.author.login == $me)) | .[] | {state, body, submittedAt}'

# 2. 自分の最終レビュー以降に積まれたコミット
gh pr view "$PR_NUMBER" --json commits \
  --jq '.commits | .[] | {oid: .oid, message: .messageHeadline, date: .committedDate}'
# 最終レビュー時刻より後のコミットに絞り、それぞれ diff を取得
git fetch origin "pull/$PR_NUMBER/head" && git show <oid> --stat && git show <oid>

# 3. CI 状態
gh pr checks "$PR_NUMBER"
```

resolved 状態も判断材料になる (resolved 済みスレッドは著者が対応済みと主張しているサイン)。取れる環境なら GraphQL の `reviewThreads.isResolved` を使う (`pr-review-loop` のステップ 2 と同じクエリ)。

## 対応の裏取り (LLM 判定パート)

指摘 1 件ごとに「指摘の意図 → 対応コミットの変更内容」を突き合わせる。判定は次の 3 値:

| 判定 | 基準 | 例 |
|---|---|---|
| **resolved** | 指摘の意図がコードで満たされている | 「エラー握りつぶし」指摘 → 該当 catch 節にログ + 再 throw が追加された |
| **partial** | 対応はあるが意図の一部しか満たしていない | 指摘した 3 箇所のうち 1 箇所だけ修正された |
| **unverifiable** | 対応コミットが見つからない / diff から判断できない | 「別 PR で対応します」とコメントのみ、該当ファイルに変更なし |

注意点:

- **表面的な一致で済ませない**: 指摘した行が変わっていても、意図 (例: 「境界値テストを足してほしい」) が満たされていなければ partial。
- **別の形での対応も認める**: 指摘と違う実装でも意図が満たされていれば resolved (指摘はあくまで例示。対応方法を強制しない)。
- **コメント返信での反論**: 著者が「これは仕様です」等と返信していて筋が通っているなら resolved 扱いにしてよい。ただしレポートに「反論を受け入れた」と明記する。

## 判定とアクション

| 状態 | アクション |
|---|---|
| 全指摘 resolved + CI green | approve (`gh pr review --approve`) |
| 全指摘 resolved + CI red / pending | スキップ。「対応確認済み、CI 待ち」として報告 |
| partial / unverifiable が残る | スキップ。どの指摘が未対応かを報告 (PR にはコメントしない) |
| 自分の前回レビューが APPROVE 済み | 対象外 (フォローアップ不要) として報告 |

approve コメントには裏取りの根拠を 1〜2 行で書く (audit ログとして後で読める):

```bash
gh pr review "$PR_NUMBER" --approve \
  --body "前回指摘 (エラーハンドリング / テスト追加) が <oid> で対応済みであることを diff で確認しました。CI green。"
```

## 最終レポート

```markdown
## review-followup 結果

| PR | author | 指摘数 | resolved | partial | unverifiable | CI | アクション |
|---|---|---|---|---|---|---|---|
| #123 | alice | 3 | 3 | 0 | 0 | ✅ | approve 済み |
| #124 | bob | 2 | 1 | 1 | 0 | ✅ | スキップ (境界値テスト未対応) |
| #125 | bot | 1 | 1 | 0 | 0 | ❌ | スキップ (CI 待ち) |

### スキップ理由の詳細
- #124: 「境界値テストを足してほしい」→ 正常系のみ追加。境界値 (0 / 上限) が未カバー
```

## 由来とブラッシュアップ方針

「指摘した後、対応されたか確認して承認する」作業がレビュー担当の抱える PR ごとに個別発生する問題を、一括スキャン + 裏取りに型化したもの。決定的な部分 (対象 PR の絞り込み、コミット・diff の取得) と LLM 判定 (対応が指摘の意図を満たすか) を分離してある。レビュー本体は `pr-review-loop`、bot PR の一括処理は `ai-bot-pr-review` が担当し、このスキルはその後段に位置する。

## 依存

- `gh` CLI と GitHub 認証 (`gh auth login`)
