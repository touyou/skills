# Code Quality Scorer — Roadmap

このファイルは **コンテキストクリア後の継続開発用の引き継ぎ文書**。SKILL.md は使用者向け、ROADMAP.md は開発者向け（次の version を作る人）。

## 現在の状態（v0.4, 2026-05-04 確定）

v0.4 でやったことの要約:
- **Tier 2 sub-agent 化** (`scripts/judge.py`) — `claude -p` を N=3 独立 process で spawn して真の独立判定。flutter_intents で smoke test 通過 (cohesion=4 を 2 サブエージェントが両方独立判定、confidence=high)。コスト ~$0.50-$1.00/run、`--judge-model haiku` で削減可
- **score_history.py を 4 言語対応** — install command + tier1/tier3 script の選択を profile-aware に。Flutter は `flutter pub get`、Swift は `swift package resolve`、Kotlin は `./gradlew --version` (warm)
- **Kotlin Android プロファイル skeleton** — reference doc は本実装、`run_tier1_kotlin_android.py` と `run_tier3_compose_ui.py` は dogfood 環境がないため structure だけ揃えて Detekt 系の主要メトリクスのみ実装。ユーザーが Compose プロジェクトで実走させて埋める想定

### 過去の状態（v0.3, 2026-05-04 確定）

