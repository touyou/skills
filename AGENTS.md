# Repository Guidelines

このリポジトリの開発・運用ルール。Claude Code (`CLAUDE.md` → このファイルへの symlink) と OpenAI Codex (`AGENTS.md` 直接) の両方が読む。

## 何のリポジトリか

touyou 個人の **Agent Skills 集** を Claude Code と Codex の両方の marketplace で配布するリポジトリ。スキル本体は `skills/<name>/SKILL.md` 中心の共通フォーマット ([Agent Skills 仕様](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview))。同じ `skills/` を 2 つの marketplace 設定 (`.claude-plugin/marketplace.json` / `.agents/plugins/marketplace.json` + `.codex-plugin/plugin.json`) から指すことで、片方のフォークやコピーを作らずに済ませる。

## ディレクトリ構造

```
skills/                       ← 単一のソース。スキル本体はすべてここ
├── proofread-touyou/
│   └── SKILL.md
└── code-quality-scorer/
    ├── SKILL.md              ← 使い方 / 設計 / 動作モード
    ├── ROADMAP.md            ← 開発者向け引き継ぎ文書
    ├── references/           ← 言語別プロファイル + ルーブリック
    ├── scripts/              ← Tier 1 / 2 / 3 / aggregate / trend / bus_factor
    └── evals/                ← eval ハーネス (将来用)

.claude-plugin/
└── marketplace.json          ← Claude Code 用 (writing-pack / quality-pack の 2 plugin に分離)

.codex-plugin/
└── plugin.json               ← Codex 用 (touyou-skills 1 plugin として全 skill を提供)

.agents/
└── plugins/
    └── marketplace.json      ← Codex 用 marketplace 定義 (リポジトリ単独で publish 可能にする)

AGENTS.md                     ← この文書 (実体)
CLAUDE.md                     ← AGENTS.md への symlink
README.md                     ← 公開向け (インストール案内 + スキル一覧)
```

スキルによっては `SKILL.md` 1 枚で完結するものと、`scripts/` や `references/` を持つ複合スキルがある。後者でも entry point は `SKILL.md` なので、エージェントは `SKILL.md` を起点に必要なリソースを参照する。

## ローカル開発（symlink での読み込み）

開発しながら直接 Claude Code に読ませたいときは、`~/.agents/skills/` 配下にシンボリックリンクを張る:

```sh
ln -s ~/Developer/Private/skills/skills/<skill-name> ~/.agents/skills/<skill-name>
ln -s ../../.agents/skills/<skill-name> ~/.claude/skills/<skill-name>
```

(`.claude/skills` は `.agents/skills` を経由する間接参照。touyou の既存セットアップに合わせている)

Codex 側もデフォルトで `~/.agents/skills/` を読むので、上記 1 段目のリンクだけで Codex 用にも有効化される。

## 新しいスキルを追加するときの手順

1. `skills/<skill-name>/SKILL.md` を作成
   - YAML frontmatter 必須: `name`, `description`
   - 推奨: `license`, `metadata.author`, `metadata.version`
   - **description は invocation trigger になる** ので、ユーザーがこのスキルを呼びたくなる時の言い回しを複数含める
2. 必要に応じて `scripts/` / `references/` / `evals/` などの補助ディレクトリを追加。SKILL.md から相対パスで参照する
3. **Claude Code 側** (`.claude-plugin/marketplace.json`):
   - 既存プラグインの description と一致するなら、対応する plugin の `skills` 配列に `./skills/<skill-name>` を追加
   - **目的が既存プラグインと違うなら新プラグインを切る** (例: `writing-pack` = ライティング系 / `quality-pack` = コード品質計測系)
4. **Codex 側** (`.codex-plugin/plugin.json`):
   - `skills` フィールドが `./skills/` を指していれば自動で拾われるので、通常は何もしない
   - 新規スキルが `mcpServers` / `apps` / `hooks` を持つ場合は plugin.json 側にも追記
