---
name: code-quality-scorer
description: コードベースのコード品質をコミット単位でスコアリングし、コミット履歴を辿ってトレンドを可視化する。テストカバレッジ・lint違反・dead code・複雑度・cognitive complexity・deprecated API使用・セキュリティといった決定論的な指標と、凝集度・DRY・bug-prone構造といったLLM判定指標を分離して扱い、AI活用の効果測定や品質回帰の検知に使える。security delta は「コード由来 vs 依存由来」を分類して報告する。ユーザーが「コード品質を採点して」「品質トレンドを見たい」「AIで書いたコードの質を測りたい」「コミット履歴の品質変化を分析して」「このプロジェクトを評価して」「scorecardを作って」と依頼した時に発動する。v0.3 で TypeScript Web / Dart Flutter / Swift iOS の3言語が本実装、Kotlin Android はプレースホルダ。
license: MIT
metadata:
  author: touyou
  version: "0.4.1"
---

# コード品質スコアラー

このスキルの目的は **「同じコードに対して同じスコアが出る」採点系を作ること**。トレンド追跡が主用途なので、揺らぐ単発スコアより、再現できる軸を重ねたほうが意味を持つ。

## 鉄則：Tier 1 と Tier 2 を混ぜない

スコアは2つの層に分ける。混ぜると意味がなくなる。

### Tier 1 — 決定論的ツール由来の指標（トレンドの主軸）

外部ツールの数値を**そのまま**使う。同じコード→同じ数値。これがトレンド分析の本体。

- **test_coverage_lines** / **test_coverage_branches** — カバレッジレポートから
- **lint_violations_per_kloc** — linter のエラー/warn 数を1000行で正規化
- **dead_code_count** — dead code 検出ツールから
- **avg_cyclomatic_complexity** / **p95_cyclomatic_complexity** — 複雑度ツールから
- **type_errors** — 型チェックのエラー数（言語が型を持つ場合）
- **security_vulnerabilities** — `{high, medium, low}` の3階層、依存スキャンから
- **code_duplication_pct** — コピペ由来のクローン重複率（jscpd 等）
- **cyclic_dependencies_count** — 循環依存の数（madge 等）
- **hallucinated_imports_count** — 解決できない import 数（"Cannot find module" + 依存に存在しないパッケージ）。**AI 活用効果測定の核心指標**: LLM が捏造した import がここに直接出る

各言語で具体的に何のツールを使うかは `references/<language>.md` に書いてある。**ツールが入ってない場合は値を `null` にして warnings に記録する**。0埋めは絶対にしない（トレンドが嘘になる）。

### Tier 2 — LLM 判定指標（スナップショットの質的補強、トレンドには使わない）

ツールでは取れない観点はLLM判定で補う。ただし**Tier 2 は本質的にゆらぐ**ことを正直に認める:

- **離散1-5スケール**（連続0-100は使わない。同じコードで4.7 vs 4.9 のような擬似精度を作らない）
- **固定ルーブリック**（後述）。各レベルの定義を必ず参照させる
- **rationale を必ず保存**（なぜそのスコアか、後から監査可能にする）
- **コミットSHAでキャッシュ**（同じコードで再判定しないことで擬似的に安定化）
- **`confidence` フィールド**で判定の確度を区別: `high`（観察証拠が強くレベルを断定できる） / `medium`（複数のシグナルがあるが部分的） / `low`（サンプルが少ない or ルーブリック軸の半分以上を観察できなかった）。`files_sampled` も保存して、後で「N=2 ファイルだけで Score 5 と言っていた」が読み取れるようにする

#### Tier 2 のゆらぎについて正直なステートメント

「N=3 サンプリング + 中央値」を試案していたが、v0.1/v0.2 では **1つの Claude ターン内で 3 回判定すると最初の判定にアンカリングして独立にならない** ため、変動を実質減らせなかった。

