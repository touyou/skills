# iPhone Duo

Duo は「閉じると細くて背の高い iPhone、開くと iPad に近い regular 幅、半開きで折り目が出る」端末。
UIKit の置き換え（`UIScreen.main` / `interfaceOrientation` / `userInterfaceIdiom` / 非対称 safe area）と
起動画面・`UIRequiresFullScreen` の確認は Apple の `app-resizability` が正本。ここには SwiftUI のアプリを
8 本対応させたときに実際に踏んだこと（2026-10、iOS 27.1）を置く。

## 状態と寸法

| 状態 | 画面 | size class | 気をつけること |
|---|---|---|---|
| 閉じた | 外側の画面。普通の iPhone よりずっと細い（スクショ 1398×2034） | compact | 固定サイズ、1 行に並べたボタン、縦に入りきらない画面 |
| 開いた（平ら） | 内側の画面。横向き 2853×2007 | regular | `NavigationSplitView` の列の出方、ツールバー |
| 半開き（book posture） | 内側の画面に折り目 | regular | 折り目の上に操作部や文字を置かない |

## 閉じた画面（細い iPhone）

- 文字ボタンが単語の途中で折り返す。1 行に収まらないときは大きいアイコンだけのボタンに切り替える
  （`ViewThatFits` で文字あり → アイコンだけの順に候補を並べる。アイコンだけのときも `Label` のタイトルは残す）
- 縦に入りきらない画面はスクロールに逃がす。上の safe area が 0 のときも閉じるボタンが端に付かないように
- チュートリアルなどの固定サイズをやめる
- ナビゲーションバーの項目は画面の横の縦のバーへ移る（→ [swiftui-rules.md](swiftui-rules.md) の 3）
- 戻るボタンも縦のバーへ移るので、UI テストは識別子で探す

## 開いた画面

- 構成の判定は「regular かつ横長」（→ [swiftui-rules.md](swiftui-rules.md) の 2）。開いた Duo の縦は 1 カラム
- `NavigationSplitView` の `columnVisibility` を `.automatic` にしない。この幅では `detailOnly` が選ばれて
  リスト列のツールバー項目が消えた。リスト列の 320pt のバーに 4 項目は入らず、タイトルまで押し出された `[measured]`
- 追加ボタンなどの主要な操作は、列の出方に左右されない場所（下のツールバーなど）に置く

## 折り目

- 折り目が問題になるのは半開きのとき。平らに開いたらふつうに並べてよい（Apple に確認）
- 折り目を避ける位置は `GeometryProxy.reservedRegions(kind: .division)` で取る。Duo 以外では空、
  不要なときは幅 0 なので、分岐せずに常に挟めばよい（27.1+）`[Apple SDK]`
- region には `frame` と `margins` がある。開いた Duo の内側（951×669pt @3x）のシミュレータでは、frame は x 455.5・幅 40pt、
  左右の margins は 20pt だった `[measured]`（2026-10、iOS 27.1）。margins の意味は文書で確かめられておらず、
  月屏風は frame を margins 分だけ外へ広げた範囲を避けている（実機では未確認）。ストア画像を CLI で書き出すときもこの値を渡す
- 角度に合わせて折り目の扱いを変えるなら、`options: .includeInactive` で使われていない region も含めて取り、角度の側で詰め方を決める。
  月屏風は 120°→180° で margins を 2 割まで詰め、二扇の間を狭めた。詰め方はアプリと書き出しの CLI で同じ関数を使う（→ [metal-rendering.md](metal-rendering.md)）
- iOS 27.1 の `ArrangementView`（split）で、表示部と操作部をシステムが折り目に合わせて置ける。
  横長では左右、縦では上下、半開きでは折り目の両側。27.1 未満は従来の `VStack` にフォールバックする
- 分けたとき、片側を中身の高さに保ち残りをもう片側へ。押すと高さが変わる部品（次へボタンなど）は場所を常に確保する
- 高さを測るときは**実際に描く幅**で測る（測る幅を間違えて、折り返した文がカードからはみ出した例がある）
- 形が変わるときは `matchedGeometryEffect` で部品をつなげて動かすと、何がどこへ行ったか分かる

