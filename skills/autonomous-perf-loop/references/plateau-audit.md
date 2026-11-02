# 停滞の監査と長時間の運用

8 時間まわす前提で、1 本のエージェントが息切れせずに最後まで進むための決まりごと。
ISUCON2026 で優勝した 8 時間の実行の記録（メインのエージェント 1 本、停滞したときだけ監査のサブエージェントを 2 回、
6.5 時間目にコンテキストの自動の要約が 1 回）から形にした。当日の経過は
[参加記](https://zenn.dev/luvtechno/articles/isucon2026-competition-day) にある。

## 1. 時系列を残す

計測を 1 回するたびに、`timeline.jsonl`（状態のファイルの隣）に 1 行を追記する。基準も候補も、不合格の回も残す。

```json
{"elapsed_min": 63.5, "score": 512000, "valid": true, "kind": "cand", "label": "tags に索引"}
```

`elapsed_min` はループを始めてからの分数。`kind` は周のはじめに起点を測った回が `base`、候補を測った回が `cand`。
伸びたかどうかは `base` の回だけで数える（差し戻した候補が運よく高く出た回で、停滞の時計を戻さないため）。`scripts/plateau.py timeline.jsonl --noise <ぶれの下限%>` が、
最後に点数が伸びた時刻と、その後に測った回数から停滞かを判定する（終了コード 3 = 停滞）。
停滞かどうかを自分の感覚で決めない。数え方を決めておかないと、伸びていない時間をいつまでも「あと 1 案」で延ばす。

点数の形には典型がある。最初は整合性チェックを通すまで 0 点が続き、大きなボトルネックを 1 つ外したところで
跳ね、その後は長い横ばいの中で少しずつ伸びる。横ばいに入ったこと自体は異常ではない。
横ばいのまま同じ種類の案を繰り返していることが問題なので、そこで監査を挟む。

## 2. 停滞したら監査を 1 回挟む

`plateau.py` が停滞と出したら、止める前に、別のエージェントに 1 回だけ監査させる（目安 20〜30 分）。
メインのエージェントの「もう案が無い」は、同じ視点で探し尽くしたというだけのことが多い。

渡すもの:

- 計測の手順書・ベンチのスクリプト・直近の計測の JSON（基準の 3 回）・`timeline.jsonl`
- 台帳の「試して効かなかった案」「却下した案と理由」（事実として。同じ案を出させないため）
- コードの場所と、計測環境の立ち上げ方

渡さないもの:

- 「次はこれが効きそう」「ここはもう削れない」というメインのエージェントの見立て。
  見立てを知っている監査役は、それを追認しやすい（リポジトリの AGENTS.md の原則 2）

```text
You are auditing a performance-tuning loop that has stopped improving. The score has not moved beyond
noise for <N> minutes / <M> runs. Read the bench script, the latest baseline results, and the code at
<repo>. The list of ideas already tried or rejected is in <ledger path>; do not re-propose them unless
you have new evidence that the earlier attempt was flawed (say what the flaw was).

Measure before you guess: profile the current baseline yourself (DB query plans and counts, CPU
profile, response sizes, lock/wait time, external calls), and look for where time actually goes now.
The bottleneck may have moved since the last big win. Also check whether the score is limited by the
benchmark setup itself (client concurrency, warm-up, a single-process dev server) rather than the app.

Also review the ledger's decisions against these questions, and name the ones that were skipped:
- Did any run change two things at once, so that the winning change was never isolated?
- For each tuned constant (cache TTL, delay, pool size, batch size), was only a fixed value tried,
  or also a form that follows the load or the data size?
- Is the measured gain larger than the run-to-run spread of the baseline?
- Is any debug or verification code the loop itself added still running?

Report every candidate, including low-confidence ones. For each: the evidence (numbers, file:line),
the expected effect on the score, a confidence label (high/medium/low), and whether it touches
security-sensitive areas (auth, per-user data, caching of responses). Do not modify files. Keep it concise.
```

戻ってきた案は全部読み、台帳の「次の周の候補」に確度の順で並べる。確度の低い案も消さない。
監査の案は仮説であって、採用の近道ではない。ふだんの周と同じく 1 つずつ測って採否を決める
（上の記録でも、監査の案の大半は点数を下げ、効いたのは「固定の値と、負荷に応じて変わる値を比べたか」という問いから出た 1 つだった）。
監査の後に 2 周続けて採用できる案が無ければ、そこで止めて人に返す（SKILL.md の Step 6）。
監査は 1 回の停滞につき 1 回まで。監査したときに `plateau.py` が出した「最後の更新」の時刻を状態に書いておき、
その時刻が変わらないまま停滞と出ても、監査はやり直さない（止めどきの数え方に進む）。点数が伸びて時刻が変わった後の
停滞では、もう 1 回挟んでよい。監査を重ねるほど同じ案が戻ってくる。

上の記録では、30 分以上点数が伸びないと Claude Code の hook が監査を促していた。hook に `plateau.py` を呼ばせると、
数えるのも促すのも人の注意に頼らずに済む。どちらにしても、促された後に監査するかは状態のファイルの「最後の更新」で決める。

## 3. メインのエージェントは 1 本で走らせる

上の記録では、探索を並列にしたり複数の案を同時に走らせたりせず、メインのエージェント 1 本で 8 時間まわした。
サブエージェントを使ったのは停滞の監査の 2 回だけで、費用の 8 割以上はメインのエージェントだった。

- 1 周で変えるのは 1 つ、という決まりと、並列の探索は相性が悪い（計測のマシンを取り合って数字も荒れる）
- サブエージェントを使うのは、独立した視点が要るところだけにする: 停滞の監査、整合性チェックのレビュー
  （bench-harness.md の 7 節）、セキュリティだけのレビュー（security-gates.md）

## 4. コンテキストを長持ちさせる

上の記録では、メインのエージェントのコンテキストが 6 時間かけて約 97 万トークンまで積み上がり、
そこで自動の要約が入って 2 万トークン強に縮んだ。要約の後もスコアは落ちずに続いた。
要約で消えて困るものを、先にファイルへ出しておいたかどうかで差が出る。

- **計測の出力を会話に流さない**。ベンチのログや JSON はファイルに書き、会話には `compare.py` と
  `plateau.py` の要約だけを出す。1 回の計測が数千トークンでも、80 回まわせば数十万トークンになる
- **プロファイルや実行計画も、必要な行だけを読む**。全文を読むのは、どこを見るか決まっていないときだけ
- **台帳の状態は周ごとに上書きする**（ledger-template.md）。要約がいつ入っても、状態と `timeline.jsonl` を
  読めば続きから始められるようにしておく
- **要約が入ったと気づいたら**（直前の作業の細部を覚えていない、会話の先頭が要約になっている）、
  まず状態のファイルと直近の周の記録、`plateau.py` の出力を読んでから次の手を決める。記憶で続けない

## 5. 終わる前に、作り直した環境で測る

最後の採用から終わりまでの間に、サーバー・DB・キャッシュを止めて立ち上げ直し、起点のコードで 3 回測る。
長く動かしたサーバーや温まったキャッシュでだけ出る点数は、人に渡した後に再現しない。
点数が `compare.py` でぶれの範囲を外れて下がったら、その差を人に伝える（どの採用が温まった状態に頼っていたかを
台帳から当たりを付ける）。終わりの直前に大きな変更を入れない。最後の 1 周は、この確認の時間を残して締める。

あわせて次を確かめる（上の記録では、終わりの 30 分前に hook がこの確認を促していた）:

- **再起動の後に、手作業なしで戻るか**。サーバーやプロセスを止めて立ち上げ直し、起動の手順を踏まずに動くか。
  順序に依存がある構成（DB とアプリなど）は、立ち上げる順序を変えても戻るか
- **再起動の前に書いたデータが読めるか**。メモリに寄せた変更は、ここで消えることがある
- **主な操作を手で通す**。ブラウザやアプリで、ログイン・投稿・一覧など、点数に入っている操作を 1 回ずつ
- **ループが動かしていたものを止める**。計測の定期実行・自動の更新・裏で動かしたサーバー。止めたことを状態に書き、
  人に返した後はコードにも環境にも触らない

## 6. ぶれが効果より大きくなったら

横ばいに入ると、1 つの案の効果が数 % になり、同じコードを測り直したときのぶれのほうが大きくなる。
上の記録では、同じ構成の 12 回の点数が 47.5 万〜63.0 万に散らばり、終盤に試した案どうしの差よりも大きかった。
この状態で 3 回ずつの比較を続けると、運よく高く出た回を「効いた」と読む。

- 停滞したら、起点を多めに（例: 8〜10 回）測ってぶれの幅を出し直し、`--noise` の値をそれに合わせる
- その幅より小さい効果は、点数では採否を決めない。回数を増やして測るか、補助の指標（クエリ数・CPU 時間など、
  ぶれの小さい数）で決める。どちらでも決まらなければ、変更は入れない（入れても効いたかが分からない）
- 2 つの変更を同じ回で入れると、ぶれの中でどちらが効いたかは二度と分からない。終盤ほど 1 周 1 つを守る