**v0.4 で本対応**: `scripts/judge.py` が `claude -p` を N 回 (デフォルト 3) **独立 process として spawn** することで、真の独立判定を実現。各 sub-agent は別 context でルーブリックとサンプルを受け取り 1-5 + rationale を返す。中央値をスコア、確度は agreement で判定 (全一致=high / 部分一致=medium / 全不一致=low)。

**v0.4 の運用**:
- Tier 2 を**トレンド追跡にも使えるようになった**（独立判定なので再現性あり）
- ただし **コストが non-trivial** (4 dimensions × 3 samples = 12 claude 呼び出し、~$0.50-$1.00/run、初回キャッシュ作成、5分以内なら以降は cache_read で安い)
- 履歴 walk では **デフォルト無効** のまま（コスト理由）
- HEAD scoring で `judge.py` を呼ぶか、明示的に `--enable-tier2` を渡した時のみ実行

判定する観点:

- **cohesion** — モジュール内の凝集度
- **dry** — 重複・抽象化の妥当性（過度な早すぎる抽象化も減点）
- **bug_prone_patterns** — null扱い、async/await 漏れ、型の信頼性、状態管理の散らばり
- **test_effectiveness** — テストの存在ではなく**実効性**（assertion の質、振る舞いを検証しているか）

Tier 2 は**コストが高い**ので履歴walkではデフォルト無効。HEADスコアリングではデフォルト有効。

### Tier 3 — UI に露出するロジックの量（届いた価値のプロキシ）

「機能量」を「コミット数」「行数」「リリース回数」で測るとコミットの質に依存して指標が壊れる。代わりに**UI に露出しているロジックの量**を測ることで、コミット履歴の整い方によらず「ユーザーに届いた価値の量」のプロキシとして使う。

frontend プロジェクト（React/Vue/Svelte）向けの観点:

- **`routes_count`** — ルーティング上で公開されているページ数（Next.js App Router なら `page.tsx` 数、React Router なら `<Route>` 宣言数）
- **`interactive_handlers_count`** — `.tsx` 内のイベントハンドラ総数（`onClick=`, `onChange=`, `onSubmit=` 等）
- **`state_hooks_count`** — `useState` / `useReducer` の使用数（UI 状態の量）
- **`ui_complexity_sum`** — `.tsx` ファイルの関数の cyclomatic complexity 総和（UI 内部ロジックの量）

これは**評価軸ではなく観測軸**。多い/少ないが直接的に良い/悪いではない（多いほど機能豊富、少ないほど整理されている等、解釈はユーザーに任せる）。**delta** で見るのが本来の使い方。

#### 増えた量と減った量を別々に出す（重要）

純増（net delta）だけだと「機能整理（削除）」や「統合による隠蔽（UX改善）」が見えない。2 ref 間の比較では、各観点で**追加された量**と**削減された量**を別々に出す:

```json
"tier3_delta": {
  "from_ref": "abc123", "to_ref": "def456",
  "routes_added": 5, "routes_removed": 2,
  "handlers_added": 87, "handlers_removed": 23,
  "hooks_added": 12, "hooks_removed": 4,
  "complexity_added": 245, "complexity_removed": 87
}
```

これにより以下の解釈が可能になる:
- **+, − ともに大** → 機能の入れ替えが活発（書き換え系の作業）
- **+ 大、− 小** → 純粋な機能追加
- **+ 小、− 大** → 機能整理 / リファクタリング / 不要機能の削除（**価値判断として重要**）
- **+, − ともに小** → 内部整備中心（バグ修正など）

特に「削減」は**不要だった機能を見極めて消した判断**として価値があるし、「追加が小さく削減が大きい」のに Tier 1/2 が改善していたら「整理によりプロダクトの密度が上がった」と読める。純増だけ見ているとこれが見えない。

実装: `git diff --unified=0 <from>..<to>` で追加/削除行を取り、それぞれの行で handler/hook/branch token の正規表現マッチをカウントする。routes は `page.tsx` ファイルの追加/削除を `git diff --name-status` で取る。

