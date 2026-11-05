# 検証

`pnpm test` のような 1 本のコマンドでは足りない。Apple のアプリは、壊れ方ごとに見る場所が違う。
最初のコミットで全部を通し、その手順を AGENTS.md の「コミット前に回すもの」に書く。

## ビルド（3 種類）

```bash
# 1. Debug を対象 OS の全 scheme で
xcodebuild build -scheme <Name> -destination 'generic/platform=iOS'
xcodebuild build -scheme <Name> -destination 'generic/platform=macOS'

# 2. Release（Archive と同じ最適化。Debug では出ないエラーがある）
xcodebuild build -scheme <Name> -configuration Release -destination 'generic/platform=iOS'

# 3. テストのビルド（configuration は指定しない）
xcodebuild build-for-testing -scheme <Name> -destination 'generic/platform=iOS Simulator'
```

- **Debug が緑でも Release だけ落ちることがある**。Release だけ `SWIFT_COMPILATION_MODE = wholemodule` なので、
  同期版と非同期版を両方持つ API の解決が変わり、`await` が無いエラーが Archive で初めて出た `[measured]`。
  Xcode の ⌘B と MCP の `BuildProject` は既定で Debug
- `build-for-testing -configuration Release` は必ず落ちる（`@testable import` は Release で使えない）。設定を変えて通さない
- enum の case 追加、protocol の要件変更、exhaustive switch、`Sendable` / actor の制約、ビルド設定の変更は特にビルドで確かめる
- Release だけで出る診断をテストのコードでも見たいときは、`@testable` を使わない UI テストのターゲットだけを Release でビルドする
  （`xcodebuild build -target <App>UITests -configuration Release -sdk iphonesimulator`。アプリ本体も依存として Release で入る）`[measured]`
- `xcodebuild ... test` に `CODE_SIGNING_ALLOWED=NO` を付けない。UI テストランナーの再署名が飛び、
  AppIntentsTesting が `Unable to run internal tests on a Customer build` で全部失敗する。`build` に付けるのはよい `[measured]`

## テスト（3 層）

| 層 | 場所 | 見るもの |
|---|---|---|
| パッケージ | `Packages/<Name>Kit/Tests`（`swift test`） | Domain・Service のロジック、Intent の静的な宣言（`title` / `supportedModes` / `allowedExecutionTargets`） |
| AppIntentsTesting | UI テストのバンドル | Intent の実経路（`makeIntent().run()`）、Entity の解決、Spotlight |
| XCUITest | UI テストのバンドル | UI 経路でだけ壊れるもの |

- Swift Testing は suite を並列に回す。`URLProtocol` のモックなど static な状態は suite ごとに分ける
- 条件付き assert（`if el.waitForExistence { XCTAssert… }`）と固定秒の待ちを書かない。緑のまま何も確かめなくなる
- `XCTSkip` は緑に見える。前提が満たせないなら失敗させる
- UI テストのアプリは言語を固定する（`-AppleLanguages (en)`）。accessibility label で引く箇所が外れる
- テストターゲットを足したら scheme の Test action に足す。足さないと、コンパイルできなくなっても赤くならない
- 詳しくは `app-intents-testing`、XCTest からの移行は Apple の `modernize-tests`
- Swift 6 では XCUI の API は main actor にある。UI テストのクラスに `@MainActor` を付ける。`setUp` はオーバーライドしても
  nonisolated のままなので、`XCUIDevice` を触るなら `setUp() async throws` + `MainActor.run` にする `[measured]`
- `isHittable` を 1 回だけ読まない（画面遷移のアニメーション中に false を拾う）。`XCTNSPredicateExpectation` で待つ
- UI テストは文言ではなく accessibilityIdentifier で探す。文言は言語や状態（「すべてコピー」→「コピー」）で変わる
- 起動時の同意画面などは `launchArguments += ["-<UserDefaults のキー>", "<値>"]`（NSArgumentDomain）で飛ばせる。アプリにテスト専用の分岐を足さずに済む
- iPad の iPadOS 26 のタブは上部に出て、XCUITest の `tabBars` に入らない `[measured]`
- シミュレータの HID が壊れてタップできないときも、XCUITest は HID を通さないので動く `[measured]`

### コードのせいに見える環境の問題

- **`xcode-select` の Xcode が古い SDK を指している**と、新しい SDK の型が「見つからない」で落ちる。`@available` は実行時の注釈で、
  SDK に型が無ければコンパイルできない。sudo 無しなら `DEVELOPER_DIR=<Xcode>.app/Contents/Developer xcodebuild ...` `[measured]`
- **同じ名前のシミュレータが複数のランタイムにある**（iOS 26.5 と 27.0 の `iPhone 17 Pro`）。`name=` だとどちらに解決されるか
  決まらないので、`-destination 'id=<UDID>'` で固定する `[measured]`
- **失敗したビルドのあとに同じ `.build` で `swift test` を回すと、直していないのに緑になる**ことがあった（Swift 6.4）。
  直ったかどうかは `--scratch-path` を新しいディレクトリに向けたクリーンビルドで見る `[measured]`
- worktree ごとに DerivedData ができてディスクを使い切り、シミュレータへのインストールまで失敗した。並行の worktree は
  増やしすぎず、終わったら DerivedData を消す `[measured]`
- 新しい Swift で出た concurrency の診断（region isolation）は `-typecheck` では出ず、SIL 生成まで進めないと再現しない `[measured]`

