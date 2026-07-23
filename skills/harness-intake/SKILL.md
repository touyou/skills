---
name: harness-intake
description: >
  touyou が実プロジェクト（jt 配下の habee-app / habee-app-codex / momentia-app-harness 等、
  sparkle 配下の sparkle-design / sparkle-design-internal 等）で日々磨いている AI エージェント
  ハーネス（CLAUDE.md / AGENTS.md、.claude/skills・agents・hooks、自動化スクリプト等）から、
  他プロジェクトにも汎用化できる気づき・パターンを見つけて touyou/skills リポジトリへの
  GitHub Issue として起票する。作業フォルダが touyou/skills 自体とは分かれているため、直接
  ファイルを編集せず Issue 経由で提案する運用を仲介するスキル。
  touyou/skills リポジトリ以外の任意のディレクトリ（jt・sparkle 配下に限らない）から呼び出す
  ことを想定している。ユーザーが「このハーネス改善を skills に提案して」「touyou/skills に
  起票して」「この気づきをスキル側に取り込みたい」「ハーネスの改善を Issue 化して」
  「/harness-intake」と依頼した時に発動する。
license: MIT
metadata:
  author: touyou
  version: "0.1.0"
---

# harness-intake

実プロジェクトでハーネス（CLAUDE.md / AGENTS.md、`.claude/skills`・`agents`・`hooks`、自動化
スクリプト等）を磨いていて「これは他のプロジェクトでも使える」と気づいたときに、その場で
`touyou/skills` へ直接コミットするのではなく、**GitHub Issue として起票するところまで**を担当
するスキル。取り込み（SKILL.md の実装・PR 作成）は `touyou/skills` リポジトリ側で別途行う。

このスキルは `touyou/skills` の外、つまり実際にハーネスを磨いている作業ディレクトリ（例:
jt 配下の habee-app / habee-app-codex / momentia-app-harness、sparkle 配下の sparkle-design /
sparkle-design-internal など）から呼び出される想定。ローカル開発用の symlink
(`~/.agents/skills/harness-intake` 経由で `~/.claude/skills/harness-intake` からも解決される)
で、`touyou/skills` をクローンしていない任意のディレクトリからでも使えるようにしてある。

## 前提: なぜ直接編集ではなく Issue 起票なのか

- 作業ディレクトリと `touyou/skills` のリポジトリは別物。作業中にそのまま `touyou/skills` を
  横から編集するとレビューが挟まらず、ハーネス側の作業文脈（プロジェクト固有の事情）が
  そのまま skills 側に混入するリスクがある。
- 過去の実例（[touyou/skills#5](https://github.com/touyou/skills/issues/5)）でも
  「実プロジェクトでレビュー・実装 → 気づきを Issue 起票 → 独立した PR で取り込み・レビュー」
  という流れを踏んでおり、このスキルはその流れの前半（起票まで）を型化したもの。

## ワークフロー

### Step 1: 何が変わったか特定する

- ユーザーが指す変更点（「このリトライ処理のパターン」「この hook」等）を最優先で使う。
- 指定がなければ、ハーネス関連ファイルの直近の差分を拾う:
  ```sh
  git log --oneline -20 -- CLAUDE.md AGENTS.md .claude .agents scripts
  git diff HEAD~5 -- CLAUDE.md AGENTS.md .claude .agents scripts
  ```
- 対象になりやすいハーネス資産: `CLAUDE.md` / `AGENTS.md`、`.claude/skills`・`.claude/agents`・
  `.claude/hooks`、`.agents/skills`、レビュー/実装補助スクリプト、サブエージェント定義など。

### Step 2: 汎用性を判定する

- プロジェクト固有のビジネスロジックや非公開情報を含まず、**他プロジェクトでも再利用可能な
  パターン**かを見極める。単なる「このプロジェクトのAPI名」レベルの修正は対象外。
- 非公開リポジトリ・社内固有の名称やURLは Issue 本文に直接転記しない。パターンの本質と
  コード抜粋のみを引用する（過去実例と同じ扱い: 情報源が非公開の場合は直接リンクを張らず、
  抜粋のみで説明する）。
- 迷ったら「このパターンを知らない別プロジェクトのエージェントに説明して伝わるか」を基準に
  判定する。

### Step 3: touyou/skills 側の既存資産と照合する

- 対象のプラグイン/スキルが既にあるかを確認する:
  ```sh
  gh api repos/touyou/skills/readme -H "Accept: application/vnd.github.raw"
  ```
  （ローカルに `touyou/skills` のクローンがあり直接読めるならそちらでもよい）
- 判定結果は次のどれかになる:
  - **既存スキルの拡張**: 該当スキル名を明記する（例: `apple-accessibility` の
    `references/implementation-patterns.md` に追加パターンとして積む、`pr-review-loop` の
    鉄則に1項目足す、等）
  - **新規スキル候補**: 既存のどのプラグインにも属さない場合。新規スキル名の案と、どの
    プラグインに乗せるべきか（既存 pack か新規 pack か）の見立てを添える

### Step 4: Issue ドラフトを作る

過去実例（Issue #5）の構成を踏襲する:

```markdown
## 気づき

<何を発見したか。どのプロジェクト・どんな作業文脈で得た気づきかを一般化した言葉で>

## なぜ汎用的と考えるか

<他プロジェクトでも再利用できると考える理由>

## 対象

- 既存スキル拡張の場合: `skills/<name>/...` のどこに何を足すか
- 新規スキル候補の場合: 新規スキル名の案 / 想定プラグイン

## 具体的なパターン

<コード抜粋・箇条書き。非公開情報は含めない>

## 確認の上取り込みお願いします
```

### Step 5: ユーザーに提示し、確認を得てから起票する

- ドラフトをそのまま表示し、**タイトル・本文をユーザーに確認してもらってから** Issue を作る。
  GitHub 上に見える公開アクションなので、勝手に起票しない。
- 承認が得られたら:
  ```sh
  gh issue create --repo touyou/skills \
    --title "<スキル名>: <一行サマリ>" \
    --body-file <一時ファイル>
  ```
- 起票後は Issue URL をユーザーに提示して完了。SKILL.md の更新やバージョンアップなど実際の
  取り込み作業は `touyou/skills` 側で別途行う（このスキルの責務はここまで）。

## 注意事項

- このスキルは `touyou/skills` リポジトリへの `gh issue create` 以外、いかなるファイルも
  書き換えない。ハーネス側（呼び出し元のプロジェクト）のファイルも変更しない。
- Issue 起票前の確認をスキップしない。
- 対象は jt / sparkle 配下に限らない。ハーネスを磨いている任意のディレクトリから汎用的に
  使えるスキルとして設計している。