Tier 3 はコミット時点で**常にデフォルト有効**（ツール実行不要、軽い）。delta は 2 ref を比較するモード（diff モード or 履歴 walk）で出る。

## 出力スキーマ（厳守）

各コミットのスコアは1つの `score.json` ファイル。フォーマットを変えない（後でツールが食えるように固定する）:

```json
{
  "schema_version": "1",
  "skill_version": "0.1",
  "commit_sha": "abc123",
  "commit_date": "2026-05-04T10:00:00Z",
  "language_profile": "typescript-web",
  "tier1_metrics": {
    "test_coverage_lines": 0.78,
    "test_coverage_branches": 0.65,
    "lint_violations_per_kloc": 2.3,
    "dead_code_count": 14,
    "avg_cyclomatic_complexity": 4.2,
    "p95_cyclomatic_complexity": 12,
    "type_errors": 0,
    "security_vulnerabilities": {"high": 0, "medium": 2, "low": 5},
    "code_duplication_pct": 3.8,
    "cyclic_dependencies_count": 0,
    "hallucinated_imports_count": 0
  },
  "tier2_observations": {
    "cohesion": {"score": 4, "confidence": "medium", "rationale": "...", "files_sampled": 5},
    "dry": {"score": 3, "confidence": "low", "rationale": "...", "files_sampled": 5},
    "bug_prone_patterns": {"score": 4, "confidence": "medium", "rationale": "...", "files_sampled": 5},
    "test_effectiveness": {"score": 5, "confidence": "low", "rationale": "...", "files_sampled": 1}
  },
  "tier3_ui_logic": {
    "routes_count": 18,
    "interactive_handlers_count": 432,
    "state_hooks_count": 87,
    "ui_complexity_sum": 312
  },
  "composite_score": 72,
  "warnings": ["coverage tool not configured; coverage values are null"],
  "tooling_used": {
    "coverage": "vitest --coverage",
    "lint": "eslint",
    "dead_code": "knip",
    "complexity": "complexity-report",
    "type_check": "tsc --noEmit",
    "security": "pnpm audit",
    "duplication": "jscpd",
    "cyclic_deps": "madge --circular"
  }
}
```

`composite_score` は**ダッシュボード向けの参考値**であって、**真の評価軸ではない**。トレンドを見る時は必ず各 dimension を個別に見る。1軸の改善が他軸の悪化を隠すケースがあるため。デフォルト重み（後述）を変えたい場合は `--weights` で渡す。

**現実的な運用**: 11個の dimension が全て埋まることは稀で、`composite_score` は `null` になりがち。`partial_composite_score`（取れた dimension のみで再正規化）が実質的な参考値として使われる。出力には `primary_score` フィールドが含まれ、これは "complete があれば composite、なければ partial" を自動選択する。サマリー表示時はこちらを主に使う。

## 3つの動作モード

### モード1: HEAD スコアリング (`score-head`)

現在のワーキングツリー（or 指定 ref）を1回採点する。Tier 1 + Tier 2 両方デフォルト有効。

```
出力: score.json + summary.md
```

ユーザーが「このプロジェクトを採点して」と言ったらこれ。

### モード2: 履歴 walk (`score-history`)

コミット履歴を辿って複数の score.json を生成し、トレンドを可視化する。Tier 1 のみデフォルト有効（コスト理由）。

サンプリング戦略（必ずどれかを選ぶ、勝手に全コミットしない）:

- **`--strategy daily`** — 各日の最新コミット1つ（デフォルト）
- **`--strategy weekly`** — 各週の最新コミット1つ
- **`--strategy merges-only`** — マージコミットのみ
- **`--strategy every-nth N`** — N コミットごと
- **`--strategy commits SHA1,SHA2,...`** — 明示指定

```
出力: scores/<sha>.json (複数) + trend.json + trend.md (per-dimension の時系列)
```

ユーザーが「AI使い始めてからコード品質変わった?」「品質トレンドを見たい」と言ったらこれ。

