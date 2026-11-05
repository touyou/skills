# 情報源と振り分け先

このスキルは正本を複製せず、名前で振り分ける。ここではどこから入手し、どの場面で読むかをまとめる。

## Apple の Xcode 同梱スキル

Xcode 27 系は Apple が書いた Agent Skills を同梱している（Xcode 内蔵のエージェントが読む）。
書き出して手元のエージェントに読ませると、App Intents と SwiftUI の最新の罠を Apple の言葉で引ける。

| スキル | 読む場面 |
|---|---|
| `app-intents-specialist` | Intent / Entity / Query / AppEnum / `@Dependency` / フレーズ / 寄付の基本の罠（バージョンに依らないもの） |
| `app-intents-whats-new-27` | iOS 26 / 27 の新 API（`supportedModes`、`LongRunningIntent`、`IntentExecutionTargets`、スキーマ、`AppIntentsTesting` など）。利用可能バージョンが API ごとに書いてある |
| `siri-app-integration` | 27.3 の Siri モデル連携（`@AppIntent(.tool)`、`@AppEntity(.generable)`、`Skills.skillsbundle`、`sirimetadataanalyzer`） |
| `siri-evaluations` | Siri が Intent をどう選んだかのテスト（実機のみ） |
| `swiftui-specialist` | View の分割、`@Observable`、`ForEach` の identity、Environment、ローカライズ |
| `swiftui-whats-new-27` | `@State` のマクロ化、ツールバーのあふれ（`visibilityPriority` / `ToolbarOverflowMenu`）、`reorderable()` など |
| `app-resizability` | Duo・Stage Manager・Split View。UIKit の `UIScreen.main` / `interfaceOrientation` / `userInterfaceIdiom` / 非対称 safe area の置き換えと、起動画面・`UIRequiresFullScreen` の確認 |
| `building-document-based-swiftui-applications` | ドキュメント型アプリ（27 の `Document` プロトコル） |
| `modernize-tests` | XCTest → Swift Testing |
| `audit-xcode-security-settings` | ビルド設定のハードニング |
| `xctrace` | Instruments のコマンドライン計測 |
| `device-interaction` | 実機・シミュレータでスクショ・UI 階層・タップによる確認 |

入手: Xcode のエージェント設定からスキルを書き出す。touyou の環境では
`~/Developer/Private/xcode-27.3-skills-export/` に 27.3 beta 版を置いている。Xcode を上げたら書き出し直す
（beta 版は GA で変わる）。**SDK を消す前に AppIntents の `.swiftinterface` も退避しておく**と、次の SDK との
差分が取れる。

## App Intents 中心設計（touyou/IntentTodo の skills）

`codex plugin marketplace add touyou/IntentTodo` / `/plugin marketplace add touyou/IntentTodo` で入る 9 本。

| スキル | 読む場面 |
|---|---|
| `app-intents-centric-design` | 入口。11 の非交渉ルール、採用レベル、症状からの振り分け、`audit_intents.py` |
| `app-intents-design-session` | ユースケース → Intent 集合を対話で導く。新規アプリの最初に使う |
| `app-intents-system-surfaces` | ウィジェット・コントロール・Action ボタン・Live Activity・Visual Intelligence のどれに出すか |
| `app-intents-execution-and-processes` | 実行プロセス、`allowedExecutionTargets`、`@Dependency` の登録、パッケージ構成 |
| `app-intents-ui-and-feedback` | `Button(intent:)`、確認ダイアログ、スニペット、画面遷移 |
| `app-intents-parameters-and-prompts` | パラメータ、`parameterSummary`、`requestValue` |
| `app-intents-entities-and-search` | Entity、Query、Spotlight、App Schema |
| `app-intents-testing` | 3 層のテスト、`inspect_appintents_metadata.py` |
| `app-intents-localization` | Intent の文言とカタログ、`check_intent_copy_localization.py` |

## このリポジトリ（touyou/skills）の関連スキル

- `apple-accessibility` — HIG の 5 カテゴリのチェックリストと SwiftUI の実装パターン
- `store-screenshot-composer` — ストア画像を JSON 設定から一括生成
- `autonomous-perf-loop` — 点数を決めて計測しながら性能を詰める
- `security-watch-setup` — 依存の脆弱性を定期的に見るルーチン

## HIG とドキュメント

- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) — 標準部品を素直に使う、が出発点
- [Layout](https://developer.apple.com/design/human-interface-guidelines/layout) / [Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars) / [Widgets](https://developer.apple.com/design/human-interface-guidelines/widgets) / [App Shortcuts](https://developer.apple.com/design/human-interface-guidelines/app-shortcuts)
- [Swift API Design Guidelines](https://www.swift.org/documentation/api-design-guidelines/)
- Tech Talk「Raise the bar with iPhone Duo」— 閉じた Duo のツールバーの指針
- [TN3208](https://developer.apple.com/documentation/technotes/tn3208-preparing-your-apps-launch-screen-to-meet-app-store-requirements)（起動画面）/ [TN3192](https://developer.apple.com/documentation/technotes/tn3192-migrating-your-app-from-the-deprecated-uirequiresfullscreen-key)（`UIRequiresFullScreen`）

## 根拠ラベル

references の記述には、IntentTodo の skills と同じ根拠ラベルを付けている。

- `[Apple]` Apple の文書・セッション・同梱スキルに書いてある
- `[Apple SDK]` SDK の宣言（`.swiftinterface`）で確かめた
- `[measured]` 実際にビルド・実行して確かめた（いつ、どのバージョンかを添える）
- `[inferred]` 状況からの推測。採用前に確かめる

SDK が上がったら `[measured]` を優先して確かめ直す。
