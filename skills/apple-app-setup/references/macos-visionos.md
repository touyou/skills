# macOS / visionOS に広げる

iOS のアプリを macOS（ネイティブ。Catalyst ではない）と visionOS にも出すときに踏んだこと。
出典は GRAPHICA（iOS / macOS / visionOS の 3 scheme、2026-06〜10）。ビルドの確かめ方は
[verification.md](verification.md)、提出で弾かれるものは [xcode-cloud.md](xcode-cloud.md)。

## 最初に決めること

- **ローカル SPM の `platforms` に、出す OS を全部書く**。iOS だけ書いてあると、他の OS のビルドで
  パッケージ側の `@available` が足りないエラーとして一斉に出る `[measured]`
- **`#if os(visionOS)` の中は、その OS の scheme をビルドしないと型チェックされない**。iOS と macOS が緑でも
  visionOS 専用ファイルの誤りは残る。対象 OS の全 scheme を回す（Release も。[verification.md](verification.md)）`[measured]`
- **OS ごとの分岐は最初はその場の `#if` で書き、互換 helper の層を先に作らない**。分岐が少ないうちは helper が
  grep のノイズになるだけだった。画面まるごとの重複が実害になってから畳む `[measured]`（GRAPHICA で一度作った
  91 行の helper をレビューで外した）
- **その OS ならではの機能は、作る前に配布要件と照らす**。macOS でローカルの CLI を `Process` で起動する機能は
  App Sandbox と両立せず、Sandbox を外す → App Store が Sandbox を要求（ITMS-90296）→ Release では機能ごと隠す、と往復した `[measured]`

## API の可用性は SDK で確かめる

- ドキュメントの対応 OS は当てにならない。`scrollDismissesKeyboard` は文書上 visionOS 1.0+ だが、
  swiftinterface では `@available(visionOS, unavailable)` だった `[Apple SDK]`
- macOS では `navigationTransition(.zoom)` / `zoom(sourceID:in:)` が unavailable。行き先だけ `#if os(macOS)` で外せば、
  対応先の無い `matchedTransitionSource` は何もしないので起点は残せる `[Apple SDK]`

## macOS で効いたこと

### サンドボックスとアセット

- **App Sandbox は外向きの通信を既定で止める**（iOS は許可）。`com.apple.security.network.client` を entitlements に
  足すまで、ネットワークから読む画面が空のままだった `[measured]`
- **macOS は @3x を使わない**。1x / 2x の枠が空のアセットは表示されない `[measured]`
- 拡張（ウィジェット）にも `ENABLE_APP_SANDBOX` / `ENABLE_HARDENED_RUNTIME` が要る。本体だけ設定すると提出で
  ITMS-90296 になる（iOS は常にサンドボックスなので気づけない）`[measured]`

### シーンとウィンドウ

- **設定は `Settings` シーン（⌘,）にし、その中で `NavigationLink` の push を使わない**。`Settings` や
  `TabView(.sidebarAdaptable)` の配下で push すると、戻るボタンが画面の中央付近に出た。macOS の語彙に合わせて、
  一時的な操作（サインインなど）と葉の一覧は `.sheet` にする `[measured]`
- 設定の中身は、CotEditor や Xcode のような**ツールバーのタブ（`TabView` + `Tab`）＋単一ペイン**が素直だった。
  `NavigationSplitView` のサイドバーにすると、カテゴリを切り替えるたびに詳細ペインの `@State` が破棄される
  （`Group { switch }` の差し替えになるため）。実行中フラグや「起動時の値」は View ではなく Service に持たせる `[measured]`
- `Settings` シーンの既定のリサイズは `.contentSize` で、`Form` だとドラッグでも緑ボタンでも大きさが変えられない。
  内容が画面の高さを超えうるなら `.windowResizability(.contentMinSize)` にする `[measured]`
- **メインのウィンドウが 1 枚前提なら `WindowGroup` ではなく `Window`**。`WindowGroup` は ⇧⌘N で 2 枚目が開き、
  ディープリンクや Intent が 1 回来ただけで両方のウィンドウが反応した。`Window` にすると「ウインドウ」メニューに
  復帰の項目が自動で付き、⌘W で閉じても戻れる `[measured]`
