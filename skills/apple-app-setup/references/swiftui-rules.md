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

ウィンドウの形を `onGeometryChange` で測るときは、`scaledToFill` の背景画像を中身と同じ階層に置かない。
画像の大きさで測った寸法が膨らみ、構成の判定が外れる。背景は `.background { … }` のモディファイアに入れる `[measured]`（チェケラ、2026-07、iPadOS 26）。

## 3. ツールバー

- 項目には必ずタイトルを付ける（画像だけのボタンも `Label` にする）。閉じた Duo では縦のバーに移り、
  入りきらないものはメニューへ回る。アイコンだけだとメニューの中で意味が伝わらない `[Apple]`
- 意味のあるボタンには role を付ける（role が無い種類の項目は `placement` で置き場所を示す）: 閉じる = `.close`、キャンセル = `.cancel`、保存・追加 = `.confirm`、全消去 = `.destructive`。
  置き場所はシステムが決める（普通の iPhone では × が右上から左上へ移る）
- 項目が 2 つ以上並ぶなら `visibilityPriority` で、残す項目と先にメニューへ回す項目を決める。自作のメニューは `ToolbarOverflowMenu` に入れる
- 正本: `swiftui-whats-new-27` の toolbar

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

## 7. アクセシビリティ

最初の画面から `apple-accessibility` のチェックリストを当てる。とくに Dynamic Type の AX サイズで
1 行に並べたボタンが崩れないこと（閉じた Duo の細い画面と同じ壊れ方をする）。

## 8. 実地で踏んだもの

GRAPHICA / Graphica Playground（2026-07〜10）で、ビルドもテストも緑のまま見た目や操作だけが壊れたもの。

- **struct に切り出すときは、その状態も一緒に下ろす**。親が `@State` を握ったままだと、struct にした意味（親の `body` の
  再評価で子を差分しない）が無くなる。別のセクションから書き換えられる状態だけを親に残す
- `.clipped()` は描画を切るだけで、**レイアウトとタップの範囲は切らない**。`aspectRatio(.fill)` の画像を ZStack に置いたカードは、
  iPad でタップの範囲が 992×992pt になり、隣のカードを押すと別のレッスンが開いた。画像は `overlay` に置き、
  `contentShape` で範囲を枠に固定する `[measured]`
- `LabeledContent` の値の側に素の `Label` を置くと、親の `LabelStyle` を拾って行の高さが 2 倍になる。`.labelStyle(.titleAndIcon)` で上書きする `[measured]`
- ナビゲーションバーの中では `Label` に `.labelStyle(.titleAndIcon)` を付けてもアイコンだけになる。文字も出すならアイコンと `Text` を自分で並べる `[measured]`
- **シートの閉じる・確定はラベル無しの `Button(role: .close)` / `Button(role: .confirm)`**（iOS 26+）。文言・グリフ・位置をシステムが持つので、
  画面ごとに「閉じる / キャンセル」「左 / 右」が割れない。何を確定するか（保存・送信）は `accessibilityLabel` で補う。
  処理中は `ProgressView` を**重ねて**ボタンの寸法を保つ（差し替えるとバーの幅が動いて押す位置がずれる）
- **ツールバーの項目は placement が同じだと画面をまたいで同じものとして扱われる**。見た目の違う項目（✨ と ⚙︎）が両方
  `.primaryAction` だと遷移でモーフする。違う項目には別の id を、同じ項目には同じ id を付ける
- `ToolbarSpacer` を固定側の placement（`topBarPinnedTrailing`）に置くと、隣の項目が出なくなった（iOS 27.0 のシミュレータ）`[measured]`
- zoom 遷移（`matchedTransitionSource` + `navigationTransition(.zoom)`）は「同じ namespace で同じ id を名乗る起点」から拡大する。
  値ベースの `NavigationLink(value:)` + `navigationDestination` は行き先にタップした場所を渡せないので、同じ作品が
  画面に 2 回出る構成では、押した場所と違うところから拡大する。ディープリンクで `NavigationPath` を使うなら、この遷移は別の設計が要る `[measured]`
- `TextField` のフォーカスは push をまたいで残る。送信時に `@FocusState` を外さないと、戻った瞬間にキーボードが復帰してタブバーを覆う `[measured]`
- 自分の型に `Layout` という名前を付けない（`enum Layout` が SwiftUI の `Layout` プロトコルを隠し、`SwiftUI.Layout` と書く羽目になる）
- 画面の大きさで構成を変えるときは、キーボードの分を足し戻して測る。入力中に高さが縮んで構成が切り替わると、ビューが作り直されてフォーカスが外れる（→ 2 の 3）
