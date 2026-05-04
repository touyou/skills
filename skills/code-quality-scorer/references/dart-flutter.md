# Dart Flutter プロファイル (v0.3 で本実装)

Flutter / Dart プロジェクト向けのツール選定と実行手順。`scripts/run_tier1_dart_flutter.py` と `scripts/run_tier3_flutter_ui.py` がこの doc に基づいて動く。

## 検出シグナル

`pubspec.yaml` が存在し、以下のいずれかを満たす:

- `dependencies.flutter` が `sdk: flutter` を指定 → Flutter アプリ/パッケージ
- `environment.flutter` キーが存在
- 上記がなくても `dependencies` に `flutter` か `flutter_test` がある

monorepo (例: `flutter_intents/app/` + `flutter_intents/packages/*`) では検出ターゲットを引数で明示的に指定する想定。デフォルトはトップレベル `pubspec.yaml`、なければ `app/` を見る。

## monorepo 内 path 依存の扱い (false positive 対策)

教訓 #2: path alias フィルタを最初に作る。Flutter の path 依存は `pubspec.yaml` の以下の形式:

```yaml
dependencies:
  app_intents:
    path: ../packages/app_intents
```

これらのパッケージ名は **「自分の monorepo 内のパッケージ」** として扱い、`hallucinated_imports` から除外する。具体的には:

- このプロジェクトの `pubspec.yaml` の `name:` (= `package:<self>/`)
- `dependencies` 内の `path:` 指定パッケージの `name:`

をすべて集めて、`import 'package:<X>/...'` の `<X>` がこの集合に入っていれば内部参照として除外する。

## ツール選定

優先順位は「広く使われていて出力が安定」が基準。**0埋めしない**原則は TS Web と同じ。

### test_coverage_lines

```
flutter test --coverage
```

成功すると `coverage/lcov.info` が出る。LCOV フォーマットを直接 parse する (lcov コマンドを必須にしない、依存を増やさないため):

```
SF:<source path>
DA:<line>,<hit_count>
LF:<lines_found>
LH:<lines_hit>
end_of_record
```

LF (lines found) と LH (lines hit) を全レコードで合計し、`LH / LF` を返す。

`flutter_test` が dev_dep に無い、または `flutter` コマンド自体がない場合は null + warning。

**branches**: LCOV の BRDA 行は Dart カバレッジでは出力されないことが多い (ツール側の制約)。null 固定 + warning でよい。

### lint_violations_per_kloc

```
dart analyze --format=machine
```

`flutter analyze` も内部で同じものを呼ぶ。`--format=machine` はパイプ区切り行を出力する:

```
INFO|LINT|invalid_use_of_internal_member|/path/file.dart|12|3|45|message
```

severity (1 列目) が `INFO` / `WARNING` / `ERROR` のいずれかの行をカウント。`ERROR` だけは別途 `type_errors` にカウントする (重複させて lint と type_errors の両方に乗せる、ESLint と tsc の関係と同じ)。

KLOC は `find . -name '*.dart' -not -path '*/.dart_tool/*' -not -path '*/build/*' -not -name '*.g.dart' -not -name '*.freezed.dart' -not -name '*.intent.dart'` の総行数で正規化。生成ファイル ( `.g.dart`, `.freezed.dart`, `.intent.dart`) は除外する。

`analysis_options.yaml` がない場合でも `dart analyze` は default ルールで動くが、プロジェクト方針との乖離が大きいので「`analysis_options.yaml` 不在」は warning に出す（数値は出す）。

### dead_code_count

`dart analyze` の出力から以下のルール ID を集計:

- `dead_code`
- `unused_element`
- `unused_field`
- `unused_local_variable`
- `unused_import`
- `unused_label`
- `unused_shown_name`

`dart_code_metrics` は archived、後継 `dart_code_metrics_presets` は別途使えるが MVP では default の dart analyze だけで十分。

### avg_cyclomatic_complexity / p95_cyclomatic_complexity

