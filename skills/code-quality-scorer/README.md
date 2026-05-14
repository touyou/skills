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

特に **`hallucinated_imports_count`** は「AI が捏造した import が残っていないか」の核心指標。Tier 2 は `claude -p` を**独立 process として N 回 spawn** することで、1 ターン内アンカリングを避けて真の独立判定を実現している。

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
| **bus factor delta** | `scripts/run_bus_factor.py` | 2 ref 間の知識集中度の変化 (AI 活用で知識が分散するかサイロ化するか) |

## コスト感

Tier 1 / Tier 3 はツール実行のみで安い。Tier 2 は **4 dimension × N=3 samples = 12 claude calls** で **~$0.50-$1.00 / run** (cache 命中時)、最悪 ~$1.50-$3.00。`--judge-model haiku` で約 1/10 に。履歴 walk では Tier 2 はデフォルト無効、HEAD scoring ではデフォルト有効。

## 詳細

- スキル本体の仕様: [SKILL.md](./SKILL.md)
- 開発者向け引き継ぎ (v0.5+ ロードマップ): [ROADMAP.md](./ROADMAP.md)
- 言語別: `references/<profile>.md`
- ルーブリック: `references/rubric-<dimension>.md`
- 正規化ルール: `references/normalization.md`
