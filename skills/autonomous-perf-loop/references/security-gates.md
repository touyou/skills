# セキュリティの基準（採用の前提）

速くなっても、ここに当たる変更は採用しない。点数より優先する。

## 最初に却下する案

試す前に台帳へ「却下: 理由」と書く。

- **人ごとに中身が変わる応答を共有キャッシュに載せる**: Cookie / Authorization で変わるページや API、
  いいね・既読などの人ごとの状態、ログイン中のユーザーを読むレイアウト。他人の情報が別の人に返る
- **CSP の nonce を含む HTML をキャッシュする**: 全員に同じ nonce が配られ、CSP が効かなくなる
- **チェックをキャッシュの後ろに置く**: キャッシュに当たると処理本体が呼ばれないので、本体にある認証・
  認可・rate limit・人間確認が素通りになる
- **可視性の条件をゆるめる・後回しにする**: 非公開・凍結・削除済み・他人の非公開データの除外を、
  「後で絞る」「クライアントで消す」に変える
- **SQL を文字列の連結で組み立てる**: 速くするための手書き SQL でも、値は必ずバインドする
- **`Set-Cookie` を含む応答を共有キャッシュに載せる / 共有キャッシュで `Vary` を落とす**: 他人のセッションが配られる、
  言語や認証で変わる応答が混ざる
- **CORS をゆるめる**: プリフライトを減らすために `Access-Control-Allow-Origin` を広げる、など
- **入力やサイズの検証を外す・後ろに回す**: 検証のコストを削ると、大きな入力で落ちる・不正な値が DB に入る
- **上限の無いメモ**: キーが人やリクエストで増えるメモをプロセスのメモリに置く（メモリが尽きる）。
  メモするなら、キーの数が決まっているものだけにするか、件数の上限を付ける
- **計測用のデータ・スクリプト・デバッグ用の窓口を本番に出す**: プロファイラの口を開けたままにする、など

## キャッシュしてよいかの判断

問いは「**その値を決める入力に、人やリクエストに由来するものが入っているか**」。
関数に引数が無くても、中で Cookie やヘッダーを読んでいたら人ごとのデータになる。

| データ | 例 | 共有のキャッシュ・メモ |
|---|---|---|
| 全員に同じ・公開 | 公開作品の件数、公開設定の一覧 | 短い期限付きなら可。何秒古くてよいかを決めて書く |
| 人ごと | いいね状態、ログイン中のユーザー、nonce、CSRF トークン | 不可 |
| 公開だが条件付き | 作品本体（作者本人は非公開でも見える） | 条件をキーに入れない限り不可 |

期限付きで持つときは、古い値が出ることを受け入れられるかも決める（件数の 60 秒は問題ない。在庫や残高は不可）。

**後から非公開にできるものは、中身を期限付きで持たない**。非公開にしても期限まで見え続けるので、
それは漏れになる。期限付きでよいのは件数のような集計値だけ。中身を持つなら、非公開化・削除のときに
消す仕組みを先に作る。

## 確認の順序に依存する変更

「存在と可視性は呼び出し側で確かめ済み」という前提の関数を作ったら、その前提を関数のコメントに書く。
呼び出し側で順序を入れ替えると、非公開のものについての情報（いいねしたか、存在するか）が漏れうる。

## 書き換えで意味が変わらないか

クエリの書き換え（OR を分ける、サブクエリにする、JOIN を外す）は、性能より先に**結果が同じか**を確かめる。
特に「別の人・別の行に解決されないか」「見えてはいけない行が出てこないか」。
計測用データの全キーで、書き換え前と後の結果が一致することを確かめるのが確実。

