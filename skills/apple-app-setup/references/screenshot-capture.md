# ストア用スクショの自動撮影

素のスクショを 1 コマンドで撮り直せる形を最初に作っておく。仕上げ（合成・文言）は `store-screenshot-composer`、
ここはその手前の「アプリの画面を撮る」工程。Intento の `scripts/capture_screenshots.sh`（iPhone / iPad / Watch /
Vision Pro / Mac × ja / en）を作ったときに踏んだもの `[measured]`（Xcode 27.0〜27.1、2026-09〜10）。

## 形

- 撮影は XCUITest で行い、`.xcresult` の attachment を取り出して `Screenshots/<platform>/<locale>/NN-name.png` に置く（gitignore）
- 例外は visionOS（下の表）。Duo の閉じた状態は手で切り替える（[iphone-duo.md](iphone-duo.md)）
- 画面は起動引数で選ぶ（`-uitest-screenshot-screen detail`）。画面ごとに起動し直して 1 枚ずつ撮ると、
  タップで遷移できないプラットフォーム（visionOS の simctl、macOS の畳まれた行）でも同じ仕組みで撮れる
- ロケールは `xcodebuild -testLanguage ja -testRegion JP` で渡す。テストの中で `-AppleLanguages` を組み立てる形は、
  環境変数がテストに届かず **ja のスクショが全部英語で撮れていた**（緑なので機械的には気づけない）。
  `-testLanguage` はアプリの `Locale.current` も動かすので、フィクスチャの言語もこれで揃う

## フィクスチャ（見本のデータ）

- DEBUG 限定でアプリ内に持ち、起動引数（`-uitest-screenshot-fixture`）で流し込む。言語ごとに中身を持つ
  （日本語のストアに英語の項目が並ぶと未翻訳のアプリに見える）。データであって UI 文言ではないのでカタログには入れない
- **一時ストアでなければ流し込まないガード**を入れる。フィクスチャは先にストアを空にするので、無いと実データを消しうる
- SwiftData の一時ストアは `ModelConfiguration(..., isStoredInMemoryOnly: true, cloudKitDatabase: .none)`。
  `cloudKitDatabase` の既定は `.automatic` で、CloudKit の entitlement を持つアプリのプロセスでは**メモリ上のストアでも同期が動く**。
  フィクスチャが iCloud に上がって開発機に降り、本物のデータが撮影に写り込んだ `[measured]`
- `App.init()` で流し込まない。`ModelContainer.init` はストアの読み込みが終わる前に返り、インストール直後の初回起動
  （UI テストでは毎回）に `mainContext` を触ると `No eligible connection available` で落ちる。シーンの `.task` で行う。
  手で `simctl launch` すると再現しない `[measured]`
- まとめて消す `delete(model:)` も（`NSBatchDeleteRequest` を通り）Objective-C の例外で落ちた。fetch して 1 件ずつ消す。macOS では `ModelContainer.init` 直後の fetch が
  空で返り、消し損ねて毎回 6 件ずつ増えた。少し待ってから fetch → delete にした（`deleteAllData()` は直後に `mainContext` を触ると落ちる）

## プラットフォームごとの撮り方

| 対象 | 撮り方 | 踏んだもの |
|---|---|---|
| iPhone / iPad | XCUITest の `XCUIScreen.main.screenshot()` | 6.9" と 13" の寸法がそのまま出る。通知許可のダイアログはフィクスチャ実行時は要求ごと飛ばす。iPad の上のタブは `tabBars` として出てこないので、タブの名前のボタンで押す。iPad のシミュレータでは Form の中の複数行の入力欄にタップでフォーカスが入らなかった（その画面は入力なしで撮るか、フィクスチャで値を入れておく）。iPad を横向きで撮ると `app.screenshot()` の向きと切り抜きが崩れるので、`XCUIScreen.main.screenshot()` で撮って仕上げで回す（`store-screenshot-composer` の `rotate_input`）。Patchday、2026-11 |
| iPhone Duo | XCUITest（`simctl io screenshot` は真っ黒） | → [iphone-duo.md](iphone-duo.md) |
| Apple Watch | XCUITest | 行の中のボタンを index で取ると、ナビゲーションではなく完了のチェックを押していた。identifier で選ぶ |
| Vision Pro | **`xcrun simctl io <device> screenshot`** | XCUITest は 1x1 か 1280x720 の切り抜きしか返さない。simctl なら部屋ごと 3840x2160（ASC の寸法）。タップできないので画面は起動引数で選ぶ。`simctl openurl` は「開きますか?」の確認が写るので使わない。前の実行のウィンドウが空間に残るので、撮影専用のシミュレータを用意し、撮る前に erase する（アプリもデータも消える） |
| Mac | XCUITest の `app.windows.firstMatch.screenshot()` | `app.screenshot()` と `XCUIScreen.main` はディスプレイ全体を返す。前回の状態が復元されてウィンドウ 0 枚で起動するので `-ApplePersistenceIgnoreState YES`。ウィンドウを `.frame` で 1440x900pt に固定し、`sips` で ASC の寸法に合わせる（`sips -Z` は長辺しか見ないので、両辺の縮小率の min を取ってからパディングする） |

macOS の UI テストは 2 つ準備が要る:

- UI テストのターゲットの `SUPPORTED_PLATFORMS` に `macosx` を入れる。無いと `Cannot test target on My Mac`。
  Intento ではいつの間にか欠けていて、Mac のスクショだけ古いまま止まっていた
- 実行時に認証のダイアログが出る（`認証はキャンセルされました` で落ちる）。手元で承認してもらうしかない

エージェントが Mac を遠隔で動かしているときは、UI テストに automation mode の許可、ウィンドウの撮影に画面収録の許可が要り、
どちらも本人の操作なしには通らない `[measured]`（Patchday、2026-11）。そのときの形:

- 画面を起動引数（DEBUG 限定）で決めて起動し、`screencapture -l <ウィンドウ ID>` で撮るスクリプトを用意して、本人に 1 回流してもらう（画面収録の許可は要る）
- 見た目を確かめるだけなら、Xcode の MCP の `RenderPreview` は画面収録の許可なしで描ける。決まったデータを返すプレビュー用の Service を用意しておくと速い

## 確かめ方

撮ったあとの照合（ASC 上の枚数と md5）は [app-store-submission.md](app-store-submission.md) の 3。
