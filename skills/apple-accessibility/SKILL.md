---
name: apple-accessibility
description: SwiftUI・UIKit アプリのアクセシビリティ実装・レビューに使う。「VoiceOver対応」「Dynamic Type改善」「iOS の a11y をレビュー」「支援技術で操作できるようにして」に対応する。対象画面と支援技術に応じた実装パターンを選び、静的な指摘と実機で確認した結果を区別する。
license: MIT
metadata:
  author: touyou
  version: "0.2.1"
---

# Apple プラットフォームのアクセシビリティ対応

Apple HIG は Accessibility を Vision / Mobility / Cognitive / Hearing / Speech の5カテゴリに分けている。このスキルはその5カテゴリに沿ったチェックリストと、実際に動く SwiftUI 実装パターンを提供する。実装依頼にもレビュー依頼にも使う。

実装パターンは良質な実例から抽出して蓄積していく方針。現在の情報源と具体的なコード例は `references/implementation-patterns.md` の冒頭「情報源」節を参照。新しい良質な実例（コンテスト優勝PR、著名OSSの実装等）が見つかったら、そこにソースを追記してパターンを拡充する。

## 使い方

- **実装依頼**（「VoiceOver対応して」等）: 該当カテゴリのチェックリストを確認 → `references/implementation-patterns.md` の該当パターンをベースにコードを書く → 表面的な `.accessibilityLabel` 追加だけで終わらせず、要素のグルーピング・読み上げ順序・タップ領域まで含めて対応する
- **レビュー依頼**（「アクセシビリティ観点で見て」等）: 5カテゴリのチェックリストを順に当てて、抜けている項目を指摘する。指摘は「HIGのどのカテゴリの何の要件を満たしていないか」を明示する
- 単発の修飾子追加で終わらせず、依頼された範囲の同種 UI に共通修正が必要かを見る。アプリ全体への展開は全体改善の依頼がある場合に行う

## チェックリスト（HIG 5カテゴリ）

### Vision（視覚）
- [ ] **Dynamic Type**: AX1以上のサイズでレイアウトが崩れない・情報が欠落しない（横並びの折返し、行数制限の緩和）
- [ ] **カラーコントラスト**: 本文テキストは WCAG AA（4.5:1）以上、UI部品・大きい文字は 3:1 以上。`.secondary` 等システム標準色を無条件に信用しない（実測すること）。テーマカラーが複数ある場合は「コントラストを上げる」設定（Increase Contrast）にも Asset Catalog の appearance variant で追従させる
- [ ] **色だけに依存しない**: 色分けしている情報には形（SF Symbol）・アイコン・テキストラベルなど色以外の手がかりを併記する
- [ ] **VoiceOver**: 標準コントロールの読み上げを確認し、意味が欠ける要素に `.accessibilityLabel` / 必要な場合だけ `.accessibilityHint`。装飾要素は `.accessibilityHidden(true)`。読み上げ順序は自然なビュー構造を優先し、必要な場合だけ `.accessibilitySortPriority` で調整し、UI上の視覚順序と体感が乖離しないようにする。フォーカス位置に依存せず伝えたい状態遷移（非同期処理の完了/失敗等）は `AccessibilityNotification.Announcement` で能動的にアナウンスする

### Mobility（運動機能）
- [ ] **タップ領域は最低 44×44pt**（Apple HIG基準）。見た目のアイコンサイズと `.contentShape` によるヒット領域を分離して確保する
- [ ] **ジェスチャーの代替手段**: スワイプ操作等には必ずタップ等の代替操作を用意する
- [ ] **Voice Control**: `.accessibilityInputLabels` で「ユーザーが実際に発話しそうな言い方」を複数登録する（正式名称だけでなく略称・別名も）
- [ ] **Full Keyboard Access**: 主要な画面遷移・アクションにキーボードショートカット（`.keyboardShortcut`）を用意し、標準ボタン/リンクのフォーカスを確認し、到達できない独自コントロールにだけ適切なフォーカス対応を追加する

### Cognitive（認知）
- [ ] **一貫した語彙**: 同じ操作には常に同じ言葉を使う（「お気に入り」と「保存」を混在させない）
- [ ] **複数形・数値の言語対応**: VoiceOverの読み上げが `1 session` / `3 sessions` のように文法的に正しくなるよう `.xcstrings` の plural variation を使う
- [ ] **空状態の明示**: 検索結果0件などは `ContentUnavailableView` 等で明示し、無言の空リストを出さない
- [ ] **急な動き・点滅を避ける**: `@Environment(\.accessibilityReduceMotion)` を見て、自動アニメーション（バナーの自動切替・マーキー等）を静的表示に切り替える
- [ ] **自動で消えるUIを作らない**: シート・アラート・通知バナーはユーザーの明示操作でのみ閉じる（自動dismissしない）

### Hearing（聴覚）
- [ ] **音声だけに頼らない**: 成功/失敗などのフィードバックには `.sensoryFeedback` によるハプティクスなど、音以外のチャネルも用意する

### Speech（発話）
- [ ] **音声入力なしで全操作可能**: タッチ・キーボード・Switch Control 等の非音声入力で全機能に到達できることを確認する
- [ ] **Switch Control対応**: 複雑なUI（地図など）は `.accessibilityRepresentation` で単一の操作可能要素に畳み込み、スキャン回数を減らす（Switch Control は発話が困難なユーザーの主要な代替入力手段の一つのため HIG では Speech カテゴリの支援技術として扱われる。運動機能の観点でも同様に有効）

## 実装時の注意

- 対象 OS・deployment target・画面・支援技術を先に特定する。参照コードの API availability を対象 SDK で確認し、使えない API をそのまま追加しない。HIG の推奨と WCAG の判定基準、実プロジェクト由来の設計例は区別する。
- 指摘には場所、影響を受ける操作、根拠、修正案、検証状態を付ける。チェックリストを見ただけで実機検証済みとしない。

- **「動くはず」で終わらせない**: Xcode Accessibility Inspector か実機の VoiceOver / Voice Control / Switch Control / Dynamic Type 設定を実際に ON にして検証する。検証していない場合は「未検証」と明示する
- **既存の共通コンポーネント化**: `AStack` や `.secondaryTextStyle()` のように、a11y対応をViewModifierや汎用コンポーネントに切り出すと、アプリ全体に一貫して展開しやすい（詳細は references 参照）
- 個別の実装パターン・コード例は `references/implementation-patterns.md` を参照すること
