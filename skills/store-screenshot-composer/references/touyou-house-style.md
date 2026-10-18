# touyou.dev に合わせたストア画像

touyou の個人アプリは、ポートフォリオ（touyou.dev）の各アプリ紹介ページと OG 画像（`touyou.github.io/public/og/*.png`）で見た目の型がそろっている。ストア画像もこの型に寄せると、LP からストアへ移ったときに同じアプリに見える。

## 型

OG 画像から読み取ったもの。`theme` と `align: "left"` と `eyebrow` でこの型になる。

- **左上にアイコンとアプリ名**。名前はグレー（`#6E6E73`）で控えめに
- **見出しは太く、黒（`#1D1D1F`）、2 行で句点まで**。「アプリを開かなくても使える、やることリスト。」「すべての音が、楽器になる。」のように言い切る。読点で改行する
- **補足は 1 行、グレーで小さく**（対応端末や数字）
- **背景はほぼ白かほぼ黒**。色はアプリごとに 1 色だけ差す（下表）
- **画面は柔らかく大きい影で浮かせる**。端末の枠は付けない。白い画面には細い縁取り
- 傾けるのは 1 セットに 1 枚まで（OG の Intento は浮いた UI を少し傾けている）

文言は LP の見出し・App Store の説明文の小見出しから取る。LP とストアで言い回しを変えない。

## アプリごとの配色

OG 画像と LP のトップのカルーセル（`src/components/home/AppCarousel.tsx`）から拾った値。

| アプリ | theme | 背景 | 差し色 | 備考 |
|---|---|---|---|---|
| Intento | light | `#FBFBFD` → `#EDEDF2` | `#0A84FF`（システムの青） | 設定例: IntentTodo の `scripts/store_frames.json` |
| Toreta | light | `#FFFFFF` → `#EFF3FC`（青みの白） | `#447BF4` / カードの `#3E8FC0` `#D85D93` `#DC9128` | カルーセルは `#5A8BF8` → `#2C5FE0` |
| チェケラ（CheckItOut） | dark | `#16171A` → `#0B0B0B` | パッドの 4 色 `#E63C35` `#FAC700` `#67B62D` `#009BDB` | 画面が横向きなら `rotate_input` |
| FFMultiplier | 単色 | `#85BF5D` | 7 セグの `#9BE06A` | 文字は `#1D1D1F` のまま |
| Programming Quiz | light | `#F2F2F7` | 正解の緑 `#34C759` | |
| GRAPHICA | dark | `#06060A` | `#D9FF4D` | LP は graphica.touyou.dev |
| Graphica Playground | dark | `#16171A` → `#0B0C0E` | `#67DABD` / `#C792EA` | |

差し色は背景に塗らず、`background.glow` の色や拡大カードの `border` に少しだけ使う。

```jsonc
// チェケラ
"style": {
  "theme": "dark",
  "align": "left",
  "background": { "type": "gradient", "colors": ["#16171A", "#0B0B0B"], "angle": 165,
                  "glow": { "color": "#009BDB", "opacity": 0.18, "y": 0.7 } },
  "eyebrow": { "icon": "icon.png", "name": { "ja": "チェケラ", "en": "CheckItOut" }, "color": "#A1A1A6" }
}
```

## 書体

LP は `-apple-system, Hiragino Sans, Noto Sans JP` の順。Mac で動かせば既定でヒラギノ（見出しは W7）になり、LP と同じに見える。見出しには `palt`（詰め組み）を掛ける（Pillow が libraqm 付きのとき）。
