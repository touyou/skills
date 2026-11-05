# プロジェクトの構成

`scripts/scaffold.py` が書き出す構成と、その理由。ひな形のファイルそのものは `assets/template/` が正本。

## ディレクトリ

```
<Name>/
├── <Name>.xcodeproj/project.xcproj  JSON 形式のプロジェクトファイル（Xcode 27.2+）。コミットする
├── AGENTS.md                   目次と「知らずに触ると壊すルール」だけ
├── CLAUDE.md -> AGENTS.md      symlink（Claude Code と Codex が同じものを読む）
├── Config/                     entitlements とウィジェットの Info.plist（同期フォルダの外に置き、リソースに混ざらないようにする）
├── App/                        アプリのターゲット。@main・依存の登録・AppShortcutsProvider だけ
│   ├── Sources/
│   └── Resources/              Assets / Localizable.xcstrings / InfoPlist.xcstrings / PrivacyInfo.xcprivacy
├── Widget/                     ウィジェット拡張。WidgetBundle と依存の登録だけ
├── Packages/<Name>Kit/         ロジックはすべてここ
│   ├── Package.swift
│   ├── Sources/
│   │   ├── Domain/             値型のモデルと純粋なロジック。Apple のフレームワークに依存しない
│   │   ├── Persistence/        保存先（JSON / SwiftData / API クライアント）
│   │   ├── AppIntentsKit/      Service（業務ロジックの唯一の入口）と Intent / Entity / Query
│   │   ├── AppUI/              アプリの画面
│   │   └── WidgetUI/           ウィジェットの画面
│   └── Tests/
├── AppUITests/                 XCUITest と AppIntentsTesting（ホストアプリが要るもの）
├── docs/
│   ├── PLAN.md                 要件と展開マトリクス
│   ├── adr/                    長い設計判断
│   └── devlog/                 経緯・実験の記録（追記のみ）
```

`Package.swift` の `platforms` はメジャー版までしか書けない（`.iOS("27.0")` は不可）。
ポイントリリースの API（Duo のヒンジは 27.1）は `#available` / `@available` で囲む。
macOS は iOS だけのアプリでも `platforms` に入れる（Mac で `swift test` を回すため）。

## 層と依存の向き

```
Domain ← Persistence ← AppIntentsKit ← AppUI
                                     ← WidgetUI
```

- **Intent は宣言と接続点、業務ロジックは Service** に置く。データ変更の後処理（ウィジェットの再読込、
  Spotlight の更新、App Shortcut のパラメータ更新）は Service の `dataDidChange()` 1 か所に集める
- UI も `Button(intent:)` で Intent を呼ぶ。`perform()` を手で呼ばない（`@Dependency` はシステム経由でしか注入されない）`[Apple]`
- 1 つのパッケージに複数ターゲットを置く形にしている（IntentTodo は 7 パッケージに分けているが、
  新規なら 1 パッケージ＋ターゲット分けで足りる。パッケージを分けるのは、別のアプリでも使うとき）

## 置き場所を間違えると無音で壊れるもの

| もの | 置き場所 | 間違えると |
|---|---|---|
| `AppShortcutsProvider` | アプリのターゲット | パッケージに置くと App Shortcut が 0 件になる。ビルドは緑 `[measured]` |
| `AppDependencyManager.shared.add` | アプリの `init()` と、各拡張の `WidgetBundle.init()` など**プロセスごと** | 登録漏れはクラッシュせず「何も起きない」 `[measured]` |
| `AppIntentsPackage` の宣言 | **書かない**（パッケージが静的リンクの間） | TestFlight / App Store 版だけ App Intents がバンドルごと読まれなくなる。Xcode から入れた版では再現しない `[measured]` |
| String Catalog | **ターゲットごと**（アプリ・ウィジェット・UI 文言を持つパッケージ） | カタログの無いバンドルはどのロケールでもキー（ソース言語）がそのまま出る |
| Intent の文言 | アプリと、その Intent を使う拡張の**両方の**カタログ | 片方のプロセスでだけソース言語が出る |
| Keychain の共有 | App Group とは**別に** `keychain-access-groups` の entitlement | App Group だけでは Keychain は共有されない。`SecItemAdd` が成功を返すのに次の読み出しで消えている、の形で失敗する `[measured]` |

詳しくは `app-intents-execution-and-processes` と `app-intents-localization`。

