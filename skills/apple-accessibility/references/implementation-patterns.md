# 実装パターン集（SwiftUI）

良質なアクセシビリティ実装の実例からパターンを抽出して蓄積する。新しい良質な実例が見つかったら、下記「情報源」に追記した上で該当パターンを本文に追加していく（単一ソースに固定しない）。SKILL.md のチェックリストと対応させて使う。

## 情報源

- [iosdevuk-accessibility-challenge PR #4](https://github.com/robinkanatzar/iosdevuk-accessibility-challenge/pull/4)（MythConf アプリへの包括的アクセシビリティパス。iOSDevUK 2026 Accessibility Challenge 優勝PR） — 「Vision — 色以外の手がかりを併記する」節までの大半のパターンの一次情報源（2026-07時点）
- graphica（iOS SwiftUIアプリ、touyou/graphica、private） — 本スキルのチェックリストで実アプリをレビューした際に見つかった追加パターンの情報源（Increase Contrast colorset variant、VoiceOverへの能動通知。2026-07時点、[Issue #5](https://github.com/touyou/skills/issues/5)）。private リポジトリのため直接リンクは張らず、コード抜粋のみ引用する

## Vision — Dynamic Type

### AX1 以上で HStack を VStack に切り替える汎用コンテナ

横並びレイアウトは大きな文字サイズで折り返して崩れがち。`dynamicTypeSize.isAccessibilitySize`（AX1以上で true）を見て自動で縦積みに切り替える。

```swift
struct AStack<Content: View>: View {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    // 名前は「どちらのレイアウトで使う値か」を表す: hAlignment は HStack 採用時に使う
    // VerticalAlignment（行内でのタテ位置合わせ）、vAlignment は VStack 採用時に使う
    // HorizontalAlignment（列内でのヨコ位置合わせ）。HStack/VStack の alignment 引数の型と揃えている。
    let hAlignment: VerticalAlignment
    let vAlignment: HorizontalAlignment
    let hSpacing: CGFloat?
    let vSpacing: CGFloat?
    let content: () -> Content

    init(
        hAlignment: VerticalAlignment = .center,
        vAlignment: HorizontalAlignment = .leading,
        hSpacing: CGFloat? = nil,
        vSpacing: CGFloat? = nil,
        @ViewBuilder content: @escaping () -> Content
    ) {
        self.hAlignment = hAlignment
        self.vAlignment = vAlignment
        self.hSpacing = hSpacing
        self.vSpacing = vSpacing
        self.content = content
    }

    var body: some View {
        if dynamicTypeSize.isAccessibilitySize {
            VStack(alignment: vAlignment, spacing: vSpacing, content: content)
        } else {
            HStack(alignment: hAlignment, spacing: hSpacing, content: content)
        }
    }
}
```

`HStack` を使っている箇所を機械的に `AStack` へ置き換えるだけで、AX1以上のレイアウト崩れの大半を防げる。

さらに折返しが起きる**その瞬間**に縦積みしたい場合（AX1を待たず、長い文字列が来たら即座に）は `ViewThatFits` を使う方が正確。

### 行数制限をAXサイズで緩和する

固定の `.lineLimit(_:)` は大きな文字サイズで情報が丸ごと切れる原因になる。AX1以上でだけ許容行数を増やす。

```swift
extension View {
    /// Like `.lineLimit(_:)` but allows extra lines once Dynamic Type enters
    /// accessibility sizes (AX1+) so larger glyphs do not amplify truncation.
    func a11yLineLimit(_ standard: Int, extra: Int = 2) -> some View {
        modifier(A11yLineLimitModifier(standard: standard, extra: extra))
    }
}

private struct A11yLineLimitModifier: ViewModifier {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    let standard: Int
    let extra: Int

    func body(content: Content) -> some View {
        content.lineLimit(dynamicTypeSize.isAccessibilitySize ? standard + extra : standard)
    }
}
```

### アイコンサイズ・スペーシング・タップ領域を文字サイズに追従させる

数値ベースのサイズ指定は `@ScaledMetric` にすると Dynamic Type に連動してスケールする。タップ領域を先に決めた最小値でクランプするとHIG基準（44pt）を割らない。

```swift
struct FavouriteButtonView: View {
    @ScaledMetric private var starSize: CGFloat = 18
    @ScaledMetric private var tapSize: CGFloat = 44
    // ...

    var body: some View {
        Button { /* toggle */ } label: {
            Image(systemName: isFavourite ? "star.fill" : "star")
                .font(.system(size: starSize, weight: .semibold))
                .frame(width: max(44, tapSize), height: max(44, tapSize))
                .contentShape(.rect)
        }
    }
}
```

## Vision — カラーコントラスト

システムの `.secondary` は思ったよりコントラストが低いことがある(例: 白背景で 3.44:1 — WCAG AA本文基準 4.5:1 未達)。**実測せずに信用しない**。専用の Color Asset を用意し、app全体を単一のmodifier経由で置き換えると監査しやすい。

```swift
extension View {
    /// Use this instead of `.foregroundStyle(.secondary)` — system `.secondary`
    /// resolves to a color that fails WCAG AA (3.44:1) on white.
    func secondaryTextStyle() -> some View {
        foregroundStyle(Color.textSecondary) // Assets.xcassets の light/dark 両対応カラー
    }
}
```

ブランドカラーやステータスカラー（黄色・ミント等）も同様に、light/dark それぞれで実測し WCAG AA（本文4.5:1 / UI部品・大文字3:1）を下回るものは差し替える。`AccentColor` も light/dark で別値を明示的に持たせると管理しやすい。

### 「コントラストを上げる」設定への追従は Asset Catalog の appearance variant で

`.secondaryTextStyle()` のような単一カラー置き換えは light/dark の2軸はカバーできるが、システム設定「設定 → アクセシビリティ → コントラストを上げる」（Increase Contrast, `contrast: high`）には追従しない。テーマカラーが複数ある場合、個別に `@Environment(\.colorSchemeContrast)` を見て分岐するより、**Asset Catalog の Color Set 側に `contrast: high` の appearance variant を追加する**方が低コストかつ網羅的。

```swift
// Theme.swift
// Contrast: High（Settings → アクセシビリティ → コントラストを上げる）の Variant も
// LineColor.colorset 側に持たせてあり、不透明度の高い色に切り替わる。
static let line = Color("LineColor")
```

`LineColor.colorset/Contents.json` に `"appearances": [{"appearance": "contrast", "value": "high"}]` を持つ colorset を1つ追加するだけで、コード側は一切変更せずにシステム設定へ自動追従する。テーマカラーが複数ある app（例: 6色のパレットを持つ app）では、ViewModifierを都度分岐させるより Asset Catalog 側にvariantを積む方が全体に一貫して展開しやすい。

## Vision — 色以外の手がかりを併記する

色分けだけに頼らず、SF Symbol・アイコン・テキストで冗長化する。

- カテゴリ分けには種類ごとに異なる SF Symbol を割り当てる（例: 種別Aは `hammer.fill`、種別Bは `mic.fill`）
- トグル状態（お気に入り等）は色変化に加えて `sparkles` のようなオーバーレイ装飾で形の変化も出す
- 外部アプリを開くリンクには `arrow.up.right.square` を添えて「これは外部に飛ぶ」と形で示す
- タップ可能な行には `chevron.right` を添えて、リンク色に頼らず「押せる」ことを示す

## Vision / Speech — VoiceOver・Switch Control で複雑なUIを畳む

`MapKit` の `Map` のような複雑なネイティブビューは、そのままだと VoiceOver/Switch Control のスキャン対象が大量発生して事実上操作不能になる。`.accessibilityRepresentation`（iOS 15+）で「単一のボタン」に置き換え、実処理（例: 外部の地図アプリを開く）に委譲するのが定石。

```swift
private var mapView: some View {
    LocationSnapshotMapView(location: location, coordinate: coordinate)
        .accessibilityRepresentation {
            // Substitute the map's complex a11y subtree with a single button that
            // VoiceOver/Switch Control users can activate to open Apple Maps.
            Button("") {
                openInMaps()
            }
            .accessibilityLabel(Text("Open in Maps: \(location.name)"))
            .accessibilityInputLabels([
                "Map", "Open map", "Open in Maps",
                "Show map", "Directions", location.name
            ])
        }
}
```

晴眼ユーザーには通常どおりインタラクティブな `Map` を見せつつ、支援技術のツリーだけを差し替えられるのがポイント。同じ発想は「操作対象は多いが本質的な操作は1つ」なUI（複雑なグラフ、カスタムピッカー等）全般に応用できる。

## Vision — 要素のグルーピングと読み上げ順序

- 一覧の1行やカードは `.accessibilityElement(children: .combine)` で単一要素に畳み、VoiceOverのスワイプ回数を減らす
- 畳んだ中に独立して操作できるボタン（お気に入り星など）がある場合は `.accessibilityElement(children: .contain)` + `.accessibilitySortPriority` で「本体」と「ボタン」を2つの独立フォーカスターゲットに分ける（`NavigationLink` の中にButtonをネストしただけだと、後者がVoiceOverから到達不能になりがち）
- 読み上げ順序は視覚的な配置ではなく `.accessibilitySortPriority` で明示制御する（例: 「種別→タイトル→話者→会場→お気に入り」の順で読ませたい場合、種別が視覚的に右上にあっても優先度で先に読ませる）
- 装飾目的だけのアイコン・画像は `.accessibilityHidden(true)`
- 画面タイトルには `.accessibilityAddTraits(.isHeader)`
- URLやホスト名をそのまま読み上げさせず、サービス名など人間が分かる形に変換した `.accessibilityLabel` を組み立てる（例: 生の "github.com/alice" ではなく "GitHub account, alice"）
- VoiceOverには読ませたいが Switch Control / Full Keyboard Access のフォーカス対象からは外したい非インタラクティブ要素（区切り行等）には `.accessibilityRespondsToUserInteraction(false)`

## Vision — 非同期処理の状態遷移を能動的にアナウンスする

進捗表示や画面上のステータス文言の更新だけでは、フォーカスがそこに無いVoiceOverユーザーには完了/失敗が伝わらない。特に処理に数秒〜十数秒かかる非同期処理で顕著な穴になる。`AccessibilityNotification.Announcement`（iOS 17+ の `post()` API。それ以前は `UIAccessibility.post(notification: .announcement, argument:)`）で、フォーカス位置に関係なくVoiceOverに読み上げさせる。

```swift
// CreateView.swift
// 生成は数秒〜十数秒かかる async 処理。VoiceOver 利用者がステータスラインに focus を
// 当て続けなくても局面遷移（特に完了/失敗）が分かるよう、phase 変化を能動読み上げする。
.onChange(of: generationPhase) { _, newPhase in
    if let spoken = newPhase.spokenLabel {
        AccessibilityNotification.Announcement(spoken).post()
    }
}
```

「進捗インジケーターが動いているだけでは完了が伝わらない」「特定要素にフォーカスを固定できない」というケース全般（保存・送信・生成・同期処理等）に応用できる汎用パターン。乱用すると読み上げが煩くなるため、状態遷移の節目（開始・完了・失敗）だけに絞る。

## Mobility — Voice Control のエイリアス

`.accessibilityInputLabels` にはラベルの正式名称だけでなく、ユーザーが実際に発話しそうな別名・略称・俗称も並べる。

```swift
.accessibilityLabel(isFavourite ? Text("Remove session from favourites") : Text("Favourite"))
.accessibilityInputLabels([
    "Favourite", "Favorite", "Star", "Bookmark",
    "Save", "Add to schedule", "Remove from schedule"
])
```

## Mobility — Full Keyboard Access / ショートカット

画面上に見えるUIを増やさずに `⌘1`〜`⌘4` のようなアプリ全体ショートカットを仕込むには、`.hidden()` にした `Button` を `.background` に忍ばせる。

```swift
.background {
    Button("Programme") { selectedTab = .programme }
        .keyboardShortcut("1", modifiers: .command)
        .hidden()
}
```

主要なフォーム操作（検索フォーカス、お気に入りトグル等）にも個別にショートカットを割り当て、Tabキーの連打なしで到達できるようにする。

## Mobility — ジェスチャーに代替操作を用意する

タブ切り替えや画面遷移をスワイプだけに頼らない。例えばセグメントピッカーの精密なタップが難しいユーザー向けに、同じ操作を横スワイプでもできるようにする（`NavigationStack` の標準エッジスワイプバックも維持する）。

## Cognitive — Reduce Motion 対応

`@Environment(\.accessibilityReduceMotion)` を監視し、自動で動き続けるUI（自動切り替わりバナー、マーキーテキスト等）は静的表示にフォールバックする。

```swift
@Environment(\.accessibilityReduceMotion) private var reduceMotion

var body: some View {
    if reduceMotion {
        Text("N parallel talks") // 静的な要約に固定
    } else {
        // 8秒ごとに自動で切り替わる通常表示
    }
}
```

シート・アラート・通知バナーは実装時に「これは自動で消えるか？」を必ず確認し、自動dismissのタイマーは入れない。

## Hearing — ハプティクスの併用

音声フィードバックだけに頼る操作結果通知には `.sensoryFeedback`（iOS 17+。それ以前は `UINotificationFeedbackGenerator` 等で代替）を添える。

```swift
.sensoryFeedback(.success, trigger: isFavourite)
```

## Cognitive — plural variation

`Localizable.xcstrings` の plural variation を使い、`1 session` / `3 sessions` のような数え上げをVoiceOverが不自然な文法で読み上げないようにする。ハードコードした文字列連結（`"\(count) session"`）は避ける。

## Cognitive — 空状態の明示

検索結果0件などを無言の空リストで終わらせず、`ContentUnavailableView`（iOS 17+。それ以前は同等のカスタムビューで代替）で「何も見つからなかった」ことを視覚・VoiceOver双方に明示する。

## 横展開の視点（レビュー時に確認すること）

1件だけ直して終わらせず、同種のUIパターンに同じ対応が漏れていないか確認する:

- カード/行コンポーネントが複数種類ある場合、`.accessibilityElement(children: .combine)` と読み上げ順序の指定は全種類に揃っているか
- タップ領域44pt保証は、アイコンボタン全般（お気に入り・ソーシャルリンク・カード）に横展開されているか
- `.accessibilityInputLabels` は主要な操作ボタン全部に設定されているか、それとも一部だけか
- Reduce Motion 対応は自動アニメーションを使っている箇所全てをカバーしているか
