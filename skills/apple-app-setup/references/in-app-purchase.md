# アプリ内課金を入れる

課金を入れると決めたときに、コードの外で詰まる場所。出典は Graphica Playground（RevenueCat ＋ サブスク 2 本・買い切り 1 本、
2026-09〜10）。RevenueCat を使わない StoreKit 直でも、App Store Connect 側の項目は同じ。
StoreKit 2 で権利を確かめるコードの落とし穴は [storekit.md](storekit.md)。

## 設計

- **課金の判定はパッケージ側のプロトコル越しにし、SDK を import するのはアプリのターゲットだけ**にする。
  パッケージのテストがネットワークと SDK 無しで回る（Playground は SDK を import する場所がアプリの 3 ファイルだけ）
- **コードに金額を書かない**。表示する価格はストアから取った文字列にする。価格を変えてもアプリの再ビルドが要らない
- テスト用の偽の課金状態は `.pro` / `.free` / `.actual` のように**呼び出し側に必ず選ばせ、既定値を置かない**。
  既定で「端末の実際の購入状態」を見ていたため、手で買ったあとだけ UI テストが落ちた `[measured]`
- 「無料だから止まる」を確かめる偽物は、商品の取得を失敗させない（取得が throw すると「課金が未設定だから止まった」に化ける）
- **Debug ビルドに設定の診断画面を置く**。SDK から実際に見えている値（キーの接頭辞、Offering、Package、
  Entitlement の識別子の食い違いなど）を純粋関数で判定して出すと、ダッシュボードを見て回るより速く、
  手順書が古くなっても判定は古くならない。長い Form の末尾に置くと遅延生成で UI テストからも見つからない `[measured]`

## App Store Connect

- **Paid Applications Agreement が Active になるまで、StoreKit は商品を 1 つも返さない**。RevenueCat 側の
  `offerings preview` は正しく 3 件返すのに端末は空、という食い違いになる。サーバを疑う前に契約を見る。
  API キーでは状態を取れないので web で見る `[measured]`
- 商品が「作れたのに `MISSING_METADATA` のまま」になる原因は複数ある `[measured]`:
  - 説明は **55 文字まで**（名前の 30 文字とは別）
  - 買い切りは**審査用スクリーンショットが必須**（`asc iap setup` にフラグが無いので `asc iap review-screenshots create` で別に上げる）
  - **アプリ本体の availability レコードが無い**。商品の availability は親に乗るので、`asc pricing availability create` を先にアプリへ
- `--price-territory` は価格を決めるだけで、**提供地域（availability）は別のオブジェクト**。価格は全地域に展開されるのに
  米国でしか買えない状態になる。商品ごとに availability を全地域へ広げる `[measured]`
- 承認済みのサブスクに価格を打つときは `--start-date` が要る（無いと `Initial price cannot be created again`）。
  買い切りの価格は schedule ごと作り直すので、基準地域の価格も一緒に渡す `[measured]`
- **承認済みの商品にはローカライズを足せない**（`Version is not in modifiable state`）。新しい version を作り、
  そこに足して、**アプリの次の版と同じ submission に入れる** `[measured]`
- 日本の価格は為替換算のままにせず、日本製アプリの相場（月額 ¥100〜550、年額 ¥3,000 前後）と比べて手で上書きする判断がある
- Terms of Use と Privacy Policy の URL、特定商取引法に基づく表記（日本で売るなら）を公開しておく

## RevenueCat

- 公開 SDK キー（`appl_`）は **`app_store` 種別の App にしか生えない**。App Store Connect のアプリのレコードが先
- Test Store のキー（`test_`）は手元の開発には楽だが、商品 ID・Entitlement の紐付け・実価格はどれも確かめられない。
  確かめる場は TestFlight（Sandbox なので請求は無い）。**Archive では `test_` を弾く**（[xcode-cloud.md](xcode-cloud.md)）
- Xcode から入れた Debug ビルドは App Store 由来でないので、StoreKit は自動で Sandbox になる
- RevenueCat の CLI（`rc` 0.1.2、2026-09）: `rc setup apple` / `rc apps apple check` は Apple 側の廃止されたエンドポイントを叩いて 404。
  `rc apps create` に資格情報を直接渡す。`rc apps update` は名前しか変えられない `[measured]`
- 買い切りだけの人には「サブスクリプションを管理」（Customer Center）を出さない。管理するものが無く、開くと一瞬出て閉じた。
  ただし買い切りのあとに月額を解約し忘れた人もいるので、有効な購読が残っていれば出す `[measured]`

## ストアの見せ方

- テスト用の Paywall の価格表示（スクリーンショット・デモ動画用）は本番の価格と揃え、価格を変えたら撮り直す
- 日本語のスクリーンショットを撮るなら、テスト用の価格もその地域の通貨にする（ドル建てのまま撮ると実価格とずれる）
