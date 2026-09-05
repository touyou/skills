# code-quality-scorer

コードベースのコード品質をコミット単位でスコアリングし、コミット履歴を辿ってトレンドを可視化するスキル。AI 活用の効果測定や品質回帰の検知に使える。

## いつ発動するか

```
このプロジェクトを採点して
品質トレンドを見たい
AIで書いたコードの質を測りたい
コミット履歴の品質変化を分析して
scorecardを作って
```

## 何を測るか

3 階層に分けて報告する (混ぜて読まないのが鉄則):

| Tier | 性質 | 主な指標 |
|------|------|----------|
| **Tier 1** | 決定論的ツール由来 (再現可能、トレンドの主軸) | test_coverage / lint_violations_per_kloc / dead_code / cyclomatic complexity / type_errors / security_vulnerabilities / code_duplication_pct / cyclic_dependencies / **hallucinated_imports** |
| **Tier 2** | LLM judge (N=3 独立 spawn、中央値) | cohesion / dry / bug_prone_patterns / test_effectiveness |
| **Tier 3** | UI に露出したロジックの量 (delta で読む観測軸) | routes_count / interactive_handlers / state_hooks / ui_complexity_sum |

解決できない import は依存不足や設定誤りでも発生するため、AI の捏造とは断定しない。Tier 2 は別プロセスで判定し、モデル・ルーブリック・サンプル条件と一致度を残す。独立した判定でも結果は揺らぐ。

## 対応言語プロファイル

| profile | Tier 1 | Tier 3 | ステータス |
|---------|:------:|:------:|------|
| `typescript-web` | ✅ | ✅ | v0.2 で本実装 (whitebox-root/frontend で dogfood) |
| `dart-flutter` | ✅ | ✅ | v0.3 で本実装 (habee-app 95k LOC で dogfood) |
| `swift-ios` | ✅ | ✅ | v0.3 で本実装 (IntentTodo で dogfood) |
| `kotlin-android` | 🟡 | 🟡 | reference doc は本実装、scripts は dogfood していない skeleton |

## 3 つの動作モード

| モード | スクリプト | 用途 |
|--------|-----------|------|
| **HEAD スコアリング** | `scripts/run_tier1_<profile>.py` + `scripts/run_tier3_<profile>.py` + `scripts/judge.py` + `scripts/aggregate.py` | 現在の HEAD を 1 回採点 |
| **履歴 walk** | `scripts/score_history.py` | コミット履歴を辿って複数 score.json を生成、`scripts/generate_trend.py` で trend report |
| **2 ref 比較** | `scripts/score_history.py --commits SHA1,SHA2` | 同条件の 2 snapshot から指標の差を報告 |

必要に応じて `scripts/run_bus_factor.py` で著者分布の変化も観測できる。知識の実測や AI の因果効果とは区別する。

## コスト感

Tier 2 の既定は 4 観点 × 3 判定 = 12 CLI 呼び出し。費用はモデルと実行時の料金・入力・キャッシュ条件に依存する。履歴スクリプトには Tier 2 の自動実行フラグはない。実行手順とキャッシュの制限は [references/execution.md](references/execution.md) を参照。

## 詳細

- スキル本体の仕様: [SKILL.md](./SKILL.md)
- 開発者向け引き継ぎ (v0.5+ ロードマップ): [ROADMAP.md](./ROADMAP.md)
- 言語別: `references/<profile>.md`
- ルーブリック: `references/rubric-<dimension>.md`
- 正規化ルール: `references/normalization.md`
