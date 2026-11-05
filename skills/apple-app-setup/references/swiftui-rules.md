# SwiftUI の規約

新規アプリの AGENTS.md にそのまま持ち込むルール。API ごとの細かい罠は Apple の `swiftui-specialist` /
`swiftui-whats-new-27` が正本で、ここには「守らないと特定の環境でだけ壊れて、手元では気づけないもの」を置く。

## 1. サブビューは独立した View struct で切る

`body` を分けるときに `private var header: some View` や `@ViewBuilder func row()` を使わない。
独立した `View` struct にする。struct は型ごとに structural identity を持ち、入力が変わらなければ
`body` の再評価が省かれる。computed property は親の `body` の一部として毎回評価される `[Apple]`。

対象外: `ViewModifier.body(content:)` と、`modifier(...)` を返すだけの View extension。

レビューでの検出:

```bash
grep -rnE 'var [a-zA-Z]+: some View' --include='*.swift' Packages App | grep -v 'var body'
# @ViewBuilder は次の行に func / var が来る書き方も拾う
grep -rnE -A1 '@ViewBuilder' --include='*.swift' Packages App | grep -E '(func|var) ' | grep -v 'var body'
```

## 2. 画面の構成は size class と縦横で決める

1. 構成（左右分割 / 1 カラム）は `horizontalSizeClass` を起点にする。`width > 700` のような閾値で構成を変えない
2. regular だけで左右に分けない。iPad の縦や開いた Duo の縦も regular。**左右に分けるのは「regular かつ横長」だけ**
3. 縦横は safe area を足し戻したウィンドウ全体の寸法で判定する（キーボードで高さが縮んだだけで切り替わらないように）
4. 判定は 1 か所に置き、子には結果（Bool や enum）を渡す。子が size class を読み直すと条件がずれる
5. 幅で決めてよいのは中身の詰め方だけ（格子の列数、折り目の回避）

`NavigationSplitView` を使うときは `columnVisibility` を `.automatic` のままにしない。開いた Duo の幅では
`detailOnly` が選ばれ、リスト列に付けたツールバー項目がまとめて消えることがある `[measured]`。

## 3. ツールバー

- 項目には必ずタイトルを付ける（画像だけのボタンも `Label` にする）。閉じた Duo では縦のバーに移り、
  入りきらないものはメニューへ回る。アイコンだけだとメニューの中で意味が伝わらない `[Apple]`
- 意味のあるボタンには role を付ける（role が無い種類の項目は `placement` で置き場所を示す）: 閉じる = `.close`、キャンセル = `.cancel`、保存・追加 = `.confirm`、全消去 = `.destructive`。
  置き場所はシステムが決める（普通の iPhone では × が右上から左上へ移る）
- 項目が 2 つ以上並ぶなら `visibilityPriority` で、残す項目と先にメニューへ回す項目を決める。自作のメニューは `ToolbarOverflowMenu` に入れる
- 正本: `swiftui-whats-new-27` の toolbar

実測で分かったこと `[measured]`（Intento、Xcode 27.0〜27.1、iPad 縦と開いた Duo）:

- **アイコンだけのボタン（`Image(systemName:)` ＋ `accessibilityLabel`）はあふれたときメニューに入らず、消える**。
  メニューの行を描けないため。`Label(..., systemImage:)` ＋ `.labelStyle(.iconOnly)` で書けば見た目は同じで、
  狭いときはメニューへ回る。`accessibilityLabel` はこの穴を埋めない。利用者の「追加ボタンが無い」で初めて分かった
- 320pt のリスト列のバーに置けるのは、システムのサイドバー切替を含めて 2〜3 個。4 個置くとタイトルまで押し出される
- `visibilityPriority` は同じ領域の中での順番でしかない。trailing はサイドバー切替が 1 席使うので、2 個置くと優先度に関係なく両方畳まれた
- `NavigationSplitView` のリスト列に置いた `.bottomBar` の項目は描画されない（`toolbarVisibility(.visible, for: .bottomBar)` でも同じ）。
  詳細列の `.bottomBar` なら出る。主要な操作は列の出方に左右されない詳細列の下に置く
- `Button(intent:)` にも role を付けられる（`Button(role:intent:label:)`、`_AppIntents_SwiftUI`）
- 自前の ⋯ メニューは iOS では `ToolbarOverflowMenu` に入れる。中の `Picker` / 入れ子の `Menu` / `Divider` はそのまま出る。
  メニュー内の項目の `accessibilityIdentifier` は UI 階層に出ないので、UI テストはタイトルか記号名で探す
- 記号にするのが基本だが、HIG は *edit* を例外に挙げている（編集は文字のまま）。macOS のシートの確定・取消は文字のボタンにする
  （ウィンドウのツールバーに並び、タイトル付きのボタンが期待される面）

macOS で `NavigationSplitView` を使うときの導線 `[measured]`:

- 既定のサイドバー切替はサイドバーの右端に付くので、畳むとウィンドウの左端へ飛ぶ。`.toolbar(removing: .sidebarToggle)` で外し、
  自前の切替を `placement: .automatic` で最初に宣言すると信号機の右隣に固定される（`.navigation` は詳細側に出て、やはり動く）
- Delete キーは `List` の `.onDeleteCommand`。`keyboardShortcut(.delete, modifiers: [])` を当てると検索欄で backspace が効かなくなる。
  クロージャで Service を直接呼ばず、確認ダイアログを開くだけにして、実行はダイアログの `Button(role: .destructive, intent:)` に寄せる
- 行の `.contextMenu` は中身が空でも空のメニューを開く。出し分けは中身の `if` ではなく、modifier を当てるかどうかで決める

## 4. 余白

外周の余白は `contentMargins` に寄せ、中身に `padding` を直接付けない。Duo は safe area が左右で違うので、
中身の padding だと片側だけ詰まる。チップの列のように端まで流したいものだけ余白を打ち消す。

## 5. UI の文言を String で運ばない

`Text` / `Label` / `Button` / `.navigationTitle` / `.accessibilityLabel` / `.help` は `String` を渡すと
`StringProtocol` のオーバーロードに解決され、**カタログを引かず、Xcode の抽出にもかからない**。
ビルドもランタイムも何も言わず、別言語の環境でソース言語の文がそのまま出る。

- 文言を持つプロパティ・引数は `LocalizedStringKey`（パッケージでは `LocalizedStringResource`）
- ユーザーのデータも通る引数は `String` のまま、リテラル側を `String(localized:)` にする
- `x ?? "読み込めませんでした"` の右辺と `AccessibilityNotification.Announcement("…")` は `String` になる。`String(localized:)` で書く
- パッケージの UI 文言は `Bundle.module` から引く。`Text("…")` の素のリテラルは実行時に `Bundle.main` を引くので、
  パッケージ側のカタログに載っていても引けない。パッケージごとに `LocalizedStringResource` を作るヘルパーを置く
- 文言を足したら、そのターゲットのカタログの全言語を同じ PR で埋める
- **パッケージのバンドルにはソース言語の `.lproj` が作られないことがある**。ソース言語の値を持つキーが 1 つも無いと
  Xcode は `en.lproj` を作らず、英語では `.copy("…")` がキーそのものに落ちる。素の文ならキー＝英語で気づかないが、
  `^[%lld todo](inflect: true)` のようなマークアップを入れた瞬間に生で表示された `[measured]`。複数形はマークアップを使わず、
  キーを `%lld todos` にしてカタログの `plural` を埋める（`<Bundle>.bundle/en.lproj/Localizable.stringsdict` が出ることをビルド生成物で見る）

レビューでの検出（第 1 引数が変数・メンバーアクセスになっている箇所を見て、型を確かめる）:

```bash
grep -rnE '(Text|Label|Button|accessibilityLabel|help|navigationTitle)\([a-z][A-Za-z]*(\.[a-z][A-Za-z]*)*[,)]' --include='*.swift' .
grep -rnE '\?\? "[^"]*[ぁ-んァ-ヶ一-龠]|Announcement\("' --include='*.swift' .
```

## 6. 使わない API

`ObservableObject` → `@Observable`（`@MainActor` を付ける）/ `NavigationView` → `NavigationStack` /
`foregroundColor` → `foregroundStyle` / GCD・Combine → Swift Concurrency /
`GeometryReader` は `containerRelativeFrame` / `visualEffect` で足りないときだけ / `AnyView` は最小限。
古い API を新しく書かない。既存の箇所の置き換えは別の PR で（`swiftui-specialist` の soft-deprecated）。

## 7. ウィジェット

インタラクティブなウィジェットを TestFlight の実機で確かめたときに踏んだもの `[measured]`（Intento 1.1.7、iOS 27.0）:

- `Link` の中身に `invalidatableContent()` を付けると、その `Link` が URL を渡さず、ウィジェット全体のタップ（アプリを開くだけ）になる。
  付けない
- 完了のチェックのように押した瞬間に見た目を変えたいものは `Button(intent:)` ではなく `Toggle(isOn:intent:)` ＋ 自前の `ToggleStyle`。
  システムがタップと同時に `isOn` を反転する（書き込みとタイムラインの再読込が届くまでの空白が消える）
- 拡張のプロセスが同じ `mainContext` を使い続けると、別プロセス（アプリ）が書いた変更が反映されなかった。
  拡張の読み取りはタイムライン・値の取得ごとに `ModelContext` を作る（効いたかは切り分けきれていない。書き込む側は `mainContext` のまま）

## 8. アクセシビリティ

最初の画面から `apple-accessibility` のチェックリストを当てる。とくに Dynamic Type の AX サイズで
1 行に並べたボタンが崩れないこと（閉じた Duo の細い画面と同じ壊れ方をする）。
