# アプリ内課金（StoreKit 2）

買い切り（非消耗型）を 1 つ持つアプリ（月屏風の「音の箱」、Toreta）で、App Store 版になってから踏んだこと。
値付けや何を課金にするかはアプリごとの判断なので、ここには置かない（アプリの docs に書く）。

## 立ち上げで置くもの

- StoreKit の設定ファイル（`.storekit`）を scheme の Run に付け、シミュレータで購入・復元を試せるようにする
- 掲載の「アプリ内課金なし」表記、審査メモ（課金が無いと書いていないか）、プライバシーの申告を直す
- 課金の状態を見る型は 1 つにまとめ、`@MainActor @Observable` にして画面から読む

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
  （App Store 版、2026-10。ASC の設定とドキュメントに原因は見つからなかった）。無ければ `Transaction.latest(for:)` でも確かめる。
  どちらも `revocationDate == nil` を見る
- 確かめ直しは、起動時・購入後・復元後・アプリに戻るたび（`scenePhase` が `.active`）に呼ぶ。並行して走るので、
  世代番号を持って**先に始まった確認が後から終わって新しい結果を上書きしない**ようにする
- 復元（`AppStore.sync()`）は結果（戻った / 通信できなかった）を画面で伝える。何も起きないように見えると、もう一度買おうとする
- 購入の画面のどこか（目立たない所）に、見えている取引と判定の経路（`currentEntitlements` / `latest` / 最終判定）を 1 行ずつ出す。
  App Store 版でしか起きない不具合を、その画面のスクリーンショット 1 枚で切り分けられた

## オファーコード

- オファーコードを一般に配らないなら、引き換えの入口（`offerCodeRedemption`）を UI に出さない
- 上の `currentEntitlements` の取りこぼしは App Store 版で起きた。引き換えを直したら、App Store 版で実際に引き換えて開くことまで確かめる

## スクリーンショットと確認

- 起動引数で状態を固定して撮る（→ [release.md](release.md)）。課金の画面は `-soundBox YES` で買わずに中身を出し、
  `-openSoundBox YES` でシートを開いて起動する
- 課金を開ける引数のキーは、アプリが `UserDefaults` に保存するキーと名前を分ける。引数ドメインと同じ読み方なので、
  同じ名前で何かを保存すると本番で開いたままになる

## 直したことの告知

課金の不具合を直した版の What's New は、不具合の中身に触れず「小さな不具合を直しました」程度にする（touyou の方針）。
