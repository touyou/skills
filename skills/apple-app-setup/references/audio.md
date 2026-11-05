# 音を鳴らすアプリ（AVAudioEngine）

手続き合成の BGM を `AVAudioEngine` で鳴らすアプリ（月屏風）で、実機で鳴らなかったこと。

- **形式はセッションのサンプルレートに合わせる**。`AVAudioUnitReverb` はレートを変換しないので、形式を省くと既定の 44.1kHz になり、
  48kHz の実機で `engine.start()` が `-10868` で失敗した `[measured]`（2026-10、実機）。セッションを有効にしたあとの
  `AVAudioSession.sharedInstance().sampleRate`（取れなければ `outputNode` の形式）で作る
- リバーブはモノラル入力を受け付けない（`-10868`）。2ch で作る
- `setActive(true)` はメインスレッドを塞ぐので裏のスレッド（`Task.detached`）で呼ぶ。非同期の `activate` は
  実機で鳴らなかった原因の候補なので使わず、実績のある同期の `setActive` を裏で呼ぶ形に戻した
- 鳴らし直すたびにセッションを落とさない。毎回 deactivate すると経路の変化が通知され、再起動が連鎖しうる
- 失敗したら、エンジンから組み直す（古いノードを残さない）。どの段階（session / configure / start）と形式で止まったかを
  隠した開発用パネルに出すと、実機で Console なしに原因が見える
- 利用者が自分でオンにした音なら `.playback` + `.mixWithOthers`（消音スイッチで止めない、他アプリの音と混ぜる）。既定はオフにする