Dart の標準ツールチェーンには cyclomatic を出すルールはない。MVP では **null 固定 + warning** にする。将来 `dart_code_metrics_presets` (`cyclomatic-complexity` rule) が安定したら入れる。

### type_errors

`dart analyze --format=machine` の出力から severity=`ERROR` の行数。コンパイル不可コードがどれだけあるかの指標。0 が望ましい。

### security_vulnerabilities

```
dart pub audit
```

(Dart SDK 3.x で追加された機能。それ以前のバージョンや CI 環境では使えないことがある)

出力を解析できない場合の代替:
- `osv-scanner --lockfile=pubspec.lock` (要 osv-scanner インストール)
- どちらも無ければ null + warning

`dart pub audit` の出力フォーマットは安定途上なので、まずは数値だけ取る。詳細 advisory 保存 (TS Web の v0.3 で導入したもの) は将来入れる。

### code_duplication_pct

`jscpd` は Dart を扱える:

```
jscpd --silent --reporters json --output /tmp/jscpd-flutter --pattern '**/*.dart' --ignore '**/.dart_tool/**,**/build/**,**/*.g.dart,**/*.freezed.dart,**/*.intent.dart' lib
```

`statistics.total.percentage` を取る。jscpd 不在時は null + warning。

### cyclic_dependencies_count

Dart 用の `madge` 相当の安定ツールは見当たらない。MVP では **null 固定 + warning**。将来は自前で `import 'package:<self>/...'` を解析して有向グラフを組む実装を入れる候補。

### hallucinated_imports_count

ロジック (TS Web 版を Dart に翻訳):

1. `dart analyze --format=machine` を実行
2. 出力から `uri_does_not_exist` ルール、または "Target of URI doesn't exist" メッセージの import を抽出
3. import が `dart:` 始まり (Dart 標準ライブラリ) なら除外
4. import が `package:<self>/...` または monorepo path 依存パッケージなら除外
5. import が相対パス (`./` `../`) なら除外
6. 残りのうち、`pubspec.yaml` の `dependencies` / `dev_dependencies` / `dependency_overrides` に**存在しない**パッケージのみカウント

これにより `package:fake_ai_pkg/foo.dart` のような捏造をカウントできる。

## 実行順序

ロックファイルが破損 / 依存解決失敗の場合があるので install フェーズを必ず通す:

```
flutter pub get
```

monorepo の場合、ターゲット先で `flutter pub get` を打つ。melos がある場合は `melos bootstrap` を優先（が、これは将来の拡張）。

## サンプリング (Tier 2 用)

含める:
- `lib/**/*.dart`
- monorepo の `packages/*/lib/**/*.dart`

除外:
- `**/test/**` (test_effectiveness は別軸)
- `**/.dart_tool/**` / `**/build/**`
- `**/*.g.dart` / `**/*.freezed.dart` / `**/*.intent.dart` (生成物)

抽出比率: TS Web と同じ 25 ファイル / 5000 行 上限。

---

## Tier 3: Flutter UI ロジックの量

「届いた価値の量」を Flutter 用に翻訳する。

### routes_count

ルーティング定義の数。複数の流派があるので合算:

| パターン | カウント方法 |
|---------|------------|
| `GoRoute(path: ...)` | `\bGoRoute\s*\(` の出現数 |
| `MaterialApp(routes: { '...': ... })` | `routes:\s*\{` ブロック内の `'<path>':` キー数 (簡易: `routes:` 直後の `\{` から対応する `\}` までの範囲で string key 抽出) |
| `AutoRoute(page: ...)` | `\bAutoRoute\s*\(` の出現数 |
| `RouteBase(...` (go_router 2.x) | `\bRouteBase\s*\(` の出現数 |
| `MaterialApp(home: const Foo())` / `CupertinoApp(home: ...)` | `\b(MaterialApp\|CupertinoApp)\s*\(` の出現数 (= "/" の暗黙ルート 1 個分) |

