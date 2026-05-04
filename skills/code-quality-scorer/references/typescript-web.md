# TypeScript Web プロファイル

TypeScript で書かれた Web フロントエンド/バックエンド/フルスタックプロジェクト用のツール選定と実行手順。

## 検出シグナル

`package.json` が存在し、以下のいずれかを満たす:

- `dependencies` または `devDependencies` に `react` / `next` / `vue` / `nuxt` / `svelte` / `@angular/core` のいずれか
- `dependencies` または `devDependencies` に `typescript`、かつ `vite` / `webpack` / `esbuild` / `rollup` / `tsup` のいずれか
- `engines.node` 指定があり TypeScript ファイル（`.ts` / `.tsx`）が存在

## ツール選定

優先順位は「広く使われていて出力が安定」が基準。

### test_coverage_lines / test_coverage_branches

`package.json` の `scripts` を見て、テストランナーを推測:

| スクリプト記載 | カバレッジコマンド |
|--------------|-------------------|
| `vitest` | `npx vitest run --coverage --coverage.reporter=json-summary` |
| `jest` | `npx jest --coverage --coverageReporters=json-summary` |
| `mocha` + `nyc` | `npx nyc --reporter=json-summary mocha` |
| `playwright` 単独（unit testなし） | カバレッジ取得不可 → `null` + warning |

カバレッジ JSON サマリーから `total.lines.pct` と `total.branches.pct` を取り、100で割って 0-1 のレンジに正規化。

ツール不在: `tier1_metrics.test_coverage_lines = null`、`warnings.append("no test runner with coverage detected")`

### lint_violations_per_kloc

優先順位:
1. `eslint` がプロジェクトに設定されている → `npx eslint . --format json` を実行
2. `biome` → `npx biome check --reporter=json .`
3. なし → `null`

ESLint の JSON 出力から `errorCount + warningCount` を集計。`cloc` または `find . -name '*.ts' -o -name '*.tsx' | xargs wc -l` で総行数を取得し、KLOC（1000行）で割る。

設定ファイル不在の場合は走らせない（デフォルトルールで判定するとプロジェクト方針と乖離するため）。

### dead_code_count

優先: `knip`。理由: 広く使われていて exports / types / files / dependencies 全部を見る。

```
npx knip --reporter=json
```

JSON 出力から `files`, `exports`, `types`, `enumMembers` の各配列の長さを合計。dependencies は別軸（後で security と一緒に扱うか検討、MVPでは含めない）。

`ts-prune` のみある場合のフォールバック:
```
npx ts-prune
```
出力行数を count（`(used in module)` 行は除外）。

両方ない: `null` + warning。

### avg_cyclomatic_complexity / p95_cyclomatic_complexity

優先: `complexity-report` の後継として、ESLint の `complexity` ルール出力を使う。

具体的には ESLint で以下を一時設定して走らせる:
```js
// .eslintrc.complexity.json (skill が一時生成)
{ "extends": "./.eslintrc", "rules": { "complexity": ["warn", 0] } }
```

`--rulesdir` または `--config .eslintrc.complexity.json` で起動して、各関数の複雑度を JSON で吸い上げる。

代替: `escomplex` / `typhonjs-escomplex` が dev dep にある場合はそれを使う。

`avg_cyclomatic_complexity` = 全関数の平均、`p95` = 95パーセンタイル（外れ値の存在を可視化するため平均だけでなく95も取る）。

### avg_cognitive_complexity / p95_cognitive_complexity (v0.3 追加)

cyclomatic は「分岐の数」を線形カウント、cognitive は「ネストの深さに指数加重」。同じ "複雑度 +500" でも、並列 switch 由来 (cognitive 低) か深いネスト if-else 由来 (cognitive 高) かを切り分けられる。

`eslint-plugin-sonarjs` の `cognitive-complexity` ルールから抽出:

```jsonc
// .eslintrc.js などに追加
{
  "plugins": ["sonarjs"],
  "rules": { "sonarjs/cognitive-complexity": ["warn", 0] }  // 0で全関数の値を出させる
}
```

