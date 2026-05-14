# ai-bot-pr-review

AI bot (Codex / Copilot / CodeRabbit / Devin / Dependabot / Renovate / 自作 Actions など) が自動生成した PR を一括レビューして、安全なものは approve→マージ、ロジックを壊しているものはクローズする。

## いつ発動するか

```
bot の PR をまとめてレビューして
自動生成 PR を一括処理して
codex の PR お願い
copilot PR マージして
dependabot まとめて
automated PR triage
```

または `/ai-bot-pr-review` で明示起動。

## 対象 PR の判定

**author × ブランチ prefix** の両方マッチで判定する (どちらか片方だけだとリリース PR 等を巻き込むため)。

デフォルト対象:

| author | ブランチ prefix の例 | 典型用途 |
|---|---|---|
| `app/github-actions` | `chore/codex-refactor-` | Codex テスト追加 |
| `copilot-swe-agent[bot]` | `copilot/` | Copilot 自動修正 |
| `coderabbitai[bot]` | `coderabbit/` | CodeRabbit auto-fix |
| `dependabot[bot]` | `dependabot/` | 依存更新 |
| `renovate[bot]` | `renovate/` | 依存更新 |

`release/` / `backport/` で始まるブランチは bot 由来でも対象外。

## カテゴリ別レビュー基準

| カテゴリ | 判別 | レビュー基準 |
|----------|------|--------------|
| **テスト追加** | テストファイルのみ変更 | テスタビリティ向上のリファクタは OK、本体ロジック変更は NG |
| **依存更新** | manifest + lockfile のみ | minor/patch + CI 成功は自動マージ、major bump はユーザー確認 |
| **自動修正** | lint / format / typo / 自明な bug fix | PR タイトルの宣言と diff が一致なら OK |
| **大規模リファクタ** | 多数の本体変更 | このスキルでは扱わない (人間レビュー必須) |

## プロジェクト固有設定 (`.claude/ai-bot-pr-review.local.md`)

```markdown
---
bot_authors:
  - app/github-actions
  - dependabot[bot]
branch_prefixes:
  - chore/codex-refactor-
  - dependabot/
exclude_branch_prefixes:
  - release/
  - backport/
test_command: "make test"
format_command: "make format"
merge_method: "auto"                # auto / merge / squash / rebase
ci_check_name: "Flutter Tests"      # 空なら全 check 集約
conventions_file: "AGENTS.md"
allow_dependency_only_merges: true
---
```

`test_command` 未設定なら package.json / Makefile / pubspec.yaml から自動推測。`merge_method: auto` なら `gh api repos/.../` の `allow_squash_merge` / `allow_merge_commit` / `allow_rebase_merge` を読んで squash → merge → rebase の優先順で fallback。

## レポートの形

```
| PR | author | カテゴリ | 判定 | アクション |
|---|---|---|---|---|
| #1234 | app/github-actions | テスト追加 | OK | マージ済み |
| #1235 | dependabot[bot] | 依存更新 (patch) | OK | マージ済み |
| #1236 | app/github-actions | テスト追加 | NG | クローズ (ロジック改変あり) |
| #1237 | dependabot[bot] | 依存更新 (major) | — | スキップ (要確認) |
```

## 詳細

スキル本体の仕様は [SKILL.md](./SKILL.md) を参照。habee-app (Flutter) で運用していた `codex-review` スキルを複数 bot 対応に汎用化したもの。
