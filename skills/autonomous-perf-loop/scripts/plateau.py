#!/usr/bin/env python3
"""計測の時系列（JSON Lines）を読み、点数が伸び止まっているかを決定論的に判定する。

使い方:
  plateau.py timeline.jsonl
  plateau.py timeline.jsonl --window 60 --min-runs 6 --noise 3

timeline.jsonl は計測 1 回ごとに 1 行を追記したもの。各行は少なくとも
  {"elapsed_min": 63.5, "score": 512000, "valid": true}
を持つ。"label"（何を測ったか: base / cand: <案> など）は任意で、出力にそのまま出す。

判定:
  合格した回（valid が true かつ score > 0）の中で、前の更新の点数を noise% より上回った回を「更新」とする。
  ぶれの範囲の伸びは更新に数えない（1 回だけ運よく高く出た回で基準を吊り上げない）。noise は手順書で決めた
  ぶれの下限（同じコードを続けて測ったときの幅）に合わせる。小さすぎると、ぶれを伸びと数えて停滞を見逃す。
  最後の更新から window 分以上たち、その後に min-runs 回以上測っていれば「停滞」。

終了コード:
  0  伸びている（または判定に足りる記録がまだ無い）
  3  停滞。停滞の監査（references/plateau-audit.md）に進む
  1  入力が不正
"""
import argparse
import json
import sys


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n}: JSON として読めない ({e})")
            t, s = r.get("elapsed_min"), r.get("score")
            if not isinstance(t, (int, float)) or isinstance(t, bool):
                raise ValueError(f"{path}:{n}: elapsed_min（数値）が無い")
            if not isinstance(s, (int, float)) or isinstance(s, bool):
                raise ValueError(f"{path}:{n}: score（数値）が無い")
            rows.append({"t": float(t), "score": float(s), "valid": r.get("valid") is True, "label": r.get("label", "")})
    rows.sort(key=lambda r: r["t"])
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timeline")
    ap.add_argument("--window", type=float, default=60, help="最後の更新からこの分数たったら停滞の候補（既定 60）")
    ap.add_argument("--min-runs", type=int, default=6, help="最後の更新の後にこの回数以上測っていること（既定 6）")
    ap.add_argument("--noise", type=float, default=3, help="更新とみなす最小の伸び（%%、既定 3）。手順書のぶれの下限に合わせる")
    a = ap.parse_args()

    try:
        rows = load(a.timeline)
    except (OSError, ValueError) as e:
        print(f"入力が不正: {e}", file=sys.stderr)
        return 1

    passed = [r for r in rows if r["valid"] and r["score"] > 0]
    failed = len(rows) - len(passed)
    if not passed:
        print(f"合格した回がまだ無い（記録 {len(rows)} 回、不合格 {failed} 回）。まず合格する基準を作る")
        return 0

    best, best_t, best_label, updates = None, None, "", []
    for r in passed:
        if best is None or r["score"] > best * (1 + a.noise / 100):
            best, best_t, best_label = r["score"], r["t"], r["label"]
            updates.append(r)

    now = rows[-1]["t"]
    since = [r for r in rows if r["t"] > best_t]
    # 直近は 1 回だけだとぶれるので、合格した最後の 3 回の中央値で見る
    recent = sorted(r["score"] for r in passed[-3:])[len(passed[-3:]) // 2]
    drop = (best - recent) / best * 100

    print(f"記録 {len(rows)} 回（不合格 {failed} 回）、経過 {now:.0f} 分")
    print(f"最後に更新した点数 {best:,.0f}。最後の更新 {best_t:.0f} 分（{best_label or 'label なし'}）、更新は計 {len(updates)} 回")
    print(f"最後の更新から {now - best_t:.0f} 分・{len(since)} 回")
    print(f"直近 3 回の合格の中央値 {recent:,.0f}（更新した点数から {drop:.1f}% 下）" if drop > 0 else f"直近 3 回の合格の中央値 {recent:,.0f}")
    if drop > a.noise * 2:
        print("注意: 直近が更新した点数からぶれの 2 倍より下がっている。採用した変更が悪化を持ち込んでいないか、起点を確かめる")

    if now - best_t >= a.window and len(since) >= a.min_runs:
        print(f"判定: 停滞（{a.window:.0f} 分・{a.min_runs} 回の基準を超えた）。references/plateau-audit.md の監査に進む")
        return 3
    print("判定: 伸びている（または停滞の基準に届いていない）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