`measure_cognitive_complexity` は既存の eslint pass の出力 (`measure_lint` の cache) を再利用するので **eslint を 2 度走らせない**。実プロジェクトの eslint は分単位の最大ボトルネックなので、これが重要。

ルール不在時: `null` + warning（`sonarjs/cognitive-complexity rule not enabled (or eslint-plugin-sonarjs not installed); cognitive complexity metrics are null`）。

### deprecated_api_count / outdated_dependencies_major (v0.3 追加: AI 効果測定の核心)

AI コード受け入れ失敗の 42.1% が「仕様無視・古い API 使用」由来（arXiv 2604.09515）。`hallucinated_imports` (実在しない import 数) と並ぶ AI 効果測定の核心指標。

#### deprecated_api_count

ソースコード内で `@deprecated` 付き API を呼んでいる箇所の数。eslint pass の cache を再利用して以下のルール ID を集計:

- `deprecation/deprecation` (`eslint-plugin-deprecation`)
- `@typescript-eslint/no-deprecated` (typescript-eslint v7+)
- 末尾が `no-deprecated` の他バリアント

ルール無効時は警告 (`deprecated_api_count is 0 — verify ...`)。

#### outdated_dependencies_major

直接依存のうち、`current` の major と `latest` の major が乖離しているパッケージ数。マイナー/パッチは正常な release cadence なので除外。

```
npm outdated --json
pnpm outdated --format json
yarn outdated --json   # NDJSON
```

major 差分のみカウントする理由: minor/patch を含めるとライブラリの release frequency に振り回されて、コード品質と相関しないノイズになる。major 遅延は API surface に手を入れる判断を先送りしている量を示す。

### type_errors

```
npx tsc --noEmit --pretty false
```

stderr/stdout の `error TS` を含む行数をカウント。0 が望ましい。

`tsconfig.json` がない場合は `null` + warning。

### code_duplication_pct

`jscpd` を使う。devDependency になくても `npx jscpd` で動くことが多い。

```
npx jscpd --silent --reporters json --output /tmp/jscpd-report .
```

レポート JSON の `statistics.total.percentage` を使う（0-100の浮動小数点）。jscpd 不在時は warning + null。

### cyclic_dependencies_count

`madge --circular` を使う。

```
npx madge --circular --extensions ts,tsx --json src
```

返ってくる JSON 配列の長さが循環依存の数。`src` がなければ `app` / `lib` / `components` / `pages` の優先順で対象を選ぶ。madge 不在時は warning + null。

### hallucinated_imports_count

**AI 活用効果測定の核心指標。** LLM が捏造したパッケージや存在しない API への参照を検出する。

ロジック:
1. `npx tsc --noEmit --pretty false` を実行し stdout/stderr を集める
2. 出力から `Cannot find module 'X'` 行を抽出
3. `X` が相対パス（`.` または `/` で始まる）または node 標準ライブラリの場合は除外
4. `package.json` の dependencies / devDependencies / peerDependencies / optionalDependencies に**存在しない**パッケージのみカウント
5. 同じパッケージは1とカウント（重複排除）

これにより:
- `import { foo } from "react-fake-package"` のような完全捏造 → カウントされる
- `import { newApi } from "react"` のような実在パッケージに架空 API → カウントされない（別の error TS で出る、 type_errors 側に乗る）

**重要な False Positive 対策**: TypeScript の path alias（`@/*`, `~/*`, `~components/*` など）は `tsconfig.json#compilerOptions.paths` を読んで自動で除外する。これがないと Next.js プロジェクトで頻発する `@/utils/foo` のような内部 import エラーが全部 "hallucination" としてカウントされてしまう。これは内部 import の壊れであって LLM の捏造ではない（type_errors 側に乗るべき）。

### security_vulnerabilities

```
npm audit --json
```

または `pnpm audit --json` / `yarn npm audit --json`。

JSON 出力の `metadata.vulnerabilities.{high,moderate,low}` を `{high, medium, low}` にマップ（moderate → medium）。critical は high に合算。

