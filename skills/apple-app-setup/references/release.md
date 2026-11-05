# 配信の段取り

立ち上げ時に決めておくと、最初の提出で慌てないもの。

## ブランチと Xcode Cloud

- `main` は統合用（デプロイのトリガーにしない）。`production` への push で Xcode Cloud が Archive → TestFlight
- `production` への反映は本人の OK を取ってから。main は自由にマージしてよい運用にしておくと、エージェントが止まらない
- Xcode Cloud のワークフローは App Store Connect 側で管理する。Xcode と macOS のバージョンは「Latest Release」にしておき、
  新しい SDK の API を使う変更は Xcode Cloud が追いついてからマージする（beta の API はブランチで待つ）
- ビルド番号は Xcode Cloud に任せるか、`CURRENT_PROJECT_VERSION` を `project.xcproj` で上げる。どちらかに決めて AGENTS.md に書く
- `ci_scripts/` は要るときだけ（`.xcodeproj` をコミットしているので生成の手順は要らない）

## 提出前に埋めるもの

| 項目 | 置き場所 | 無いと |
|---|---|---|
| 起動画面 | `INFOPLIST_KEY_UILaunchScreen_Generation: YES` | iOS 27 ではアップロードが `ITMS-90870` で弾かれる `[Apple]` |
| 暗号の申告 | `INFOPLIST_KEY_ITSAppUsesNonExemptEncryption: NO` | 提出のたびに質問される |
| プライバシーマニフェスト | `App/Resources/PrivacyInfo.xcprivacy` | 必須理由 API（UserDefaults・ファイルの日時など）を使うと審査で止まる |
| 表示名 | `INFOPLIST_KEY_CFBundleDisplayName` と `InfoPlist.xcstrings` | ホーム画面の名前が英名のまま |
| カテゴリ | `INFOPLIST_KEY_LSApplicationCategoryType` | Mac 版で必須 |
| 使用目的の文言 | `INFOPLIST_KEY_NS…UsageDescription` と `InfoPlist.xcstrings` | 権限を求めた瞬間にクラッシュ |

## 掲載物

- 掲載文は `metadata/` か `docs/app-store/` に置き、App Store Connect の CLI（`asc`）で反映する
- ストア画像は `store-screenshot-composer`。Duo・iOS 27 のヘッダー／検索画像も同じ設定から
- アプリ内課金があるなら StoreKit の設定ファイルを scheme に付け、掲載の「アプリ内課金なし」表記を直す
- 審査で情報提供を求められたら、画面収録と目的・手順・外部サービス・地域差・権利を英文で返す

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