### モード3: diff 比較 (`score-diff`)

2つの ref を採点して差分を出す。`score-history` の軽量版。

```
出力: score-base.json + score-head.json + diff.md
```

## ワークフロー

### 1. 言語プロファイル検出

リポジトリのトップで以下を順に確認:

| シグナル | プロファイル |
|---------|------------|
| `package.json` に `react` / `next` / `vue` / `vite` / `tsc` などがある | `typescript-web` |
| `pubspec.yaml` あり、かつ `flutter` キーがある | `dart-flutter` |
| `Package.swift` または `*.xcodeproj` / `*.xcworkspace` | `swift-ios` |
| `build.gradle.kts` または `build.gradle` に `com.android.application` プラグイン | `kotlin-android` |

複数該当する場合（モノレポ等）はユーザーに確認する。該当なしならエラーで止める（無理に走らせない）。

### 2. プロファイル reference を読む

`references/<profile>.md` を読み、その言語固有の以下を取得:
- どのツールを使うか（必須/任意）
- どうインストールされているか確認するか
- どう実行するか
- 出力をどう Tier 1 メトリクスに変換するか
- ツール不在時の `warnings` 文言

これは言語ごとに別ファイル。SKILL.md 本体には書かない。

### 3. Tier 1 ツール実行

各ツールを実行して数値を集める。ツールが**ない**場合:
- `tier1_metrics.<key>` を `null` にする
- `warnings` に追加（例: `"knip not installed; dead_code_count is null"`）
- **絶対に推測値や0で埋めない**

ツールが**失敗**した場合（テストが落ちた、tsconfig が壊れている等）:
- 同様に `null` + warnings
- failure の stderr 末尾を warnings に含める（後でデバッグ可能に）

### 4. Tier 2 LLM 判定（有効時のみ、v0.4 で sub-agent 化）

`scripts/judge.py` が以下を実行:

1. リポジトリの**代表的なファイル**を SHA-seeded サンプリング (再現可能)
2. 各 dimension について `references/rubric-<dimension>.md` のルーブリックを読み込み
3. ルーブリック + サンプルを **N 個の独立 `claude -p` process** に spawn (デフォルト N=3)
4. 各 sub-agent は別 context で 1-5 + confidence + rationale を JSON で返す
5. 中央値をスコア、agreement で confidence (high/medium/low) を再判定、全 sample と rationale を保存

```bash
python scripts/judge.py --repo PATH --profile typescript-web \
  --commit-sha $(git -C PATH rev-parse HEAD) \
  --samples 3 --max-files 20 --max-lines 4000 \
  --out tier2.json
```

代表ファイル抽出ルール:
- ソースコード（テスト/設定/生成物以外）から、SHA + dimension 名で seed されたシャッフル後に file count / line count 上限で打ち切り
- 上限: 20ファイル または 4000行（claude context に収まる範囲、デフォルト）
- `test_effectiveness` だけはテストファイルを対象にする (TEST_FILE_RULES)
- 同じコミットSHA + dimension なら毎回同じファイルになる

**コスト**: 4 dim × 3 samples = 12 claude calls。**ベストケース**: 全 12 callを Anthropic prompt cache の 5 分 TTL 内に走らせ、各 dim 内 N=3 でプロンプト再利用 → ~$0.50-$1.00。**ワーストケース**: dimension 間で 5 分以上空く / 一晩寝かせて再実行 → 各 dim の 1 回目で毎回 cache 再作成 → ~$1.50-$3.00。`--judge-model haiku` を渡せば 1/10 程度に下がる (rubric 適用精度は若干落ちる)。

**confidence の 2 種類**: tier2.json には 2 種類の confidence が混在する。
- `raw_runs[*].confidence`: 各 sub-agent が自己評価した「サンプルから rubric を適用する確度」
- `tier2_observations.<dim>.confidence`: aggregator が計算した「N 個の独立 judges の agreement」