**順序にも気をつける**。メモリ上の処理を SQL に移すと、行が決まった順で来なくなる（`ORDER BY` の無い再帰クエリなど）。
後段の処理が入力の順に依っていると、同じデータでも答えが変わる。gp-space では、タグの代表の表記を
`localeCompare(..., "ja")` で選んでいたが、`"DESIGN"` と `"ＤＥＳＩＧＮ"` を同じと返すので、同数のときは先に来た方が選ばれていた
（レビューの bot が見つけた）。並べ替えの比較に、同値のときの決まった順（コードポイントなど）を足すか、SQL に順序を書く。
SQL の `ORDER BY` では、最後に一意な列（主キーなど）を足して同値の行の順も決める。
入力の順を入れ替えても答えが変わらないことをテストにする

**組織・テナントの境界は結合にも書く**。主キーが今は ID だけで重ならなくても、複合キーへの移行が予定されているなら、
結合の条件に組織の ID も入れておく（`d.organization_id = $org and d.id = r.document_id`）

## セキュリティだけのレビュー（採用の前に 1 回）

別のエージェントに頼む。**自分の結論（安全だと思う理由）は渡さない**。渡すと追認になりやすい。
渡すのは差分と、この基準と、確かめてほしい具体的な点だけ。

```text
You are doing a security-only review of a performance change in <repo>. Do not review style or
performance; only look for ways the change could leak data, bypass checks, introduce injection,
poison a shared cache, or let a request exhaust memory or CPU (for example an in-process memo whose
keys grow with users or requests). Do not modify any files.

The diff: <path or `git diff <base>`>. It changes: <1 行ずつ、何を変えたか（なぜ安全かは書かない）>

Rules the change must satisfy:
- Don't change visibility conditions (<非公開・凍結などの列名>).
- Don't put per-user responses, per-user state, or CSP-nonce HTML into shared caches
  (<edge cache の関数名>, cache-control public, or module memory shared across requests).
- SQL only through parameter binding, never string concatenation.
- Don't bypass auth, rate limits or human checks.
- Bench tooling must stay local and never ship to production.

Things to check specifically: <呼び出し元をすべて見る / 確認の順序 / 共有メモに人ごとの値が入らないか /
新しいスクリプトがバンドルに入らないか、など>
<画面側のキャッシュ・取り直しの条件を変えたとき: a list stuck loading (an answer dropped while nothing asks again),
a periodic refresh or retry swallowed, stale data shown after a local change / permission change / deletion,
module-level caches surviving sign-out or a workspace switch>

Report each finding with file:line, a concrete failure scenario, and a confidence label
(high/medium/low). Include low-confidence ones too. If you find nothing, say so plainly and list
what you checked. Keep the report concise.
```

確度の低い指摘も全部出させ、捨てずに扱う。扱いは確度で決まり、変更を書いた側が「問題ない」と判断して消すことはしない。

| 指摘の確度 | 扱い |
|---|---|
| high / medium | 採用を止める。直してから同じ手順でレビューをもう 1 回。直せないなら変更を差し戻す |
| low | 直せるなら直す。直さないものは、PR の説明の「要確認」に指摘の全文と、直さなかった理由を載せて人に見せる |

指摘の件数と扱いは台帳にも残す。

画面側のキャッシュ（取り直すかどうかの判定）を変える周では、漏れに加えて「止まる・古いまま残る」を必ず確かめさせる。
gp-space の 4 周目では、捨てられる要求を待ち続けて読み込み中のまま止まる経路と、定期の読み直しが飛ぶ経路がこのレビューで見つかった。
判定は純粋関数に切り出してテストする（「文書が足されただけでは取り直さない」「定期の読み直しでは取り直す」「失敗した後は再試行する」）。

## 計測のコードを製品に残さない

アプリの中で測るとき（bench-harness.md の 9 節）、プローブや計測用の起動引数が Release に残ると、
誰でも計測用の経路（メモリ上のデータ、ログの書き出し先）を動かせる。`#if DEBUG` で囲むだけでなく、
Release のバイナリにプローブの記号・文字列が無いことを、採用の前に毎周スクリプトで確かめる。
