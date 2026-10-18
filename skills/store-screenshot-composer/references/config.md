# 設定ファイルの全項目

`compose.py` が読む JSON。パスはすべて**設定ファイルのあるフォルダからの相対**。

```jsonc
{
  "locales": ["ja", "en"],          // --locale で絞れる
  "fonts": {                        // 省略可。macOS はヒラギノ、Linux は Noto CJK / IPA を探す
    "bold": "/path/to/Bold.ttf",
    "regular": "/path/to/Regular.ttf",
    "en": { "bold": "...", "regular": "..." }   // ロケール別に上書き
  },
  "style": { ... },                 // 全セット共通のスタイル（下表）
  "sets": [
    {
      "name": "iphone",             // --set で絞れる
      "preset": "iphone-6.9",       // または "size": [1320, 2868]
      "input": "../Screenshots/iphone/{locale}",
      "output": "../StoreImages/iphone/{locale}",
      "style": { ... },             // このセットだけの上書き
      "shots": [
        {
          "file": "01-list.png",    // input フォルダ内のファイル名
          "output": "01-list.png",  // 省略時は file と同じ
          "title": { "ja": "…", "en": "…" },       // 文字列 1 つでも可
          "subtitle": { "ja": "…", "en": "…" },    // 省略可
          "style": { ... }          // この 1 枚だけの上書き
        }
      ]
    }
  ]
}
```

スタイルは `既定値 ← theme ← style ← sets[].style ← shots[].style` の順で上書きされる。

見出しに `\n` を入れるとその位置で必ず改行し、行の中では折り返さない（収まらなければ文字が縮む）。日本語は文節の切れ目に `\n` を入れておくのが確実。

見出しの位置が `top` のとき、アプリ名と見出しはどの画像でも同じ高さから始まり、見出しが長いときは端末のほうが下がる。

## スタイル

| キー | 既定値 | 意味 |
|---|---|---|
| `theme` | なし | `light` / `dark`。touyou.dev の LP・OG 画像と同じ配色（背景・文字色・影・縁取り）を一式で入れる。個別のキーで上書きできる。中身は [touyou-house-style.md](touyou-house-style.md) |
| `align` | `center` | 見出しの揃え。`left` で OG 画像と同じ左揃え |
| `eyebrow` | なし | 見出しの上に出すアイコンとアプリ名。`{"icon":"path.png","name":"Intento","color":"#6E6E73"}`。`name` はロケール別の辞書でもよい |
| `eyebrow_size` | `0.042` | アプリ名の文字サイズ（キャンバス幅比）。アイコンはその 2 倍角 |
| `outline` | なし（`light` では `#00000014`） | 画面のまわりの細い縁取り。白い画面が明るい背景に溶けるのを防ぐ |
| `background` | `{"type":"solid","color":"#1C1C1E"}` | 下の「背景」 |
| `panorama` | `false` | セット全体で 1 枚の背景を作って横に切り分ける。並べると 1 枚の絵につながる。セットの `style` に書く |
| `text_color` | `#FFFFFF` | 見出しの色 |
| `subtitle_color` | 見出しの色の 75% | 補足の色 |
| `caption` | `top` | 見出しの位置。`top` / `bottom` |
| `caption_height` | `0.22` | 見出しの帯の高さ（キャンバス高さ比） |
| `title_size` | `0.075` | 見出しの最大文字サイズ（キャンバス幅比）。収まらなければ自動で縮む |
| `subtitle_size` | `0.038` | 補足の最大文字サイズ |
| `max_title_lines` | `2` | 見出しの最大行数。`\n` で明示改行もできる |
| `device_width` | `0.80` | 画面（枠を除く）の幅（キャンバス幅比）。大きくすると下にはみ出す |
| `device_offset` | `0` | 端末の上下位置の追加ずらし（キャンバス高さ比、+ で下） |
| `corner_radius` | `0.11` | 画面の角丸（画面幅比）。iPhone の実機に近い値 |
| `bezel` | なし | 端末の枠。`{"width":0.035,"color":"#0A0A0A","edge":"#4A4A4E"}`。`edge` は外周の縁取り |
| `shadow` | `{"blur":0.03,"opacity":0.45,"offset":0.012}` | 端末の影。`null` で消す |
| `tilt` | `0` | 端末の傾き（度、反時計回りが正） |
| `rotate_input` | `0` | 素のスクショを回してから使う（90 / 180 / 270、時計回り） |
| `callout` | なし | 下の「拡大カード」 |

## 背景

```jsonc
{"type": "solid", "color": "#1C1C1E"}
{"type": "gradient", "colors": ["#2B1055", "#7597DE"], "angle": 160}   // CSS と同じ向き。180 = 上→下
{"type": "image", "path": "assets/bg.jpg", "dim": 0.35}               // cover で敷き、dim で暗くする
```

どれにも `"glow": {"color": "#FFFFFF", "opacity": 0.25, "x": 0.5, "y": 0.62, "radius": 0.45}` を足せる（端末の後ろのぼかした光）。

## 拡大カード

```jsonc
"callout": {
  "box": [0.0, 0.30, 1.0, 0.25],  // 素のスクショのどこを切り出すか（x, y, 幅, 高さ。すべて比率）
  "width": 0.9,                   // カードの幅（キャンバス幅比）
  "x": 0.5, "y": 0.45,            // カードの中心（キャンバス比）
  "corner_radius": 0.05,
  "border": "#FFFFFF"             // 省略可
}
```

## preset

| preset | 寸法 | ASC / Play の枠 |
|---|---|---|
| `iphone-6.9` | 1320x2868 | iPhone 6.9"（これ 1 つで小さい iPhone にも流用される） |
| `iphone-6.5` | 1284x2778 | iPhone 6.5" |
| `iphone-6.3` | 1206x2622 | iPhone 6.3" |
| `iphone-5.5` | 1242x2208 | iPhone 5.5" |
| `ipad-13` | 2064x2752 | iPad 13" |
| `ipad-12.9` | 2048x2732 | iPad 12.9" |
| `mac` | 2880x1800 | Mac |
| `vision` | 3840x2160 | Apple Vision Pro |
| `watch-ultra` | 422x514 | Apple Watch Ultra |
| `play-phone` | 1080x1920 | Google Play スマートフォン（9:16） |

横向きにしたいときは `"size": [2868, 1320]` のように直接書く。

## コマンド

```bash
python3 compose.py store_frames.json                    # 全ロケール・全セット
python3 compose.py store_frames.json --locale ja        # ロケールを絞る（複数回指定可）
python3 compose.py store_frames.json --set iphone       # セットを絞る（複数回指定可）
python3 compose.py store_frames.json --sheet            # 出力フォルダに _overview.png も書く
python3 compose.py store_frames.json --placeholder      # 素のスクショ無しで配置だけ確かめる
```

素のスクショが欠けていると、作れた分を書き出したうえで欠けたパスを列挙して終了コード 1 で終わる。