5. README のスキル一覧テーブルに行を追加
6. ローカルで symlink を張って動作確認
7. コミット

## スキル文書設計: SKILL.md = ルーター、references = 正本

`references/` を持つ複合スキルでは、**同じ内容を SKILL.md と references の両方に書かない**（二重管理は必ず drift する）:

- **SKILL.md 本体**: 手順の流れ・各ステップの要点・ハッピーパスのスケルトン・判断ポイントを示す**ルーター**。抜粋スケルトンまでは置いてよい
- **references/xxx.md**: コピペで使う完全版の設定ファイル・テンプレート・チェックリストの**正本**。丸ごとのファイルは必ずこちらだけに置く
- SKILL.md からは相対パスで references を指し、「完全版はこちら」と明示する

SKILL.md 1 枚で完結する小さいスキルにはこの分割を強制しない。「本体が肥大化してきた」「同じ設定ブロックを 2 箇所で直した」が分割のサイン。

## スキルが生成するプロンプトの設計原則

スキルの中には、サブエージェントや別 CLI に渡すプロンプトを組み立てるものがある (`pr-review-loop` のレビューエージェント指示、`parallel-review-harness` の観点別プロンプト等)。**そのプロンプトの設計にも一貫した原則を敷く**。個別スキルで場当たりに直すと必ず drift するため、ここを正本にする。

### 1. 発見と絞り込みを同じステップに混ぜない

発見役に「重要なものだけ報告して」「保守的に判断して」と言うと、**その指示に忠実に従って本物の発見を握り潰す**。発見の網羅性 (recall) と報告の精度 (precision) は別の工程で担保する:

- **発見ステップ**: 確度が低いもの・軽微なものも含めて全部出させる。各発見に確度と重大度のラベルを付けさせる (絞り込みの材料にするため)
- **フィルタステップ**: ラベルを使って、スキル側の決定論的なロジックか別パスの判定で絞る

**絞った結果は捨てない**。ここを間違えると、握り潰しをモデルからスキルに移し替えただけで元の問題が残る。落としたものは「要確認」「要相談」のような別枠に必ず残し、件数も報告する。フィルタが決めてよいのは *どこに出すか* (インラインか、サマリの末尾か) と *自動で手を入れてよいか* であって、*人間の目に触れさせるかどうか* ではない。

**ラベルの設計そのものが漏れの原因になる**ので、分類軸を作ったら次の 3 つを満たすか確認する:

- **1 軸 1 意味**: 種別・重み・確からしさは別の軸に分ける。「軽微」を種別と重みの両方に持たせると、どちらの経路からも落ちる指摘ができる
- **網羅**: どの値にも出力先がある。行き先のない値を enum に置いた時点で、そこに落ちた指摘は黙って消える
- **排他**: 1 つの発見が複数の区分に該当しない。重なる条件を並べるなら、上から評価して最初に当たった行で確定する優先順位を明記する。「中〜高」のような幅のある値も置かない (レポートの節に置き場がなくなる)

分類を追加・変更したら、**全区分をひととおり辿って出力先を数える**。これは原則 3 の「汎用的な自己検証」ではなく、有限の集合を数える決定論的な確認なので、必ずやる。

単一パスで自己フィルタさせたい場合も「重要なものだけ」のような定性的な表現は使わず、「誤動作・テスト失敗・誤った結果につながりうるものは全部。純粋な命名やスタイルの好みだけ除外」のように**基準を具体的に書く**。

### 2. 委譲にはコストがあることを明示する

サブエージェントは 1 体ごとに文脈の再構築・再探索・報告・親側での再読が発生する。「使えるから使う」ではなく、**オーバーヘッドを上回る見返りがある時だけ**使わせる:

