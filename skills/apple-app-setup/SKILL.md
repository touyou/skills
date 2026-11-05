---
name: apple-app-setup
description: 新しい Apple プラットフォームのアプリ（iOS / iPadOS / macOS / visionOS、iPhone Duo を含む）を、App Intents 中心設計・Apple 公式の Xcode スキル・HIG に沿った形で立ち上げる。「新しい iOS アプリを作りたい」「Apple のアプリのひな形を作って」「アプリをセットアップして」「プロジェクトの初期構成を決めたい」「Duo にも対応したアプリを新規で」に使う。構想の聞き取り → できることを App Intents の一覧として設計 → 対象 OS と構成の決定 → JSON 形式の Xcode プロジェクト（project.xcproj）とローカル SPM のひな形の書き出し → エージェント向けの規約（AGENTS.md・devlog）→ 検証と配信の段取りまでを行う。既存アプリへの後付けの App Intents 設計だけなら app-intents-centric-design、既存アプリの Duo・リサイズ対応だけなら Apple の app-resizability を使う。
license: MIT
metadata:
  author: touyou
  version: "0.6.5"
---

# apple-app-setup

新しい Apple プラットフォームのアプリを、最初の 1 コミットから「あとで作り直さなくて済む形」で立ち上げるスキル。
ひな形を書き出すだけでなく、**どこで無音の失敗が起きるか**を最初から構成に織り込むのが目的。

Apple の開発は、ビルドが緑でも機能が存在しない失敗が多い（App Shortcut が消える、訳が引かれない、
Release だけ落ちる、閉じた Duo でボタンが消える）。どれも後から気づくと直す場所が散らばるので、
**置き場所と検査を最初に決める**。

## このスキルが使う情報源

内容を複製せず、場面ごとに正本へ振り分ける。対応表と入手方法は [references/sources.md](references/sources.md)。

| 場面 | 正本 |
|---|---|
| アクション・エンティティの設計 | `app-intents-centric-design` ほか 9 本（touyou/IntentTodo の skills） |
| App Intents の API の罠と新 API | Apple の `app-intents-specialist` / `app-intents-whats-new-27` / `siri-app-integration` / `siri-evaluations`（Xcode 同梱） |
| SwiftUI の書き方 | Apple の `swiftui-specialist` / `swiftui-whats-new-27`（Xcode 同梱）＋ [references/swiftui-rules.md](references/swiftui-rules.md) |
| 画面サイズの変化・Duo | Apple の `app-resizability`（UIKit の置き換え中心）＋ [references/iphone-duo.md](references/iphone-duo.md)（SwiftUI と実地の落とし穴） |
| 音の再生・録音 | [references/audio.md](references/audio.md)（セッションのカテゴリ、Intent からの再生、押した瞬間の遅れ、録音、AVAudioEngine の形式） |
| macOS / visionOS へ広げる | [references/macos-visionos.md](references/macos-visionos.md)（シーン・メニュー・サンドボックス・アイコン） |
| ローカライズの設定と検査 | IntentTodo の `app-intents-localization` ＋ [references/localization.md](references/localization.md) |
| Xcode Cloud・提出の検証 | [references/xcode-cloud.md](references/xcode-cloud.md) |
| アクセシビリティ | `apple-accessibility`（このリポジトリの a11y-pack） |
| ストア画像 | 素のスクショの撮影は [references/screenshot-capture.md](references/screenshot-capture.md)、仕上げは `store-screenshot-composer`（store-pack） |
| ビルド設定のセキュリティ | Apple の `audit-xcode-security-settings` |
| 性能の計測 | Apple の `xctrace` ＋ `autonomous-perf-loop`（perf-pack） |
| デザインの原則 | [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) |
| 自前の Metal 描画・書き出し用の CLI | [references/metal-rendering.md](references/metal-rendering.md) |
| アプリ内課金 | [references/storekit.md](references/storekit.md)（StoreKit 2 のコード）＋ [references/in-app-purchase.md](references/in-app-purchase.md)（ASC・RevenueCat の設定） |