v0.3 でやったことの要約:
- TS Web の security 分類 (code-driven / newly-disclosed / resolved) を generate_trend.py で出すようにした (v0.2 dogfood で唯一誤読していた pain の解消)
- cognitive_complexity (sonarjs) を tier1 に追加 — eslint pass の cache 再利用で実行コスト 0
- deprecated_api_count (eslint deprecation rule) と outdated_dependencies_major (npm/pnpm/yarn outdated) を追加 — AI コード品質の核心指標
- Dart Flutter プロファイル本実装 (`run_tier1_dart_flutter.py` / `run_tier3_flutter_ui.py`) — flutter_intents で dogfood 通過
- Swift iOS プロファイル本実装 (`run_tier1_swift_ios.py` / `run_tier3_swift_ui.py`) — IntentTodo (7 SPM monorepo) で dogfood 通過
- 両プロファイルとも monorepo path 依存フィルタを最初から組み込み (教訓 #2 の言語横断適用)
- v0.3 #4 (Tier 2 sub-agent 化) は1日仕事のため見送り、v0.4 priority 1 に再配置

### 過去の状態（v0.2, 2026-05-04 確定）

### 実装済み機能

| カテゴリ | 機能 | ファイル | 動作確認 |
|---------|------|---------|---------|
| HEAD スコアリング | Tier 1 + 2 + 3 を一発で出す | `scripts/run_tier1_typescript_web.py` `run_tier3_ui_logic.py` `aggregate.py` | ✅ whitebox-root/frontend |
| 履歴 walk | git worktree ベース、本流を汚さない | `scripts/score_history.py` | ✅ 3コミット成功 |
| trend report | per-dimension スパークライン + delta テーブル | `scripts/generate_trend.py` | ✅ markdown 出力済 |
| bus factor | KCI delta を 2 ref 間で計算 | `scripts/run_bus_factor.py` | ✅ -0.007 動作 |
| Tier 3 delta | added/removed を別出し | `scripts/run_tier3_delta.py` | ✅ 動作 |
| Tier 2 ルーブリック | confidence + サンプル不足デフォルト | `references/rubric-*.md` | ✅ 改善反映済 |

### 計測している観点（Tier 別）

**Tier 1（決定論的、トレンドの主軸）**:
- test_coverage_lines / test_coverage_branches （vitest/jest/nyc）
- lint_violations_per_kloc （eslint/biome）
- dead_code_count （knip/ts-prune）
- avg/p95_cyclomatic_complexity （eslint complexity rule）
- type_errors （tsc）
- security_vulnerabilities {high, medium, low} （pnpm/npm/yarn audit）
- code_duplication_pct （jscpd）
- cyclic_dependencies_count （madge）
- hallucinated_imports_count （tsc + tsconfig paths filter）

**Tier 2（LLM 判定、スナップショットのみ）**:
- cohesion / dry / bug_prone_patterns / test_effectiveness
- 各 confidence: high/medium/low + files_sampled

**Tier 3（UI ロジック量、git diff ベース）**:
- routes_count / interactive_handlers_count / state_hooks_count / ui_complexity_sum
- 2 ref 間で added / removed を別出し

### dogfood 結果（whitebox-root/frontend, 2026-04-02 → 2026-05-03）

```
lint density       6.68 → 5.82  (-0.86)  改善
type errors          69 → 64    (-5)     改善
duplication       3.39% → 3.23% (-0.16)  改善
security high        30 → 33    (+3)     悪化（依存由来ノイズ）
security medium      29 → 40    (+11)    悪化（依存由来ノイズ）
handlers          1008 → 1147 (+139)     +222/-83 (整理しながら追加)
hooks              218 → 250   (+32)     +38/-6
complexity        3191 → 3743 (+552)     +687/-138
KCI delta: -0.007 (within noise)
```

これが「v0.2 で何を出せるか」のサンプル。

---

## v0.5 優先事項

### 🔥 1. Dart Flutter / Swift iOS プロファイルの本格化 (v0.3 で MVP は通った)

v0.3 で動くところまで作った。実プロジェクトで使い込みながら以下を埋めていく:

**Flutter**:
- cyclomatic / cognitive complexity の代替ツール検証 (`dart_code_metrics_presets` の安定性確認)
- cyclic_dependencies 自前実装 (Package.swift / pubspec.yaml の `import 'package:'` を有向グラフ化)
- `dart pub audit` の出力フォーマット安定化を待って security_advisories 詳細保存
- monorepo (`flutter_intents/app/` + `packages/*/`) を一発で全部スキャンする `--monorepo` モード
- `flutter test --coverage` の branch coverage 取得 (Dart coverage 側の機能追加待ち)

**Swift iOS**:
- xcodebuild coverage の `--xcode-scheme` / `--xcode-destination` 受け取り実装
- Periphery のセットアップ自動化 (`periphery scan-syntax` だけなら build なしで動く)
- SwiftLint の cyclomatic_complexity rule severity を 0 にする手段の調査 (全関数を計測対象にする)
- SwiftLint analyzer rule の `cognitive_complexity` を有効化 (compiler args が要るので xcodebuild 連携)
- `swift build` の error 解析を `swift build -Xfrontend -dump-ast` 等で精密化

実プロジェクトで dogfood した時に「ここがおかしい」が出てきたら個別 issue 化して潰す。

---

### 🔶 2. Kotlin Android プロファイル本実装 (v0.4 skeleton)

reference doc 完備、scripts は Detekt のみ実装した skeleton。実プロジェクトで dogfood しながら埋める残作業:

- JaCoCo / Kover XML parsing → coverage
- `./gradlew compileDebugKotlin --warning-mode all` parsing → type_errors / hallucinated_imports / deprecated
- OWASP dependency-check / osv-scanner → security
- `gradle dependencyUpdates` → outdated_dependencies_major
- jscpd `--pattern '**/*.kt'` → code_duplication_pct
- multi-module 内 namespace を `applicationId` から自動抽出
- Compose Tier 3 の正規表現を実プロジェクトで calibration

サンプル候補: Now in Android (Google 公式)、または個人の Compose プロジェクト。

### 🔶 3. v0.4 完了後の小残務 (next session で 30 分以内)

- TS Web の `run_tier1_typescript_web.py` を実プロジェクト (whitebox-root/frontend など) で 1 回回して、cognitive_complexity / deprecated_api / outdated_deps が **実 eslint output で意図通り抽出されるか** を確認。v0.3 では合成データテストと最小 fixture (`/tmp/ts-smoke`) のみで、本物のプロジェクトでは未走行。
- Flutter の `MaterialApp.router(routerConfig: GoRouter(...))` 構成で **GoRoute 数が "/" を含むか / 含まないか** を実プロジェクトで確認 (今は GoRouter の最初の GoRoute が "/" になる前提でカウントしている。プロジェクト側で `home:` を別途書いてる場合は重複カウントの可能性が残る)。
- iOS の `cyclomatic_complexity` トレンド軸利用は危険 (`.swiftlint.yml` 変更で値が動く)。`normalization.md` に追記済だが、`generate_trend.py` でこの dimension を Swift プロファイルだけ表示しないオプションも検討余地。
- Tier 2 sub-agent の `--judge-model haiku` を実プロジェクトで試して、quality vs cost のトレードオフを確認。Opus 4.7 デフォルトは ~$0.50-$1.00/run、haiku は推定 1/10 程度。
- score_history の Flutter / Swift / Kotlin プロファイルでの worktree 経路は **未 dogfood**。実プロジェクトで履歴 walk を走らせると `flutter pub get` の cache 共有問題、`swift package resolve` の repository fetch 問題、Gradle wrapper のダウンロード問題などで詰まる可能性あり。詰まったら `--skip-install` フォールバックで先に進める判断を入れる。


---

## v0.5+ 候補

### 5. cisq_reliability_weaknesses (Semgrep)

ISO/IEC 5055 の Reliability 138 weaknesses を Semgrep ルールセットで検出。Empty/overly-broad catch、Resource Shutdown 漏れ、Timeout 欠落、Unbounded Retry 等。`bug_prone_patterns` (Tier 2) の決定論的下支えになる。

**実装メモ**: Semgrep をプロジェクトに入れずに `npx @semgrep/cli` で走らせる。p/owasp-top-ten + p/javascript の組み合わせから始める。

### 6. mutation_score (Stryker)

カバレッジ % が低くてもテストは効果的なケース、逆も。mutation testing で「テストがバグを検出する力」を直接測る。**コスト高**（プロジェクト全体で数十分〜数時間）なので、`--mutation-test` opt-in フラグで実装。

### 7. coupling/instability (Martin metrics)

各モジュールの Afferent (Ca) / Efferent (Ce) / Instability `I = Ce/(Ca+Ce)` を madge ベースで計算。「抽象パッケージが I≈1（不安定）になっている」異常を検出。

### 8. public_api_doc_ratio

公開 API のうち TSDoc/JSDoc が付いているものの割合。`eslint-plugin-jsdoc` の `require-jsdoc` で取れる。

### 9. accessibility (UI プロジェクト用)

axe-core / @axe-core/cli を使ってビルド済みの DOM をチェック。**実行ビルドが要る**ので CI 統合を視野に入れる必要がある。HEAD スコアリングだけ、history walk からは外す。

### 10. Kotlin Android プロファイル本実装 (Flutter / Swift iOS は v0.3 で完了)

`references/kotlin-android.md` のプレースホルダを埋める。

**ツール候補**:
- coverage: JaCoCo (`./gradlew jacocoTestReport`)
- lint: Detekt (`./gradlew detekt`) — JSON/XML reporter
- dead_code: Detekt の `unused-*` ルール群、または ktlint
- complexity: Detekt `complexity` ルール
- type_errors: Kotlin compiler の警告/エラー
- security: OWASP Dependency-Check Gradle plugin、または gradle audit (新興)
- duplication: jscpd `--pattern '**/*.kt'`

**Tier 3 (Jetpack Compose)**:
- routes_count: `composable("<route>")` の宣言数 (Navigation Compose)
- handlers: `onClick = { }`, `onValueChange = { }`, `onCheckedChange = { }`, etc.
- state: `remember { mutableStateOf(...) }` / `rememberSaveable` / `collectAsState()`
- complexity: `when`, `if`, `for`, `while` トークン

**サンプルプロジェクト**: 未指定。Compose ベースの個人プロジェクトがあれば dogfood に使える。

---

## v0.1/v0.2 で得た教訓（v0.3 以降の判断材料）

### 🔑 決定論性が load-bearing constraint

トレンド追跡が主目的なので、「同じコード→同じスコア」は妥協できない。**Tier 2 を sub-agent 化するまでは、トレンド軸として使わない**。SKILL.md にも明記済。

### 🔑 path alias フィルタは絶対必要（false positive 対策）

`hallucinated_imports` の精度は tsconfig.json の `paths` を読まないと壊れる。Next.js プロジェクトで頻発。同じ問題が:
- jsconfig.json paths（純 JS プロジェクト）
- webpack/vite resolve.alias 設定
- Flutter の package: prefix
- Swift の Package.swift の dependencies
... にも当てはまる。各言語プロファイルでの実装時に**最初に作る pitfall リストに入れる**こと。

### 🔑 `--skip-install` は trend 分析を壊す

eslint・tsc・jscpd 等は node_modules がないと走らない。`--skip-install` を使うと該当 metric が全部 null になる。score_history.py のドキュメントとデフォルト挙動で「install が高い時のみオプトアウト」を強調。

### 🔑 partial_composite_score を主指標として推す

11 metrics 全部が埋まることは稀で、`composite_score` は null になりがち。`primary_score` フィールド（complete があれば composite、なければ partial）を使う設計にしてある。UI 表示時はこちらを使う。

### 🔑 added/removed を別出しは net delta より圧倒的に有用

dogfood で `handlers +222 / -83` が見えたとき、純増 +139 だけだと「機能整理（削除）」が見えない。今後の Tier 拡張でも **delta は + と - を分けて出す**を原則にする。

### 🔑 security の delta は依存由来ノイズが入る

dogfood で唯一誤読しそうなのが security の悪化。コードと無関係な依存ライブラリの CVE 発見でカウントが動く。v0.3 の優先1で分離する。

### 🔑 Tier 2 のサンプル不足は容赦なくデフォルト 3

実 dogfood で 4 ファイル読んだだけで test_effectiveness=5 を付けてしまっていた。新ルール（サンプル不足は default=3 + confidence:low）で修正済。新しい Tier 2 観点を増やすときも同じパターンを踏むこと。

---

## 既知の制約

| 項目 | 制約 | 対処 |
|------|------|------|
| 履歴 walk のコスト | 60K LOC プロジェクト 1コミット = install ~2min + tier1 ~5-7min | サンプリング戦略（daily/weekly）で削減、SHA キャッシュで重複回避 |
| bus factor のコスト | `git log --follow` を全ファイル分 = N git invocations | ファイル数 ~500 まで OK。それ以上は worker pool 化検討 |
| Tier 2 のゆらぎ | 1 ターン内の独立判定が成立しない | sub-agent 化（v0.3 priority 4）まで「snapshot only」運用 |
| 4 言語プロファイル | TS Web のみ実装、他は placeholder | v0.4+ で順次本実装 |
| 依存ツール不在時 | jscpd/madge/knip 等が入っていないと該当 metric は null | warnings に明記、`tooling_used` も保存 |

---

## dogfood の再現方法

### TS Web (whitebox-root/frontend、v0.2/v0.3 dogfood の元)

```bash
# 最新 1ヶ月の比較
REPO=~/Developer/Saikicorp/whitebox-root/frontend
SKILL=~/Developer/Private/skills/skills/code-quality-scorer
SHA_1MO=$(git -C $REPO log --before="1 month ago" -1 --format=%H)
SHA_2WK=$(git -C $REPO log --before="2 weeks ago" -1 --format=%H)
SHA_HEAD=$(git -C $REPO rev-parse HEAD)

# 履歴 walk (約 25-30 分、install 含む)
python3 $SKILL/scripts/score_history.py --repo $REPO \
  --commits "$SHA_1MO,$SHA_2WK,$SHA_HEAD" \
  --out-dir $REPO/.code-quality-scorer-cache

# trend レポート生成 (v0.3 から security 分類が出る)
python3 $SKILL/scripts/generate_trend.py \
  --in-dir $REPO/.code-quality-scorer-cache \
  --out /tmp/trend.md --repo whitebox-root/frontend

# bus factor delta
python3 $SKILL/scripts/run_bus_factor.py \
  --repo $REPO --from $SHA_1MO --to HEAD \
  --out /tmp/bus_factor.json
```

### Dart Flutter (flutter_intents、v0.3 で MVP dogfood)

```bash
SKILL=~/Developer/Private/skills/skills/code-quality-scorer
REPO=~/Developer/Private/flutter_intents/app  # monorepo の app/ をターゲット

cd $REPO && flutter pub get

# Tier 1 (3-5 分: flutter test --coverage が支配的)
python3 $SKILL/scripts/run_tier1_dart_flutter.py --repo . --out /tmp/flutter_tier1.json

# Tier 3 (数秒)
python3 $SKILL/scripts/run_tier3_flutter_ui.py --repo . --out /tmp/flutter_tier3.json

# 合成
SHA=$(git -C ~/Developer/Private/flutter_intents rev-parse HEAD)
DATE=$(git -C ~/Developer/Private/flutter_intents log -1 --format=%cI)
python3 $SKILL/scripts/aggregate.py \
  --tier1 /tmp/flutter_tier1.json --tier3 /tmp/flutter_tier3.json \
  --commit-sha $SHA --commit-date $DATE \
  --profile dart-flutter --skill-version 0.4 \
  --out /tmp/flutter_score.json

# Tier 2 (v0.4 で追加、claude CLI を spawn — コスト発生)
python3 $SKILL/scripts/judge.py \
  --repo . --profile dart-flutter --commit-sha $SHA \
  --samples 3 --max-files 20 --max-lines 4000 \
  --out /tmp/flutter_tier2.json
```

期待される結果 (v0.3/v0.4 時点、main HEAD): `partial_composite_score: ~65` (Tier 2 込みで ~66+)、coverage ~15%、lint ~2.6/KLOC、hallucinated 0 (3 path-deps + self を正しく除外)、cohesion=4 (Tier 2 sub-agent 2/2 agreement)、`routes_count: 1` (`MaterialApp(home:)` を v0.3 末で対応)。

### Swift iOS (IntentTodo、v0.3 で MVP dogfood)

```bash
SKILL=~/Developer/Private/skills/skills/code-quality-scorer
REPO=~/Developer/Private/IntentTodo

# Tier 1 (5-10 分: swift build * 7 SPM packages が支配的)
python3 $SKILL/scripts/run_tier1_swift_ios.py --repo $REPO --out /tmp/ios_tier1.json

# Tier 3 (数秒)
python3 $SKILL/scripts/run_tier3_swift_ui.py --repo $REPO --out /tmp/ios_tier3.json

# 合成
SHA=$(git -C $REPO rev-parse HEAD)
DATE=$(git -C $REPO log -1 --format=%cI)
python3 $SKILL/scripts/aggregate.py \
  --tier1 /tmp/ios_tier1.json --tier3 /tmp/ios_tier3.json \
  --commit-sha $SHA --commit-date $DATE \
  --profile swift-ios --skill-version 0.3 \
  --out /tmp/ios_score.json
```

期待される結果 (v0.3 時点、main HEAD): `partial_composite_score: ~51`、lint ~48/KLOC (.swiftlint.yml が strict)、duplication ~2%、hallucinated 0 (7 SPM packages + Apple frameworks を正しく除外)、type_errors 0。Periphery / osv-scanner が brew で入っていない場合 dead_code / security は null + warning。

---

## 進め方の推奨

新セッションで v0.5 に着手する時:

1. **このファイルを最初に読む** ← 引き継ぎ情報全部ここにある
2. **SKILL.md を読む** ← 使用者向けのフロー全体感
3. **実プロジェクトでの dogfood を最優先** ← v0.4 は構造を整えるフェーズだった。v0.5 は「実プロジェクトで使う中で出てくる痛点」を潰すフェーズ
4. **新フィーチャーは個別 PR / セッション** ← Semgrep 統合 / mutation testing / accessibility 等は単独で大きいので、ROADMAP の `v0.5+ 候補` セクションを参照
5. **完了したら advisor に最終チェックを依頼** ← v0.1〜v0.4 すべてで良い指摘が来た

advisor は会話の全文脈を見て指摘してくれるので、判断に迷ったら呼ぶ価値がある。Tier 2 の "fake N=3" 問題も、v0.3 の言語拡張優先順位も、Flutter `MaterialApp(home:)` の routes_count 漏れも advisor が捕まえた。

## v0.3 で得た追加教訓（v0.2 教訓に追加）

### 🔑 monorepo path 依存フィルタは言語ごとに作り方が違う

教訓 #2 (path alias) の実装は言語によって完全に別物:
- **TS Web**: `tsconfig.json#compilerOptions.paths` を読む
- **Dart Flutter**: `pubspec.yaml` の `dependencies.<name>.path` 指定を集める + 自身の `name:` フィールド
- **Swift iOS**: monorepo 内の全 `Package.swift` の `name:` を集める + `@testable import` 対応

実装を始める時に「このプロファイルでの monorepo 内参照とは何か」を1番目に決めること。後から付けると false positive が積もる。

### 🔑 言語ごとに「null + warning にする項目」が違う、それでいい

Flutter は `cyclomatic_complexity` `cognitive_complexity` `cyclic_dependencies_count` が標準ツールに無い → 全部 null。Swift iOS は `coverage` が xcodebuild 依存で fragile → デフォルト null。これらを「対応してない」と隠すのではなく、**warnings に書いて null のまま出す**。`partial_composite_score` がそれを吸収する。0 で埋めるより遥かに正直で、トレンドが歪まない。

### 🔑 Tier 2 sub-agent 化は単独セッション必須

v0.3 で見送ったのは正しい判断だった。他の3項目 (security split / cognitive / deprecated) はそれぞれ 1-3 時間、Tier 2 sub-agent 化だけ「1日」と明記されている。複数の小タスクと同じセッションで混ぜると、sub-agent の独立判定の検証 (一番重要なテスト) を端折ることになる。**v0.4 priority 1 として独立セッションで取り組む**。

### 🔑 dogfood が "score.json が出る" まで来れば一旦止めていい

v0.3 では Flutter / iOS の Tier 1 + Tier 3 + aggregate が score.json を吐くところまで確認した。各メトリクスの「実プロジェクトでの妥当性」を詰めるのは次フェーズ (v0.4 priority 2)。dogfood の最初の段階は **「動かない箇所が無い」** を確認するのが目的で、**「数値の精度」** はその次の段階。これを混ぜると初実装で詰む。
