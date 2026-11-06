# SwiftUI の規約

新規アプリの AGENTS.md にそのまま持ち込むルール。API ごとの細かい罠は Apple の `swiftui-specialist` /
`swiftui-whats-new-27` が正本で、ここには「守らないと特定の環境でだけ壊れて、手元では気づけないもの」を置く。

## 1. サブビューは独立した View struct で切る

`body` を分けるときに `private var header: some View` や `@ViewBuilder func row()` を使わない。
独立した `View` struct にする。struct は型ごとに structural identity を持ち、入力が変わらなければ
`body` の再評価が省かれる。computed property は親の `body` の一部として毎回評価される `[Apple]`。

対象外: `ViewModifier.body(content:)` と、`modifier(...)` を返すだけの View extension。
`Menu { … }` や `.toolbar { … }` の中身を返す `@ViewBuilder` / `@ToolbarContentBuilder`（メニューの項目は描き直しの単位にならない）と、
`ImageRenderer` で 1 回だけ描く画像用の View も、無理に分けなくてよい。

**一覧の絞り込みのような重い computed property は body の先頭で 1 回だけ読む**（`let cards = self.filteredCards`）。
空かどうかの分岐、`ForEach`、件数の表示でそれぞれ読むと、そのたびに全件を絞り直す。
Toreta / MiaIdolActivity の一覧は 1 回の描画で 4〜5 回、全カードを絞り込んでいた。

struct にしても、**親が毎回作り直す値を渡していれば子は毎回描き直される**。比べられないのはクロージャ
（`let select: (Day) -> Void`）と、body の中で作る `Binding(get:set:)` `[inferred]`。格子のマスのように数が多い子には、
値（選んでいる id など）だけを渡し、押したときの処理は Environment に置いた action にする。action の型は
クロージャを比べずに「選んでいるもの・開けるかどうか」だけで `Equatable` にすると、選ぶたびに全部のマスが
描き直されるのを避けられる（Patchday の `OpenDetailAction`）。効いているかは `Self._printChanges()` か
Instruments の SwiftUI テンプレートで見る（Patchday ではまだ測っていない）。

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
- 項目が 2 つ以上並ぶなら `visibilityPriority` で、残す項目と先にメニューへ回す項目を決める（ただし同じ領域の中の順番でしかない。下の実測）。自作のメニューは `ToolbarOverflowMenu` に入れる
- 正本: `swiftui-whats-new-27` の toolbar

実測で分かったこと `[measured]`（Intento、Xcode 27.0〜27.1、iPad 縦と開いた Duo）:

- **アイコンだけのボタン（`Image(systemName:)` ＋ `accessibilityLabel`）はあふれたときメニューに入らず、消える**。
  メニューの行を描けないため。`Label(..., systemImage:)` ＋ `.labelStyle(.iconOnly)` で書けば見た目は同じで、
  狭いときはメニューへ回る。`accessibilityLabel` はこの穴を埋めない。利用者から「追加ボタンが無い」と言われて初めて分かった
- 320pt のリスト列のバーに置けるのは、システムのサイドバー切替を含めて 2〜3 個。4 個置くとタイトルまで押し出される
- `visibilityPriority` は同じ領域の中での順番でしかない。trailing はサイドバー切替が 1 席使うので、2 個置くと優先度に関係なく両方畳まれた。項目を減らすのが先
- `NavigationSplitView` のリスト列に置いた `.bottomBar` の項目は描画されない（`toolbarVisibility(.visible, for: .bottomBar)` でも同じ）。
  詳細列の `.bottomBar` なら出る（iPad で確認。開いた Duo では未確認）。regular 幅では主要な操作を詳細列の下に置き、
  compact 幅（iPhone、閉じた Duo）では一覧のバーに置く（compact では詳細列が最初の画面に出ない）
- `ToolbarOverflowMenu` の中の `Picker` / 入れ子の `Menu` / `Divider` はそのまま出る。
  メニュー内の項目の `accessibilityIdentifier` は UI 階層に出ないので、UI テストはタイトルか記号名で探す
- 記号にするのが基本だが、HIG は *edit* を例外に挙げている（編集は文字のまま）。macOS のシートの確定・取消は文字のボタンにする
  （ウィンドウのツールバーに並び、タイトル付きのボタンが期待される面）

ほかに: 行の `.contextMenu` は中身が空でも空のメニューを開く（iOS の長押しが空振りした）。出し分けは中身の `if` ではなく、modifier を当てるかどうかで決める。

