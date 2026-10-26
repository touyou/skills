# ルーチンのプロンプト雛形（正本）

`{{...}}` を埋め、使っていないエコシステム・ツールの行を消してから登録する。
`<!-- -->` のコメントは埋め方のメモなので、登録するプロンプトからは消す。

埋める値:

| 置き換え | 中身 | 例 |
|---|---|---|
| `{{USER}}` | 本人の呼び名（通知・TODO の宛先） | alice |
| `{{SHELL}}` | バージョン管理ツールを有効にしているシェル（SKILL.md Step 1）。コマンド例の構文もこれに合わせる | fish |
| `{{SHELL_CMD}}` | `{{SHELL}}` を設定ファイルごと読ませて 1 コマンド実行する形。mise / nvm を `.zshrc` / `.bashrc` で有効にしているなら `-i` も要る | `fish -c`、`zsh -ilc`、`bash -ilc` |
| `{{CHECK_SHELLS}}` | ランタイムを確かめるシェル。`{{SHELL}}` と、`runtimes_by_shell` で実体が違ったシェル | fish・zsh・bash |
| `{{REPO_ROOTS}}` | リポジトリの置き場所（複数可） | `~/Developer` |
| `{{REPORT_DIR}}` | レポートの保存先 | `~/Documents/security-watch` |
| `{{SCRIPTS}}` | このスキルの `scripts/` の絶対パス | `~/.claude/skills/security-watch-setup/scripts` |
| `{{PR_REPOS}}` | PR を出してよいリポの一覧（owner/repo かパターン）。なければ「なし」 | `alice/*`、`acme/design-*` |
| `{{REPORT_ONLY_NOTES}}` | 報告だけのリポの連絡先など。なければ空にして、その文ごと消す | `acme/web` は ◯◯さん宛て |
| `{{SOURCES}}` | [sources.md](sources.md) から選んだ一次情報の行 | |
| `{{RUNTIME_CHECKS}}` | 確かめるランタイムとコマンド | `node -v`、`ruby -v`、`bun -v` |
| `{{UPDATE_POLICY}}` | 自動で上げてよい範囲 | Homebrew の formula（名前が変わるメジャー移行と Cask を除く）と mise のランタイム |
| `{{BOT_PR_POLICY}}` | `{{PR_REPOS}}` にある Dependabot / Renovate の PR の扱い。既定は「マージしない」。`{{PR_REPOS}}` が「なし」なら「触らない」 | ロックファイルだけの変更で CI が緑ならマージしてよい |
| `{{NOTIFY}}` | 通知の方法 | 下の「通知」節のコマンド |

---

