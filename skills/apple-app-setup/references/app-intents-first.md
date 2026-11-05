# App Intents を先に設計する

新規アプリでは「画面 → あとから Intent」ではなく、**「できること（Intent）→ それを呼ぶ画面」**の順に作る。
アプリ内のボタン、Siri、ショートカット、ウィジェット、コントロール、Spotlight が同じ定義を呼ぶので、
面を足すたびにロジックを複製せずに済む。設計の正本は `app-intents-centric-design`（11 ルール）。

## 立ち上げ時にやること

1. `app-intents-design-session` で、1 文の構想から Intent と Entity の一覧を作る
2. 一覧の各行に「どの面に出すか」「アプリを前面に出すか（`supportedModes`）」「書き込むか」を付ける
3. 書き込む Intent と App Shortcut に登録する Intent は `allowedExecutionTargets = [.main]`（27.0+）`[Apple]`
4. 最初のコミットに入れるのは 2〜3 個（開く・数を聞く・1 つ操作する）。残りは issue にする
5. `audit_intents.py --fail-on error` が通る状態を保つ

## 最初から守ること（IntentTodo の AGENTS.md より）

- アクションは Intent として定義し、UI からも `Button(intent:)` で実行する
- `requestConfirmation` / `requestChoice` を含む Intent をアプリ内の `Button(intent:)` から呼ばない（何も起きない）
- `parameterSummary` は Shortcuts の編集画面の allowlist。載せないパラメータは編集できない
- **公開した Intent のパラメータ名と型は変えない**（保存済みのショートカットが外れる）。最初の名前を丁寧に決める
- App Shortcut に登録した Intent の `@Parameter` に system value 型（`PlaceDescriptor` など）を置かない。
  27.1 までのツールチェーンで Siri のフレーズ学習が丸ごと消える不具合があった（27.2 で修正。配信ビルドの Xcode が 27.2 以上か確かめてから外す）`[measured]`
- App Schema に適合させる型は watchOS 向けに別の型名にする（同じ名前だとメタデータが上書きされる）`[measured]`
- 確認はビルドの成否ではなく、生成されたメタデータで行う。それもクリーンビルドで

## 実地の補足（チェケラ、2026-10）

- `AppDependencyManager.shared.add(dependency:)` の引数は escaping で nonisolated の autoclosure。`App.init()` で
  `self.container` を渡すと self を捕まえてビルドエラーになる。ローカル変数に入れてから渡す `[measured]`（2026-10、Xcode 27.x）
- 依存の登録は `App.init()` で同期的に済ませる（置き場所は [project-skeleton.md](project-skeleton.md)）。背面の Intent はシーンを出さずにプロセスを起こすので、
  `onAppear` や `.task` での登録では間に合わない `[inferred]`
- Entity の `DisplayRepresentation` にユーザーが付けた名前を出すときは `"\(name)"` の補間で書く。
  `LocalizedStringResource(stringLiteral: name)` にすると、ユーザーの文字列がローカライズのキーとして扱われる
- 表示名が英字で、話すときは別の名前で呼ばれるアプリ（Checkitout →「チェケラ」）は、Info.plist の `INAlternativeAppNames`
  に別名と読み（`INAlternativeAppNamePronunciationHint`）を入れる。別名で呼ばれたときに Siri がアプリを特定できるようにするため `[Apple]`
- パラメータ付きのフレーズは、起動時と Entity の集合が変わったとき（音を足す・消す）に
  `updateAppShortcutParameters()` を呼ぶ。呼ばないと、Entity を一度取得するまでそのフレーズが出ない `[Apple]`
- `AppShortcuts.xcstrings` は App Shortcut 1 つにつき 1 キーで、値は言語ごとの `stringSet`（フレーズの配列）。
  言語ごとにフレーズの数が違ってよい（チェケラは en 3 本、ja 5 本）。フレーズを足すときは配列に足し、キーを増やさない
- Entity の `suggestedEntities()` の順番は、Siri が話された名前を照合する候補の順でもある。よく使うもの（パッドに割り当て済みの音）を先にする `[inferred]`

## Siri のモデル連携（27.3 以降）

27.3 の Siri AI Developer Preview で、スキーマに当てはまらない Intent も `@AppIntent(.tool)` で
Siri のツールにできるようになった `[Apple]`。プレビュー期間は開発署名と内部 TestFlight でしか動かない。

立ち上げ時にやっておくこと:

- Intent と `@Parameter` の `title` / `description` を、モデルが読んでも分かる文にしておく（あとで `.tool` を付けるときにそのまま効く）
- Entity の `@Property` にも説明を付けられるようにしておく。ただし `@Property(description:)` は
  最低 OS が 27.3 未満だとビルドエラーになるので、最低 OS を 27.3 に上げるまでは付けない `[measured]`
- Siri 対応ドメインのスキーマに適合させた Intent に `.tool` を付けるとビルドエラー `[Apple]`
- `.tool` の採用は、最低 OS が 27.3 未満の間はブランチで進め、GA と Xcode Cloud の対応を待ってマージする

正本は Apple の `siri-app-integration` と `siri-evaluations`。

## UI との接続で迷ったら

`app-intents-ui-and-feedback`（ボタン・確認・遷移・スニペット）と
`app-intents-system-surfaces`（どの面に出すか）。
