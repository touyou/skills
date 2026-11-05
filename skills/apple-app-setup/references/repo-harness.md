# エージェント向けの規約（リポジトリのハーネス）

複数の端末・複数のエージェント（手元の Claude Code、別の環境の Claude、Codex、Xcode 内蔵のエージェント）が
同じリポジトリを触る前提で、最初から置いておくもの。

## AGENTS.md

`AGENTS.md` を実体にして、`CLAUDE.md` はその symlink にする（Codex は AGENTS.md、Claude Code は CLAUDE.md を読む）。
**常に読み込まれるので、目次と「知らずに触ると壊すが、壊れたことに気づけないルール」だけを置く**。説明は置かない。

ひな形（`assets/template/AGENTS.md`）に入っている節:

1. 環境（OS・Xcode・Swift のバージョン、ビルドの道具）
2. 構成（ディレクトリと層。拡張はひな形だけ）
3. 触る前に知っておくルール（番号付き。1 行で書き、詳しい説明は docs に置いて AGENTS.md から目次でたどる）
4. コミット前に回すもの（3 種類のビルド・`swift test`・静的チェック）
5. ドキュメントの置き場所（下の表）
6. 共通の運用ルール（ブランチ名・アップデート文・後片付け）

Xcode 内蔵のエージェントは `.xcodeproj` のあるディレクトリを作業ルートにする。`CLAUDE.md` は上の階層まで
遡って読まれるが、`.claude/settings.json`（フック）は遡らないので、フックを使うなら `.xcodeproj` の隣にも置く。

## ドキュメントの置き場所

| 書くもの | 置き場所 | 性質 |
|---|---|---|
| 常に必要な地図 | `AGENTS.md` / `README.md` | 目次とルールだけ |
| 現在のルール・結論 | `docs/*.md`、`docs/adr/` | 最新の事実と why だけ。履歴は混ぜない |
| 経緯・実験の記録 | `docs/devlog/` | 過去形・追記のみ。何を試し、何が違い、どのコミットで直したか |
| 残タスク | GitHub issue | 状態が変わるもの。docs に `- [ ]` を残さない |

判断が「やらない」で決着したら、理由つきで docs に残す（同じ検討を半年後に繰り返さないため）。

## devlog

PR を作ったとき・マージしたときに `docs/devlog/YYYY-MM.md` へ追記する。テンプレ:

```markdown
## YYYY-MM-DD 見出し（PR #N）

- やったこと:
- 詰まったこと・違っていた仮説:
- 学び（ほかのアプリにも効くもの）:
```

ほかのアプリにも効く学びは、このスキル（touyou/skills）か IntentTodo の skills に戻す。
`harness-intake` が起票を手伝う。

## コードコメント

why / 制約 / 落とし穴だけ。3 行以内が目安。書かないもの: リファクタの経緯、コードを読めば分かる説明、
将来の計画（やるなら issue）、issue・PR 番号。長い設計判断は `docs/adr/` に書き、コードには ADR への 1 行リンクだけ。
**コードから docs へのリンクは ADR だけ**（ほかへのリンクは腐っても誰も気づかない）。

コメントの言語は、公開して参考実装として見せるなら英語、個人の非公開アプリなら日本語でよい。最初に決めて AGENTS.md に書く。

## 共通の運用ルール（touyou の全リポジトリ共通）

- ブランチ名は役割の接頭辞＋短い英語（`feature/` `fix/` `chore/` `docs/` `refactor/` `style/` `release/x.y.z`）。`claude/...` は使わない
- アップデート文（What's New・リリースノート）は冒頭に使う人へのひとことを添えてから変更点。ja / en とも同じ温度
- 使い終わったブランチ（リモートも）・一時ファイル・ビルド成果物・書き出した画像は消す。`main` / `production` / 開いている PR のブランチは消さない
- 新しいリポジトリでは最初に「マージ時にブランチを自動削除」（`delete_branch_on_merge`）を有効にする

```bash
gh repo edit <owner>/<repo> --delete-branch-on-merge
```

## Xcode のプロジェクトファイル

- `project.xcproj` を外部から書き換えない。ターゲット・ビルド設定・言語・カタログのターゲット追加は Xcode で行う
- Xcode を開いたまま外部からプロジェクトファイルを変えると（`git checkout` での復元も含む）Xcode が落ちることがある
- 例外は版番号（`MARKETING_VERSION` / `CURRENT_PROJECT_VERSION`）。数行の置き換えなのでテキストで上げてよい
