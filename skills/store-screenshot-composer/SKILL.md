---
name: store-screenshot-composer
description: 撮影済みの素のスクリーンショットから、見出し・背景・端末の枠・拡大カードを付けた App Store / Google Play 用の画像を JSON 設定 1 枚で一括生成する。「ストア画像を作って」「スクショに見出しを付けて」「App Store のスクリーンショットを工夫したい」「スクショを撮り直したのでストア画像も作り直して」に使う。
license: MIT
metadata:
  author: touyou
  version: "0.2.0"
---

# store-screenshot-composer

アプリの画面を撮る工程（XCUITest / `simctl io screenshot` / adb など）と、ストアに載せる画像に仕上げる工程を分ける。仕上げは `scripts/compose.py` が JSON 設定から決定論的に作るので、画面を撮り直したらコマンド 1 回で全ロケール・全サイズが作り直せる。Illustrator や Figma の手作業を挟まない。

必要なのは Python 3 と Pillow（`python3 -m pip install pillow`）だけ。

## 手順

1. **素のスクショの置き場を確かめる**。撮影スクリプトがあるリポジトリ（例: `scripts/capture_screenshots.sh` の出力 `Screenshots/<platform>/<locale>/`）はそれを使う。無ければ先に撮影を用意する（このスキルの範囲外）
2. **設定ファイルを書く**。リポジトリの `scripts/store_frames.json` などに置き、パスはその設定ファイルからの相対で書く。雛形は [examples/store_frames.json](examples/store_frames.json)、全項目は [references/config.md](references/config.md)
3. **見出しを決める**。1 枚 1 メッセージ。画面の説明（「一覧画面」）ではなく、使う人が得るもの（「話しかけるだけで片づく」）を書く。ストアの説明文・プロモーションテキストから拾うと文言がぶれない。ja は 14 字前後、en は 5 語前後に収まると 2 行に入る
4. **レイアウトだけ先に確認する**: `python3 scripts/compose.py <config> --placeholder --sheet`。素のスクショが無くても枠と文字の収まりが見られる
5. **本番を作る**: `python3 scripts/compose.py <config> --sheet`。各出力フォルダの `_overview.png` で並びを確認し、ユーザーに見せる
6. 出力は既定で gitignore 済みの場所に置く（素のスクショと同じ扱い）。設定ファイルだけをコミットする

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
| 傾ける | `tilt: -6` など | 1 セットに 1 枚までのアクセント |
| 一部を拡大したカード | `callout` | 小さく写る肝心の UI（ウィジェット、ボタン、グラフ） |
| 横につながる背景 | `panorama: true` | ストアで横スクロールしたときに 1 枚の絵に見せたいとき |
| 端末の枠 | `bezel` | 画面が白っぽく背景と溶けるとき |
| 背景の光 | `background.glow` | 単色・グラデーションが平板に見えるとき |

## 落とし穴

- **ASC はアルファ付き PNG を受け付けない**。スクリプトは RGB で書き出す
- **寸法は ASC の枠ごとに固定**。`preset` を使うと受け付けられる寸法になる（一覧は config.md）。キャンバスと素のスクショの寸法は一致しなくてよい（端末は `device_width` で縮める）
- **日本語フォントは環境で変わる**。macOS ではヒラギノを自動で使う。Linux や別の書体にしたいときは `fonts` で明示する。ロケールごとに書体を変えるときは `fonts.<locale>`
- **iPad と iPhone で同じ見出しを使うと iPad で文字が小さく見える**ことがある。`sets[].style.title_size` で上書きする
- 価格・日付・個人名が写る画面は、撮影側のフィクスチャで実際の値に揃えておく（ストアの価格とずれた画像は審査で引っかかる）
