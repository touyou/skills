#!/usr/bin/env python3
"""計測結果（JSON）を基準と候補で比べ、採用の判定の材料を出す。

使い方:
  compare.py --base b1.json b2.json b3.json --cand c1.json c2.json c3.json
  compare.py --cand c1.json c2.json c3.json   # 1 組だけ確かめる

各 JSON は score（数値）/ valid（true か false）/ failures（文字列の配列）を持つ。
ほかの数値（入れ子の scenarios.*.p50 なども）は中央値を並べる。

終了コード:
  0  点数がぶれより大きく上がった（採用の候補）
  2  点数はぶれの範囲。補助の指標で判断する（下の「補助の指標」を見る）
  1  差し戻し（どちらかの組が不合格、点数が悪化、または入力が不正）
"""
import argparse
import json
import statistics
import sys

MIN_RUNS = 3
# 小さいほど良い指標。名前の末尾で判定し、それ以外は大きいほど良いとみなす。
LOWER_IS_BETTER = ("_ms", "_per_req", "p50", "p95", "p99", "errors")
IGNORE = {"concurrency", "requests", "n"}


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif is_num(v):
            out[key] = float(v)
    return out


def lower_is_better(key):
    leaf = key.rsplit(".", 1)[-1]
    return leaf.endswith(LOWER_IS_BETTER)


def load(paths, name):
    runs, problems = [], []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            problems.append(f"{p}: 読めない ({e})")
            continue
        if not isinstance(r, dict):
            problems.append(f"{p}: JSON がオブジェクトでない")
            continue
        failures = r.get("failures") or []
        if not isinstance(failures, list):
            failures = [failures]
        failures = [f if isinstance(f, str) else json.dumps(f, ensure_ascii=False) for f in failures]
        if not is_num(r.get("score")):
            problems.append(f"{p}: score が数値でない ({r.get('score')!r})")
        elif r["score"] <= 0:
            problems.append(f"{p}: score が 0")
        if r.get("valid") is not True:
            problems.append(f"{p}: valid が true でない ({r.get('valid')!r})")
        problems += [f"{p}: {f}" for f in failures]
        runs.append(r)
    if len(paths) < MIN_RUNS:
        problems.append(f"{name}: 計測が {len(paths)} 回しかない（{MIN_RUNS} 回以上で比べる）")
    return runs, problems


def summarize(runs):
    flat = [flatten(r) for r in runs]
    keys = sorted({k for f in flat for k in f})
    med, spread = {}, {}
    for k in keys:
        xs = [f[k] for f in flat if k in f]
        m = statistics.median(xs)
        med[k] = m
        spread[k] = (max(xs) - min(xs)) / 2 / abs(m) * 100 if m else float("inf")
    return med, spread


def pct(b, c):
    return (c - b) / abs(b) * 100 if b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", nargs="*", default=[])
    ap.add_argument("--cand", nargs="+", required=True)
    a = ap.parse_args()

    cand_runs, cand_problems = load(a.cand, "cand")
    base_runs, base_problems = load(a.base, "base") if a.base else ([], [])
    for p in base_problems + cand_problems:
        print(f"不合格: {p}")
    if base_problems or cand_problems or not cand_runs:
        print("判定: 差し戻し（入力または整合性チェックに問題がある。基準が不合格なら測り直す）")
        return 1

    cmed, cspread = summarize(cand_runs)
    print(f"[cand] scores={[r['score'] for r in cand_runs]} median={cmed['score']} ぶれ=±{cspread['score']:.1f}%")
    if not base_runs:
        return 0
    bmed, bspread = summarize(base_runs)
    print(f"[base] scores={[r['score'] for r in base_runs]} median={bmed['score']} ぶれ=±{bspread['score']:.1f}%")

    print("--- 補助の指標（中央値。改善 = 良い向きにどちらの組のぶれよりも大きく動いた）")
    better, worse = [], []
    for k in sorted(set(bmed) & set(cmed)):
        if k == "score" or k.rsplit(".", 1)[-1] in IGNORE:
            continue
        d = pct(bmed[k], cmed[k])
        if d is None:
            print(f"  {k:>28}: {bmed[k]:>10.2f} -> {cmed[k]:>10.2f}  (基準が 0 で比べられない)")
            continue
        noise = max(bspread[k], cspread[k])
        gain = -d if lower_is_better(k) else d
        mark = ""
        if gain > noise:
            mark = "改善"
            better.append(k)
        elif gain < -noise:
            mark = "悪化"
            worse.append(k)
        print(f"  {k:>28}: {bmed[k]:>10.2f} -> {cmed[k]:>10.2f}  ({d:+.1f}%, ぶれ ±{noise:.1f}%) {mark}")

    d = pct(bmed["score"], cmed["score"])
    noise = max(bspread["score"], cspread["score"])
    if worse:
        print(f"悪化した指標: {', '.join(worse)}（採用するなら理由を台帳と PR に書く）")
    if d > noise:
        print(f"判定: 点数 +{d:.1f}%（ぶれ ±{noise:.1f}% より大きい）→ 採用の候補")
        return 0
    if d < -noise:
        print(f"判定: 点数 {d:.1f}%（悪化）→ 差し戻し")
        return 1
    if better and not worse:
        print(f"判定: 点数 {d:+.1f}% はぶれの範囲。改善した指標: {', '.join(better)} → 指標で採用できる")
    else:
        print(f"判定: 点数 {d:+.1f}% はぶれの範囲で、はっきり改善した指標が無い → 差し戻しか、回数を増やして測り直す")
    return 2


if __name__ == "__main__":
    sys.exit(main())