```markdown
{{USER}} の PC と {{REPO_ROOTS}} 配下のリポジトリについて、直近に公開された脆弱性・悪性パッケージ・
ランタイムのセキュリティリリースの影響を確認し、必要な対応をしてください（定期実行）。
本人はこの場にいないので、実装の細部は自分で決めて結果に書く。外に出る操作（PR 作成・push・
通知）は、この手順に書いてあるものだけ行う。パスワード・2FA など対話入力を求めるコマンドは実行せず、
必要な操作として TODO に書く。トークン・鍵などの秘密情報はレポートにも通知にも書かない。
公開・リリースの操作（パッケージの publish、本番へのデプロイやリリース用ブランチへのマージ、OS の更新）はしない。

コマンドを実行するシェル（エージェントの既定のシェル）は、本人が普段使う {{SHELL}} と違うことがあり、
PATH も違う（mise / nvm のランタイムが見えないことがある）。ランタイムやバージョン管理ツールを使う
コマンドは、必ず `{{SHELL_CMD}} '...'` の形でシェルを指定して実行する。それ以外のコマンドは、
どのシェルでも動く書き方にする。

## 0. 前回の結果を読む
- 最初に `date` で今の時刻（ローカル時刻）を取る。レポートのファイル名と、7 章の「朝の回か」の判定に使う
- {{REPORT_DIR}} の最新レポートと TODO.md を読み、対応済み・報告済み・保留中の項目を把握する。
  状況が変わったものだけを書き、同じ内容を繰り返さない
- 前回のチェック時刻を控える（1 章の検索範囲に使う）。レポートのファイル名はローカル時刻なので、
  API に渡すときは UTC に直す。初回（レポートがない）は直近 7 日を範囲にする
- **前回レポートに書いてあることを「今回も確認済み」とみなさない**。1 章は毎回やり直す
- TODO.md の「保留」（修正版がまだ無い・誤検知と判定したもの）は、書いてある再確認の条件
  （修正版の公開・勧告の更新）が満たされたときだけ報告に出す。条件の確認は毎回やる。
  保留は「勧告・リポ・解決済みバージョン」の組で持ち、どれかが変わったら（ロックファイルの更新で
  該当版が戻った、別のリポにも出た など）保留を外して判定し直す

## 1. 最新の脆弱性を洗い出す（前回チェック以降を全部）
新規の報告は 1 日に数十件出るので、毎回すべての情報源を実際に開く。検索で新しいものが
出なかったときは、一次情報のページを直接開く。

毎回必ず開く一次情報:
{{SOURCES}}

追加で WebSearch する:
- 直近 48 時間の「malicious package」「supply chain attack」「CVE」「security release」
- **名前の付いた脆弱性**（「◯◯2Shell」「◯◯Bleed」など）がニュースに出ていたら、名前でも検索して
  CVE・影響範囲・修正版を確かめる。同じ CVE が言語や製品ごとに別の名前で報じられることがあるので、
  レポートには「名前 → CVE」の対応を全部書く（本人が名前で尋ねたときに引けるようにする）

GitHub Advisory API の結果は、手元のエコシステムのものだけ候補にする。100 件を超えたら次のページも見る。

## 2. ローカルを最新化する
- ツール: {{UPDATE_POLICY}}。起動中のアプリを落とすもの・再起動が要るものは上げず、手順をレポートに書く。
  「セキュリティ修正を含む」とみなすのは、1 章の候補に該当するもの、またはそのバージョンのリリースノート・
  勧告に security / CVE の記載があるもの。判断できないものは上げずに一覧だけ書く
- ランタイム: {{RUNTIME_CHECKS}} を **{{CHECK_SHELLS}} のそれぞれ**で、シェルを明示して実行し
  （例: `fish -c 'command -s node; node -v'`、`zsh -ilc 'command -v node; node -v'`、`bash -ilc '...'`）、
  修正版になっているか確かめる。シェルで実体が違うときは全部書く。古ければ、そのランタイムを入れている
  管理ツールで上げる。OS 同梱のもの（macOS の /usr/bin/ruby など）は上げられないので、その旨だけ書く。
  JDK は `/usr/libexec/java_home -V`（macOS）や管理ツールの一覧で入っているものを全部見る。既定で使われるものが
  EOL の版なら、修正が出ても届かないので要対応として TODO に書く
- リポのバージョン指定が実際に効いているか: `.node-version` などを持つリポで
  `{{SHELL_CMD}} 'cd <リポ> && node -v'` のように実行し、指定と一致するか確かめる。一致しないときは、
  指定の版が未インストール（入れてよい）か、管理ツールがそのファイルを読まない設定（mise の
  `idiomatic_version_file_enable_tools` など。設定は変えずに報告する）か、リポの別のファイル
  （`.tool-versions` の `latest` など）が優先されている。
- **修正版が公開済みなのに、管理ツール（Homebrew / mise など）にまだ来ていない**ときは、上げられる版と
  CVE をレポートと TODO に書き、次回以降に再確認する（前回から状況が変わっていなければ一行で済ませる）
- **脆弱な旧版の残置**: 管理ツールに古い版が並んで残っていないか見る（`mise ls`、`brew list --versions` で
  複数版が並ぶ formula など）。修正版より古い版で、どのリポの `.node-version` / `.ruby-version` /
  `.python-version` / mise 等の設定からも、グローバル設定（`~/.tool-versions`、`~/.config/mise/config.toml`）
  からも参照されておらず、Homebrew なら `brew uses --installed <formula>` が空のときだけ削除する（`mise uninstall <tool>@<version>`、
  `brew cleanup <formula>`）。参照されているものは消さず、参照元と一緒にレポートに書く
- 共有ライブラリ（openssl / zlib / curl / libxml2 / brotli / nss / ca-certificates など）: Homebrew 等で入って
  いる版と、言語のバインディング・ランタイムやアプリに同梱された版の両方を見る。1 章の候補がこれらに
  当たるときは、二次的な影響（例: Node の脆弱性が同じライブラリを同梱する Python パッケージや
  brew の formula にも及ぶ）まで辿る。Node・Chromium の脆弱性は Electron 製アプリ（VS Code・Discord・
  Notion など）にも同梱されるので、入っている Electron 製アプリと版を並べ、TODO の GUI アプリの更新に
  「この修正を含むか（確かめたか / 未確認か）」を添える
- パッケージマネージャの「公開から一定時間は入れない」設定（mise の `minimum_release_age` 等）で
  新版が保留されたら、設定は上書きせず、入れられる時刻をレポートと TODO に書く
- リポジトリ: `python3 -I {{SCRIPTS}}/repo_scan.py sync {{REPO_ROOTS}}`
  （fetch は全リポ。pull はクリーンなデフォルトブランチだけ ff-only。作業中のリポは触らない）。
  `FETCHFAIL` は権限切れ・削除済みのことが多いので、前回と同じなら一行で済ませる。
  `FETCHTIMEOUT` / `PULLTIMEOUT`（1 リポ 180 秒で打ち切り）は、続くようなら `--jobs 2` に下げて報告する

## 3. 影響を確認する
候補ごとに、各リポの **origin のデフォルトブランチ**で判定する（ローカルの作業ブランチは見ない）。
- パッケージ: `python3 -I {{SCRIPTS}}/repo_scan.py scan {{REPO_ROOTS}} --npm <名前,...> --malware <名前・スコープ,...>`
  が解決済みバージョンを出すので、勧告の affected range と照らし合わせる。候補のあるエコシステムの
  オプションだけ付ける（`--npm` `--pip` `--gem` `--pod` `--spm` `--pub` `--composer` `--go` `--cargo` `--maven`）。
  `npm audit` では出ないことがあるので、こちらを正とする
- Maven / Gradle（`--maven group:artifact`）は、gradle.lockfile と pom.xml・build.gradle に**直接書かれた**
  バージョンしか拾えない（推移的な依存は出ない）。出てこなかったリポは「未確認」と書き、影響が大きく
  最近も更新されているリポだけ `./gradlew dependencies` などで確かめる。全リポを毎回ビルドしない
- ランタイム本体（Node・Ruby・Python・PHP・Bun など）: `python3 -I {{SCRIPTS}}/repo_scan.py runtimes {{REPO_ROOTS}}`
  で Dockerfile の `FROM`・`.node-version` 等・CI の指定を見る。EOL 版や固定タグ・digest は要対応、
  浮動タグ（`node:24-slim` 等）は再ビルドで反映される、と書き分ける
- 発火条件（設定・使っている API・実行環境）まで見て、「影響あり / 条件を満たさず低い / 対象外」に分ける。
  低い・対象外も、理由を一行ずつ残す（黙って落とさない）
- GitHub Actions: `runtimes` の出力の `action` 行（ワークフローの `uses:`）を、GitHub Advisory API の
  `ecosystem=actions` の勧告と、侵害が報じられた action と照らし合わせる。侵害された action を
  タグ（`@v4` など）で参照していたら影響ありとして、修正版のコミット SHA への固定を推奨対応に書く
- 悪性パッケージは、名前の一致に加えて既知の痕跡（勧告にあるファイル・プロセス・接続先）も確かめる
- **CA の不信任・失効**（1 章の「証明書・CA」の告知）は、ベンダーの更新を待つだけで終えない。手元の信頼ストアごとに
  該当の CA が残っているかを確かめる: OS（macOS は `security find-certificate -a -c "<CA 名>" -Z
  /System/Library/Keychains/SystemRootCertificates.keychain` と `security dump-trust-settings -d` で不信任の設定の有無）、
  JDK ごとの cacerts（`keytool -list -cacerts`）、Homebrew の ca-certificates、Python の certifi、Ruby・Node が
  別に持つ CA ファイル、CA を同梱するアプリ（Docker Desktop など）。外す対象は告知（OpenJDK・Mozilla などの
  一覧）に載っている CA だけにし、**別名ではなく SHA-256 の指紋で照合する**（JDK の配布元ごとに別名が違う）。
  載っていない近縁の CA は残して、レポートに書く
  - ホーム配下にあり sudo の要らない信頼ストア（ユーザー領域に入れた JDK の cacerts など）: バックアップを
    `{{REPORT_DIR}}/` に取ってから自分で外し、外した後もよく使う接続先（Maven Central など）に TLS でつながるか確かめる
  - 管理者権限が要るもの（macOS のシステムキーチェーンなど）: 証明書ファイルを `{{REPORT_DIR}}/` に書き出し、
    貼ればそのまま動くコマンド（例: `sudo security add-trusted-cert -d -r deny -k /Library/Keychains/System.keychain <ファイル>`）を TODO に書く
- 最終コミットが 1 年以上前の休眠リポは、影響が大きいときだけ詳しく見る

## 4. 対応する前に既存の作業を確かめる（重複防止）
対応が要るリポごとに、着手前に必ず:
- `gh pr list --repo <owner/repo> --state open --search "<CVE 番号 or パッケージ名>"` と
  `gh pr list --repo <owner/repo> --state open` で同じ修正の PR（Dependabot / Renovate / 他メンバー / 過去の自分）がないか
- `gh pr list --repo <owner/repo> --state merged --search "<パッケージ名>" --limit 5` で既に直っていないか
- `git branch -r` に同じ目的のブランチがないか
当たれば新しく作らず、そのリンクをレポートに書く。

## 5. 対応する
**PR を出してよいのは次のリポだけ**: {{PR_REPOS}}
<!-- 「なし」のときは、この節を「PR は出さない。全リポとも報告と連絡文だけ」に置き換える -->

これらは: デフォルトブランチの最新から `security/<パッケージ>-<修正版>` ブランチを切る → 修正
（バージョン更新・ロックファイル再生成。ロックファイルの取得元 URL が社内ミラー等に変わったら
公式レジストリに戻し、integrity が一致することを確かめる）→ ビルド・テストを実行 → コミット・push →
`gh pr create`（本文に CVE・深刻度・修正版・実害の見立て・確認結果）。自分で作った PR は
**マージしない**。作業は追加の worktree で行い、PR が開いている間は残す。

これらのリポにある Dependabot / Renovate の PR: {{BOT_PR_POLICY}}
マージしてよいとされていても、マージが本番へのデプロイ・リリースを起動するリポ（デフォルトブランチへの
push でデプロイされるもの）、上げる先の版が公開から 24 時間たっていないもの、`type=malware` の勧告に
当たるものはマージせず、TODO に書く

それ以外のリポには PR を出さない。影響と推奨対応をまとめ、オーナー向けの連絡文（チャットに
そのまま貼れる短文）をレポートに用意する。{{REPORT_ONLY_NOTES}}

## 6. レポートを残す
`{{REPORT_DIR}}/YYYY-MM-DD-HHMM.md` に書く:
1. 新しく見つけた脆弱性と判定（影響あり / 低い / 対象外）と出典リンク
2. 自分で対応したこと（更新したツール、作った PR のリンク）
3. オーナーに任せるもの（リポ・内容・連絡文）
4. 既存 PR があったので見送ったもの
5. 前回からの持ち越し（未対応のまま残っているもの）

## 7. 本人に知らせる
- `{{REPORT_DIR}}/TODO.md` を毎回上書きする。本人がやることだけを優先度順のチェックリストで書く:
  自分の PR のレビュー・マージ（リンク付き）、上げられなかった GUI アプリ（終了してから打つコマンド付き）、
  オーナーへの連絡（レポートの該当箇所）、保留中の更新（入れられる時刻）、そのほか判断が要るもの。
  各項目に「いつから残っているか」の日付を付ける。何もなければ「なし（YYYY-MM-DD HH:MM 時点）」と書く
- TODO.md の最後に「保留」節を置き、修正版がまだ無い・誤検知と判定したものを、勧告・リポ・解決済み
  バージョンと理由・再確認の条件付きで残す（上書きのたびに引き継ぐ）。保留は本人のやることではないので、下の通知の件数には数えない
- TODO に新しい項目が増えたか、影響ありの脆弱性があれば通知する。変化がなければ 1 日 1 回
  （朝の回 = 0 章で取った時刻が正午より前の回）だけ送る。TODO が 0 件なら送らない
- 通知: {{NOTIFY}}

## 最後に
影響ありのものや本人の操作が要るものがあれば、まとめの冒頭に書く。何もなければ「新規の影響なし」と一言で終える。
```

---

## 通知コマンドの例

| 環境 | コマンド |
|---|---|
| macOS | `osascript -e 'display notification "<本文>" with title "セキュリティチェック" sound name "Glass"'` |
| Linux（デスクトップ） | `notify-send "セキュリティチェック" "<本文>"` |
| Windows | `powershell -Command "New-BurntToastNotification -Text 'セキュリティチェック','<本文>'"`（BurntToast が入っている場合）。なければ通知はやめて TODO.md だけにする |
| Claude Code（デスクトップの定期タスク） | 上の OS 通知に加えて `PushNotification` ツール（Remote Control が有効なときはスマホにも届く） |

本文は 1 行・200 字以内で、やることを先に書く（例: 「セキュリティ: PR 2 件のマージ待ち・Docker Desktop の更新が必要。TODO.md 参照」）。
