---
name: pr-review-loop
description: PR に対してレビュー → (自分の PR なら) 自動修正 → 再レビューを「指摘がなくなるまで」自動で繰り返す。author が自分なら auto-fix モード (修正して push まで)、author が他人や bot なら comment-only モード (インラインコメント付きの Pull Request Review を投稿、Actionable 指摘あれば REQUEST_CHANGES、無ければ APPROVE) を既定にする。`--auto-fix` / `--comment-only` で明示的に上書き可能。ユーザーが「レビューループして」「review loop」「指摘がなくなるまでレビューして」「このPRのレビュー回して」「PRを自動レビューして」と依頼した時、または `/pr-review-loop <PR番号>` を実行した時に発動する。
license: MIT
metadata:
  author: touyou
  version: "0.2.0"
---

# レビューループ

PR に対してレビュー → 修正 → 再レビューのサイクルを、プログラムで修正可能な指摘がなくなるまで自動で繰り返す。人間のレビュアーに出す前にコード品質を底上げし、レビューの往復回数を減らすことが目的。

## 鉄則

- **他人 / bot の PR には勝手に commit を乗せない**。既定の auto-fix は author が自分のときだけ。
- **収束しない指摘は 2 回試行で打ち切る** (Discussion 格上げ)。無限ループを構造的に防ぐ。
- **push 失敗時に `--force` は使わない**。rebase が競合したら `git rebase --abort` でクリーンに戻す。
- **resolved スレッドの再投稿はしない**。GraphQL の `isResolved` で除外、無理なら REST + ループ収束で吸収。
- **APPROVE は「マージ安全」の保証ではない**。CI 緑はベースコミット時点の main に対する保証でしかないので、終了前に `mergeStateStatus` を確認して結果に添える (後述)。

## モード

| モード | 用途 | 既定で選ばれる条件 |
|---|---|---|
| **auto-fix** | 指摘を自動修正して push まで進める | PR author が自分 (= `gh api user` の login) と一致 |
| **comment-only** | インラインコメント付きで Pull Request Review を投稿 (Actionable な指摘があれば `REQUEST_CHANGES`、無ければ `APPROVE`)。コードは一切編集しない | PR author が自分以外 (他人 / bot) |

明示フラグ:

| フラグ | 効果 |
|---|---|
| `--comment-only` | author に関係なく comment-only に固定 |
| `--auto-fix` | author に関係なく auto-fix に固定 (他人の PR に直接 commit を乗せるエスケープハッチ) |
| 両方指定 | エラー (ユーザー確認) |
| 指定なし | 上の DEFAULT_MODE |

## 設定 (project ごと)

リポジトリのルートに `.claude/pr-review-loop.local.md` を置くと挙動を調整できる。

```markdown
---
test_command: "make test"            # 修正後のテスト実行用、未設定なら自動推測
format_command: "make format"        # 修正後の format 用、未設定なら自動推測
conventions_file: "AGENTS.md"        # レビュー時に参照するプロジェクト規約
max_iterations: 5                    # 収束しない場合の打ち切り
default_mode: "auto"                 # auto / auto-fix / comment-only
# レビューに使うエージェント (touyou/pr-review-toolkit プラグインの skill 名前提)
review_agents:
  required:
    - pr-review-toolkit:code-reviewer
    - pr-review-toolkit:silent-failure-hunter
  recommended:
    - pr-review-toolkit:code-simplifier
    - pr-review-toolkit:pr-test-analyzer
    - pr-review-toolkit:type-design-analyzer
    - pr-review-toolkit:comment-analyzer
  optional:
    - codex:review
---

# プロジェクト固有のレビュー注意点
（任意のメモ）
```

`test_command` / `format_command` 未設定時の自動推測は `ai-bot-pr-review` と同じ (package.json / Makefile / pubspec.yaml から推測)。

## ワークフロー

### 1. 対象 PR の特定とモード判定

```bash
ARGS="$*"
# PR URL or 数値 から PR 番号を抽出
PR_NUMBER=$(echo "$ARGS" | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+' | head -1)
[ -z "$PR_NUMBER" ] && PR_NUMBER=$(echo "$ARGS" | grep -oE '[0-9]+' | head -1)
[ -z "$PR_NUMBER" ] && PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null)

# モード判定
OWNER=$(gh repo view --json owner --jq '.owner.login')
REPO=$(gh repo view --json name --jq '.name')
PR_AUTHOR=$(gh pr view "$PR_NUMBER" --json author --jq '.author.login')
GH_USER=$(gh api user --jq '.login')

if [ "$PR_AUTHOR" = "$GH_USER" ]; then
  DEFAULT_MODE=auto-fix
else
  DEFAULT_MODE=comment-only
fi

# --auto-fix / --comment-only で上書き
case "$ARGS" in
  *--auto-fix*--comment-only*|*--comment-only*--auto-fix*)
    echo "Error: --auto-fix と --comment-only は同時指定不可" >&2; exit 1 ;;
  *--comment-only*) MODE=comment-only ;;
  *--auto-fix*)     MODE=auto-fix ;;
  *)                MODE=$DEFAULT_MODE ;;
esac
```

