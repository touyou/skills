# Tier 1 メトリクス正規化ルール

各 Tier 1 メトリクスを 0-100 スケールに正規化する。`composite_score` 計算時のみ使う（生の値は `tier1_metrics` にそのまま保存する）。

正規化は線形ではなく、**「健全な閾値」に近いほど100に近づく**設計にする（プロジェクトが目指すべき水準で頭打ちにする）。

## test_coverage_lines / test_coverage_branches

| 生値 | 正規化値 |
|-----|---------|
| 0% | 0 |
| 50% | 60 |
| 70% | 80 |
| 80% | 90 |
| 90% | 100 |
| それ以上 | 100 |

線形補間。80% を実用的な閾値、90%以上で頭打ち。100%カバレッジを狙うコストはトレードオフ悪化する場面が多いため。

## lint_violations_per_kloc

低いほど良い。逆スケール:

| 生値 | 正規化値 |
|-----|---------|
| 0 | 100 |
| 1 | 90 |
| 5 | 70 |
| 10 | 50 |
| 30 | 20 |
| 50以上 | 0 |

線形補間。

## dead_code_count

リポジトリ規模で正規化したいので、まず KLOC で割って density に変換:

`dead_code_density = dead_code_count / KLOC`

| dead_code_density | 正規化値 |
|------------------|---------|
| 0 | 100 |
| 0.5 | 90 |
| 2 | 70 |
| 5 | 40 |
| 10 | 10 |
| 20以上 | 0 |

## avg_cyclomatic_complexity

| 生値 | 正規化値 |
|-----|---------|
| 1.0 | 100 |
| 3.0 | 90 |
| 5.0 | 75 |
| 8.0 | 50 |
| 12.0 | 20 |
| 20以上 | 0 |

p95_cyclomatic_complexity は別観点（外れ値の存在）として `composite_score` には含めない。warnings として「p95 が 25 を超えています」のような形で報告する。

### Swift プロファイル特有の注意 (v0.3 で追加)

Swift iOS の `avg_cyclomatic_complexity` は SwiftLint の `cyclomatic_complexity` ルールの**閾値超過関数のみ**を集計したもの (SwiftLint の rule severity を 0 にして全関数を出させる手段がない)。このため:

- **`.swiftlint.yml` の `cyclomatic_complexity.warning` 値を変えると、コードが変わってなくても avg/p95 が動く**。トレンド軸として使うのは推奨しない。
- Swift プロファイルの `composite_score` では `complexity` weight をデフォルトで使うが、上記の理由から「閾値超過関数の平均」を 0-100 に正規化していると解釈する必要がある。
- 真の全関数 cyclomatic を取るには `lizard` (言語横断) などの外部ツールが要る (v0.4+ で検討)。

`tooling_used.complexity_caveat` フィールドにこの旨が自動で入る。trend を読むときは必ず `complexity_caveat` の有無を確認すること。

## avg_cognitive_complexity (v0.3 追加)

cyclomatic と違ってネスト深度に指数加重するので、同じ値でも「読みづらさ」が大きい。SonarSource 推奨の警告閾値は関数あたり 15。

| 生値 | 正規化値 |
|-----|---------|
| 0 | 100 |
| 3 | 90 |
| 8 | 75 |
| 15 | 40 |
| 25 | 10 |
| 40以上 | 0 |

p95_cognitive_complexity は外れ値観測軸として composite には含めない。

**v0.3 時点の運用方針**: cognitive_complexity も `composite_score` には**含めない**（観測軸扱い）。理由は、既存スコアとの後方互換性を壊さず、トレンド画面に追加軸として並べる方が dogfood で「+552 cyclomatic」が「並列分岐由来か深ネスト由来か」を切り分けやすいから。将来 weights でデフォルトに入れる判断は、複数プロジェクトで dogfood してから。

## type_errors

ゼロ寛容。1個でもあれば一気に下がる:

| 生値 | 正規化値 |
|-----|---------|
| 0 | 100 |
| 1 | 70 |
| 5 | 40 |
| 20 | 10 |
| 50以上 | 0 |

## security_vulnerabilities

重み付け合計を計算: `score = high * 10 + medium * 3 + low * 1`

| score | 正規化値 |
|-------|---------|
| 0 | 100 |
| 3 | 80 |
| 10 | 50 |
| 30 | 20 |
| 100以上 | 0 |

high が1つでもあると最大 -10 で大きく下がる設計。

## composite_score 計算

各 dimension の正規化値に重みを掛けて加重平均。デフォルト重みは SKILL.md 本体の "5. 合成 + 出力" セクション参照。

**`null` の dimension がある場合**: `composite_score` は `null` にする（不完全合成は誤解を生む）。`partial_composite_score` を別フィールドで補助的に出してもよい（取れた dimension のみで再正規化）。

例:
```json
"composite_score": null,
"partial_composite_score": 68,
"composite_status": "partial: missing test_coverage, security"
```

## なぜこの形なのか

- **線形ではなく階段状**: 「カバレッジが10% → 20% に上がった」と「80% → 90% に上がった」は同じ +10pt でも価値が違う。前者はまだスタート地点、後者は仕上げ
- **頭打ちを設ける**: 100% を目指すコストが他を圧迫する場面（カバレッジ、複雑度0等）。健全な閾値で頭打ちにすることで、「過剰最適化が他を犠牲にしてないか」を可視化する
- **ゼロ寛容な軸を分ける**: type_errors と security high はゼロが正常。1個出ただけで大きく下がる設計にすることで、トレンド上で発生した瞬間が視覚的に飛び出る