Apple の Xcode 同梱スキルは「Apple が書いた最新の正本」として扱い、自分の記憶と食い違ったら
そちらを採る。ただし宣言（SDK）と実行時の挙動は別物なので、**このスキルの references にある
`[measured]` の記述は実際に動かして確かめたもの**として、Apple の文書に書かれていない落とし穴の補足に使う。

## 進め方

各ステップの要点だけをここに置き、完全版は references にある。

### 1. 構想を聞き取る（[references/interview.md](references/interview.md)）

コードを書く前に、次の 6 つを決める。決まっていないものは推奨を添えて聞く。軽微な判断
（ターゲット名、フォルダ名、既定の色など）は自分で決めて、決めたことを書き残す。

1. **誰が・どの場面で・何をするアプリか**（1 文で）。この文の動詞がそのまま最初の App Intent 候補になる
2. **対象 OS と最低バージョン**。新規なら最新メジャー（例: iOS 27.0）を推奨。新 API はそのまま使えて、
   ポイントリリースの API（例: Duo のヒンジは 27.1）だけを `#available` で囲めば済む
3. **データの置き場所**（端末内 / iCloud / 自前サーバ）と、ウィジェットなど拡張から読むか
4. **システムの面**（Siri・ショートカット・ウィジェット・コントロール・Spotlight・Live Activity）のどれに届けるか
5. **Duo・iPad・Mac で画面の形が変わるときの方針**（1 カラム／左右分割／Duo 専用の体験）
6. **配信**（App Store / TestFlight 内部のみ / 社内配布）と課金の有無

### 2. できることを App Intents で設計する（[references/app-intents-first.md](references/app-intents-first.md)）

**構成やひな形より先に**、「このアプリでできること」を Intent と Entity の一覧にし、`docs/PLAN.md` の
中心に置く（画面の一覧ではなく、この一覧が仕様）。設計と実装の中身は **IntentTodo の skills が正本**で、
このスキルは複製しない。どの順にどれを読むかだけを references に置いた。

実装も Intent が先: Service と Intent / Entity / Query をテスト付きで最初の機能 PR にし、次に小さい面
（ウィジェット・コントロール・App Shortcut）、アプリの画面は最後。「画面を作ってから Intent を足す」順にすると、
ロジックが View に入り込み、Intent がその写しになる。進捗の一覧やチェックリストでも App Intents を最後の行に置かない。

**終わった印**: `docs/PLAN.md` に IntentTodo の `app-intents-design-session` の 4 表（ユースケース → Intent と Entity → 面 → 名前）が
入るまで、AppUI に手を付けない。ひな形の AppUI（下の 4）はビルドを通すための仮の画面で、最初の機能 PR では
置き換えない（最初の PR は Domain・Service・Intent とそのテストだけ）。サンプルを全部置き換える作業から入ると、画面にも同時に手が伸びる。

### 3. 構成を決める（[references/project-skeleton.md](references/project-skeleton.md)）

- プロジェクトファイルは Xcode 27.2 の **JSON 形式の `project.xcproj`**（IntentTodo と同じ）。同期フォルダなので
  ファイルを足してもプロジェクトファイルは変わらず、差分が読める。XcodeGen は最初の書き出しにだけ使い、
  `project.yml` は変換後に消す（正本を 2 つにしない）。ターゲットや設定の変更は Xcode で行い、外部から書き換えない
- ロジックは **ローカル SPM パッケージ**に置き、アプリと拡張のターゲットは `@main` などのひな形だけにする。
  層は `Domain ← Persistence ← AppIntentsKit ← AppUI / WidgetUI` の一方向
- `AppShortcutsProvider` は**アプリのターゲット**に、`@Dependency` の登録は**アプリと各拡張のターゲット**に置く。
  パッケージに置くと App Shortcut がビルドエラー無しで消える
