# 配信の段取り

立ち上げ時に決めておくと、最初の提出で慌てないもの。

## ブランチと Xcode Cloud

- `main` は統合用（デプロイのトリガーにしない）。`production` への push で Xcode Cloud が Archive → TestFlight
- `production` への反映は本人の OK を取ってから。main は自由にマージしてよい運用にしておくと、エージェントが止まらない
- Xcode Cloud のワークフローは App Store Connect 側で管理する。Xcode と macOS のバージョンは「Latest Release」にしておき、
  新しい SDK の API を使う変更は Xcode Cloud が追いついてからマージする（beta の API はブランチで待つ）
- ビルド番号は Xcode Cloud に任せるか、`CURRENT_PROJECT_VERSION` を `project.xcproj` で上げる。どちらかに決めて AGENTS.md に書く
- `ci_scripts/` は要るときだけ（`.xcodeproj` をコミットしているので生成の手順は要らない）

Xcode Cloud で踏んだもの `[measured]`（Intento、2026-09〜10）:

- Xcode Cloud の書き出しが全プラットフォームで `Communication with Apple failed`（ポータルへの `listTeams` が 502）で落ちた。
  同じ日に他のアプリでも出ていて、数時間後に同じコミットを再実行したら通った。コードを疑う前に時間をおく。
  手元で代わりに上げようとすると、`xcodebuild archive` 自体は通るが、CLI からの書き出し（export / upload）は Xcode のアカウントが使えず（`missing Xcode-Token`）署名で止まる
- `production` への push で自動起動しないことがあった。`asc xcode-cloud run --workflow <名前> --branch production` で手で起動できる
- ワークフローを beta の Xcode に向けたままにすると、ビルドは通っても提出で弾かれる（[app-store-submission.md](app-store-submission.md) の 1）

## 提出前に埋めるもの

| 項目 | 置き場所 | 無いと |
|---|---|---|
| 起動画面 | `INFOPLIST_KEY_UILaunchScreen_Generation: YES` | iOS 27 ではアップロードが `ITMS-90870` で弾かれる `[Apple]` |
| 暗号の申告 | `INFOPLIST_KEY_ITSAppUsesNonExemptEncryption: NO` | 提出のたびに質問される |
| プライバシーマニフェスト | `App/Resources/PrivacyInfo.xcprivacy` と、必須理由 API を使う**拡張・Watch アプリのバンドルごと** | アップロード後に ITMS-91053 の警告が来る。下の注 |
| 表示名 | `INFOPLIST_KEY_CFBundleDisplayName` と `InfoPlist.xcstrings` | ホーム画面の名前が英名のまま |
| カテゴリ | `INFOPLIST_KEY_LSApplicationCategoryType` | Mac 版で必須 |
| 使用目的の文言 | `INFOPLIST_KEY_NS…UsageDescription` と `InfoPlist.xcstrings` | 権限を求めた瞬間にクラッシュ |
| アプリアイコン | `AppIcon.appiconset`（ライト / ダーク / tinted） | Xcode Cloud の Archive と書き出しは成功するのに、App Store Connect への取り込みで失敗する（気づきにくい）`[measured]`（2026-10） |
| 写真への保存 | `INFOPLIST_KEY_NSPhotoLibraryAddUsageDescription` | 画像を共有シートに渡しても「画像を保存」が出ない `[measured]`（2026-11） |

プライバシーマニフェストの注（理由コードと置き場所の規則は `[Apple]`、置いた結果は `[measured]`、Intento 1.0）:

- `UserDefaults` は理由コードを使い方ごとに選ぶ。`standard` は `CA92.1`（アプリ自身だけが読む）、
  `UserDefaults(suiteName: "group.…")` は `1C8F.1`（同じ App Group のアプリと拡張だけが読む）。両方使うなら両方書く
- 置き場は「必須理由 API を使う実行ファイルを含むバンドル」ごと（Apple の文書）。アプリ本体・ウィジェット・Live Activity・
  Watch アプリの 4 つに置いた。同期フォルダに置けばプロジェクトファイルの変更は 0 行。
  **プロジェクトファイルに差分が出たら、同期フォルダの外に置いてしまっている**（ターゲットに入っていない）

最初の提出の前に、全プラットフォームの Release ビルドと実署名の `xcodebuild archive`（`-allowProvisioningUpdates`）を通し、
archive の中身を見る: マニフェストが全バンドルにあるか、版番号、`ITSAppUsesNonExemptEncryption`、拡張が埋め込まれて
同じチームで署名されているか、`<lang>.lproj/nlu.appintents`（Siri のフレーズの学習データ）が言語ごとに出ているか。
ここまで見て「Xcode Cloud が通る状態」と言える。

## 掲載物

- 掲載文は `metadata/` か `docs/app-store/` に置き、App Store Connect の CLI（`asc`）で反映する
- ストア画像は `store-screenshot-composer`。Duo・iOS 27 のヘッダー／検索画像も同じ設定から
- アプリ内課金があるなら StoreKit の設定ファイルを scheme に付け、掲載の「アプリ内課金なし」表記を直す
- 審査で情報提供を求められたら、画面収録と目的・手順・外部サービス・地域差・権利を英文で返す
  （月屏風 1.0.0、2026-10-24。項目は画面収録 / 目的と対象 / 手順 / 外部サービス / 地域差 / 規制業種と第三者の素材の 6 つ。
  アカウント・UGC・課金・通信が無いことも、無いと書く。同じ英文を審査メモにも入れておく）
- アプリの画面のスクリーンショットは、起動引数で状態を固定して撮る（`-place 2 -season 3 -debugDegrees 150` など）。
  起動引数は `UserDefaults` の引数ドメインに入るので、保存した設定と同じ読み方で上書きできる
- 絵をコードで描くアプリは、元絵とアイコンを Mac の CLI で書き出す（→ [metal-rendering.md](metal-rendering.md)）
- 素のスクショの撮影は [screenshot-capture.md](screenshot-capture.md)、`asc` での版の作成・差し替え・提出で踏んだものは
  [app-store-submission.md](app-store-submission.md)

## What's New

変更の羅列だけにしない。冒頭に使う人へのひとこと（その変更で何がうれしくなるか）を添えてから変更点。ja / en とも同じ温度。

> いつも使ってくださり、ありがとうございます。今回は○○をもっと気持ちよく使えるようにしました。
> - …

touyou のアプリでは、App Store で配信されると What's New がそのまま dev-null.sh に投稿される
（touyou.github.io の `devnull-appstore.yml` に表示名で登録する）。

## 新しいリポジトリを作ったら

1. `delete_branch_on_merge` を有効にする
2. `production` ブランチを作り、Xcode Cloud のワークフローをつなぐ
3. 依存の脆弱性の定期チェック（`security-watch-setup` で作ったルーチン）の対象に足す
4. ポートフォリオ・LP に載せるなら、その段取りを issue に