macOS で `NavigationSplitView` を使うときの導線 `[measured]`:

- 既定のサイドバー切替はサイドバーの右端に付くので、畳むとウィンドウの左端へ飛ぶ。`.toolbar(removing: .sidebarToggle)` で外し、
  自前の切替を `placement: .automatic` で最初に宣言すると信号機の右隣に固定される（`.navigation` は詳細側に出て、やはり動く）
- Delete キーは `List` の `.onDeleteCommand`。`keyboardShortcut(.delete, modifiers: [])` はメニューのキー等価が入力欄より先に評価されるので、検索欄で backspace が効かなくなる（試さずに捨てた）。
  クロージャの中で削除をどう実行するか（確認ダイアログの Intent に寄せる形）は IntentTodo の `app-intents-ui-and-feedback`（`references/ui-integration.md`）

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
  `^[%lld todo](inflect: true)` のようなマークアップを入れた瞬間に生で表示された `[measured]`。**パッケージのカタログでは**
  マークアップを使わず、キーを `%lld todos` にしてカタログの `plural` を埋める（`<Bundle>.bundle/en.lproj/Localizable.stringsdict` が出ることをビルド生成物で見る）。
  アプリのターゲットでは inflect が動くので、Intent の文言は `app-intents-localization` のとおり inflect でよい

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

ウィジェットの操作は Intent なので、IntentTodo の `app-intents-system-surfaces` が正本
（行のチェックは `Toggle(isOn:intent:)`、`Link` に `invalidatableContent()` を付けない、拡張の読み取りの `ModelContext`）。

## 8. アクセシビリティ

最初の画面から `apple-accessibility` のチェックリストを当てる。とくに Dynamic Type の AX サイズで
1 行に並べたボタンが崩れないこと（閉じた Duo の細い画面と同じ壊れ方をする）。

`.font(.system(size: 9))` のような固定の大きさは Dynamic Type で大きくならない。テキストスタイル（`.caption2`）か、
`@ScaledMetric(relativeTo:)` で持った大きさを使う。行の高さだけ `@ScaledMetric` にして文字を固定にすると、
大きい文字の設定で余白だけ広がる。標準のカレンダーの月表示のように、あえて固定するものは理由をコメントに書く。

- `.font(.custom("…", size:))` は既定で `.body` に合わせて大きくなる（`relativeTo:` で基準を変えられる）。固定になるのは `.system(size:)` と `.custom(_:fixedSize:)`
- 引数で大きさを受ける部品（バッジなど）は、受けた値に `@ScaledMetric` の倍率（既定値 1）を掛ける
- 固定のままでよいもの: `ImageRenderer` で書き出す画像（幅が決まった 1 枚の絵なので、端末の文字設定で崩さない）、絵の一部の飾りの記号、
  高さを固定したサムネイルに重ねる記号。どれもコメントに理由を書く

## 9. SwiftUI の型と同じ名前を付けない

自分の型に `Section` / `Group` / `Label` / `Layout` / `Settings` / `Tab` / `Form` などの名前を付けない。
同じモジュールでは自分の型が勝ち、`SwiftUI.Section { … }` と書く羽目になる（Patchday では 17 か所）。

- 画面の区分は `AppSection`、まとまりは `ProductGroup` のように、何の区分かを名前に入れる
- **別のパッケージの型でも起きる**。Domain の `Settings` は、SwiftUI と両方を import した画面のファイルで `Settings` シーンと
  ぶつかり、`Domain.Settings` と書くことになった（Patchday）。データの型は最初から `AppSettings` などにしておく
- 修飾付きの `SwiftUI.Section` が増えてきたら、名前がぶつかっている印
- **型引数の名前も同じ**。`struct CountStepper<Label: View>` の中では `Label("…", systemImage:)` が型引数を指して通らない。
  `Content` / `MenuContent` のように付ける（Toreta・チェケラ・Intento で見つかった）

## 10. 画面と処理の分け方

- **システムのモディファイアに渡すクロージャは、package の関数へ渡すだけにする**。`.translationTask` / `.fileImporter` /
  `.dropDestination` / `.task` などは、渡される値（翻訳のセッション、URL）を使う処理をそのまま中に書きたくなるが、
  そこはテストも Intent からの再利用もできない。Patchday では翻訳の要求の組み立てと結果の組み直しが 40 行ほど画面にあり、
  `Sendable` でない型への `nonisolated(unsafe)` まで画面に置いていた。`@MainActor` の関数として package に移し、
  画面は保存と失敗の記録だけにした
