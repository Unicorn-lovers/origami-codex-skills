# ドット絵から折り紙の展開図を作る

依頼で指定されたドットの並びを基準にする。8×8の左上を原点にして、上の行から順に読み込む。黒と白以外の2色の場合は、どちらを絵柄にするかを `--foreground '#rrggbb'` で指定する。透明背景と不透明の単色で描いたPNGも使える。透明なマスには折り上がった紙が掛からないことまで検査する。

## 実行

```sh
python3 scripts/dotfold.py input.png --out-dir work/pixel-result
python3 scripts/dotfold.py assets/examples/pixel-art/letter-l.txt --out-dir work/letter-l
```

作例の十字は、正方形の四隅を折って裏色を見せると、中央に元の色が28マス残る。`python3 scripts/dotfold.py assets/examples/pixel-art/cross.png --foreground '#126871' --out-dir work/cross` で再現できる。[入力PNG](../assets/examples/pixel-art/cross.png)・[山谷付き展開図](../assets/examples/pixel-art/cross.cp)・[計算した折り上がり](../assets/examples/pixel-art/cross-folded.svg)

PNGは8×8ピクセルまたは各マスを同じ整数倍で拡大した画像。テキストは8文字×8行の `#` と `.`（または `1` と `0`）、もしくは64桁の二進文字列で指定する。前景が1。元絵が多色、長方形、アンチエイリアス付きの場合は、利用できる元データや、どのように8×8・2色にするかを依頼者と確認する。

Python 3.10以降、C++17コンパイラ（`c++` または `CXX`）、検証用のNode.js 18以降を使う。PNGの読み込みにはPillowも必要。例えば `uv run --with pillow python scripts/dotfold.py input.png --out-dir work/result` で実行できる。初回は固定版のソースを取得して計算部分をビルドし、次回からキャッシュを利用する。`--cache-dir` で保存先を、`--source-dir` と `--flat-folder-dir` で取得済みの各リポジトリを指定できる。[dotFoldSolver](https://github.com/sakusaku858/dotFoldSolver/tree/96e04662b6b981c5baae11420a825086a47352b8)・[Flat-Folder](https://github.com/origamimagiro/flat-folder/tree/d50004815fb738d009e5b87b2307fbaefa717ef0)

## 結果の読み方

- `exact` は、dotFoldSolverが出した候補についてFlat-Folderで層順序が求まり、見える面の前景色が元絵と面積差ゼロ（数値許容誤差内）で一致した状態。表裏、回転、位置合わせは `report.json` に残る。背景が不透明なら紙の裏色と台紙の背景を同じ色として見る。
- `candidate.cp` は山谷付きのOriedita用展開図。`assigned.fold` は編集用、`folded.fold` は層順序付きの折り上がり。`target.svg` が元絵、`folded.svg` が実際に見える面から描いた図。紙での折りやすさは実紙で確かめる。
- `candidate_only` なら上流が返した線を `unassigned.fold` で編集できる。山谷と見える色が決まった場合にだけ `candidate.cp` を出す。輪郭や奇数枚重なった領域だけの一致で完成と判定しない。
- 上流の探索条件は、元絵の境界をたどる経路が32歩になること。穴や離れた領域を含む場合は、それらをつなぐ経路も計算する。条件外は `unsupported`、探索で候補が出なければ `no_candidate`、制限時間に達すれば `timeout` として元のマス目を保存する。`--timeout`（各計算の秒数）と `--max-states`（比較する層状態の上限）を調整できる。結果は新規ディレクトリに出し、完全一致だけ終了コード0を返す。
