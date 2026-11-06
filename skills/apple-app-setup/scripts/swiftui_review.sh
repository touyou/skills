#!/usr/bin/env bash
# SwiftUI の規約（references/swiftui-rules.md）に照らして、見るべき箇所の候補を並べる。
# 候補を出すだけで、合否は決めない（LocalizedStringResource を返すプロパティなど、正しいものも引っかかる）。
# 使い方: scripts/swiftui_review.sh [調べるディレクトリ ...]（省略時は .）
set -uo pipefail

roots=("$@")
[ ${#roots[@]} -eq 0 ] && roots=(.)

swift_grep() {
  grep -rnE "$@" --include='*.swift' --exclude-dir=.build --exclude-dir=DerivedData --exclude-dir=Tests --exclude-dir='*UITests' "${roots[@]}" 2>/dev/null
}

section() {
  local title="$1" rule="$2" hits
  hits=$(printf '%s\n' "$3" | grep -v '^[[:space:]]*$')
  local count=0
  [ -n "$hits" ] && count=$(printf '%s\n' "$hits" | wc -l | tr -d ' ')
  printf '\n## %s（%s 件）— %s\n' "$title" "$count" "$rule"
  [ -n "$hits" ] && printf '%s\n' "$hits"
}

echo "# SwiftUI レビューの候補: ${roots[*]}"

section "computed property のサブビュー" "1. 独立した View struct にする" \
  "$(swift_grep 'var [a-zA-Z]+: some View' | grep -v 'var body')
$(swift_grep -A1 '@ViewBuilder' | grep -E '(func|var) ' | grep -v 'var body' | grep -v 'let ')"

section "View に渡しているクロージャ" "1. クロージャは比べられないので、受け取る子は毎回描き直される。値か Environment の action にできないか" \
  "$(swift_grep '^\s+(let|var) [a-zA-Z]+: (\(@MainActor \))?\(\(?[A-Za-z.?, ]*\)?\) -> (Void|\(\))')"

section "body の中の Binding(get:set:)" "1・10. 毎回作り直される Binding。繰り返すなら Service 側に Binding を返すヘルパーを置く" \
  "$(swift_grep 'Binding\(get:|Binding\($' )"

section "SwiftUI の型と同じ名前の自前の型" "9. 名前を変える（SwiftUI.Section のように修飾し始めたら印）" \
  "$(swift_grep '(enum|struct|class|protocol|typealias|actor) (Section|Group|Label|Layout|Settings|Tab|Form|List|Text|Image|Button|Menu|Toggle|Picker|Link|Grid|Table|Alert|Gauge|Window|Scene)\b')
$(swift_grep 'SwiftUI\.(Section|Group|Label|Layout|Settings|Tab|Form|List|Text|Image|Button|Menu|Toggle|Picker|Link|Grid|Table)\b')
$(swift_grep '(struct|func) [A-Za-z]+<(Section|Group|Label|Menu|Text|Image|Button|Toggle|List|Form)\b')"

section "UI に String を渡している候補" "5. 型が String なら LocalizedStringKey / LocalizedStringResource に" \
  "$(swift_grep '(Text|Label|Button|accessibilityLabel|help|navigationTitle)\([a-z][A-Za-z]*(\.[a-z][A-Za-z]*)*[,)]' | grep -v 'format:')
$(swift_grep '\?\? "[^"]*[ぁ-んァ-ヶ一-龠]|Announcement\("')"

section "固定の文字の大きさ" "8. Dynamic Type で大きくならない。テキストスタイルか @ScaledMetric に（ウィジェットのアクセサリなど、決めて固定するものは理由をコメントに）" \
  "$(swift_grep '\.font\(\.system\(size: *[0-9]')"

section "使わない API" "6. 新しく書かない（既存の置き換えは別の PR で）" \
  "$(swift_grep 'ObservableObject|@Published|NavigationView|\.foregroundColor\(|DispatchQueue|AnyView|\.cornerRadius\(|GeometryReader')"

section "見た目は同じでも意味が違う候補" "12. その部品の役割（ボタン・一覧の行・閉じられるアラート）の型で書かれているか" \
  "$(swift_grep '\.onTapGesture|\.accessibilityAddTraits\(\.isButton\)|enumerated\(\)\), id: \\\.offset')
$(swift_grep '\.constant\(' | grep -v '#Preview\|Preview(\|_Previews')
$(swift_grep -A1 'label: \{ *$' | grep -E '^[^:]+-[0-9]+- *Image\(systemName' )"

section "システムのモディファイアに渡した長いクロージャ" "10. 画面の側は Service や package の関数へ渡すだけにする（25 行を超えるものを出す）" \
  "$(for root in "${roots[@]}"; do
      find "$root" -name '*.swift' -not -path '*/.build/*' -not -path '*/Tests/*' 2>/dev/null | while read -r file; do
        awk -v f="$file" '
          /\.(translationTask|task|fileImporter|fileExporter|onDrop|dropDestination|onOpenURL|refreshable|onSubmit)\(/ && /\{ *([a-z_]+ in)? *$/ {
            start = NR; depth = 0; text = $0
          }
          start {
            n = gsub(/\{/, "{"); m = gsub(/\}/, "}"); depth += n - m
            if (depth <= 0 && NR > start) { if (NR - start > 25) printf "%s:%d: %d 行\n", f, start, NR - start; start = 0 }
          }' "$file"
      done
    done)"

echo
echo "目で見るもの（grep では拾えない）: 構成の判定が 1 か所か（2）、ツールバーの項目にタイトルと role があるか（3）、外周の余白（4）、@Observable の作り置きの目印に入力がすべて入っているか（10）、重い一覧を body で何度も読んでいないか（1）、1 つにまとめた要素の中に VoiceOver から消えた操作が無いか（12）"
echo "computed property の候補には、View extension の @ViewBuilder func（モディファイア）やメニューの中身も出る。それらは対象外（1）"