- 数回のツール呼び出しで自分で終わる仕事は委譲しない
- 「自分の出した答えを念のため見てもらう」ための委譲はしない (それは原則 3 の過剰検証を外注しているだけ)
- 1 体で足りるなら 1 体。並列は独立した大きめのトラックに限る
- 起動数がコストに直結するスキルでは、上限だけでなく**下限** (この規模ならハーネス自体を使わない) も書く

**独立した視点を得るための委譲は別物**で、これは推奨する。`parallel-review-harness` が観点ごとにレビューアを分けるのは「同じ答えを再確認させる」のではなく「互いの結果を見ない複数の視点に別々に探させ、一致・不一致を確度の材料にする」ため。前者は過剰検証、後者は設計。区別の目安は **委譲先が自分の結論を知っているか** — 知っていれば追認になりやすく、知らなければ独立した証拠になる。

### 3. 汎用的な自己検証を指示しない

「最後に必ず検証して」「返答前に再確認して」のような**抽象的な自己検証の指示は書かない**。過剰検証を招くだけで質は上がらない。書いてよいのは「lint / test を実行して結果を報告する」のような**具体的なツール実行と、その結果の報告義務**。他者の主張の裏取り (`review-followup` の「対応コミットの diff を読む」等) も別物で、これは残す。

### 4. 軽微な判断で止まらせない

「不明な点があれば確認する」だけ書くと、命名・デフォルト値・同等な選択肢のどれかといった**些末な判断まで人間に投げ返してくる**。確認を求めてよい範囲を具体的に区切る:

- 軽微な判断 (命名・書式・デフォルト値・同等案の選択) → 自分で決めて、決めたことを注記する
- スコープの変更・破壊的操作・仕様の解釈が割れる箇所 → 確認する

### 5. 長さは長さとして指示する

出力が長すぎる時に推論の深さ (effort 等) を下げても、**可視出力の長さは変わらない**。長さを制御したいなら「簡潔に」「前置きを省く」と明示的に書く。逆に、機械的なステージには浅い推論、判定ステージには深い推論、と使い分ける指示を書くのはコスト削減に効く。

## プラグイン切り分けの方針 (Claude Code 側)

1 プラグイン = 1 つの目的領域、を緩く守る:

- **writing-pack**: 文章・コンテンツ系 (校正、リライト、翻訳)
- **quality-pack**: コード品質計測・分析系 (スコアリング、トレンド、bus factor)

新しい skill を追加するときは、既存プラグインの description と一致するなら同居 OK、ズレるなら別プラグインを切る判断を README / marketplace.json と一緒に行う。

Codex 側は `.codex-plugin/plugin.json` が「1 リポジトリ = 1 plugin」前提のため、現状は `touyou-skills` 1 plugin にすべての skill をまとめている (Codex でプラグイン分割が必要になったら、subdirectory に plugin.json を分けて `source.source = "git-subdir"` で marketplace から指す方式を検討)。

## バージョン管理

- 各 skill の `SKILL.md` frontmatter にある `metadata.version` は **skill 単位の semver** (例: code-quality-scorer は `"0.4.1"`)
- `.claude-plugin/marketplace.json` の `metadata.version` は **marketplace 全体の semver**
- `.codex-plugin/plugin.json` の `version` は **Codex plugin 全体の semver** (Claude marketplace と歩調を合わせる)
- 新規 skill 追加・plugin 構成変更は marketplace 側 minor bump、skill 内部の機能追加は skill 側 minor bump

## コミット / プルリクの方針

- 個人リポジトリなので main 直 push 可。ただし広範な構造変更や互換破壊は事前にメモを残す
- コミットメッセージは「変更の why」を 1〜3 文。長くなる場合は箇条書きの body を付ける
- Co-Authored-By trailer は AI と協働した場合に付ける

## このリポジトリで読むべきドキュメント

- スキル個別の仕様: `skills/<name>/SKILL.md` (常に entry point)
- スキル開発者引き継ぎ: 各 skill の `ROADMAP.md` (存在する場合)
- 公開向け: `README.md`