- 設定の画面で `Binding(get: { settings.x }, set: { service.updateSettings { $0.x = $1 } })` を繰り返さない。
  `WritableKeyPath` を受けて `Binding` を返すヘルパーを Service の extension に 1 つ置く（集合への出し入れのトグルも 1 つ）
- `@Observable` の Service で、作り直しの重い値（一覧の並び、日ごとの束）を版の番号で作り置くなら、**目印に入力をすべて入れる**。
  引数で暦（`Calendar`）を受けるのに版の番号だけで作り置いていたので、地域やタイムゾーンを変えても古い区切りが返った（Patchday）

## 11. 実地で踏んだもの

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

## 12. 見た目は同じでも意味が違う書き方

AI に書かせた SwiftUI は、画面の見た目は合っていても、コードの意味（役割・同一性・データの流れ）が違うことがある。
タッチで触る限り気づけず、キーボード・ポインタ・VoiceOver・アニメーションでだけ壊れる。

| 書き方 | 見た目 | 本当の意味 | 直し方 |
|---|---|---|---|
| `.onTapGesture` + `.accessibilityAddTraits(.isButton)` | 押せるタイル | タッチでしか押せない。キーボード（Full Keyboard Access・Mac の Designed for iPad）やポインタのホバーではボタンにならない | `Button { … } label: { … }.buttonStyle(.plain)`。押した位置が要るとき（絵の中の月など）だけ gesture |
| 絵の座標で当たりを判定する `onTapGesture(coordinateSpace:)` | 月を押すと雑学 | VoiceOver からは押す手段が無い | 同じ位置に見えない要素を置き、`accessibilityAction` を付ける（月屏風） |
| `accessibilityElement(children: .ignore)` で 1 つにまとめたタイル | 中に「−」ボタンが見える | 中のボタンは VoiceOver から消える | 消えた操作を `accessibilityActions { … }` で足す |
| `Button` に `.accessibilityElement(children: .ignore)` + `.accessibilityAddTraits(.isButton)` | 押せるタイル | 新しい要素を作るので Button の役割と操作が捨てられ、`.isButton` を描き足しているだけ。ダブルタップは要素の中心を叩くことになり、中心に別のボタンがあればそれが押される | ラベルと値は Button に直接付ける。`onTapGesture` から Button に替えたときに残りやすい |
| Button のラベルの中に別の Button（タイルの中の「−」） | 押せる場所が 2 つ | 内側が優先されるが、キーボードとポインタではタイル全体が 1 つの的になり、VoiceOver では内側に届かない | 内側の操作を `accessibilityActions` にも出す。実機で内側を押したとき外側が動かないことを確かめる |
| ラベルが `Image(systemName:)` だけのボタン | ＋ の記号 | VoiceOver は「plus」と読む。ツールバーがあふれたときのメニューにも題名が無い | `Label("追加", systemImage: "plus")`。ツールバーでは記号だけで表示される |
| `.alert(isPresented: .constant(error != nil))` | エラーが出て閉じられる | 閉じても値を書き戻せない。ボタンの処理で消しているから動いているだけ | `Binding(get:set:)` で `nil` に戻す、または `item` 版のモディファイア |
| `ForEach(Array(xs.enumerated()), id: \.offset)` に `onDelete` / `onMove` | 一覧が並ぶ | 位置が識別子なので、2 行目を消すと最後の行が消えるアニメーションになり、行の状態が隣にずれる | 要素に安定した id を持たせる（同じカードが 2 回並ぶ配列なら、記録ごとの UUID） |
| 固定の `Binding` と空の `onChange` で「動かないスライダー」 | 触れそうなスライダー | 動かしても戻るだけで、触れないことが伝わらない | `.disabled(true)` を付けて、開ける操作は外側に別のボタンで（GRAPHICA Playground はこの形） |

レビューでは「この部品は何として振る舞うべきか（ボタン・トグル・見出し・一覧の行）」を先に決め、その役割の型で書かれているかを見る。

## レビューで回す

既存のアプリをこの規約で見直すときは、最初に `scripts/swiftui_review.sh <ディレクトリ>` で候補を並べる。
grep なので候補を出すだけで、合否は決めない（`LocalizedStringResource` を返すプロパティも「String の候補」に出る）。
構成の判定・ツールバー・余白・作り置きの目印は grep で拾えないので目で見る。
