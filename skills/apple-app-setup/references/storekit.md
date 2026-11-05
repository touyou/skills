# アプリ内課金（StoreKit 2）

買い切り（非消耗型）を 1 つ持つアプリ（月屏風の「音の箱」、Toreta の「Toreta Plus」）で、App Store 版になってから踏んだこと。
値付けや何を課金にするかはアプリごとの判断なので、ここには置かない（アプリの docs に書く）。

## 立ち上げで置くもの

- StoreKit の設定ファイルと掲載の表記は [release.md](release.md) の「掲載物」。加えて、審査メモ（課金が無いと書いていないか）も直す
- 課金の状態を見る型は 1 つにまとめ、`@MainActor @Observable` にして画面から読む

## オファーコードの取りこぼしを直した順

同じ症状（オファーコードで引き換えた買い切りが開かない）に、2 段で手を入れた。

1. **Toreta 1.2.4・月屏風 1.3.1**: 起動時に `Transaction.unfinished` を finish、アプリに戻るたびに確かめ直す、
   引き換えのあとに確かめ直す（Toreta は `onInAppPurchaseCompletion` でも）、取引の確認の行を画面に出す。Toreta はこれで直った（本人が確認）
2. **月屏風 1.3.2**: 1 の形でも App Store 版で開かなかった（下の `[measured]`）。`Transaction.latest(for:)` の併用、
   世代番号、復元の結果の表示を足した

Toreta はいまも `currentEntitlements` だけで判定していて、困っていない。どの条件で `currentEntitlements` から漏れるかは
分かっていないので、新しく作るなら最初から 2 の形にしておく。

## 権利の確かめ方

```swift
// 起動時: アプリが動いていない間に App Store で引き換えた分などが、終わらないまま残っていることがある
for await result in Transaction.unfinished {
    if case .verified(let t) = result { await t.finish() }
}
// 別の端末での購入や返金は、アプリが開いている間にもここへ届く
for await result in Transaction.updates { ... finish → 確かめ直す }
```

- 権利は `Transaction.currentEntitlements(for:)` だけで判定しない。**オファーコードで引き換えた買い切りが、
  `Transaction.all` には verified / Production で出ているのに `currentEntitlements` に出てこず、開かなかった** `[measured]`
  （月屏風 1.3.1 の App Store 版、2026-10-30。ASC の設定とドキュメントに原因は見つからなかった）。無ければ `Transaction.latest(for:)` でも確かめる。
  どちらも `revocationDate == nil` を見る（この併用で直ったかは、App Store 版での確認待ち）
- 確かめ直しは、起動時・購入後・復元後・アプリに戻るたび（`scenePhase` が `.active`）に呼ぶ。並行して走るので、
  世代番号を持って**先に始まった確認が後から終わって新しい結果を上書きしない**ようにする
- 商品（`Product.products(for:)`）が取れなかったときに読み込み直せる口を置く。値段が出ないまま買えなくなる
- 復元（`AppStore.sync()`）は結果（戻った / 通信できなかった）を画面で伝える。何も起きないように見えると、もう一度買おうとする
- 購入の画面のどこか（目立たない所）に、見えている取引と判定の経路（`currentEntitlements` / `latest` / 最終判定）を 1 行ずつ出す。
  上の取りこぼしは、この行を足した版で見つかった

## オファーコード

- オファーコードを一般に配らないなら、引き換えの入口（`offerCodeRedemption`）を UI に出さない
- 出すなら、使うファイルで `import StoreKit` する（SwiftUI だけでは修飾子が見つからずビルドが落ちた）。
  iOS 27 の SDK では `offerCodeRedemption(options:isPresented:onCompletion:)` の形に合わせる `[measured]`（2026-10、Xcode 27）
- 上の `currentEntitlements` の取りこぼしは App Store 版で起きた。引き換えを直したら、App Store 版で実際に引き換えて開くことまで確かめる

## スクリーンショットと確認

- 起動引数で状態を固定して撮る（→ [release.md](release.md)）。課金の画面は `-soundBox YES` で買わずに中身を出し、
  `-openSoundBox YES` でシートを開いて起動する
- 課金を開ける引数は `#if DEBUG` に閉じ込めるのが安全（月屏風は Release でも読んでいて、スクショを Release で撮る都合）。
  Release でも読むなら、アプリが `UserDefaults` に保存するキーと名前を分ける。同じ名前で保存すると本番で開いたままになる

## 直したことの告知

課金の不具合を直した版の What's New は、不具合の中身に触れず「小さな不具合を直しました」程度にする（touyou の方針）。