- Swift 6 言語モード、String Catalog、生成 Info.plist、アセットのシンボル生成を最初から有効にする
- `developmentRegion` / `knownRegions` をカタログのソース言語と揃える（ずれると日本語の端末で英語で開く。[references/localization.md](references/localization.md)）
- macOS / visionOS も出すなら、パッケージの `platforms` に全部書き、OS ごとの分岐は互換層を作らずその場の `#if` で始める（[references/macos-visionos.md](references/macos-visionos.md)）

### 4. ひな形を書き出す

```bash
python3 scripts/scaffold.py --name Patchday --display-name Patchday \
  --bundle-id dev.touyou.patchday --team XXXXXXXXXX \
  --platforms ios,macos --widget --source-language ja --out ~/Developer/Private/Patchday
```

書き出すもの: `.xcodeproj`（`project.xcproj`）、ローカル SPM（4〜5 層＋テスト）、アプリ・ウィジェットのひな形、
最初の Intent / Entity / Query、ターゲットごとの String Catalog、`PrivacyInfo.xcprivacy`、
`AGENTS.md`（`CLAUDE.md` はその symlink）、`docs/devlog/`、`.gitignore`、`.swiftlint.yml`。
スクリプトは書き出しの最後に `xcodegen generate` と `xcodebuild -convert-project "Xcode Project"` を自動で回す
（どちらも Mac で。無い環境では手順を表示し、変換するまで `project.yml` を残す）。**3 種類のビルド**（下の 6）が緑になるまでを最初のコミットにする。

スクリプトは Python 標準ライブラリだけで動く。オプションの全量は `--help`。
サンプルの文言（Intent のタイトル・Siri のフレーズ・画面の文字）は `--source-language` の言語で書き出す。
Siri のフレーズはソース言語で書かないとその言語の Siri に出ないので、ja なら日本語のフレーズが入る。
もう一方の言語の訳は、ビルドでカタログにキーが出たあとで埋める（フレーズは `AppShortcuts.xcstrings`）。

Xcode 27.2 で、書き出した直後の状態が `swift test`・iOS / macOS の Debug・iOS の Release・`build-for-testing` の
すべてで警告なしに通り、出荷されるメタデータに App Shortcut が 2 件載ることを確かめている `[measured]`
（iOS + macOS、ウィジェットありの組み合わせ。JSON 形式への変換後も同じ）。visionOS、iOS だけ、`--no-widget` の組み合わせはまだ
ビルドで確かめていないので、使ったら 3 種類のビルドを回して結果を報告する。

パッケージに置いた Intent の文言は Xcode の抽出にかからない。キーはアプリとウィジェットのカタログに手で足し、
IntentTodo の skills にある `check_intent_copy_localization.py` で漏れを確かめる。

### 5. 画面を作る（[references/swiftui-rules.md](references/swiftui-rules.md) / [references/iphone-duo.md](references/iphone-duo.md)）

守ることの要点:

- サブビューは computed property ではなく独立した `View` struct で切る
- 構成（左右分割か 1 カラムか）は `horizontalSizeClass` ＋縦横で 1 か所で決め、子には結果だけを渡す。
  ピクセル幅の閾値で構成を変えない
- UI の文言は `String` 型のプロパティや引数で運ばない（`LocalizedStringKey` / `LocalizedStringResource`）
- ツールバー項目には必ずタイトルと role（`.close` / `.cancel` / `.confirm` / `.destructive`）を付け、
  あふれる順を `visibilityPriority` で決める（閉じた Duo では縦のバーへ移り、アイコンだけだと意味が伝わらない）
- 外周の余白は `contentMargins` に寄せる（Duo は safe area が左右で違う）
- Duo の折り目は「見る側」と「触る側」を分ける好機。ヒンジ角度を体験にするのは Duo 専用アプリのときだけ
- 音を鳴らす・録るアプリは、セッションのカテゴリを場面ごとに決めて切り替えを 1 か所に集める（[references/audio.md](references/audio.md)）

### 6. 検証の仕組みを入れる（[references/verification.md](references/verification.md)）

最初のコミットの時点で、次がすべて通る状態にする。

0. 最初だけ、App ID・App Group・iCloud コンテナを Developer アカウントに登録する（Xcode の Signing & Capabilities か、
   `-allowProvisioningUpdates` を付けた build を 1 回）。登録前は App Group などが無いと言われて署名で落ちる `[measured]`