Apple の助言（ワークショップで確認）: 比率より「折り目にかぶせない」を優先する／特定の posture に
最適化しすぎない／横スクロールは避けなくてよい。折り目回避のネイティブな指定は無い。

## ヒンジ角度を体験にする（Duo 専用アプリのとき）

```swift
// SwiftUI（27.1+）
.onHingeChange { old, new in
    guard let hinge = new.hinge else { return }   // Duo 以外は nil
    angle = hinge.angle                           // status: .closed / .partiallyOpen / .fullyOpen
}
// UIKit: UIHingeInteraction(updateHandler:) を addInteraction。angle はラジアン
```

- 更新はコールバックだけ（Observation / Combine / AsyncSequence の口は無い）`[Apple SDK]`
- Duo かどうかは `reservedRegions(kind: .division)` の有無で判定する
- シミュレータでは起動時にヒンジ角 0°（closed）が届き、division は報告されないことがある（2026-10、iOS 27.1）。「division が無い = スライダー」と
  決め打ちせず、ヒンジの値が一度でも動いたらヒンジに従う、とするとシミュレータでもヒンジ操作を試せる `[measured]`
- 27.1 は Duo にしか無い（シミュレータの 27.1 ランタイムも Duo しか選べない）。27.0 の通常の iPhone で
  スライダーだけで動くことを別に確かめる
- 角度は 0° = 閉じた、180° = 平ら、を前提にしている。実機での向きと値域は未確認
- 最低 OS を 27.0 にして、ヒンジと折り目の API は `#available(iOS 27.1, *)` で囲む。Duo 以外の代わりの操作（スライダーなど）を必ず用意する
- ヒンジを動かしている間は毎フレーム描き直しになる。重い描画は「静的な層」と「角度で変わる層」に分け、
  動かしている間は軽い層だけ描き直す（月屏風で約 2ms）

## 確かめ方（実機なし）

- Xcode 27 には Simulator.app が無い。Duo シミュレータの開閉は DeviceHub から**手で**切り替える。
  `simctl` でも DeviceInteraction でもできない `[measured]`。自動の確認は開いた状態と回転だけ
- `simctl io screenshot` は真っ黒になる。XCUITest の `XCUIScreen.main.screenshot()` なら撮れる
- 画像に付く EXIF の回転情報は消す
- 並列テストは閉じた複製で走るので、撮影のテストは並列を切る
- 開いた Duo でも `XCUIScreen.main` は外側の画面のまま。画素数がいちばん多い画面（内側）を選んで撮る。
  その画像は縦長の向きで返るので 90° 回して 2853×2007 にそろえる（`XCUIScreen` の画像は 1px 足りず 2006×2852）`[measured]`（2026-10、iOS 27.1）
- 既定の画面の寸法では開閉を見分けられない（開いていても外側の画面を横にした 2034×1398 が返る）。内側の画面がまっ黒（PNG が 100KB ほど）かどうかで判定し、
  合わなければ止める `[measured]`
- xcodebuild は Duo の横のバーの時計を 9:41 に固定しない。UDID で宛先を指定して `simctl status_bar <udid> override` を当てる（効くかは未確認）`[inferred]`
- 開いた Duo はすべて横長なので、横向きのスクショは撮らない
- 半開きの見た目は DeviceHub で手で半開きにして撮る
- Duo シミュレータで UI テストとスクショのテストをまとめて流すと、失敗したり無出力のまま 10 分止まったりした。
  シミュレータを起動し直して少ない本数で流すと通った（1 回の観測で、原因は切り分けていない）`[measured]`
- regular 幅での `NavigationSplitView` の列の出方と選択状態は、スクショもタップも素直に動く iPad Air 11-inch 縦で代わりに見られる

## ストアの見せ方

ストア画像に Duo の帯（開いた画面）を足す。Duo が主役のアプリは 120° 以上で撮り、ヘッダー・検索の画像は
閉じた Duo。合成は `store-screenshot-composer`。
