# __DISPLAY_NAME__ — エージェント向けルール

__ONE_LINER__

このファイルは常に読み込まれるので、**目次と、知らずに触ると壊すルールだけ**を置く。
説明・経緯は docs/ に置き、同じことを 2 か所に書かない。

## 環境

- __PLATFORMS_TEXT__ __MIN_OS__+ / Xcode 27+ / Swift 6
- プロジェクトファイルは JSON 形式の `__NAME__.xcodeproj/project.xcproj`（Xcode 27.2+）。フォルダは同期フォルダなので、
  既存のフォルダにファイルを足すだけならプロジェクトファイルは変わらない
- **ターゲット・ビルド設定・言語の追加は Xcode で行う**。`project.xcproj` を外部から書き換えない
  （Xcode を開いたままだと落ちる。`git checkout` での復元も同じ）。版番号（`MARKETING_VERSION`）だけはテキストで上げてよい

```
App/                    アプリ。@main・依存の登録・AppShortcutsProvider だけ
⟪widget⟫Widget/                 ウィジェット拡張。WidgetBundle と依存の登録だけ
⟪/widget⟫Packages/__NAME__Kit/   Domain ← Persistence ← AppIntentsKit ← AppUI⟪widget⟫ / WidgetUI⟪/widget⟫
AppUITests/             XCUITest と AppIntentsTesting
docs/                   PLAN.md（要件）/ adr/（設計判断）/ devlog/（経緯）
```

## 触る前に知っておくルール

1. **アクションは App Intent として定義し、UI からも `Button(intent:)` で呼ぶ**。業務ロジックは `ItemService`、
   データ変更の後処理は `dataDidChange()` の 1 か所
2. **`AppShortcutsProvider` はアプリのターゲットに置く**（パッケージに置くと App Shortcut が 0 件になる）
3. **`@Dependency` はプロセスごとに登録する**（アプリの `init()`⟪widget⟫ と `WidgetBundle.init()`⟪/widget⟫、拡張を足したらその拡張でも）。漏れても何も起きないだけで気づけない
4. **書き込む Intent と App Shortcut に登録した Intent は `allowedExecutionTargets = [.main]`**
5. **公開した Intent のパラメータ名と型は変えない**（保存済みのショートカットが外れる）
6. **`AppIntentsPackage` を宣言しない**（静的リンクの間は不要で、配布版だけ App Intents が読まれなくなる）
7. **サブビューは computed property ではなく独立した `View` struct で切る**
8. **画面の構成は `horizontalSizeClass` と縦横で 1 か所で決める**。左右に分けるのは「regular かつ横長」だけ。ピクセル幅の閾値で構成を変えない
9. **UI の文言を `String` のプロパティや引数で運ばない**。パッケージでは `Text(.copy("…"))`。文言を足したらそのターゲットのカタログの全言語を埋める
10. **ツールバー項目にはタイトルと役割（role か `.confirmationAction` などの placement）を付け、項目が複数なら `visibilityPriority` であふれる順を決める**（閉じた iPhone Duo では縦のバーやメニューに移る）。外周の余白は `contentMargins`

## コミット前に回すもの

```bash
__BUILD_COMMANDS__
(cd Packages/__NAME__Kit && swift test)
```

- 最初の 1 回は App ID・App Group・iCloud コンテナが Developer アカウントに無いので、署名で落ちる。
  Xcode の Signing & Capabilities を一度開くか、build に `-allowProvisioningUpdates` を付けて 1 回だけ回して登録する
- Debug が緑でも Release だけ落ちることがある。Release は必ず回す
- `xcodebuild test` に `CODE_SIGNING_ALLOWED=NO` を付けない（AppIntentsTesting が全部落ちる）
- 回せなかったものは PR に「回せなかった」と書く

## ドキュメントの置き場所

| 書くもの | 置き場所 |
|---|---|
| 現在のルール・結論 | `docs/*.md` / `docs/adr/` |
| 経緯・実験 | `docs/devlog/`（追記のみ。PR を作ったとき・マージしたとき） |
| 残タスク | GitHub issue（docs に `- [ ]` を残さない） |

コードコメントは why / 制約 / 落とし穴だけ、3 行以内。issue・PR 番号や将来の計画は書かない。
長い設計判断は `docs/adr/` に書き、コードには ADR への 1 行リンクだけ。

## 共通の運用ルール（全リポジトリ共通）

- **ブランチ名は役割で付ける**: `feature/` `fix/` `chore/` `docs/` `refactor/` `style/` `release/x.y.z` などの接頭辞 + 短い英語の説明（例: `fix/widget-crash`）。`claude/...` や自動生成の名前は使わない
- **アップデート文は少しあたたかく**: What's New などの告知は、冒頭に使う人へのひとことを添えてから変更点を書く。ja / en とも同じ温度にする
- **使い終わったものは消す**: マージ済みの作業ブランチ（リモートも）、一時ファイル、ビルド成果物、書き出した画像は作業の最後に削除する。`main` / `production` / 開いている PR のブランチは消さない
- `main` は統合用。`production` への push で Xcode Cloud が TestFlight まで配信する（反映は本人の OK を取ってから）