trend 表示で見るのは後者 (集約後 confidence)。「3つ全部 agree → high なら、独立 reader が同じ rubric から同じスコアに到達した = rubric 適用が安定」と読む。

### 5. 合成 + 出力

デフォルト重み（合計100）:
- test_coverage: 15
- test_effectiveness: 15
- lint_density: 10
- dead_code: 5
- complexity: 10
- type_safety: 10
- security: 15
- cohesion: 5
- dry: 5
- bug_prone_patterns: 10

各メトリクスを 0-100 に正規化してから加重平均（正規化ルールは `references/normalization.md`）。**Tier 1 が `null` の場合、その重みは他のメトリクスに比例配分**せず、`composite_score` も `null` にする（不完全な合成は誤解を招く）。

`summary.md` のテンプレ:

```markdown
# Code Quality Scorecard
**Project:** <name> | **Commit:** <sha-short> | **Date:** <date>

## Composite: <score>/100

## Tier 1 (deterministic)
| Metric | Value | Status |
|--------|-------|--------|
| Test coverage (lines) | 78% | ✓ |
| ...

## Tier 2 (LLM judgment, median of 3)
| Dimension | Score | Rationale (excerpt) |
|-----------|-------|---------------------|
| Cohesion | 4/5 | "..." |
| ...

## Warnings
- <list>
```

## 履歴 walk の実行戦略

履歴walkはコストがかかる。以下を守る:

### キャッシュ

`<repo>/.code-quality-scorer-cache/<sha>.json` に保存。再実行時に SHA + skill_version + tooling_used が一致したらスキップ。

### checkout の取り扱い

各コミットで:
1. ワーキングツリーが clean か確認（dirty なら最初に止めてユーザーに確認）
2. `git checkout <sha>`
3. `<install command>` を実行（package.json/pubspec.yaml 等が変わっていれば）
4. ツール実行
5. 元の HEAD に `git checkout` で戻す

**install が失敗するコミットがある**（依存が変わって解けない、Node のバージョン違い等）。その場合:
- `tier1_metrics` を可能な範囲で取る（lint だけ取れる、複雑度だけ取れる、等）
- `warnings` に install failure を記録
- スコアリングを完全には諦めない（部分情報でも時系列に意味がある）

### サンプリングのデフォルト判断

履歴 walk が無指定で呼ばれた場合:
- 直近30コミット以下 → 全コミット
- それ以上 → `daily` 戦略
- 1年以上の範囲 → `weekly` 戦略

### trend.md の出力

各 dimension の時系列を ASCII スパークラインで描く。例:

```
test_coverage_lines:
  0.45 ▁▂▃▅▆▆▇▇▇ 0.78  (delta: +0.33)
lint_violations_per_kloc:
  2.3  ▇▆▅▃▂▁▁▁▁ 0.4   (delta: -1.9)
```

絶対値より**delta と方向**を強調する（トレンド追跡の主目的）。

## このスキルの限界（書き残しておく）

LLMはコードの意図を超えて評価できない。以下は**測れないので測ろうとしない**:

- ビジネスロジックの正しさ（テストの仕事）
- アーキテクチャ判断の妥当性（人間レビューの仕事）
- パフォーマンスの実測値（ベンチマークの仕事）
- 「機能量」「進捗速度」（行数/コミット数で測ると品質と引き換えになるため、別軸として後回し）

このスキルが言うのは **「ツールで観測できる品質指標」+「LLMが安定的に判定できる範囲のコード健全性」** だけ。それ以上を主張しない。

## アクセシビリティ

UI プロジェクトのアクセシビリティ評価は実行されたDOMが必要で、静的解析だけでは限界がある。MVP では含まない。後で `references/accessibility.md` として追加予定。

## v0.4 の実装範囲

