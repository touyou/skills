# Swift iOS プロファイル (v0.3 で本実装)

Swift / SwiftUI iOS プロジェクト向けのツール選定と実行手順。`scripts/run_tier1_swift_ios.py` と `scripts/run_tier3_swift_ui.py` がこの doc に基づいて動く。

## 検出シグナル

以下のいずれか:

- ルートに `Package.swift` がある (Swift Package)
- ルートまたは `*.xcodeproj` / `*.xcworkspace` がある (Xcode project)
- monorepo: `Packages/*/Package.swift` の集合 (例: IntentTodo)

## monorepo / SPM パッケージ参照の扱い

教訓 #2: path alias フィルタが必要。Swift では:

- 同一 monorepo 内の SPM パッケージ間参照: 各 `Packages/*/Package.swift` の `name:` フィールドを集めて `import <Name>` の `<Name>` がこの集合に入っていれば「内部参照」として除外
- ルートの `Package.swift` の `dependencies` 内で `path:` を指定しているローカルパッケージも同じ扱い
- `@testable import <X>` も内部参照とみなす

## ツール選定

advisor で警告されている通り、xcodebuild 系はビルド構成 (scheme / destination / SPM の resolve 状況) に強依存して頻繁に壊れる。**「壊れない固いところ」は SwiftLint と Periphery と SwiftPM** の3つに絞る。それ以外は **null + warning** で受け流して、トレンドが歪まない事を優先する。

### test_coverage_lines

`xcodebuild test -enableCodeCoverage YES` → `xcrun xccov view --report --json <result>.xcresult` の流れ。**しかし scheme 名 / destination 名 / Provisioning が解決できないと壊れる**ので、デフォルトは null + warning に倒す。`--xcode-scheme NAME --xcode-destination NAME` を明示渡しした時だけ実行する設計にする (ROADMAP 5番台で改善候補)。

MVP では:
- 引数なし: `null` + warning (`"xcodebuild coverage skipped; pass --xcode-scheme to enable"`)
- 引数あり: 試行、失敗時も `null` + stderr 末尾を warning に

### lint_violations_per_kloc

```
swiftlint lint --reporter json --quiet
```

JSON 配列を返す。長さがそのまま total violations。`.swiftlint.yml` がある場合プロジェクト方針通りに動く。SwiftLint 不在: `null` + warning。

KLOC は `find . -name '*.swift' -not -path '*/.build/*' -not -path '*/Pods/*' -not -path '*/.swiftpm/*' -not -path '*/DerivedData/*'` の総行数。テストファイル (`*Tests.swift`) は LOC からは除外する。

### dead_code_count

Periphery がデファクト。

```
periphery scan --format json --skip-build [--targets <Target>]
```

xcodebuild との連携が必要 (Periphery は内部で SourceKit を呼ぶ)。SPM プロジェクトでは:

```
periphery scan --format json --skip-build
```

これは Package.swift をターゲットに動く。失敗時 `null` + warning。Periphery 不在: `null` + warning。

### avg_cyclomatic_complexity / p95_cyclomatic_complexity

SwiftLint の `cyclomatic_complexity` ルールが個別関数の値を返す:

メッセージ例: `"Function should have complexity 10 or less: currently complexity is 14"`

`swiftlint lint --reporter json` の出力で `rule_id == "cyclomatic_complexity"` のメッセージから `currently complexity is (\d+)` を正規表現抽出。avg と p95 を計算。

**重要**: SwiftLint の cyclomatic_complexity rule は **threshold 超過したものしか報告しない**ため、threshold 以下の関数は計測対象から外れる。これは TS Web の `eslint complexity rule` と同じ性質 (rule severity を 0 に下げて全関数を出させる、という手は SwiftLint にはない)。

このため:
- `avg` は「閾値超過関数の平均複雑度」を意味する (全関数平均ではない)
- 関数全部を見たければ `lizard` (言語横断 cyclomatic ツール) を使う代替が必要 (v0.4+)

`tooling_used.complexity_caveat` に「SwiftLint reports only over-threshold functions; avg/p95 are over-threshold subset」を入れて、解釈を間違えないようにする。

