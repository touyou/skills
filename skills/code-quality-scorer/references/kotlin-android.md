# Kotlin Android プロファイル (v0.4: reference doc + skeleton scripts)

Kotlin Android (Jetpack Compose 主体) プロジェクト向けのツール選定と実行手順。

**v0.4 ステータス**: reference doc は本実装、`scripts/run_tier1_kotlin_android.py` と `scripts/run_tier3_compose_ui.py` は **dogfood していないスケルトン**。実プロジェクトで使う時に必ず動作確認すること。サンプルプロジェクトが手元にないため v0.4 では「構造を揃えて、ツール出力フォーマットを文書化する」までで止める判断。

## 検出シグナル

以下のいずれか:

- `build.gradle.kts` または `build.gradle` に `com.android.application` プラグインが宣言されている
- `settings.gradle.kts` または `settings.gradle` がある + `app/build.gradle*` がある (典型的な Android Studio プロジェクト構成)
- ルートに `AndroidManifest.xml` がある (古い構成)

multi-module は典型的に `app/`, `core/`, `data/`, `feature/<x>/` のような構成。各モジュールで build.gradle が分散する。

## monorepo / multi-module 内 path 依存の扱い

教訓 #2: Kotlin の場合:

- multi-module 内のモジュール参照は `implementation(project(":<name>"))` の形 (Gradle)
- `settings.gradle.kts` の `include(":app", ":core", ":feature:auth")` から全モジュール名を取得
- `import com.<myapp>.<module>.*` の `<myapp>` は `applicationId` / `namespace` から特定
- これらを除外集合に入れて hallucinated_imports をフィルタ

## ツール選定

### test_coverage_lines / test_coverage_branches

**JaCoCo** がデファクト。Android Gradle Plugin 8+ では `enableUnitTestCoverage = true` でカバレッジが取れる:

```
./gradlew testDebugUnitTest jacocoTestReport
```

レポートは `app/build/reports/jacoco/jacocoTestReport/jacocoTestReport.xml` に XML で出る。XML を parse して `<counter type="LINE" missed="X" covered="Y"/>` から `Y / (X+Y)` を計算。同様に `BRANCH`。

`build.gradle.kts` に `jacoco` plugin が無い場合: `null` + warning (`"JaCoCo plugin not configured; coverage is null"`)。

複数モジュールの場合は集計 XML を結合する (Gradle plugin で `koverXmlReport` を使う方が簡潔)。

### lint_violations_per_kloc

**Detekt** がデファクト (Kotlin の SwiftLint 相当):

```
./gradlew detekt
```

レポートは `<module>/build/reports/detekt/detekt.xml` (Checkstyle XML 形式) または `detekt.json`。violation 数を XML/JSON の長さでカウント。

`detekt` plugin が無い場合は `ktlint` (`./gradlew ktlintCheck`) にフォールバック。両方無ければ `null` + warning。

KLOC は `*.kt` ファイルから (`*Test.kt` 除外)。

### dead_code_count

Detekt の以下のルールで集計:

- `unused-import`
- `unused-private-class`
- `unused-private-member`
- `unused-parameter`

または IntelliJ Inspection (`./gradlew inspectionsDebug` + コードインスペクション結果) — 環境依存性が高いので Detekt のみを使う。

### avg_cyclomatic_complexity / p95_cyclomatic_complexity

Detekt の `complexity/CyclomaticComplexMethod` ルール (デフォルト閾値 15)。violation メッセージから値を抽出:

```
Cyclomatic complexity: <N>
```

SwiftLint と同じ「閾値超過のみ」性質を持つ。`tooling_used.complexity_caveat` に明記する。

### type_errors

Kotlin compiler は `./gradlew compileDebugKotlin` で error を出す。stderr の `e: ` 始まりの行をカウント。

または `./gradlew --warning-mode all` で全 warning も含めた集計。

### security_vulnerabilities

**OWASP Dependency-Check Gradle plugin** がデファクト:

```
./gradlew dependencyCheckAnalyze
```

レポートは `build/reports/dependency-check-report.json`。CVE 件数を severity 別にカウント。

または **OSV-Scanner**:
```
osv-scanner --lockfile=app/build.gradle.kts  # build.gradle のサポートは限定的
osv-scanner --lockfile=gradle/libs.versions.toml  # 新しい version catalog 形式
```

OWASP plugin の方が包括的だが初回スキャンが遅い (CVE DB ダウンロードに数分)。

### code_duplication_pct

```
jscpd --silent --reporters json --output /tmp/jscpd-kotlin --pattern '**/*.kt' --ignore '**/build/**,**/.gradle/**,**/Test.kt'
```

### cyclic_dependencies_count

multi-module 間の循環は Gradle 自体が弾くので普通は 0。
モジュール内の package 間循環は Detekt の `complexity/CyclomaticComplexMethod` では取れない。代替: **Konsist** や **Module Graph Plugin** だが、MVP では `null` + warning。

### hallucinated_imports_count

`./gradlew compileDebugKotlin` の error から `Unresolved reference: <X>` を抽出 (Kotlin 2.x)。

filter:
- `org.jetbrains.kotlin.*` / `kotlin.*` (標準ライブラリ) → 除外
- `android.*` / `androidx.*` / `dalvik.*` → 除外
- `java.*` / `javax.*` → 除外
- monorepo 内のモジュール (`<applicationId>.*` プレフィックス) → 除外
- build.gradle の `implementation` で宣言された外部依存 → 除外
- 残りをカウント

