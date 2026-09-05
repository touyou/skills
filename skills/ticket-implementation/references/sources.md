# Source 別のチケット取得

コネクタ / MCP / CLI は環境で実際に利用可能なものを探す。例示されたツール名の存在を前提にしない。取得できない場合はユーザー提供の本文で進められる範囲を判断する。

## Notion

URL の query / fragment を除いた path から 32 桁 hex またはハイフン付き UUID のページ ID を取り出す。URL 末尾 32 文字をそのまま使わない。プロパティ、ページ本文、子ブロック、コメントをページングして取得する。relation は一般的な関連リンクにも使われるため、関連ページをすべてサブチケットと見なさず、プロパティ名・設定・内容から親子関係を確認する。

## Linear

URL path の issue identifier を取り、issue・comments・sub-issues を取得する。利用可能なツールが URL を直接受け取れるなら ID を独自抽出せず渡す。state 名は team ごとに取得し、英語の固定値を押し付けない。

## GitHub Issue

URL から owner/repo と番号を取り、他の checkout にいても対象を固定する。

```bash
gh issue view "$ISSUE_NUMBER" --repo "$OWNER/$REPO" \
  --json title,body,comments,labels,assignees,milestone
```

ネイティブ sub-issues と本文のタスクリストを区別する。チェックボックスだけなら受け入れ条件の可能性があり、別チケットとして分割しない。別 Issue へのリンクなら内容を取得して関係を確認する。

## Plain text

ユーザーの本文を起点に、結論・受け入れ条件・補足を整理する。確認できないコメントや更新履歴を補わない。チケット URL やステータス更新先は創作しない。
