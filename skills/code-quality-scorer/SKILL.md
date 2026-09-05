---
name: code-quality-scorer
description: コード品質の採点、2 ref の比較、コミット履歴の品質トレンドを作る。「コード品質を採点」「品質スコアカード」「AI導入前後の品質変化」に使う。ツール指標・LLM判定・UIロジック量を分離する。TypeScript Web・Dart Flutter・Swift iOS に対応し、Kotlin Android は未実証の skeleton。通常のコードレビューとは区別する。
license: MIT
metadata:
  author: touyou
  version: "0.4.3"
---

# コード品質スコアラー

同じ条件で観測した指標をコミット間で比較する。Tier 1（ツール指標）、Tier 2（LLM 判定）、Tier 3（UI ロジック量）を分けて報告し、合成点だけで品質や AI の効果を断定しない。

## モードを選ぶ

| 依頼 | モード | 実行と出力 |
|---|---|---|
| 現在の品質を採点 | score-head | Tier 1 + 3、利用可能なら Tier 2。score.json と summary.md |
| 履歴の品質変化 | score-history | Tier 1 + 3、既定は daily。SHA ごとの JSON と trend.md |
| 2 ref の比較 | score-diff | 2 ref の Tier 1 + 3、要求された場合は Tier 2。2 件の JSON と diff.md |

これらは依頼を分類するモード名で、同名の CLI サブコマンドではない。履歴の対象期間が不明なら直近 30 日を使って明記し、1 年を超える場合は weekly を提案する。全コミットは明示指定時のみ。短い履歴だからと勝手に all に変えない。

## プロファイルと参照先

| シグナル | profile / 言語ガイド | Tier 1 / Tier 3 スクリプト |
|---|---|---|
| package.json に Web/TypeScript の依存 | [typescript-web](references/typescript-web.md) | run_tier1_typescript_web.py / run_tier3_ui_logic.py |
| pubspec.yaml に Flutter の依存 | [dart-flutter](references/dart-flutter.md) | run_tier1_dart_flutter.py / run_tier3_flutter_ui.py |
| Package.swift、xcodeproj、xcworkspace | [swift-ios](references/swift-ios.md) | run_tier1_swift_ios.py / run_tier3_swift_ui.py |
| Gradle に Android plugin | [kotlin-android](references/kotlin-android.md) | run_tier1_kotlin_android.py / run_tier3_compose_ui.py（skeleton） |

依頼のディレクトリに合うガイドだけを読む。モノレポは対象パッケージを明示して個別採点する。複数候補があり対象を決められない場合だけ確認する。対応外の言語を別 profile として採点しない。Kotlin は未実証・未実装の指標を明記する。

## 計測の原則

- Tier 1 はツール・設定・依存・実行環境も揃えて比較する。同じコードでも脆弱性データベースやツールの変更で値は変わる。欠測・実行失敗は `null` と warnings にし、0 や推測で埋めない。
- Tier 2 は cohesion / dry / bug_prone_patterns / test_effectiveness の 1〜5 判定。独立プロセスの一致度は判定の再現性の材料であり、正しさの証明ではない。同じモデル・ルーブリック・サンプル条件でも揺らぐ。
- Tier 3 は routes / handlers / state hooks / complexity の静的な近似計数。品質点には混ぜない。機能量・ユーザー価値・進捗の直接測定として扱わない。
- 解決不能な import だけで AI の捏造と断定しない。設定や依存不足も原因になる。bus factor も Git の著者分布の近似で、実際の知識量や AI 利用の因果を示すものではない。
- 対象 ref は SHA に解決する。未コミットの変更がある場合は committed HEAD を専用 worktree で採点する。作業ツリーを含める依頼なら別 snapshot として条件を記録し、HEAD のキャッシュに保存しない。

## 実行

スクリプトはこのスキルの `scripts/` 配下にある。インストール場所を `SKILL_DIR`、対象リポジトリを `REPO`、成果物ディレクトリを `OUT` に設定し、絶対パスで使う。

1. 採点対象・profile・期間・Tier 2 の有無を短く示す。
2. [references/execution.md](references/execution.md) の該当モードを実行する。履歴採点は既存の worktree ベースのスクリプトを使い、ユーザーの checkout を切り替えない。
3. Tier 2 を使う場合は `scripts/judge.py` を使う。既定は 4 観点 × 3 判定 = 12 CLI 呼び出し。モデルと呼び出し数を明示し、利用可能な予算・認証・権限内で行う。外部 CLI が使えなければ Tier 2 を未実施として残す。同一会話で 3 回考えた結果を独立判定と称しない。
4. [references/normalization.md](references/normalization.md) の定義に従って `aggregate.py` の出力を読む。出力の意味と報告形式は [references/output.md](references/output.md) を参照する。

ツールのインストール失敗は取れる指標と欠測理由を残す。認証・usage limit などで実行できなかった判定を成功扱いしない。終了時は、この実行が作った worktree の残留を `git worktree list` で確認し、残っていれば成果物を保全してからその worktree だけを片付ける。

実装の拡張を行う場合は [ROADMAP.md](ROADMAP.md) を先に読む。採点だけの依頼で未実装プロファイルやツール設定を追加しない。
