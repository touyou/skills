---
name: store-screenshot-composer
description: App Store / Google Play 用のスクリーンショット画像を作る。撮影済みの素のスクリーンショットに見出し・背景・端末の枠を付けて JSON 設定から一括生成するか、Web ページに横長の 1 枚絵として描いてブラウザで撮り、1 枚ずつに切り分ける。「ストア画像を作って」「スクショに見出しを付けて」「App Store のスクリーンショットを工夫したい」「スクショを撮り直したのでストア画像も作り直して」に使う。
license: MIT
metadata:
  author: touyou
  version: "0.4.0"
---

# store-screenshot-composer

アプリの画面を撮る工程（XCUITest / `simctl io screenshot` / adb など）と、ストアに載せる画像に仕上げる工程を分ける。仕上げは JSON 設定（`scripts/compose.py`）か Web ページ（`scripts/capture_web.py`）から決定論的に作るので、撮り直しや文言の変更はコマンド 1 回で全ロケールに反映できる。Illustrator や Figma の手作業を挟まない。

必要なのは Python 3 と Pillow（`python3 -m pip install pillow`）だけ。Mac 以外で動かすときは先に `scripts/fetch_fonts.sh` で Noto Sans JP を入れる（入れないと太字の無い書体で代用して見え方が変わる）。

## 2 つの作り方

| 作り方 | 向いているとき | 道具 |
|---|---|---|
| **Web で描いて切る** | LP や紹介ページがあり、その部品（描き直した UI・吹き出し・ウィジェット）で絵を作りたい。部品を画像の境目をまたいで置きたい | `scripts/capture_web.py` |
| **素のスクショに枠と見出しを付ける** | 実機の画面をそのまま見せたい。ページを作る手間をかけたくない | `scripts/compose.py` |

touyou のアプリで紹介ページ（touyou.dev）があるものは Web のほうを選ぶ。紹介ページと同じ部品・書体・色になり、見た目を合わせ直す手間がない。

## Web で描いて切る

1. **横長の 1 枚絵のページを作る**。画像 1 枚ぶんを CSS の寸法で決め（iPhone 6.9" なら 440×956 を 3 倍、iPad 13" なら 1032×1376 を 2 倍）、その N 枚ぶんの幅の要素を左上に置く。部品は帯の左端からの位置で絶対配置するので、境目をまたいで置ける。紹介ページの部品は、表示だけの部品（状態を props で受ける）に切り出して両方から使う
2. ページはアニメーションと遷移を止め、開発サーバーのインジケータを隠す。本番では開けないようにする（`notFound()`）
3. **撮って切る**: `python3 <このスキルのフォルダ>/scripts/capture_web.py <URL> --frame 440x956 --count 6 --scale 3 --out <出力先>`。Chrome（無ければ Chromium）を headless で動かし、RGB の PNG を `01.png` から書き出す。`_overview.png` は切る前の 1 枚絵
4. 境目に部品の切れ端が数ピクセルだけ残っていないか、1 枚ずつ並べて見る。またがせるなら半分くらい大きく、またがせないなら境目から離す
5. 実例は touyou.github.io の `src/app/store/intento/`（`scripts/store-screenshots.sh` で撮る）

## 素のスクショに枠と見出しを付ける

1. **素のスクショの置き場を確かめる**。撮影スクリプトがあるリポジトリ（例: `scripts/capture_screenshots.sh` の出力 `Screenshots/<platform>/<locale>/`）はそれを使う。無ければ先に撮影を用意する（このスキルの範囲外）
2. **設定ファイルを書く**。リポジトリの `scripts/store_frames.json` などに置き、パスはその設定ファイルからの相対で書く。雛形は [examples/store_frames.json](examples/store_frames.json)、全項目は [references/config.md](references/config.md)
3. **見出しを決める**。1 枚 1 メッセージ。画面の説明（「一覧画面」）ではなく、使う人が得るもの（「話しかけるだけで片づく」）を書く。ストアの説明文・プロモーションテキストから拾うと文言がぶれない。ja は 14 字前後、en は 5 語前後に収まると 2 行に入る
4. **レイアウトだけ先に確認する**: `python3 <このスキルのフォルダ>/scripts/compose.py <config> --placeholder --sheet`。素のスクショが無くても枠と文字の収まりが見られる。スクリプトはアプリのリポジトリにコピーせず、このスキルの中のものを呼ぶ
5. **本番を作る**: `python3 <このスキルのフォルダ>/scripts/compose.py <config> --sheet`。各出力フォルダの `_overview.png` で並びを確認し、ユーザーに見せる
6. `output` には gitignore 済みの場所を指定する（無ければ `.gitignore` に足す。素のスクショと同じ扱い）。設定ファイルだけをコミットする

