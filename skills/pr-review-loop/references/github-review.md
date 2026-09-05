# GitHub の証拠収集とレビュー投稿

`OWNER/REPO/PR_NUMBER` は対象 PR から、`REVIEW_HEAD` はレビューした SHA から設定する。別リポジトリの URL を現在の checkout と混同しない。

## コメントの取得

```bash
gh api --paginate "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" \
  --jq '.[] | {id, author: .user.login, path, line, original_line, commit_id, body}'
gh api --paginate "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" \
  --jq '.[] | {id, author: .user.login, body}'
```

resolved 状態には GraphQL の `reviewThreads` を使う。`pageInfo { hasNextPage endCursor }` と `after` で全ページを取得する。スレッド内の comments もページングする。未取得ページが残れば取得未完として扱う。resolved の指摘は現在のコードで解消済みなら再投稿しない。

## インラインと本文

- 追加行は `side: RIGHT`、削除行は `side: LEFT` とし、それぞれのファイル側の行番号を指定する。削除行を近くの追加行に付け替えない。
- diff で参照できない行・バイナリ・取得できない差分は本文へ。インライン化不能でも REQUEST_CHANGES の件数から落とさない。
- 本文には軽微・要確認・要相談・スコープ外の場所と要旨を列挙する。重複統合したものには元の指摘との対応を残す。
- `SUMMARY_FILE` は完成した本文、`COMMENTS_FILE` は検証済みの `{path,line,side,body}` 配列を保存したファイル。空配列も有効。

## 投稿

直前に head SHA を再取得し、`REVIEW_HEAD` と一致しなければ新差分をレビューして payload を作り直す。event は SKILL.md の判定表から決める。

```bash
jq -n --arg commit "$REVIEW_HEAD" --arg event "$EVENT" \
  --rawfile body "$SUMMARY_FILE" --slurpfile comments "$COMMENTS_FILE" \
  '{commit_id: $commit, event: $event, body: $body, comments: $comments[0]}' \
  > "$PAYLOAD_FILE"
gh api -X POST "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" \
  --input "$PAYLOAD_FILE"
```

投稿失敗時はまずレビュー一覧を取得し、同じ commit/body のレビューが作成済みか確認する。タイムアウトを未投稿と決めつけて二重投稿しない。明確な行指定エラーなら該当指摘を本文に移し、元の event と全指摘を保って一度だけ再試行する。認証・権限エラーや成否不明が残る場合は本文ファイルと理由を報告し、別コメント API へ自動転送しない。

API のフィールドは [GitHub のレビュー作成仕様](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request) と [行・side の仕様](https://docs.github.com/en/rest/pulls/comments#create-a-review-comment-for-a-pull-request) を参照する。
