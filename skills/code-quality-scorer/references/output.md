# 出力と読み方

完全な JSON は `scripts/aggregate.py` が生成する。スキーマを手で組み立て直さず、`schema_version: "1"` と生成されたフィールドを維持する。履歴スクリプトが保存する snapshot は集計前の観測値であり、合成点が必要なら aggregate.py に渡す。

| フィールド | 意味 |
|---|---|
| commit_sha / commit_date / language_profile / skill_version | 対象と生成条件 |
| tier1_metrics / tooling_used / warnings | ツール値・実行手段・欠測理由 |
| tier2_observations | 1〜5 の判定、confidence、rationale、files_sampled |
| tier3_ui_logic / tier3_meta | 静的 UI 計数と条件 |
| composite_score | 必要な全 dimension がある場合だけの合成点。それ以外は null |
| partial_composite_score | 観測できた dimension の重みを再正規化した参考値 |
| primary_score / primary_score_kind | complete があれば complete、それ以外は partial を選択 |
| weights_used / normalized_contributions / composite_status | 重み・正規化値・欠測 dimension |

重みと正規化の説明は [normalization.md](normalization.md)、実行時の値は `weights_used` を正とする。部分点は欠測の組み合わせが変わるだけでも動くため、必ず欠測軸を併記する。

Tier 2 の raw_runs の confidence は各判定の自己評価、集約後の confidence は judges の一致度。両者を混同しない。ルーブリックは [cohesion](rubric-cohesion.md)、[dry](rubric-dry.md)、[bug-prone](rubric-bug-prone.md)、[test-effectiveness](rubric-test-effectiveness.md) に分かれており、judge.py が必要なものを読み込む。

## summary.md / diff.md / trend.md

対象 SHA・profile・実行条件を示し、Tier ごとに指標・値・欠測理由を表にする。合成点を示すなら complete/partial と欠測軸を隣に置く。比較では各 dimension の増減を主にし、security はコードと依存の変化を分けて根拠を示す。トレンドの同時変化だけで原因を断定しない。

テスト・型チェックの実行結果と、計測自体の失敗を分ける。警告があるときは「全指標を計測済み」と表現しない。最後に成果物へのリンクを返す。