ツール不在（lockfile がない等）: `null` + warning。

#### v0.3: 「コード由来 vs 依存由来」分離のためのデータ保存

`tier1_metrics.security_vulnerabilities`（集計）に加えて、以下も保存する:

- **`tier1_metrics.security_advisories`**: `[{package, severity, range}]`。各 vulnerable package の per-advisory 情報。`data.vulnerabilities` の dict（npm 7+ / pnpm の標準形式）または list（一部 yarn の旧形式）の両方をハンドル
- **`dep_snapshot`** (tier1.json トップレベル): package.json の `dependencies` + `devDependencies` + `peerDependencies` + `optionalDependencies` のキー集合（version は持たない、追加削除を見るため）

これらは HEAD scoring では「将来比較に使うデータ」として保存されるだけだが、`generate_trend.py` で 2 ref 比較すると以下の3分類が出る:

- **Code-driven**: head にあって baseline の direct deps になかったパッケージの advisory → コード/依存追加由来
- **Newly-disclosed (ecosystem noise)**: head にあって baseline の deps にも既にあったパッケージの advisory → CVE 開示が起きただけ、コードと無関係
- **Resolved**: baseline にあって head から消えた advisory

これにより v0.2 dogfood で唯一誤読していた security の悪化が「コード変更由来 5件、エコシステム由来 6件」のように分解できる。

## 実行順序

依存ツールが入っていない場合、`npm ci` / `pnpm install --frozen-lockfile` / `yarn install --frozen-lockfile` を**最初に1回だけ**実行。

ロックファイル種別:
- `package-lock.json` → npm
- `pnpm-lock.yaml` → pnpm
- `yarn.lock` → yarn

履歴 walk でコミットを移動した時、ロックファイルが変わっていたら再 install が必要。

## サンプリング（Tier 2 用）

Tier 2 LLM 判定で「代表ファイル」を抽出する時の TypeScript Web プロファイル固有のルール:

含める:
- `src/**/*.{ts,tsx}` （メインソース）
- `app/**/*.{ts,tsx}` （Next.js App Router 等）
- `lib/**/*.{ts,tsx}` （ユーティリティ）

除外:
- `**/*.test.{ts,tsx}` / `**/*.spec.{ts,tsx}` （テストは別途 test_effectiveness で扱う）
- `**/node_modules/**`
- `**/dist/**` / `**/build/**` / `**/.next/**`
- `**/*.d.ts` （宣言ファイル）
- `**/__generated__/**` / `**/*.gen.ts`

抽出比率の目安: ファイル数の20%まで、または25ファイル/5000行に達したら停止。

## tooling_used に記録する内容

`score.json` の `tooling_used` には実際に使ったコマンドを書く。例:

```json
"tooling_used": {
  "coverage": "vitest run --coverage",
  "lint": "eslint .",
  "dead_code": "knip",
  "complexity": "eslint with complexity rule",
  "type_check": "tsc --noEmit",
  "security": "pnpm audit",
  "package_manager": "pnpm",
  "lockfile": "pnpm-lock.yaml"
}
```

これを残す理由: 後で「このコミットの coverage が低いのはツールが違うせいか?」を判別できるようにするため。トレンド分析の信頼性に直結する。

## ツール不在時の挙動まとめ

| ツール | 不在時の値 | warning 文言 |
|-------|-----------|-------------|
| coverage | `null` | `"no test runner with coverage detected"` |
| lint | `null` | `"no lint config detected; skipping lint"` |
| dead_code | `null` | `"knip not installed; dead_code_count is null"` |
| complexity | `null` | `"complexity tool not available"` |
| type_check | `null` | `"tsconfig.json not found"` |
| security | `null` | `"audit unavailable; lockfile may be missing"` |

**0埋めをしない**理由: 「カバレッジ0%」と「カバレッジ計測不可」は意味が違う。前者は深刻、後者は環境問題。トレンドで一緒にすると、ツール導入のタイミングで「コード品質が劇的に向上した」という誤った結論が出る。
