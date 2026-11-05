# 要件

## 一文で

__ONE_LINER__

## できること（Intent の一覧）

この表が仕様の中心。画面はここにある Intent を `Button(intent:)` で呼ぶ形で作る。

| Intent | 何をする | 面 | 書き込む | 前面に出す |
|---|---|---|---|---|
| `AddItemIntent` | 項目を足す | ショートカット・Siri・アプリ内 | ○ | — |
| `GetItemCountIntent` | 件数を答える | Siri | — | — |

## 決めたこと

| 項目 | 決定 | 理由 |
|---|---|---|
| 対象 OS | __PLATFORMS_TEXT__ __MIN_OS__+ | |
| データの置き場所 | 端末内（App Group の JSON） | |
| 届けるシステムの面 | ショートカット・Siri⟪widget⟫・ウィジェット⟪/widget⟫ | |
| 画面の形が変わるとき | 1 カラム基本、regular かつ横長だけ左右分割 | |