Keychain について補足（GRAPHICA、2026-06 に実機で数時間溶かした）`[measured]`:

- コードの access group は Team ID の接頭辞付き（`<TeamID>.group.…`）で書く。entitlement の展開後の値と一致しないと黙って失敗する
- プロファイルの `keychain-access-groups` の `<TeamID>.*` は app 固有の group（`<TeamID>.<bundle id>`）しか覆わず、
  `group.` 形式は覆わなかった。拡張から読まないトークンは app 固有の group に置くとプロファイルの反映に頼らずに済むが、
  それだけでは直らず、最終的に access group 指定ありと無しの両方へ書く形でやっと実機で安定した
- 書いた直後の読み出しは内部のキャッシュで成功して見えることがある。保存の検証は 1 回の読み直しで終わらせない

bundle id・App Group・OAuth の client id のような識別子は、大文字小文字まで全箇所で突き合わせる。サーバ側の設定が
`dev.touyou.graphica`、Xcode が `dev.touyou.Graphica` で、Sign in with Apple の audience が本番でだけ合わなかった `[measured]`。

## ビルド設定の既定

scaffold.py が下書きの `project.yml` に書き、変換後の `project.xcproj` に引き継がれる。

```yaml
options:
  bundleIdPrefix: dev.touyou
  deploymentTarget: { iOS: "27.0", macOS: "27.0" }
  developmentLanguage: ja
  createIntermediateGroups: true
settings:
  base:
    SWIFT_VERSION: "6.0"
    SWIFT_EMIT_LOC_STRINGS: YES
    LOCALIZATION_PREFERS_STRING_CATALOGS: YES
    ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS: YES
    ENABLE_USER_SCRIPT_SANDBOXING: YES
    DEAD_CODE_STRIPPING: YES
```

- `SWIFT_DEFAULT_ACTOR_ISOLATION: MainActor`（Xcode の新規プロジェクトの既定）は**ひな形では入れない**。
  `AppShortcutsProvider` や `TimelineProvider` のように nonisolated な要件を持つプロトコルへの準拠が
  main actor に寄せられ、拡張のプロセスや Intent の実行で詰まりやすい `[inferred]`。
  View は元から `@MainActor`、Service は型に `@MainActor` を明示する
- `GENERATE_INFOPLIST_FILE: YES` にして、キーで書けない項目だけ部分 plist に置く
- 起動画面は `INFOPLIST_KEY_UILaunchScreen_Generation: YES`（無いと iOS 27 では提出で弾かれる `[Apple]`）
- iPad を対象にするなら 4 方向すべての向きを宣言する（Stage Manager とリサイズ前提。`UIRequiresFullScreen` は使わない `[Apple]`）
- `INFOPLIST_KEY_ITSAppUsesNonExemptEncryption: NO`（独自の暗号を使わない場合。提出のたびの質問が省ける）
- 拡張と共有するデータがあるなら App Group を entitlements に。名前は `group.<bundle id>`
- `DEVELOPMENT_TEAM` を入れておかないと、署名が要るテスト（AppIntentsTesting）が動かない

## SwiftLint

ルートに `.swiftlint.yml`。ビルドフェーズに入れるなら `ENABLE_USER_SCRIPT_SANDBOXING` との兼ね合いで
入力ファイルを宣言する。最初はローカルと CI のコマンドで回す形が簡単。

## .gitignore

`build/` `DerivedData/` `xcuserdata/` `*.xcuserstate` `.build/` `.swiftpm/` `.DS_Store`、ストア画像の書き出し先、
`.asc/`（App Store Connect の CLI の作業ファイル）。`*.xcodeproj` は**無視しない**。

## JSON 形式の project.xcproj

- Xcode 27.2 の `xcodebuild -convert-project "Xcode Project"` が書き出す形式。`.xcodeproj` のディレクトリ名は
  変わらないので `-project <Name>.xcodeproj` を渡すスクリプトはそのまま動く。Xcode 27.0 / 27.1 でも読める `[measured]`（IntentTodo）
- 中身はオブジェクト ID の参照グラフではなく、同期フォルダごとの `target-membership` / `membership-exceptions` と
  ターゲットごとのビルド設定。拡張を一部の OS から外すと、埋め込み product に `"platforms": [ "ios" ]` が付く
- 手順書のない形式なので、構成は Xcode に変えさせて差分を読む。外部から書き換えない（版番号だけは例外）