### deprecated_api_count

Kotlin compiler は `@Deprecated` 付き API への参照を warning として出す:

```
warning: 'foo' is deprecated. Use bar instead.
```

`./gradlew compileDebugKotlin --warning-mode all` の出力から `is deprecated` を含む warning 数。

### outdated_dependencies_major

```
./gradlew dependencyUpdates --refresh-dependencies
```

Ben Manes' `gradle-versions-plugin` を要する。レポート `build/dependencyUpdates/report.json` から `outdated.dependencies[*]` を見て current/latest の major 差分をカウント。

plugin 不在時: `null` + warning。

## 実行順序

1. `./gradlew --offline help` (verify Gradle wrapper works)
2. `./gradlew detekt` (lint + complexity + dead_code を一発で)
3. `./gradlew jacocoTestReport` (coverage)
4. `./gradlew compileDebugKotlin --warning-mode all` (type errors + deprecated + hallucinated)
5. `./gradlew dependencyUpdates` (outdated)
6. `./gradlew dependencyCheckAnalyze` (security — 重い、optional)

`--offline` で実行できる環境では offline 推奨 (CI でネットワーク不安定な時の安定化)。

## サンプリング (Tier 2 用)

含める:
- `app/src/main/java/**/*.kt` / `app/src/main/kotlin/**/*.kt`
- `<module>/src/main/java/**/*.kt` / `<module>/src/main/kotlin/**/*.kt`

除外:
- `**/build/**` / `**/.gradle/**`
- `**/test/**` / `**/androidTest/**` / `**/*Test.kt` / `**/*Tests.kt`
- `**/Generated/**` / `**/*.g.kt` (KSP 等の生成物)

## tooling_used に記録する内容

```json
"tooling_used": {
  "coverage": "jacoco (gradle)",
  "lint": "detekt",
  "dead_code": "detekt unused-* rules",
  "complexity": "detekt complexity/CyclomaticComplexMethod",
  "complexity_caveat": "Detekt reports only over-threshold methods; avg/p95 are over-threshold subset",
  "type_check": "gradle compileDebugKotlin",
  "security": "owasp-dependency-check or osv-scanner",
  "duplication": "jscpd --pattern **/*.kt",
  "cyclic_deps": null,
  "hallucinated_imports": "kotlinc + build.gradle cross-check + multi-module filter",
  "package_manager": "gradle",
  "build_system": "gradle (kts or groovy)"
}
```

---

## Tier 3: Jetpack Compose UI ロジックの量

### routes_count

Navigation Compose の宣言:

| パターン | カウント方法 |
|---------|------------|
| `composable("<route>") { ... }` | `\bcomposable\s*\(` の出現数 |
| `composable<Route>(...)` (typed routes, Nav3) | 上の正規表現でも拾える |
| `dialog(...)` / `bottomSheet(...)` (Accompanist Nav) | `\b(dialog\|bottomSheet)\s*\(` |
| 古い Fragment ナビ (`NavGraphBuilder.fragment`) | `\bfragment\s*\(` |

`NavHost(...)` 自体はコンテナなのでカウントしない。

### interactive_handlers_count

```
\b(onClick|onLongClick|onValueChange|onCheckedChange|onChange|onSubmit|onPress|onFocusChanged)\s*=\s*\{
```

`Modifier.clickable { }`, `Modifier.combinedClickable { }`, `Modifier.toggleable { ... }` も登録パターン:

```
\bModifier\.(?:clickable|combinedClickable|toggleable|selectable|swipeable|draggable)\s*[\({]
```

### state_hooks_count

Compose の state primitives:

- `remember { ... }`
- `remember { mutableStateOf(...) }` (state = remember + mutableState の組)
- `rememberSaveable { ... }`
- `rememberCoroutineScope()`
- `collectAsState()` / `collectAsStateWithLifecycle()`
- `produceState { ... }`
- `derivedStateOf { ... }`

正規表現:
```
\b(remember(?:Saveable|CoroutineScope)?|mutableStateOf|collectAsState(?:WithLifecycle)?|produceState|derivedStateOf)\s*[\({]
```

### ui_complexity_sum

`.kt` ファイル中の制御フロートークン:

```
\b(if|else if|when|case|catch|for|while|do)\b|\?\:|&&|\|\|
```

Kotlin 特有の `when` (switch 相当) と `?:` (Elvis 演算子) を追加。

### 除外対象

- `**/build/**`, `**/.gradle/**`
- `**/test/**`, `**/androidTest/**`, `**/*Test.kt`
- `**/Generated/**`, `**/*.g.kt`

## 不在時挙動まとめ

| ツール | 不在/失敗時 | warning 文言 |
|-------|-----------|-------------|
| gradle wrapper | 全部 null | `"./gradlew not executable; Android metrics disabled"` |
| jacoco | coverage null | `"JaCoCo plugin not configured; coverage is null"` |
| detekt | lint/complexity/dead null | `"detekt plugin not in build.gradle; falling back to ktlint"` |
| OWASP dep-check | security null | `"OWASP dependency-check plugin not configured; security is null"` |
| jscpd | duplication null | `"jscpd not installed; code_duplication_pct is null"` |
| kotlinc errors | type_errors / hallucinated null | `"./gradlew compileDebugKotlin failed; type errors and hallucinated imports unavailable"` |