ストアへのアップロード（`asc screenshots upload` など）と審査提出はユーザーの OK を取ってから。

## touyou のアプリなら touyou.dev の型に合わせる

touyou の個人アプリは、ポートフォリオの紹介ページと OG 画像で見た目の型（左上にアイコンとアプリ名、太い黒の見出しを句点まで、ほぼ白かほぼ黒の背景に 1 色だけ差す、柔らかい影）がそろっている。`"theme": "light"`（または `"dark"`）+ `"align": "left"` + `"eyebrow"` でこの型になる。アプリごとの配色と設定例は [references/touyou-house-style.md](references/touyou-house-style.md)。

## 工夫の引き出し

設定で切り替えられる表現。1 セットの中で全部を使わず、2〜3 種類に絞ると統一感が出る。

| 表現 | 設定 | 向いている画面 |
|---|---|---|
| 見出し + 端末（基本） | `caption: "top"` | ほぼ全部 |
| 端末を下にはみ出させる | `device_width` を大きく / `device_offset` | 縦に長い一覧。上半分が見えれば伝わる画面 |
| 見出しを下に置く | `caption: "bottom"` | 画面の上部が主役の画面 |
| 端末の枠 | `bezel` | 画面が白っぽく背景と溶けるとき |
| 背景の光 | `background.glow` | 単色・グラデーションが平板に見えるとき |

### 絵に動きを出す

ストアでは画像が横に並び、横にスクロールして見られる。並びを 1 枚の絵として作ると、止まった画像でも流れが出る。`panorama: true` のセットではセット全体を横長の 1 枚に描いてから切り分けるので、下の表現が画像をまたいでつながる。

| 表現 | 設定 | 効き方 |
|---|---|---|
| 流れる帯 | `background.ribbons` | 波打つ色の帯が全部の画像を貫く。視線が右へ流れる。差し色を薄く |
| 画像をまたぐ端末 | `device_x: 0.98` + `tilt` | 端末が次の画像に半分はみ出し、「続きがある」と感じさせる。次の画像は `device_x` を右へ寄せて重ねるか、`device: false` で場所を譲る |
| 傾き | `tilt: -7`〜`4` | まっすぐな端末の間に 1〜2 枚。向きを交互に変えるとリズムが出る |
| 飛び出すカード | `callout` + `callout.tilt` | 画面の一部を拡大して、端末から浮かせる。端末と逆向きに傾けると立体感が出る |
| 左右にずらす | `device_x: 0.56` など | 見出しが左揃えのとき、端末を少し右へ寄せると対角線ができる |

1 枚目（表紙）と最後の 1 枚は落ち着かせ、間で動かすとまとまる。アプリのアイコンとアプリ名は 1 枚目だけに出る（`eyebrow_scope`）。実例は IntentTodo の `scripts/store_frames.json`。

## 落とし穴

- **ASC はアルファ付き PNG を受け付けない**。スクリプトは RGB で書き出す
- **寸法は ASC の枠ごとに固定**。`preset` を使うと受け付けられる寸法になる（一覧は config.md）。キャンバスと素のスクショの寸法は一致しなくてよい（端末は `device_width` で縮める）
- **書体は環境で変わる**。macOS ではヒラギノ（W6 / W3）、それ以外では `fetch_fonts.sh` で入れた Noto Sans JP（700 / 400）を使う。どちらも touyou.dev の LP がその環境で使う書体。何も見つからないと太字の無い書体を縁取りで太らせて代用するので、見本にしか使わない。別の書体は `fonts` で明示する（可変フォントは `{"path": ..., "weight": 800}`）
- **`panorama` で画像をまたがせたら、端に細く切れ端が残っていないか `_overview.png` で見る**。傾けた端末の角や影だけが隣に数ピクセル入ると汚れに見える
- **iPad と iPhone で同じ見出しを使うと iPad で文字が小さく見える**ことがある。`sets[].style.title_size` で上書きする
- 価格・日付・個人名が写る画面は、撮影側のフィクスチャで実際の値に揃えておく（ストアの価格とずれた画像は審査で引っかかる）
