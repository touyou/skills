# ローカライズをプロジェクトに組み込む

コードの書き方（`String` で運ばない）は [swiftui-rules.md](swiftui-rules.md) の 5、Intent の文言とパッケージの UI 文言の
置き場所は IntentTodo の `app-intents-localization`（`intent-copy` / `package-ui-copy`）が正本。ここには
**プロジェクトの設定・カタログの運用・検査**で踏んだことを置く。出典は GRAPHICA（ソース言語 ja）と
Graphica Playground（ソース言語 en、ja を後から追加）、2026-07〜10。

## プロジェクトの設定

- **`developmentRegion` と `knownRegions` をカタログの `sourceLanguage` と揃える**。カタログは ja が原文なのに
  プロジェクトが `en` / `(en, Base)` のままで、`CFBundleDevelopmentRegion` が en になり、日本語の端末でアプリが英語で開いた。
  コードは何も触っていなかった。ビルド後の `Info.plist` の `CFBundleDevelopmentRegion` と `CFBundleLocalizations` を見て確かめる `[measured]`
- これらの変更はプロジェクトファイルの変更なので Xcode で行う（外から書き換えない）
- カタログがターゲットごとに要ること（[project-skeleton.md](project-skeleton.md) の表）は、ビルドもテストも何も言わないので、
  ビルド後の `.appex` に `en.lproj/Localizable.strings` があるかを `plutil -p` で見る `[measured]`
- **ソース言語の文言は、ソース言語で書く**。ソース言語のカタログに別の言語のリテラルを書くと、その言語の訳が無いまま
  端末に出る（逆向きの漏れ）。検査も「ソース言語でない」リテラルを素通りする `[measured]`。Intent の文言での実例と、
  綴りが推測できない Intent のキーは IntentTodo の `app-intents-localization`（`intent-copy`）

## カタログの運用

- **`xcodebuild build` はカタログを書き戻さない**。`-exportLocalizations` も、別のアーキテクチャでビルドされる CLI のターゲットが
  プロジェクトにあると `Processed-Info.plist` が見つからずに落ちた（Xcode 26.6 と 27.0 で同じ）。型を直した PR で、キーを足して訳を入れるところまでやる `[measured]`
- 抽出の結果は `xcodebuild build` の `.stringsdata`（`SWIFT_EMIT_LOC_STRINGS`）で読める。これとカタログを突き合わせると漏れが 0 にできる。
  App Shortcut のフレーズの扱いは `app-intents-localization`（`siri-phrases`）
- Xcode が自動で書き出したカタログの差分は、**中身を比べてから取り込む** `[measured]`:
  - DEBUG 専用の画面や他の OS 専用の画面の文言に付く `stale` は、その構成でビルドしていないだけの誤判定
- Xcode のエディタで訳を入力して消すと `"value" : ""` が残る。**英語の端末でラベルが空欄**になる（ソース言語が出るより悪い）`[measured]`
- 同じ語が別の意味で既にキーになっているとき（メニューの動詞「生成」と設定のタブ名「生成」）は、
  `String(localized: "設定タブ「生成」", defaultValue: "生成")` で別のキーにする。同じキーだと訳が 1 つに潰れる
- `LocalizedStringKey` を受けた `Text` はインラインの Markdown を解釈する。ファイルパスなどは `String(localized:)` で訳を引いて `String` で渡す
- 単位の語をつなげて文を作らない（「1」+「month」）。1 文を 1 キーにして、数は複数形のバリエーションで扱う
- パッケージのカタログでも symbol の生成が走る。`%@` だけのような**記号だけのキー**は symbol 名を作れずビルドが落ちる。そういうキーを作らない `[measured]`
- `Bundle.module` は internal なので、public な init の既定引数に `String(localized:bundle: .module)` は書けない。optional にして本体で解決する `[measured]`

### 訳さないもの

モデル（LLM）に渡すプロンプトと、モデルに返す検証の理由文。書き出すコードとその先頭のコメント（利用者のプロジェクトに入る）。
ファイル名や型名の元になる名前（訳すと識別子にできず既定の名前に落ちる）。Codable / UserDefaults のキーと Intent の識別子。

## 検査

カタログを読むテストをパッケージに置き、`swift test` で回す（GRAPHICA の `LocalizableCatalogTests`）。落とすもの:

- ソース言語でないキーに訳が無い（空文字・空白だけも未訳。複数形のバリエーションも読む）
- 訳にソース言語の文字が残っている（日本語なら、かな・漢字に加えて約物「、。」と半角カナも）
- **書式指定子の綴り**が原文と訳で違う。個数だけ比べると `%lld` → `%@` の取り違え（整数がポインタとして読まれる）が通り、
  `%.2f` のような幅つきの指定子は数えられていなかった
- ソースのリテラル（パッケージの `String(localized:)`、ウィジェットのソース）がカタログに無い。
  Intent と Entity の文言の突き合わせは `app-intents-localization` の検査スクリプト
- パッケージの UI 文言の `bundle: .module` の書き忘れ（パッケージの文言を `LocalizedStringResource` で持ち、`locale` を変えて引くと落とせる）

検査そのものの作り方:

- **カタログを 1 か所ずつ壊して、落ちることを確かめる**。最初に書いた版は 4 つの壊し方のうち 3 つを緑のまま通していた `[measured]`
- リテラルの抜き出しは字句解析ではない。raw string や正規表現のリテラルで同期を失うと**以降を丸ごと落として緑**になる。
  拾えた件数の下限をテストで固定する（総数ではなく、実際に検査する件数に掛ける）
- `swift test` の実行プロセスに `AppleLanguages` を渡しても `Bundle.module.preferredLocalizations` は変わらなかった。
  ロケールごとの表示はアプリのテストで見る `[measured]`
- シミュレータの言語が ja だと、英語の文言を見るテストが訳を足した途端に落ちる。スキームのテスト言語と
  UI テストの起動引数で言語を固定する（[verification.md](verification.md)）
