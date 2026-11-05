# App Intents を先に設計する

App Intents 中心設計の正本は **IntentTodo の skills**（`touyou/IntentTodo` の `skills/`、9 本）。
ルール・API の罠・実地の知見はすべてそちらに置き、ここには**新規の立ち上げで、どの順にどれを読むか**だけを書く。
ここで気づいた App Intents の知見は、このファイルではなく IntentTodo の skills に足す。

## 立ち上げでの順番

| 順 | やること | 読む skill |
|---|---|---|
| 1 | 1 文の構想から、Intent と Entity の一覧を作る（`docs/PLAN.md` の中心に置く） | `app-intents-design-session` |
| 2 | 小さい面から外へ、どの Intent をどの面に出すか決める | `app-intents-system-surfaces` |
| 3 | 11 ルールに照らして置き場所と形を決める | `app-intents-centric-design`（入口。迷ったらここ） |
| 4 | Service と Intent / Entity / Query をテスト付きで実装する（最初の機能 PR） | `app-intents-entities-and-search` / `app-intents-parameters-and-prompts` / `app-intents-execution-and-processes` / `app-intents-testing` |
| 5 | ウィジェット・コントロール・App Shortcut を載せる | `app-intents-system-surfaces` / `app-intents-execution-and-processes` |
| 6 | アプリの画面を、同じ Intent を呼ぶ形で最後に組む | `app-intents-ui-and-feedback` |
| 7 | 文言・Siri のフレーズを全言語で埋める | `app-intents-localization` |

- 最初のコミット（ひな形）に入っている Intent は、置き換える前提のサンプル 2 つ（足す・数を聞く）
- `app-intents-centric-design/scripts/audit_intents.py --fail-on error` が通る状態を保つ

## Siri のモデル連携（27.3 以降）

`@AppIntent(.tool)` などの Siri AI Developer Preview は、Apple の `siri-app-integration` / `siri-evaluations` が正本。
IntentTodo での採用と知見は `feature/siri-ai-tools` ブランチにあり、27.3 の正式版のあとで main に入る。
立ち上げ時は、Intent と `@Parameter` の `title` / `description` をモデルが読んでも分かる文にしておくだけでよい。
