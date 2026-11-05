# App Store への提出（asc で回すとき）

App Store Connect の CLI（`asc`）で版の作成・掲載文・スクショ・提出を回したときに踏んだもの。
Intento（touyou/IntentTodo、iOS / macOS / visionOS の 3 プラットフォーム）で 2026-09〜10 に
1.0.0〜1.1.9 を出した記録（`docs/devlog/`）から、ほかのアプリでも同じ形で起きるものだけを置く。
立ち上げ時に決めることは [release.md](release.md)。

## 1. `asc validate` が緑でも提出は通らないことがある

`asc validate` は公開 API で読めるものしか見ない。次の 3 つは validate が errors 0 のまま提出で弾かれた `[measured]`。

| 弾かれ方 | 原因 | 直し方 |
|---|---|---|
| `You must have published answers to your app's data usages.` | App プライバシー（データの使用）が未公開。validate は `info`（blocking に数えない）で出すだけ | ASC の Web UI で公開する（`asc web privacy publish` は Apple ID + 2FA の Web セッションが要る） |
| `You must provide a value for the attribute 'hasHighMotionLabel'` | visionOS だけの申告（動きの激しいコンテンツの有無）。`appStoreVersions.update` の属性に無く、`asc` から触れない | ASC の Web UI で答える |
| `Build SDK build is not yet supported. / Build Xcode build is not yet supported.` | Xcode Cloud のワークフローが beta の Xcode を指していた。`asc` はワークフローの `xcodeVersion` を返さない | ASC の Web でワークフローの Xcode を正式版に戻して再ビルド |

- **提出でしか出てこない必須項目はプラットフォームごとに違う**。iOS / macOS が通っても visionOS が通るとは限らないので、別々に出して確かめる
- 上の 2 つの申告は一度答えると次の版でも効いている（毎回は要らない）`[measured]`
- RC の Xcode で作ったビルドは受け付けられる（27.0 RC の build が `VALID` で通り審査も通過）。
  「正式版の Xcode で出し直したい」と思ったら、先に正式版が本当に出ているかを `asc xcode-cloud xcode-versions` と
  developer.apple.com の RSS で確かめる。`Latest Release` に切り替えると新 SDK が無く、最低 OS を新しくしたアプリはビルドできない `[measured]`

## 2. 版レコードの作り方

- **審査中・承認済みで公開待ち（`PENDING_APPLE_RELEASE`）の版があると、次の版は作れない**
  （`You cannot create a new version of the App in the current state.`）。in-flight の扱い `[measured]`
- 差し替えたいときは、取り下げてから**同じレコードを改名**するのが速い。掲載文・キーワード・スクショが残る

```bash
asc submit cancel --version-id <VERSION_ID> --app <APP_ID> --confirm   # state は DEVELOPER_REJECTED に（1 分ほどかかる）
asc versions update --version-id <VERSION_ID> --version 1.1.0
asc versions attach-build --version-id <VERSION_ID> --build-id <BUILD_ID>
asc review submit --app <APP_ID> --version-id=<VERSION_ID> --build-id=<BUILD_ID> --confirm
```

- 取り下げると審査の順番を失う。片方のプラットフォームだけ先に公開済みなら、そちらは新しい版、
  審査中のほうは審査を通してから次を出す、と分けたほうが安いこともある
- 前の版が公開済みなら `asc versions create --copy-metadata-from <前の版> --exclude-fields whatsNew` で作り、
  whatsNew だけ入れる。**`--copy-metadata-from` はスクショもコピーする**（`metadataCopy.selectedFields` には
  テキスト項目しか出ないので気づきにくい）。そのまま追加で上げると枚数が倍になる `[measured]`
- `asc` のフラグは `--version-id=<ID>` の形で渡す。サブコマンドによっては `--version-id <ID>` が `flag needs an argument` になる

## 3. 掲載文とスクショ

- **初回リリースの版では `whatsNew` を編集できない**（`Attribute 'whatsNew' cannot be edited at this time`）。
  番号が 1.1.0 でも、公開済みの前の版が無ければ初回扱い。validate は warning を出すだけで提出は通る `[measured]`
- `asc metadata` は plan → approve → apply。**`plan` は `.asc/metadata/review/plan.json` を毎回上書きし、
  `approve` は中身を見ずに通る**。プラットフォームごとに plan → 出力を読む → approve → apply を通しで回す
  （plan の出力を捨てて approve したら、前のプラットフォームの plan を承認していた）`[measured]`
- `asc localizations upload` は `.strings` を期待する別物。`metadata/` の JSON には使えない
- 審査中の版があると app info が 2 つになり、`metadata plan` / `apply` に `--app-info` が要る
  （`multiple app infos found`。公開中の `READY_FOR_DISTRIBUTION` 側を渡す）。**`asc validate` は `--app-info` を受け取らない**ので
  この間は走らない。代わりに `asc review submit --dry-run` の `wouldSubmit: true` を見る `[measured]`
- app info の id は提出が終わる・取り下げると入れ替わる。毎回 `asc apps info list` で引き直す
- `asc screenshots list` の戻りは `.data[]` ではなく `.sets[].screenshots[]`。`.data[]` で読むと「1 枚も無い」と誤読する
- `--skip-existing` の判定は `sourceFileChecksum`（ファイルの md5）。撮り直すとファイル名が同じでも別物として上がる。
  入れ替えは `--replace --confirm`、上げたあとで `sourceFileChecksum` をローカルの `md5 -q` と照合する
- `screenshots upload` が途中の枚数で止まることがある（出力も JSON として読めない）。流し直すと通る。照合で気づける `[measured]`
- 設定画面などにバージョン番号が写るなら、版番号を上げたあとで撮り直す

## 4. 価格と配信地域（初回）

- `availability` がレコードごと無いことがある（`app availability not found`）。`asc pricing availability create` には
  `--all-territories` が無いので、`asc pricing territories list` の全件（175）を明示して渡す `[measured]`
- 価格スケジュールの開始日を「今日」にすると、UTC では未来になって弾かれる（`The first interval has a start date ... in the future`）。前日を渡す `[measured]`

## 5. 消えないドラフト

失敗した提出がドラフトの submission を残し、`asc submit cancel` で `Resource is not in cancellable state` になることがある。
ASC の Web UI には出ず、次からの提出も「stale なのでスキップ」で迂回される。放っておいてよい `[measured]`（Intento で 1.1.4〜1.1.9 の間ずっと残った）

## 6. 公開する前に Intent の形を確定させる

公開済みの Intent のパラメータ名と型は変えられない（保存済みのショートカットが外れる）。審査を通って
公開待ちの段階なら利用者はまだいないので、**承認を捨てて取り下げ、作り直してから出すのが一番安い**。
Intento は 1.0.0 の承認を捨て、App Schema に合わせて作り直した形を 1.1.0 として最初に公開した。
公開後は別 Intent + `isAssistantOnly = true` で移行する（`app-intents-parameters-and-prompts`）。
