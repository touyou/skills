# プロジェクト設定

リポジトリのルートに `.claude/pr-review-loop.local.md` を置くと挙動を調整できる。

```markdown
---
test_command: "make test"            # 修正後のテスト実行用、未設定なら自動推測
format_command: "make format"        # 修正後の format 用、未設定なら自動推測
conventions_file: "AGENTS.md"        # レビュー時に参照するプロジェクト規約
max_iterations: 5                    # 収束しない場合の打ち切り
default_mode: "auto"                 # auto / auto-fix / comment-only
# レビューアの設定例。利用可能な場合に使い、不在なら直接レビューする
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

`test_command` / `format_command` 未設定時の自動推測は プロジェクトの package.json / Makefile / pubspec.yaml と CI 定義から判断する。

