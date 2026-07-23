---
name: apple-accessibility
description: SwiftUI / UIKit など Apple プラットフォームのアプリにアクセシビリティ対応を実装・レビューする。Apple HIG の5カテゴリ（Vision / Mobility / Cognitive / Hearing / Speech）に沿ったチェックリストと、Dynamic Type・VoiceOver・Voice Control・Switch Control・Reduce Motion・十分なタップターゲット・WCAG カラーコントラストなどの実装パターン（SwiftUI コード例つき）を提供する。ユーザーが「アクセシビリティ対応して」「VoiceOver対応して」「Dynamic Typeに対応させたい」「a11y改善して」「HIGのアクセシビリティチェックリストで見てほしい」「iOSアプリのアクセシビリティをレビューして」と依頼した時、または SwiftUI/UIKit コードに `.accessibilityLabel` 等のa11y修飾子を追加・レビューする文脈で発動する。
license: MIT
metadata:
  author: touyou
  version: "0.1.0"
---

# Apple プラットフォームのアクセシビリティ対応

Apple HIG は Accessibility を Vision / Mobility / Cognitive / Hearing / Speech の5カテゴリに分けている。このスキルはその5カテゴリに沿ったチェックリストと、実際に動く SwiftUI 実装パターンを提供する。実装依頼にもレビュー依頼にも使う。

出典: [iosdevuk-accessibility-challenge PR #4](https://github.com/robinkanatzar/iosdevuk-accessibility-challenge/pull/4)（MythConf という実アプリへの包括的アクセシビリティパスから抽出）。具体的なコード例は `references/implementation-patterns.md` を参照。

## 使い方

- **実装依頼**（「VoiceOver対応して」等）: 該当カテゴリのチェックリストを確認 → `references/implementation-patterns.md` の該当パターンをベースにコードを書く → 表面的な `.accessibilityLabel` 追加だけで終わらせず、要素のグルーピング・読み上げ順序・タップ領域まで含めて対応する
- **レビュー依頼**（「アクセシビリティ観点で見て」等）: 5カテゴリのチェックリストを順に当てて、抜けている項目を指摘する。指摘は「HIGのどのカテゴリの何の要件を満たしていないか」を明示する
- 単発の修飾子追加で終わらせず、**同種のUIパターン（一覧行・カード・地図・画像ボタン等）に横展開できないか**を必ず確認する

## チェックリスト（HIG 5カテゴリ）

### Vision（視覚）
- [ ] **Dynamic Type**: AX1以上のサイズでレイアウトが崩れない・情報が欠落しない（横並びの折返し、行数制限の緩和）
- [ ] **カラーコントラスト**: 本文テキストは WCAG AA（4.5:1）以上、UI部品・大きい文字は 3:1 以上。`.secondary` 等システム標準色を無条件に信用しない（実測すること）
- [ ] **色だけに依存しない**: 色分けしている情報には形（SF Symbol）・アイコン・テキストラベルなど色以外の手がかりを併記する
- [ ] **VoiceOver**: 全てのインタラクティブ要素に意味のある `.accessibilityLabel` / 必要に応じ `.accessibilityHint`。装飾要素は `.accessibilityHidden(true)`。読み上げ順序は `.accessibilitySortPriority` で制御し、UI上の視覚順序と体感が乖離しないようにする

### Mobility（運動機能）
- [ ] **タップ領域は最低 44×44pt**（Apple HIG基準）。見た目のアイコンサイズと `.contentShape` によるヒット領域を分離して確保する
- [ ] **ジェスチャーの代替手段**: スワイプ操作等には必ずタップ等の代替操作を用意する
- [ ] **Voice Control**: `.accessibilityInputLabels` で「ユーザーが実際に発話しそうな言い方」を複数登録する（正式名称だけでなく略称・別名も）
- [ ] **Full Keyboard Access**: 主要な画面遷移・アクションにキーボードショートカット（`.keyboardShortcut`）を用意し、全てのボタン/リンクが `.focusable()` で到達可能

### Cognitive（認知）
- [ ] **一貫した語彙**: 同じ操作には常に同じ言葉を使う（「お気に入り」と「保存」を混在させない）
- [ ] **複数形・数値の言語対応**: VoiceOverの読み上げが `1 session` / `3 sessions` のように文法的に正しくなるよう `.xcstrings` の plural variation を使う
- [ ] **空状態の明示**: 検索結果0件などは `ContentUnavailableView` 等で明示し、無言の空リストを出さない
- [ ] **急な動き・点滅を避ける**: `@Environment(\.accessibilityReduceMotion)` を見て、自動アニメーション（バナーの自動切替・マーキー等）を静的表示に切り替える
- [ ] **自動で消えるUIを作らない**: シート・アラート・通知バナーはユーザーの明示操作でのみ閉じる（自動dismissしない）

### Hearing（聴覚）
- [ ] **音声だけに頼らない**: 成功/失敗などのフィードバックには `.sensoryFeedback` によるハプティクスなど、音以外のチャネルも用意する

### Speech（発話）
- [ ] **音声入力なしで全操作可能**: キーボード操作・Switch Control・Voice Controlのタップ代替だけで全機能に到達できることを確認する
- [ ] **Switch Control対応**: 複雑なUI（地図など）は `.accessibilityRepresentation` で単一の操作可能要素に畳み込み、スキャン回数を減らす

## 実装時の注意

- **「動くはず」で終わらせない**: Xcode Accessibility Inspector か実機の VoiceOver / Voice Control / Switch Control / Dynamic Type 設定を実際に ON にして検証する。検証していない場合は「未検証」と明示する
- **既存の共通コンポーネント化**: `AStack` や `.secondaryTextStyle()` のように、a11y対応をViewModifierや汎用コンポーネントに切り出すと、アプリ全体に一貫して展開しやすい（詳細は references 参照）
- 個別の実装パターン・コード例は `references/implementation-patterns.md` を参照すること
