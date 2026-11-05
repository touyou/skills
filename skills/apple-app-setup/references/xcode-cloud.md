# Xcode Cloud と提出の検証

[release.md](release.md) の段取りを、実際に回して踏んだことで補う。出典は GRAPHICA と Graphica Playground
（1 リポジトリに Xcode プロジェクトが 2 つ、2026-06〜10）。

## 提出でしか出ないエラーは、最初期に空撃ちする

ローカルのビルド・開発配布では出ず、App Store Connect の処理で初めて出るエラーがある。しかも 1 つ直すと次が出る
層の構造だった。動くものができた時点で TestFlight まで一度通し、機能が揃うのを待たない `[measured]`

| エラー | 原因 |
|---|---|
| CFBundleVersion の不一致（ITMS-90049 ほか） | 拡張（ウィジェット）の `CURRENT_PROJECT_VERSION` / `MARKETING_VERSION` が本体とずれた |
| 暗号の申告・プライバシーマニフェストで保留 | `ITSAppUsesNonExemptEncryption` と `PrivacyInfo.xcprivacy` が無い |
| ITMS-90296 | macOS の拡張に `ENABLE_APP_SANDBOX` が無い |
| ITMS-90970 | visionOS のアイコンが無い（`.icon` は visionOS 非対応。[macos-visionos.md](macos-visionos.md)） |
| ITMS-90626 | App Intent の文言に Apple の商標が入っていた（書き方は IntentTodo の `app-intents-localization`） |

- **本体と拡張で揃えるもの**: 版番号・ビルド番号・サンドボックスの設定。プロジェクトファイルはターゲット × 構成で
  同じ値を重複して持つので、「本体だけ直して拡張を忘れる」が構造的に起きる。版を上げる手順に、全ターゲットを
  同じ値にする確認を入れる `[measured]`

## workflow をリポジトリで持つ

- **Xcode Cloud の product は API で作れない**（`ciProducts` への POST が無い）。最初の 1 回だけ Xcode の
  Product ▸ Xcode Cloud ▸ Create Workflow で作る。そこから先（起動条件・パスフィルタ・アクション）は
  `ci/xcode-cloud-workflow.json` などに置き、スクリプトで反映する `[measured]`
- 反映のスクリプトは**件数で決める**（workflow が 1 本なら更新、0 本なら作成、2 本以上なら止まる）。名前で探すと、
  JSON の `name` を変えたときに既存を見つけられず 2 本目を作る `[measured]`
- `X="$(asc ... | jq ... | head -1)"` は `set -e` が効かない（パイプラインの終了コードは最後のコマンド）。
  一覧の取得が失敗すると空文字になり、「無い」と誤判定して 2 本目を作る。取得はパイプラインから分ける `[measured]`
- ダッシュボードで TestFlight への配信を付けると、`actions` を含む PATCH が
  `Deployment configured for unknown action` で落ちる。Xcode / macOS の版だけ変えるときは `relationships` だけを PATCH する `[measured]`
- `manualBranchStartCondition` を入れておくと、`production` にマージせずに任意のブランチで手動ビルドを試せる
- 1 リポジトリに複数のアプリがあるなら、**workflow ごとにパスフィルタ**（`ios/<App>/`）。無いと Web だけの変更でも
  全アプリの Archive が走る

### Xcode の版

- **「Latest Beta or Release」を選ばない**。正式版が出たあと beta に解決され、そのビルドは TestFlight には載るが、
  審査の submission に入れると `Build SDK build is not yet supported` / `Build Xcode build is not yet supported` で弾かれる。
  気づくのは提出のときだけ `[measured]`（2026-09-29 と 2026-10-17 の 2 回）
- ポイントリリースの SDK の API（例: iOS 27.1 の `ArrangementView`）を使うなら、その SDK を含む正式版を名指しし、
  Latest Release がそこに追いついたら戻す

## 秘密の値と `ci_scripts`

- gitignore した `Config/Secrets.xcconfig` は、`ci_scripts/ci_post_clone.sh` で Xcode Cloud の秘密の環境変数から書き出す。
  **Archive のときは値が無ければ落とす**（無くてもビルドは緑で、課金だけ動かない `.ipa` が出る）。
  `CI_XCODEBUILD_ACTION` が未設定なら archive とみなす（安全側に倒す）`[measured]`
- **Xcode Cloud が認識する `ci_scripts` はリポジトリに 1 つだけ** `[Apple]`。プロジェクトが 2 つあると、片方用の
  スクリプトがもう片方のビルドでも走る。先頭で `CI_BUNDLE_ID` を見て振り分ける（`CI_PRODUCT` は表示名で変わりうる）`[measured]`
- **Archive の成功は、値が入った証明にならない**。スクリプトが走らなかった場合も緑になる。成果物を見る `[measured]`:

  ```bash
  # app-store エクスポートの .ipa を取り出して、Info.plist に本番の値が入っているか（値は出力しない）
  asc xcode-cloud artifacts list --run-id <RUN_ID> --output json
  asc xcode-cloud artifacts download --id <ID> --path /tmp/app-store.zip
  plutil -extract <KEY> raw Payload/<App>.app/Info.plist | grep -c '^<期待する接頭辞>'
  # 署名された entitlements
  codesign -d --entitlements :- Payload/<App>.app | grep -o 'com\.apple\.developer\.[a-z.-]*'
  ```

- **プロファイルに無い entitlement は、署名で黙って剥がれて Archive は緑になる**（申請中の Private Cloud Compute で実測）。
  承認待ちの entitlement を使う機能は、署名済みの成果物で確かめるまで出さない `[measured]`

## リモートの SPM 依存とオンボーディング

- 別の組織のリポジトリ（例: RevenueCat の `purchases-ios-spm`）に依存していると、Xcode Cloud のオンボーディングが
  その組織への GitHub App の接続を求め続けて終わらない。public な依存には本来 grant は不要 `[Apple]`。
  回避は、プロジェクトファイルからその依存の参照を一時的に外す → Xcode を開き直してオンボーディング →
  最初のビルドは断る → `git checkout` で戻す `[measured]`
- アプリのレコードは Xcode からは作れないことがあった。App Store Connect の web（または `asc web apps create`、
  パスワードと 2FA が要る）で先に作ってから Xcode の手順に戻る。API キーではアプリのレコードは作れない `[measured]`
- 「作れたはず」は画面ではなく API で確かめてから次へ進む（`asc xcode-cloud products list` が空だった）

## 動かないときの逃げ道

- **push を取りこぼすことがある**。マージから 5 分たっても run が無ければ `asc xcode-cloud run --workflow-id <ID> --branch production`
  で手で起こす。手動の run には開始条件（ブランチ・パス）が効かないので、変更の無い workflow は起こさない `[measured]`
- **export だけが `Communication with Apple failed` / 502 で落ち続ける**ことがある（archive は通る）。コードでは直せない。
  ローカルで `xcodebuild archive -allowProvisioningUpdates CURRENT_PROJECT_VERSION=<番号>` → `-exportArchive` →
  `asc builds upload` で出せる。ビルド番号は配信済みの最大と、失敗した run が使った番号の両方より大きくする
  （同じ版で後から Xcode Cloud が同じ番号を振るとアップロードが重複で弾かれる）。手元の秘密の値が開発用でないかも確かめる `[measured]`
- 失敗の原因は `asc xcode-cloud doctor --run-id <RUN_ID>` でログから引ける
- 審査に出す版は `production` を通ったビルドにする。main から手動で作ったビルドで出すと、出した物と `production` がずれる