**起動時アナウンス**: 既定で comment-only に振られた場合 (= 他人 / bot の PR) は、起動直後に「このPRは <author> さんの作業のため comment-only で進めます。auto-fix にしたければ `--auto-fix` を付けてください」と一言伝える。

### 2. PR コメントの収集

レビューエージェント実行と並行して、PR に投稿済みのコメントを集める (人間 / CodeRabbit 等のボットの既存指摘との重複を避けるため)。

```bash
# インラインコメント
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --jq '.[] | {author: .user.login, path: .path, line: .line, body: .body}'

# issue レベルコメント
gh api repos/{owner}/{repo}/issues/{number}/comments \
  --jq '.[] | {author: .user.login, body: .body}'
```

**resolved スレッドの除外**は REST API では取れないので、GraphQL を使う:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviewThreads(first: 100) {
          nodes {
            isResolved
            comments(first: 10) {
              nodes { id databaseId author { login } path line body }
            }
          }
        }
      }
    }
  }' -F owner=$OWNER -F repo=$REPO -F number=$PR_NUMBER \
  --jq '.data.repository.pullRequest.reviewThreads.nodes
        | map(select(.isResolved | not))
        | map(.comments.nodes) | add'
```

GraphQL が使えない環境では REST をそのまま使い、resolved の除外は未実施として記録 (ステップ 7 の収束判定で「同じ指摘」検出があるので無限ループにはならない)。

### 3. レビューエージェントの実行 (並列)

`.claude/pr-review-loop.local.md` の `review_agents` を読んで並列起動。トークン残量が少ない場合は `required` に絞る。

各エージェントには以下を渡す:

```text
PR #<NUMBER> の対象差分をレビューしてください。
- 初回: `gh pr diff <NUMBER>` で PR 全体差分を取得
- 2 回目以降: 前回レビュー以降の変更差分のみを対象に (全体再レビュー禁止)
- <conventions_file> のプロジェクト規約に照らして確認
- 各指摘に重要度を付ける (🔴 修正必須 / 🟡 推奨 / 🟢 軽微)
```

エラー時:
- 一部のエージェントのみ失敗 → 成功分で続行、最終レポートに失敗を明記
- 全部失敗 → ユーザーに通知して終了

### 4. 指摘の分類

全結果を集約し、各指摘を以下に正規化:

```json
[
  {
    "category": "actionable | discussion | minor | out-of-scope",
    "severity": "🔴 | 🟡 | 🟢",
    "path": "lib/example.dart",
    "line": 42,
    "side": "RIGHT",
    "body": "指摘本文の要約"
  }
]
```

**スコープ判定**: PR の変更ファイル (`gh pr diff <number> --name-only`) に含まれないファイルへの指摘、サブモジュール (`.gitmodules` 配下) への指摘は `out-of-scope` に振り分け、最終レポートに件数のみ記載。

**カテゴリ**:

- **actionable**: 正解が明確なもの (バグ、エラー握りつぶし、スタイル違反、デッドコード、テスト不足、コメント不正確)
- **discussion**: 設計判断・トレードオフ (アーキ選択、命名の好み、仕様の曖昧さ、パフォーマンスの両立)

迷ったら actionable 側に倒す (修正してテストが通ればそれが正解)。

### 5a. 自動修正 (auto-fix モード)

Actionable な指摘を修正する。関連する指摘はまとめて 1 コミットにしてよい。

各修正 (または修正グループ) ごとに:

1. コードを修正
2. `<format_command>` を実行
   - stderr に `command not found` / 環境エラー → 環境起因。スキル全体を停止してユーザー通知
   - それ以外 (`dart format` が構文エラーを報告等) → 修正自体の問題。修正取り消し → スキップリスト
3. `<test_command>` を実行
4. **テスト通過** → コミット

```bash
git add <修正ファイル>
git commit -m ":recycle: レビュー指摘対応: <修正内容の要約>"
```

5. **テスト失敗** → 失敗原因を分析
   - 実行自体が失敗 (コンパイルエラー、タイムアウト) → 修正と無関係の可能性。ユーザー通知
   - 修正が正しくテストが古い → テストも修正して再 `<test_command>`
   - 修正が間違い → 修正グループの全ファイルを `git restore` で取り消し。新規追加ファイルは**修正グループで生成したパスだけを配列に記録**して `rm -f "${NEW_FILES[@]}"` で狙い撃ち削除 (`git clean -fd` は使わない、`.env` 等を巻き込むため)。`git status --porcelain` でクリーン確認後、スキップリストに追加
   - 判断不能 → 取り消してスキップ (安全側に倒す)

全修正後 `git push`:
- リモートが新しい → `git pull --rebase` を 1 回試み、競合なければ再 push
- rebase が競合 → **必ず `git rebase --abort` でクリーンに戻して**ユーザー通知 (rebase-in-progress を残さない)
- 認証エラー等 → ユーザーに手動 push 依頼して終了 (`--force` は使わない)

### 5b. レビューコメントの投稿 (comment-only モード)

ステップ 4 の分類結果を、**インラインコメント付きの 1 件の Pull Request Review** として投稿する。`gh pr review` の CLI ではインラインコメントを送れないので、`gh api` で REST `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` を直接呼ぶ。

**event 判定**:

| 状態 | event | 意図 |
|---|---|---|
| 🔴 または 🟡 が 1 件以上 | `REQUEST_CHANGES` | 対応を促す。インラインコメントで該当箇所を指す |
| 🟢 のみ / discussion のみ / 0 件 | `APPROVE` | レビュー上問題なし。サマリだけ残す |

**例外**: PR author が自分 (自分自身に APPROVE は GitHub 側で弾かれる) → `event: COMMENT` にフォールバック。

```bash
# Actionable のみ抽出 (🔴 + 🟡)
ITEMS_JSON=$(echo "$CLASSIFIED_FINDINGS_JSON" | jq '
  map(select(.category == "actionable" and (.severity == "🔴" or .severity == "🟡")))
')
ACTIONABLE_COUNT=$(echo "$ITEMS_JSON" | jq 'length')

# インラインコメント (側は RIGHT 固定、LEFT 側削除行は近傍の追加行へ移すか summary に降ろす)
COMMENTS_JSON=$(jq -n --argjson items "$ITEMS_JSON" '
  $items | map({
    path: .path,
    line: (.line | tonumber),
    side: "RIGHT",
    body: ("\(.severity) \(.body)")
  })
')

# サマリ本文
SUMMARY_BODY=$(cat <<'EOF'
## レビュー結果（自動レビュー）

🤖 <review_agents> の各エージェントと PR の既存コメントを集約しました。Actionable 指摘はインラインコメントで該当行に付けています。

### サマリ
- 🔴 修正必須: N件
- 🟡 推奨: M件
- 🟢 軽微: K件（インラインのみ・サマリ重複なし）
- 議論が必要: L件（下記列挙）
- スコープ外: J件（件数のみ）

### 議論が必要（参考）
- ...

> 自動レビューのため誤検知の可能性あり。各指摘は実装意図と照らして判断してください。
EOF
)

# event 決定
[ "$ACTIONABLE_COUNT" -gt 0 ] && EVENT=REQUEST_CHANGES || EVENT=APPROVE

# REST API で投稿 (インライン + summary + event を 1 回でまとめて)
REVIEW_PAYLOAD=$(jq -n \
  --arg event "$EVENT" \
  --arg body "$SUMMARY_BODY" \
  --argjson comments "$COMMENTS_JSON" \
  '{event: $event, body: $body, comments: $comments}')

REVIEW=$(gh api -X POST "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" \
  --input - <<<"$REVIEW_PAYLOAD")
REVIEW_URL=$(echo "$REVIEW" | jq -r '.html_url')
```

`comments[].line` は **PR diff 上で参照可能な行**に限る (削除行を指すと 422)。`side=LEFT` の指摘は近傍の追加行 (RIGHT 側) へ移すか、インラインから除外して summary に記載。

**投稿失敗時のフォールバック**:

```bash
BODY_FILE=$(mktemp /tmp/gh-body-XXXXXX)
printf '%s' "$SUMMARY_BODY" > "$BODY_FILE"
gh pr review "$PR_NUMBER" --comment --body-file "$BODY_FILE"
rm -f "$BODY_FILE"
```

注意: `gh pr comment` は使わない (issue-level コメントになりレビュー履歴に残らない)。

### 6. 再レビュー (auto-fix モード)

修正後のコードに対して再レビュー (ステップ 3 と同じ)。ただし 2 回目以降は**差分のみ**を対象に。

```bash
# イテレーション開始時 (初回はステップ 1 直後、以降はステップ 5a の push 完了後)
PREV_HEAD=$(git rev-parse HEAD)

# push 完了後、再レビュー前に変更ファイル一覧を算出
CHANGED_FILES=$(git diff "$PREV_HEAD..HEAD" --name-only)
```

エージェントに `CHANGED_FILES` を渡し、「このファイル群のみをレビュー対象」と明示する。

### 7. 収束判定 (auto-fix モード)

以下のいずれかで終了:

- **Actionable な指摘が 0 件** → 成功
- **前回と同じ指摘が繰り返されている** → 自動修正の限界。Discussion に格上げ
- **修正可能な指摘が全てスキップされた** → これ以上自動では直せない
- **`max_iterations` 到達** → 打ち切り

**同じ指摘の判定**: (ファイルパス, 行範囲, 指摘要旨) のタプルで同一性を見る。「指摘 ID → 試行回数」のマップをインメモリで保持し、修正成功でエントリ削除、同一指摘の再出現でカウント増加。**カウント ≥ 2 で Discussion に格上げ**。

### 7.5. マージ可能性の確認 (mergeStateStatus)

ループ終了後 (auto-fix なら最終 push 後、comment-only ならレビュー投稿の前 — event が APPROVE か REQUEST_CHANGES かを問わず実施する) に、PR がベース遅れやコンフリクトを抱えていないかを確認する。CI 緑は「ベースコミット時点の main」に対する保証でしかなく、レビュー中に main が進むとセマンティックコンフリクト (マーカーなしで組み合わせると壊れる) の芽が残るため。

```bash
gh pr view "$PR_NUMBER" --json mergeStateStatus --jq '.mergeStateStatus'
```

| mergeStateStatus | 対応 |
|---|---|
| `CLEAN` | そのまま終了。レポートに「マージ可」と記載 |
| `BEHIND` | auto-fix (= 自分の PR) なら `gh pr update-branch` して CI 再完走を待つ。comment-only なら手を出さず、レポートに「base 遅れ。update-branch 後の CI 確認を推奨」と明記 |
| `DIRTY` | コンフリクト解消が必要。レポートに明記してユーザーに戻す |
| `BLOCKED` / `UNSTABLE` | CI・レビュー要件待ち。状態をレポートに記載 |
| `UNKNOWN` | 数秒待って再取得。それでも不明なら「状態未確定」と記載 |

comment-only モードの APPROVE はレビュー上の判断であって、この確認を省略する理由にはならない (APPROVE + `BEHIND` はあり得る組み合わせ。その旨をサマリに書く)。

### 8. 最終レポート

#### auto-fix モード

```markdown
## レビューループ結果 — PR #<NUMBER>

### 実行サマリー
- モード: auto-fix
- イテレーション回数: N回
- 修正コミット数: M件
- 使用レビューエージェント: <列挙>
- 失敗したエージェント: （あれば記載）
- マージ可能性 (mergeStateStatus): CLEAN / BEHIND（update-branch 済み・CI 待ち）等

### 修正済み（N件）
| イテレーション | コミット | 内容 |
|---|---|---|
| 1 | abc1234 | 未使用 import の削除 |
| 1 | def5678 | エラーハンドリング追加 |
| 2 | ghi9012 | テスト追加 |

### 要相談（M件）
- 🟡 ... — アーキ判断が必要
- 🟡 ... — 仕様確認が必要

### スキップ（K件）
- ... — テスト修正を試みたが別の箇所で失敗

### テスト結果
✅ 全テスト通過 / ❌ N件失敗（詳細: ...）
```

#### comment-only モード

```markdown
## レビューループ結果 — PR #<NUMBER>（comment-only）

### 実行サマリー
- モード: comment-only（コードの編集・コミット・push は行っていません）
- 投稿 event: APPROVE / REQUEST_CHANGES / COMMENT（フォールバック時のみ）
- 使用レビューエージェント: <列挙>
- 投稿先: <REVIEW_URL>
- マージ可能性 (mergeStateStatus): CLEAN / BEHIND（base 遅れ・update-branch 推奨）等

### 投稿した指摘
- 🔴 修正必須: N件（インラインコメント）
- 🟡 推奨: M件（インラインコメント）
- 🟢 軽微: K件（サマリ本文のみ）
- 議論が必要: L件（サマリ本文のみ）
- スコープ外: J件（件数のみ）

### 判定の根拠
- Actionable（🔴/🟡）が <count> 件 → REQUEST_CHANGES（対応を促す）
- もしくは 0 件 → APPROVE（マージ可と判断）

詳細は PR の Reviews タブを参照してください。
```

## 由来とブラッシュアップ方針

このスキルは habee-app (Flutter) で運用していた `review-loop` スキルを汎用化したもの。`make format` / `make test` / `AGENTS.md` / 特定のレビューエージェント名を `.claude/pr-review-loop.local.md` に外出ししてある。

他プロジェクトで類似のレビューループを動かしていたら、収束判定 (ステップ 7)・カテゴリ判別 (ステップ 4)・event 決定 (ステップ 5b) の差分を集めて、このスキルをブラッシュアップする想定。

## 依存

- `pr-review-toolkit` プラグイン (もしくは互換のレビューエージェント群) を Claude Code にインストール
- `gh` CLI と GitHub 認証 (`gh auth login`)
- (任意) `codex:review` などプロジェクトで動いているレビューツール