1. `xcodebuild build`（Debug）を対象 OS の全 scheme で
2. `xcodebuild build -configuration Release`（Release だけで出るエラーがある）
3. `xcodebuild build-for-testing`（configuration は指定しない）と `swift test`（パッケージ）

App Intents のメタデータ（App Shortcut が 0 件になっていないか）と、String Catalog の訳漏れは
ビルドでは分からないので、IntentTodo の skills にある検査スクリプトを回す。
Duo の開閉は Xcode 27 ではシミュレータでも手で切り替えるしかない（DeviceHub）。自動の確認は
開いた状態と回転だけになる前提で、閉じた状態の確認は手順に入れておく。

### 7. エージェント向けの規約を置く（[references/repo-harness.md](references/repo-harness.md)）

`AGENTS.md` には「目次」と「知らずに触ると壊すが、壊れたことに気づけないルール」だけを置く。
説明・経緯は `docs/` と `docs/devlog/` に分け、同じことを 2 か所に書かない。残タスクは issue にする。
コードコメントは why / 制約 / 落とし穴だけ、3 行以内。

### 8. 配信の段取りを決める（[references/release.md](references/release.md) / [references/app-store-submission.md](references/app-store-submission.md)）

- `main` は統合用、`production` への push で Xcode Cloud が Archive → TestFlight
- 動くものができたら機能が揃う前に一度 TestFlight まで通す。提出の検証（拡張の版番号のずれ、サンドボックス、visionOS のアイコン、
  Intent の説明文の商標）はローカルでは出ない。Xcode Cloud の Xcode は beta を選ばない（審査に出せないビルドになる）。
  Archive の成功は秘密の値が入った証明にならないので、成果物を見る（[references/xcode-cloud.md](references/xcode-cloud.md)）
- 課金を入れるなら Paid Applications Agreement を最初に有効にする（無いと商品が 1 つも返らない。[references/in-app-purchase.md](references/in-app-purchase.md)）
- What's New は変更の羅列だけにせず、冒頭に使う人へのひとことを添える（ja / en とも同じ温度）
- 動的フレームワークは Embed & Sign（Do Not Embed は Debug で動き、配布版だけ起動直後に落ちる）
- 起動画面のキー（iOS 27 では無いと提出で弾かれる）、`ITSAppUsesNonExemptEncryption`、
  プライバシーマニフェスト（必須理由 API を使う拡張のバンドルにも）、アプリ名の表示名をこの時点で埋める
- 課金があるなら StoreKit の設定ファイルと、権利の確かめ方（`currentEntitlements` だけに頼らない）を最初から入れる（[references/storekit.md](references/storekit.md)）
- 最初の提出の前に、全プラットフォームの Release ビルドと実署名の archive を通して中身を見る
- `asc validate` が緑でも提出で弾かれる項目がある（App プライバシーの公開、visionOS のモーション申告、beta の Xcode）。
  公開前なら Intent の形はまだ変えられるので、承認を捨ててでも確定させてから最初の版を出す

## 終わったときに報告すること

- 決めたこと（対象 OS・層・データの置き場所・届ける面・Duo の方針）と、自分で決めた軽微な判断
- 3 種類のビルドと `swift test` の結果（実際に回したかどうかを区別して書く。回せなかったものは回せなかったと書く）
- 未確認のもの（Duo の閉じた状態、実機でしか見えない Siri の挙動など）と、それをどこに記録したか

## やらないこと

- 既存プロジェクトの移行（このスキルは新規の立ち上げ用。既存の `project.pbxproj` は Xcode 27.2 の
  `xcodebuild -convert-project "Xcode Project"` で変換でき、IntentTodo の devlog に等価性の確かめ方がある）
- Apple のスキルの中身の複製。振り分け先の名前と、補足だけを書く
- 1 アプリでしか通用しない判断（絵の方針、課金の値付けなど）を規約に入れること。それはアプリ側の docs に置く