**注意**: `Navigator.push` は runtime のページ遷移呼び出しであって route declaration ではない。`routes_count` には**含めない** (handlers 側にも出るので二重計上を避ける)。ただし routing 宣言が0個でも `Navigator.push` が大量にある場合は `state_hooks` 的な意味合いで `interactive_handlers` 側に乗る。

**MaterialApp.router の扱い**: `MaterialApp.router(routerConfig: ...)` は宣言的ルーティングで、子の GoRoute / RouteBase 数で routes が出る。`MATERIAL_APP_HOME_RE` は `MaterialApp\s*\(` (`.router` 抜き) のみマッチするので、router 形式と二重計上にはならない。

### interactive_handlers_count

ウィジェット内のコールバック登録数。Dart の named-argument 構文 `onXxx: ...` を全 `.dart` ファイルで数える:

```
\bon[A-Z]\w*:\s*[\(\[<\w]
```

具体例: `onPressed:`, `onTap:`, `onChanged:`, `onSubmitted:`, `onLongPress:`, `onSaved:`, `onDismissed:`, `onWillPop:`, etc.

加えて `Navigator.push(`, `Navigator.pushNamed(`, `Navigator.of(context).pop(` も「ユーザー操作の trigger」としてカウントする (これらは handler の中身として登場するパターンが多い):

```
\bNavigator\.(push|pushNamed|pushReplacement|pop)\s*\(
```

### state_hooks_count

UI 状態の量:

- `\bsetState\s*\(` (StatefulWidget の標準パターン)
- `\buseState\s*\(` / `\buseEffect\s*\(` (`flutter_hooks` 使用時)
- `\bValueNotifier\s*<` 宣言
- `\bChangeNotifier` を継承した class

合計を `state_hooks_count` とする。React の `useState` と概念対応する。

### ui_complexity_sum

`.dart` ファイル中の制御フロートークンの総和 (簡易 cyclomatic):

```
\b(if|else if|case|catch|for|while|do)\b|\?\s*[^:?]+\s*:|&&|\|\|
```

TS Web 版と同じ正規表現で十分動く (Dart syntax は近い)。

### 除外対象 (Flutter Tier 3)

- `**/test/**` (テストファイル)
- `**/*.g.dart` / `**/*.freezed.dart` / `**/*.intent.dart` (生成物 — UI ロジックではない)
- `**/.dart_tool/**` / `**/build/**`

### Tier 3 delta (added/removed 別出し)

教訓 #5: 純増 (net delta) だけだと整理 (削除) が見えない。`run_tier3_delta.py` 相当を Flutter 版でも作る場合は同じ規則で `_added` / `_removed` を別フィールドで出す。MVP では HEAD scoring のみ実装、delta は v0.4+。

## tooling_used に記録する内容

```json
"tooling_used": {
  "coverage": "flutter test --coverage (lcov.info)",
  "lint": "dart analyze --format=machine",
  "dead_code": "dart analyze (unused_*)",
  "complexity": null,
  "type_check": "dart analyze (severity=ERROR)",
  "security": "dart pub audit",
  "duplication": "jscpd --pattern **/*.dart",
  "cyclic_deps": null,
  "hallucinated_imports": "dart analyze + pubspec cross-check",
  "package_manager": "pub",
  "pubspec": "pubspec.yaml"
}
```

## 不在時挙動まとめ

| ツール | 不在/失敗時 | warning 文言 |
|-------|-----------|-------------|
| flutter | 全部 null | `"flutter SDK not on PATH; Flutter metrics disabled"` |
| coverage | null | `"flutter test failed or coverage/lcov.info not produced"` |
| analyze | lint/dead/type 全 null | `"dart analyze failed"` (stderr 末尾を含める) |
| pub audit | security null | `"dart pub audit unavailable (Dart SDK <3.x?)"` |
| jscpd | duplication null | `"jscpd not installed; code_duplication_pct is null"` |

`flutter` コマンドが PATH にない場合でも `dart` だけで動く部分 (`dart analyze`) は試す。`flutter test --coverage` だけが flutter を要求する。