### avg_cognitive_complexity / p95_cognitive_complexity

SwiftLint には `cognitive_complexity` ルールがある (analyzer rule)。`swiftlint analyze` (lint と分かれている) で取れるが、analyzer の実行には事前に compiler arguments が必要なので **MVP では null + warning** に倒す。SwiftLint plain `lint` で取れない。

### type_errors

```
swift build 2>&1 | grep "error:"
```

または `xcodebuild build` の error 行。SPM プロジェクトでは `swift build`、Xcode-only の場合は `xcodebuild` だが後者はスキーム指定が要る。MVP では `swift build` のみ試行。

monorepo (`Packages/*/Package.swift`) の場合、各パッケージで `swift build` を試行し errors 合算。

### security_vulnerabilities

SPM 標準には `audit` 相当が無い。代替:

- `osv-scanner --lockfile=Package.resolved` (osv-scanner は brew で入る Google 製)
- 不在: `null` + warning

`Package.resolved` のないプロジェクト: `swift package resolve` を打って生成してから osv-scanner、または null + warning。

### code_duplication_pct

```
jscpd --silent --reporters json --output /tmp/jscpd-swift --pattern '**/*.swift' --ignore '**/.build/**,**/.swiftpm/**,**/DerivedData/**,**/Pods/**'
```

jscpd 不在: `null` + warning。

### cyclic_dependencies_count

SPM では Package.swift の dependencies グラフを解析できる。MVP では **null 固定 + warning**。将来は Package.swift を AST parse して有向グラフを組む実装候補。

### hallucinated_imports_count

ロジック (TS Web 版を Swift に翻訳):

1. `swift build 2>&1` の出力から `no such module '<X>'` 行を抽出
2. `<X>` が:
   - 同 monorepo の SPM パッケージ name と一致 → 除外
   - Apple フレームワーク (`Foundation`, `SwiftUI`, `UIKit`, `SwiftData`, `Combine`, `Observation`, `os`, `XCTest`, etc.) → 除外
   - Package.swift の `dependencies` で宣言された外部パッケージ name → 除外
   - 残りをカウント

Apple フレームワーク一覧は `references/swift-ios.md` の付録に保持 (固定リスト、SDK 26 時点)。

## 実行順序

1. `swift package resolve` (Package.swift がある場合) — 依存解決
2. SwiftLint 実行 (`.swiftlint.yml` 不在でもデフォルトで動く)
3. Periphery 実行 (失敗しがち、null 受容)
4. swift build (errors / hallucinated imports 検出)
5. jscpd 実行
6. (optional) xcodebuild coverage

## サンプリング (Tier 2 用)

含める:
- `Sources/**/*.swift` (SPM)
- `<AppName>/**/*.swift` (Xcode project main target)
- `Packages/*/Sources/**/*.swift` (monorepo)

除外:
- `**/Tests/**` / `**/*Tests.swift`
- `**/.build/**` / `**/.swiftpm/**` / `**/DerivedData/**` / `**/Pods/**`
- `**/Generated/**` (例: SwiftGen 出力)

抽出比率: 25 ファイル / 5000 行 上限。

---

## Tier 3: SwiftUI UI ロジックの量

### routes_count

SwiftUI のナビゲーション宣言:

| パターン | カウント方法 |
|---------|------------|
| `NavigationLink(...)` | `\bNavigationLink\s*[\(<{]` の出現数 |
| `.navigationDestination(for: ..., destination:)` | `\.navigationDestination\s*\(` の出現数 |
| `Tab(...)` (TabView 内の Tab) | `\bTab\s*\(` の出現数 |
| `.sheet(isPresented:)` / `.fullScreenCover` / `.popover` | 各 `.sheet|\.fullScreenCover|\.popover` modifier 数 |

`NavigationStack` 自体はコンテナなので routes ではない (子の destination を数える)。

### interactive_handlers_count

ユーザー操作の登録箇所:

- `Button(action:` / `Button(intent:` / `Button("...") {`
- `.onTapGesture {`
- `.onLongPressGesture {`
- `.onChange(of:`
- `.onSubmit {`
- `.onAppear {` / `.onDisappear {`
- `.gesture(`
- `.swipeActions {`
- `.contextMenu {`
- `.toolbar {` 内のボタンは別途 `Button` でカウントされる

正規表現:
```
\bButton\s*\(|\.on[A-Z]\w*\s*[\({]|\.gesture\s*\(|\.swipeActions\s*[\({]|\.contextMenu\s*\{
```

### state_hooks_count

SwiftUI の state propertyWrapper 宣言:

- `@State`
- `@StateObject`
- `@ObservedObject`
- `@Binding`
- `@Environment`
- `@EnvironmentObject`
- `@Bindable` (iOS 17+ Observation)
- `@Query` (SwiftData)
- `@AppStorage` / `@SceneStorage`

正規表現: `@(State(Object)?|ObservedObject|Binding|Environment(Object)?|Bindable|Query|AppStorage|SceneStorage)\b`

### ui_complexity_sum

`.swift` (View 含む) ファイル中の制御フロー総和:

```
\b(if|else if|case|catch|for|while|do|guard)\b|\?\?|&&|\|\|
```

guard と `??` (nil-coalescing) は Swift 特有なので追加。三項演算子 `?:` は Swift では `cond ? a : b` 形式で、TS と同じ正規表現が使える (が `??` と区別が付くように `??` を別途マッチ)。

### 除外対象 (Swift Tier 3)

- `**/Tests/**`, `**/*Tests.swift`, `**/*UITest*/**`
- `**/.build/**`, `**/.swiftpm/**`, `**/DerivedData/**`, `**/Pods/**`
- `**/Generated/**`

## tooling_used に記録する内容

```json
"tooling_used": {
  "coverage": null,                                 // xcodebuild は明示指定時のみ
  "lint": "swiftlint lint --reporter json",
  "dead_code": "periphery scan --format json",
  "complexity": "swiftlint cyclomatic_complexity rule",
  "complexity_caveat": "SwiftLint reports only over-threshold functions; avg/p95 are over-threshold subset",
  "type_check": "swift build (errors)",
  "security": null,
  "duplication": "jscpd --pattern **/*.swift",
  "cyclic_deps": null,
  "hallucinated_imports": "swift build + Package.swift cross-check + monorepo SPM filter",
  "package_manager": "swiftpm",
  "spm_packages": [...]
}
```

## 不在時挙動まとめ

| ツール | 不在/失敗時 | warning 文言 |
|-------|-----------|-------------|
| swiftlint | lint/complexity 全 null | `"swiftlint not installed; install via brew install swiftlint"` |
| periphery | dead_code null | `"periphery not installed; dead_code_count is null"` |
| swift build | type/hallucinated null | `"swift build failed; type_errors and hallucinated_imports unavailable"` |
| osv-scanner | security null | `"osv-scanner not installed; security_vulnerabilities is null"` |
| jscpd | duplication null | `"jscpd not installed; code_duplication_pct is null"` |

## 付録: Apple フレームワーク allowlist (SDK 26 時点)

hallucinated_imports 検出で除外する Apple 公式モジュール:

```
Foundation Combine SwiftUI UIKit AppKit WatchKit WidgetKit
SwiftData CoreData CloudKit
Observation
os Logging
XCTest Testing
Network URLSession
CoreLocation MapKit
AVFoundation AVKit Photos PhotosUI
StoreKit
HealthKit HomeKit
ARKit RealityKit SceneKit SpriteKit
Vision CoreML CreateML NaturalLanguage Speech Sound
GameKit
Intents AppIntents UserNotifications
ActivityKit  // Live Activities
LocalAuthentication CryptoKit Security
MetricKit
Compression Accelerate Metal MetalKit
QuickLook QuickLookThumbnailing
DeveloperToolsSupport
```

このリストは `scripts/run_tier1_swift_ios.py` 内で `APPLE_FRAMEWORKS = {...}` として持つ。SDK 更新時に doc と同期。