- ✅ TypeScript Web プロファイル（Tier 1 自動収集 + Tier 2 ルーブリック + Tier 3 UI logic）
- ✅ HEAD スコアリング
- ✅ 履歴 walk スクリプト (`scripts/score_history.py` — git worktree ベース、**v0.4 で 4 言語対応**)
- ✅ trend report 生成 (`scripts/generate_trend.py` — per-dimension スパークライン + delta テーブル + security 分類)
- ✅ knowledge_concentration / bus factor (`scripts/run_bus_factor.py`)
- ✅ security の「コード由来 vs 依存由来」分離 (v0.3 #1)
- ✅ cognitive_complexity (sonarjs) 追加 (v0.3 #2)
- ✅ deprecated_api_count / outdated_dependencies_major (v0.3 #3)
- ✅ **Tier 2 sub-agent 化 (`scripts/judge.py` — claude CLI を N=3 spawn して真の独立判定、v0.4)**
- ✅ Dart Flutter プロファイル (`run_tier1_dart_flutter.py`, `run_tier3_flutter_ui.py`)
- ✅ Swift iOS プロファイル (`run_tier1_swift_ios.py`, `run_tier3_swift_ui.py`)
- 🟡 Kotlin Android プロファイル (reference doc は本実装、scripts は **dogfood していないスケルトン**)
- ⏳ アクセシビリティ観点

**v0.5 以降の計画は `ROADMAP.md` に独立した文書としてまとめてある**。新しい version に着手する時はそちらを最初に読む。

ユーザーが対応外のプロファイルを依頼した場合、現バージョンの制約を伝えてから可能な範囲で対応する。

## オーケストレーション手順（Claude が実行する）

### HEAD スコアリングの実行手順

1. **言語プロファイル検出**: 上記の検出ルールで判定
2. **Tier 1 収集**:
   - TS Web の場合: `scripts/run_tier1_typescript_web.py --repo <path> --out tier1.json`
   - これが標準出力に warnings と tooling_used を含む JSON を吐く
3. **Tier 3 UI logic 収集** (frontend プロファイルで常時):
   - TS Web の場合: `scripts/run_tier3_ui_logic.py --repo <path> --out tier3.json`
   - routes / handlers / state hooks / ui complexity を計測
4. **Tier 2 判定**（有効時のみ、デフォルト有効）:
   - 各 dimension について `references/rubric-<name>.md` を読む
   - サンプリング: `references/<profile>.md` のサンプリングルールに従って代表ファイル群を集める
   - **1回判定する**: rubric を読み → サンプルを評価 → 1-5 と rationale を出力
   - rubric の「サンプル不足時の挙動」に従って `confidence` を決める（high / medium / low）
   - サンプル数 (`files_sampled`) も保存
   - **重要**: ルーブリックの「rationale の書き方」セクションに従い、観察した具体ファイル名/シグナルを書く。形容詞だけで終わらせない
   - 全 dimension をまとめた tier2.json を作る（フォーマットは出力スキーマ参照）
5. **合成**: `scripts/aggregate.py --tier1 tier1.json --tier2 tier2.json --tier3 tier3.json --commit-sha <sha> --commit-date <iso> --profile <profile> --out score.json`
6. **summary.md 生成**: SKILL.md "出力スキーマ" のテンプレに従って、score.json から human-readable サマリーを書く

### 履歴 walk の実行手順 (v0.2: スクリプト化済み)

```
# 範囲指定 + サンプリング戦略
python scripts/score_history.py --repo <path> --from <ref> --to <ref> \
  --strategy daily   # or merges-only / every-nth / all

# 明示的なコミット指定
python scripts/score_history.py --repo <path> \
  --commits SHA1,SHA2,SHA3
```

各コミットで自動的に:
1. git worktree で /tmp に独立した checkout を作る（本流ワーキングツリーは触らない）
2. lockfile から install コマンドを推測して実行 (pnpm/yarn/npm)
3. Tier 1 + Tier 3 snapshot を回す（Tier 2 は履歴 walk では実行しない）
4. score-<sha>.json を `<repo>/.code-quality-scorer-cache/` に保存（同じ skill_version でキャッシュ済みなら skip）
5. worktree を削除

install / tool 失敗は skip + warning でリカバリ。途中で止まらず全コミット試行する。

完了後 trend report を生成:
```
python scripts/generate_trend.py --in-dir <repo>/.code-quality-scorer-cache --out trend.md
```

各 dimension の **First / Last / Δ / 8階層スパークライン** を markdown テーブルに出す。

### bus factor delta の取り方 (v0.2)

```
python scripts/run_bus_factor.py --repo <path> --from <ref> --to <ref>
```

knowledge_concentration_index (0-1) を 2 ref で比較し、delta を計算:
- 正の delta = サイロ化が進んだ（少数の手に知識が集中した）
- 負の delta = 知識が分散した

AI 活用効果としての読み方: AI を 1 人で使い始めると delta は正（サイロ化）に振れる。チーム全体で AI を使うと delta はゼロ近辺で安定。AI で「他人が書いた領域も読み解いて触れた」場合は delta が負（分散）に振れる。

## References

言語別:
- `references/typescript-web.md` — TypeScript Web プロジェクト（v0.1 で実装済み）
- `references/dart-flutter.md` — Dart Flutter（v0.1 はプレースホルダ）
- `references/swift-ios.md` — Swift iOS（同上）
- `references/kotlin-android.md` — Kotlin Android（同上）

横断:
- `references/normalization.md` — Tier 1 メトリクスを 0-100 に正規化するルール
- `references/rubric-cohesion.md` — 凝集度1-5のルーブリック
- `references/rubric-dry.md` — DRY 1-5のルーブリック
- `references/rubric-bug-prone.md` — bug-prone 1-5のルーブリック
- `references/rubric-test-effectiveness.md` — テスト実効性1-5のルーブリック

スクリプト:
- `scripts/run_tier1_typescript_web.py` — TS Web の Tier 1 収集
- `scripts/run_tier1_dart_flutter.py` — Dart Flutter の Tier 1 収集
- `scripts/run_tier1_swift_ios.py` — Swift iOS の Tier 1 収集
- `scripts/run_tier1_kotlin_android.py` — Kotlin Android の Tier 1 収集 (skeleton)
- `scripts/run_tier3_ui_logic.py` — Tier 3 UI logic 観測 (TS Web)
- `scripts/run_tier3_flutter_ui.py` — Tier 3 UI logic 観測 (Flutter)
- `scripts/run_tier3_swift_ui.py` — Tier 3 UI logic 観測 (SwiftUI)
- `scripts/run_tier3_compose_ui.py` — Tier 3 UI logic 観測 (Jetpack Compose, skeleton)
- `scripts/judge.py` — Tier 2 LLM 判定 (claude CLI を N=3 spawn、v0.4 新規)
- `scripts/aggregate.py` — Tier 1 + Tier 2 + Tier 3 を合成し composite を計算
- `scripts/score_history.py` — 履歴 walk (v0.4 で 4 profile 対応)

### プロファイル別の Tier 1 / Tier 3 スクリプト対応表

| profile | Tier 1 collector | Tier 3 collector | dogfood ステータス |
|---------|-----------------|-----------------|-----------------|
| `typescript-web` | `run_tier1_typescript_web.py` | `run_tier3_ui_logic.py` | v0.2 (whitebox-root/frontend) |
| `dart-flutter` | `run_tier1_dart_flutter.py` | `run_tier3_flutter_ui.py` | v0.3 (flutter_intents) |
| `swift-ios` | `run_tier1_swift_ios.py` | `run_tier3_swift_ui.py` | v0.3 (IntentTodo) |
| `kotlin-android` | `run_tier1_kotlin_android.py` | `run_tier3_compose_ui.py` | 🟡 skeleton (未 dogfood) |

`aggregate.py` と `judge.py` は profile 不問で動く（tier1.json / tier3.json のスキーマだけ揃っていれば良い、judge は profile-aware sampling rule を内蔵）。
