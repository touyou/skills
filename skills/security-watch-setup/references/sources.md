# 毎回見る一次情報（ルーチンの `{{SOURCES}}` に入れる候補）

detect-env.sh の結果で、使っているものの行だけを選んでルーチンに入れる。
「共通」と「証明書・CA」はどの環境でも入れる。「使っている」の判断は SKILL.md の Step 1 に従う
（手元にランタイムが無くても、ロックファイル・Dockerfile・CI に出てくれば入れる）。

GitHub Advisory API の `published=>=<日時>` の絞り込みは、`curl -s "https://api.github.com/advisories?per_page=100&type=reviewed&published=>=2026-10-22T00:00:00Z"` の
形で動くことを確認済み（2026-10-23）。

## 共通

- GitHub Advisory Database API（全エコシステムの勧告と悪性パッケージ。前回時刻以降を見る）
  - `https://api.github.com/advisories?per_page=100&type=reviewed&published=>=<前回時刻 UTC ISO8601>`
  - `https://api.github.com/advisories?per_page=100&type=malware&published=>=<前回時刻 UTC ISO8601>`
  - `&ecosystem=npm` などで絞れる。100 件を超えたら `&page=2` 以降も見る。`gh api` 経由なら認証付きでレート制限に余裕がある
- CISA KEV（実際に悪用されている脆弱性）: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- ニュース（WebSearch で直近 48 時間）: The Hacker News、BleepingComputer、StepSecurity、Socket、Aikido、Snyk の各ブログ

## ランタイム

| 使っているもの | 一次情報 |
|---|---|
| Node.js | https://nodejs.org/dist/index.json（`security: true` の行）、https://nodejs.org/en/blog/vulnerability |
| Bun | https://bun.sh/blog（リリースノート。Node の脆弱性が Bun にも及ぶことがある） |
| Deno | https://github.com/denoland/deno/releases |
| Ruby | https://www.ruby-lang.org/en/news/（本体と default gems。正規表現エンジンなどの修正もここ） |
| Python | https://www.python.org/downloads/ 、https://pyfound.blogspot.com/ |
| PHP | https://www.php.net/ （トップのニュース）、https://www.php.net/ChangeLog-8.php |
| Go | https://go.dev/doc/devel/release |
| Java（OpenJDK） | https://openjdk.org/groups/vulnerability/advisories/ |
| Swift / Xcode | https://support.apple.com/en-us/100100 （Apple のセキュリティアップデート一覧に Xcode も載る） |
| Flutter / Dart | https://github.com/dart-lang/sdk/security/advisories 、https://docs.flutter.dev/release/release-notes |

## パッケージ（GitHub Advisory API でカバーされるが、反映が遅れることがある）

| ロックファイル | 追加で見るところ |
|---|---|
| npm 系（package-lock / pnpm-lock / yarn.lock / bun.lock） | https://socket.dev/blog 、https://www.stepsecurity.io/blog （乗っ取り・悪性版の第一報が早い） |
| pip 系（uv.lock / poetry.lock / requirements） | https://blog.pypi.org/ |
| Gemfile.lock | https://rubysec.com/ |
| Podfile.lock / Package.resolved | 各ライブラリの GitHub Security Advisories（GitHub Advisory API の `ecosystem=swift`） |
| pubspec.lock | GitHub Advisory API の `ecosystem=pub`、https://github.com/dart-lang/sdk/security/advisories |
| build.gradle / pom.xml / gradle.lockfile | GitHub Advisory API の `ecosystem=maven`（repo_scan.py の `--maven` は直接書かれたバージョンだけを拾う。扱いはルーチン雛形の 3 章） |
| composer.lock | https://github.com/FriendsOfPHP/security-advisories |
| go.sum | https://pkg.go.dev/vuln/ |
| Cargo.lock | https://rustsec.org/advisories/ |
| `.github/workflows/*.yml`（GitHub Actions） | GitHub Advisory API の `ecosystem=actions`、https://www.stepsecurity.io/blog （action の乗っ取りの第一報が早い） |

## OS・ツール

| 使っているもの | 一次情報 |
|---|---|
| macOS | https://support.apple.com/en-us/100100 |
| Windows | https://msrc.microsoft.com/update-guide/ |
| Linux（Docker イメージ・サーバー） | 使っているディストリのセキュリティ告知（Debian: https://www.debian.org/security/ 、Ubuntu: https://ubuntu.com/security/notices 、Alpine: https://security.alpinelinux.org/ 、Amazon Linux: https://alas.aws.amazon.com/ 、RHEL / UBI: https://access.redhat.com/security/security-updates/ ） |
| Chrome | https://chromereleases.googleblog.com/ |
| Docker Desktop / Engine | https://docs.docker.com/desktop/release-notes/ 、https://docs.docker.com/engine/release-notes/ |
| git | https://github.blog/open-source/git/ （セキュリティリリースの告知） |
| Homebrew | `brew update && brew outdated` の結果そのもの（個別の告知は少ない） |
| 共有ライブラリ（openssl / zlib / curl / libxml2 / brotli / nss） | https://openssl-library.org/news/vulnerabilities/ 、https://curl.se/docs/security.html 、https://github.com/madler/zlib/releases 、https://gitlab.gnome.org/GNOME/libxml2/-/releases 、https://github.com/google/brotli/releases （言語のバインディングやランタイムに同梱された版にも及ぶ） |
| mise / asdf / uv / pnpm | 各 GitHub リポジトリの Releases と Security タブ |
| VS Code / Cursor / Electron 製アプリ | 各アプリのリリースノート（Electron の勧告は GitHub Advisory API の `ecosystem=npm` の electron） |

Docker イメージのディストリの決め方: タグに名前が入っていればそれ（`-alpine`・`-bookworm`（Debian）・
`-al2`（Amazon Linux）・`ubi`（RHEL）など）。`node:24-slim` や `python:3.13` のように付いていない公式イメージは
Debian。`node:latest` や `node:${NODE_VERSION}` のように決まらないものは、Dockerfile の `ARG` の既定値か
公式イメージの既定（多くは Debian）とみなし、レポートに「推定」と書く。

## 証明書・CA

- 主要ブラウザ・OS のルート証明書の不信任・失効の告知（Chrome Root Program、Mozilla の dev-security-policy、Apple の信頼ストア）。
  不信任になった CA を使うサーバーや、CA の信頼を製品に埋め込んでいるツール（Docker Desktop など）の更新が要ることがある
