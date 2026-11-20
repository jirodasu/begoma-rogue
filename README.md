# begoma-rogue

ベゴマ・ローグ（仮）— モンスターをコマ型の乗り物「ベゴマ」に乗せて戦う、3対3勝ち抜きのローグライク（Pyxel試作）。

## 遊ぶ

- ブラウザ（iPhone可・仮想ゲームパッド付き）:
  https://kitao.github.io/pyxel/wasm/launcher/?run=jirodasu.begoma-rogue.begoma_rogue&gamepad=enabled
- PC: `pip install -U pyxel` → `python begoma_rogue.py`
  - 日本語表示: `umplus_j10r.bdf`（Pyxelのサンプル同梱フォント）を同じフォルダに置く。無ければ英語表示

## 操作

| 操作 | キー | ゲームパッド |
|---|---|---|
| 加速 | 方向キー / WASD | 十字 |
| ブレーキ | X / Shift | B |
| 必殺（ゲージMAX） | Z / Space | A |
| 決定 | Z / Enter | A |

## テスト（Pyxel不要・偽のPyxelで実行）

`python -I tests/test_game.py`
