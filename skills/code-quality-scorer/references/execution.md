# 採点の実行手順

`SKILL_DIR` / `REPO` / `OUT` は絶対パス、`PROFILE` と collector 名は SKILL.md の表から設定する。各コマンドの追加オプションは `--help` を読む。以下は TypeScript Web の例。

## HEAD

コミット採点では対象 SHA を checkout した専用 worktree を `REPO` に使う。出力は worktree の外に保存する。

```bash
mkdir -p "$OUT"
SHA=$(git -C "$REPO" rev-parse HEAD)
COMMIT_DATE=$(git -C "$REPO" show -s --format=%cI HEAD)
python3 "$SKILL_DIR/scripts/run_tier1_typescript_web.py" --repo "$REPO" --out "$OUT/tier1.json"
python3 "$SKILL_DIR/scripts/run_tier3_ui_logic.py" --repo "$REPO" --out "$OUT/tier3.json"
```

Tier 2 を実施する場合だけ:

```bash
python3 "$SKILL_DIR/scripts/judge.py" --repo "$REPO" --profile "$PROFILE" \
  --commit-sha "$SHA" --samples 3 --max-files 20 --max-lines 4000 \
  --judge-model "$JUDGE_MODEL" --out "$OUT/tier2.json"
```

judge.py は SHA と dimension でファイル抽出を seed する。テスト実効性のみテストファイルを読む。モデル・rubric・サンプル数・実行時刻も成果物と一緒に記録する。固定のドル見積もりは使わず、現在の契約・モデル・実使用量に従う。

```bash
python3 "$SKILL_DIR/scripts/aggregate.py" \
  --tier1 "$OUT/tier1.json" --tier2 "$OUT/tier2.json" --tier3 "$OUT/tier3.json" \
  --commit-sha "$SHA" --commit-date "$COMMIT_DATE" --profile "$PROFILE" \
  --skill-version "$SKILL_VERSION" --out "$OUT/score.json"
```

`SKILL_VERSION` は SKILL.md の metadata.version。Tier 2 を実施しなかった場合は `--tier2` を省く。過去の tier2.json を偶然取り込まないよう実行ごとに出力ディレクトリを分ける。

## 履歴

```bash
python3 "$SKILL_DIR/scripts/score_history.py" --repo "$REPO" --profile "$PROFILE" \
  --from "$FROM_REF" --to "$TO_REF" --strategy daily --out-dir "$OUT"
python3 "$SKILL_DIR/scripts/generate_trend.py" --in-dir "$OUT" --out "$OUT/trend.md"
```

実装済みの strategy は `daily/weekly/merges-only/every-nth/all`。every-nth の間隔は `--every-nth N`、SHA の直接指定は `--commits SHA1,SHA2`。通常の ref 範囲は from を除いて to を含むため、始点も採点する場合は commits で明示する。

スクリプトは各 SHA の一時 worktree を作り、profile に合う依存導入・Tier 1・Tier 3・片付けを行う。履歴に Tier 2 を有効化するフラグは実装されていない。要求された場合のみ、選んだ SHA ごとに HEAD 手順の judge と aggregate を実行する。

**キャッシュの制限**: 現行 score_history.py は SHA のファイル名と内部 `SKILL_VERSION` だけでキャッシュを照合する。profile・ツール版・オプション変更は検出しない。条件を変えるときは新しい `--out-dir` を使い、異なる条件のファイルを同じ trend 入力に混ぜない。内部 version は文書の版番号とは独立している。

## 2 ref の比較

両 ref を SHA に解決し、`--commits` でその 2 件を採点する。同じ SHA なら一度だけ採点して差分 0 とする。Tier 2 が必要なら上の個別手順を追加する。各指標の base/head/差分と、両側の欠測・ツール条件を diff.md に書く。欠測との比較を 0 差分としない。

TypeScript Web の追加/削除別 UI 計数は `run_tier3_delta.py --repo ... --from ... --to ... --out ...`。この delta collector は他 profile 用ではないため、他言語では snapshot の差として報告し、追加/削除の別が未計測であることを明記する。

著者分布も求められたときは `run_bus_factor.py --repo ... --from ... --to ...`。knowledge_concentration_index の増加は著者集中、減少は分散を示す。