### XCUITest で踏んだこと（チェケラ、Xcode 27.x）

- `xcodebuild test` に `-collect-test-diagnostics never` を付ける。付けないと、テストが通ったあと `simctl diagnose` で約 10 分止まった（チェケラの PR #10、2026-10）
- 選んだ 2 点に同時に指を置く API は無い。`tap(withNumberOfTaps: 1, numberOfTouches: 2)` は要素の中心の左右に、
  要素の幅の約 0.9 倍の間隔で指を置く。2 つのボタンの同時押しは、境目に置いた見えない要素（テストのときだけ）を叩く `[measured]`
- UIKit は `UITouch` を使い回す。タッチを記録して down と up を ID だけで結ぶと、前の押下と混ざる `[measured]`
- `@Dependency` を持つ Intent の `perform()` をアプリやテストから直接呼ぶと、ランタイムの外でアサートして落ちる `[measured]`。
  中身の Service を呼んで確かめ、Intent の経路は AppIntentsTesting で通す
- テスト用の状態は起動引数で切り替える（`-uitest-screenshot-fixture` など）。そのときは SwiftData をメモリだけにし、
  初回のシードやデータ移行を飛ばし、権限のアラートが出る画面は固定の中身で代える。判定は `#if DEBUG` の中で、Release では常に `false`

## Release に残さないもの

Debug だけのもの（サンプルのリソース、テストのフィクスチャ、計測のプローブ）が Release に入っていないことを、
**Release をビルドしてバイナリとバンドルを見て**確かめる。コードを読んだだけでは、呼び出しの 1 行が `#if DEBUG` の外に出ても気づけない。
計測のプローブの扱いそのものは `autonomous-perf-loop`（bench-harness.md / security-gates.md）が正本。

- **リソース**: シードを `#if DEBUG` で囲むだけでは、ファイルは Release にも同梱される。Release の構成だけに
  `EXCLUDED_SOURCE_FILE_NAMES` を設定して外す（チェケラは 17 本の音源を外し、Release はシードする 3 本だけになった `[measured]`、2026-10）
- **コード**: 探す文字列は「ファイル全体が `#if DEBUG` の型」と「その中でだけ読む起動引数」にする。
  `isActive` を Release で `false` にするだけの型（チェケラの `ScreenshotFixture`）は、型名も `static let` の起動引数もバイナリに残るので対象にならない

```bash
set -euo pipefail
xcodebuild build -quiet -scheme <Name> -configuration Release \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath build/release
APP=build/release/Build/Products/Release-iphonesimulator/<Name>.app
found=0
for bin in "$APP/<Name>" "$APP"/*.dylib; do        # *.dylib は Debug だけにある。無ければ飛ばす
  [ -f "$bin" ] || continue
  if strings -a "$bin" | grep -qE 'TapLatencyProbe|perf-tap-bench'; then  # パターンはアプリごと
    echo "debug-only code in $bin" >&2; found=1
  fi
done
exit $found
```

チェケラは `scripts/perf/release_check.sh` で計測の周ごとに回している。

## ビルドでは分からないもの

```bash
# App Intents の静的監査（24 ルール）と、どの面に届いているか
python3 <IntentTodo>/skills/app-intents-centric-design/scripts/audit_intents.py . --fail-on error
# 実際に出荷されるメタデータ（App Shortcut 0 件、プロパティ 0 件の Entity など）。クリーンビルドの後で
python3 <IntentTodo>/skills/app-intents-testing/scripts/inspect_appintents_metadata.py --find <Name>
# Intent の文言がカタログから漏れていないか
python3 <IntentTodo>/skills/app-intents-localization/scripts/check_intent_copy_localization.py
```

- 判定はクリーンビルドで。インクリメンタルではパッケージ側のメタデータが再生成されず、古い値が混ざる
- 「生成物が正しい」は「配布物が読まれる」を意味しない。システムの面に関わる変更は TestFlight まで通して確かめる
- String Catalog は、ソース言語でないキーに訳が無い・訳にソース言語の文字が残る・書式指定子が違う、を
  パッケージのテストで落とす（graphica の `LocalizableCatalogTests` の形）

## 画面

- レイアウトに触ったら: iPhone 縦 / 横、iPad 縦 / 横、iPad の Split View 1/2、Duo の開いた状態。
  Duo の閉じた状態と半開きは DeviceHub で手で（→ [iphone-duo.md](iphone-duo.md)）
- 実機・シミュレータの操作は Apple の `device-interaction`
- 再現しにくいバグは推測より先にログ（`os_log`）で証拠を取る。「これで直るはず」が 1 回外れたら、2 回目の前にログを仕込む
- **見た目のバグも数値で見る**。UI テストから `app.cells` などの frame をダンプすると、「空行がある」と思っていたものが
  「1 行が 2 倍の高さ」だと 1 回で分かった。逆に「要素はあるのに hittable でない」ときは、数値より先にスクリーンショットを撮る
  （キーボードが覆っていたのに、キーボードの frame は画面外を返していた）`[measured]`
- macOS と visionOS の確かめ方は [macos-visionos.md](macos-visionos.md)

## PR に書くこと

回したビルドとテストを、コマンドと結果で書く。回せなかったもの（Mac が無い、実機が要る）は回せなかったと書き、
誰がどこで確かめるかを issue に残す。