- 値つきの `WindowGroup(id:for:)` は「同じ値のウィンドウがあれば前面に出す」。毎回新しいウィンドウにしたいなら、
  値に UUID を含める（空文字の値だと 2 枚目が開けない）`[measured]`
- シートの中身を外から差し替える（Intent で文面を渡すなど）なら `sheet(isPresented:)` ではなく `sheet(item:)`。
  表示中のシートは作り直されず、初期値が効かない `[measured]`

### メニューバー

- **ウィンドウを開くコマンド（⌘N）は `@Environment(\.openWindow)` を Commands から直接呼ぶ**。`focusedSceneValue`
  に乗せると、設定ウィンドウが前面のときやウィンドウが 0 枚のときに効かなくなる。表示中の内容に効くコマンドだけ
  `FocusedValues` を使う `[measured]`
- `CommandGroup(replacing: .newItem)` は replacing のまま、代わりの項目を自分で置く。`after:` だと既定の
  「新規ウインドウ」が ⌘N を握ったまま衝突する `[measured]`
- `focusedSceneValue` はシーン単位なので、`TabView` が保持している**見えていないタブ**の値がメニューを乗っ取る。
  タブを environment で配り、現在のタブと違えばメニュー項目を disabled にする（誤爆より無効化）`[measured]`
- 対象が無いときのメニュー項目は消さずに disabled で残す（macOS の慣習）
- `List` で選択と Delete キーを効かせるには `List(selection:)` + `contextMenu(forSelectionType:)` + `onDeleteCommand` が要る

### 描画

- **`MTKView` など AppKit のビューは SwiftUI の上に重ねてもヒットテストに参加する**。ホバーで重ねた途端に
  下のリンクのクリックと `.onHover` を奪い、点滅した。`hitTest(_:)` が nil を返すサブクラスにする
  （iOS の `isUserInteractionEnabled = false` と対になる）`[measured]`
- 一覧の格子は OS ごとに列数を固定しない。iOS だけ幅で列数を決める形に直したら、Mac と Vision Pro の広い
  ウィンドウで 2 列のまま右に寄った。全 OS で同じ行組み（最小幅から列数を決める）を使う `[measured]`

## visionOS

- **アイコン**: Icon Composer の `.icon` は visionOS に対応していない。visionOS 用に Asset Catalog の 3 層の
  image stack（solid image stack）を別に用意しないと `CFBundleIcons` が生成されず、提出で ITMS-90970 になる `[measured]`
- **拡張の埋め込みを OS で絞る**。iOS 用のウィジェット appex が visionOS のビルドに入らないよう、埋め込みに
  プラットフォームの絞り込みを付ける（JSON 形式の `project.xcproj` では埋め込み product に `"platforms"`）`[measured]`
- **`RealityView` の `update` クロージャの中で `@State` を書き換えない**（未定義の動き）。推測の修正を 3 回外したあと、
  ログを入れて特定した `[measured]`
- 同期処理を非同期にしたときは、**呼び出し側が「同期で終わる」ことを前提にしていた箇所を全部洗う**。
  `RealityView` の make クロージャ直後にテクスチャを作る経路が、コンパイルの非同期化で一度逃すと復帰しなくなった `[measured]`

## 動作の確かめ方

- macOS の UI テストは最初に自動操作の許可（管理者のパスワード）を求め、無人だと
  `Timed out while enabling automation mode` で止まる。一度手で許可しておく `[measured]`
- `xcodebuild test` を macOS の destination で回すと、テストランナーが接続前にハングして 1 件も走らないことがあった
  （Xcode 27.0、2026-09）。ロジックは `swift test`、アプリのテストは iOS Simulator で回す `[measured]`
- 画面を撮るときは `NSView.cacheDisplay` では SwiftUI の中身が写らない。`screencapture -l<windowNumber>` で撮る `[measured]`
- System Events で操作するときは、Xcode から起動した同名のプロセスに当たらないよう PID で指定し、
  ウィンドウは名前ではなく番号で持ち直す（タブを切り替えるとタイトルが変わって参照が切れる）。
  Mac がロック中だと AX ではメニューの enabled が全部 false で返るので、構成は見られても状態は見られない `[measured]`
- Vision Pro は UI テストが使えないので、起動引数で画面を選んで `simctl io screenshot` で撮る `[measured]`
