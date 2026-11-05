# 構想の聞き取り

コードを書く前に決めること。1 つずつ聞かず、分かっていることを埋めた表を見せて、空欄と推奨だけを聞く。
相手が急いでいるときは推奨で進め、あとから変えにくいもの（★）だけを確認する。

## 聞くこと

| # | 項目 | 推奨（決まっていないとき） | あとから変えにくい理由 |
|---|---|---|---|
| 1 | アプリを 1 文で（誰が・いつ・何を） | — | Intent の一覧と画面の構成がここから出る |
| 2 ★ | アプリ名（表示名）と英名、bundle id | 表示名は短く。bundle id は `dev.<owner>.<英名の小文字>` | bundle id は提出後に変えられない。App Group・iCloud コンテナの名前にも波及する |
| 3 ★ | 対象 OS と最低バージョン | 最新メジャー（iOS 27.0）。Mac が要るなら macOS ネイティブ（Catalyst ではなく） | 最低バージョンを上げるのは簡単だが、下げると `#available` が全体に散る |
| 4 ★ | データの置き場所 | 端末内（SwiftData か JSON）。共有が要るなら iCloud（CloudKit）、組織で共有するなら自前のサーバ | CloudKit のスキーマは本番に出したら消せない。SwiftData を CloudKit で使うなら制約（全リレーション optional など）を最初から守る |
| 5 | 拡張（ウィジェット・コントロール・Live Activity・Watch）から読むか | ウィジェットは最初から入れる | 拡張が読むなら App Group が要り、データの置き場所が変わる |
| 6 | 届けるシステムの面 | ショートカット・Siri・Spotlight・ウィジェット | `app-intents-design-session` で Intent ごとに決める |
| 7 | 画面の形が変わるときの方針（iPad・Mac・Duo） | 1 カラム基本。「regular かつ横長」だけ左右分割。Duo は折り目で見る側と触る側を分ける | 判定の場所を後から 1 か所に寄せるのは手間が大きい |
| 8 | 言語 | ja と en。ソース言語は自分が書く方 | ソース言語を後で変えるとカタログのキーが全部変わる |
| 9 | 配信 | App Store。`production` push で Xcode Cloud → TestFlight | — |
| 10 | 課金 | 入れるなら最初から StoreKit の設定ファイルを置く | ストアの「アプリ内課金なし」表記などの掲載物に波及 |
| 11 | 公開リポジトリか | 非公開。参考実装として見せたいなら公開 | 公開ならコメントを英語にする判断が要る（IntentTodo は英語） |

## 1 文から Intent 候補を出す

「CSIRT の担当者が、朝いちばんに、今週期限の脆弱性を確かめて、対応済みにする」なら、

- 動詞: 確かめる（一覧を開く・今週の件数を聞く）、対応済みにする → `OpenDeadlinesIntent` / `GetDueCountIntent` / `MarkResolvedIntent`
- 名詞: 脆弱性、期限 → `VulnerabilityEntity`
- 場面: 朝いちばん → ウィジェット・Siri・Action ボタン

詳しい導き方は `app-intents-design-session`。

## 決めたことの残し方

決めたことは `docs/PLAN.md`（要件と展開マトリクス）に書き、理由が長いものは `docs/adr/` に 1 件 1 ファイル。
AGENTS.md には書かない（AGENTS.md は目次とルールだけ）。
