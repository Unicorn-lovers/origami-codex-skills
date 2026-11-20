# ドット絵から折り紙の展開図を作る

8×8または16×16のドット絵を、表裏の色が異なる正方形の紙1枚で表す。元絵を左上から行ごとに読み、指定されたマス目のまま展開図を探索する。最後に、計算した折り上がりで見える色を元絵と照合する。

## 実行

スキルのディレクトリで実行し、`--out-dir` に新しい出力先を指定する。

```sh
python3 scripts/dotfold.py input.png --out-dir work/pixel-result
python3 scripts/dotfold.py assets/examples/pixel-art/letter-l.txt --out-dir work/letter-l
python3 scripts/dotfold.py assets/examples/pixel-art/diamond-16.txt --out-dir work/diamond-16
```

16×16のひし形では、行ごとに幅が変わる輪郭から山折り12本・谷折り16本が見つかり、前景144マスが元絵と一致した。出力先の `target.svg` が元絵、`folded.svg` が重なり順から描いた折り上がり。山谷付きの `candidate.cp` はOrieditaで開ける。[ひし形の入力テキスト](../assets/examples/pixel-art/diamond-16.txt)・[山谷付き展開図](../assets/examples/pixel-art/diamond-16.cp)・[計算した折り上がり](../assets/examples/pixel-art/diamond-16-folded.svg)

8×8の十字では、四隅を折って裏色を見せると、中央に元の色が28マス残る。`python3 scripts/dotfold.py assets/examples/pixel-art/cross.png --foreground '#126871' --out-dir work/cross` で再現できる。[入力PNG](../assets/examples/pixel-art/cross.png)・[山谷付き展開図](../assets/examples/pixel-art/cross.cp)・[計算した折り上がり](../assets/examples/pixel-art/cross-folded.svg)

## 入力形式

- **テキスト**は `#` と `.`、または `1` と `0` を8文字×8行または16文字×16行で記す。`#` と `1` が前景。改行なしの64桁または256桁の二進文字列も使える。
- **PNG**は原寸なら1ピクセルが1マス。各マスを同じ整数倍に拡大した正方形のPNGも使える。16×16ピクセルは既定で16マス四方として読む。8×8の元絵を2倍にした画像には `--size 8` を指定する。原寸より大きい画像で両方の格子が成立する場合は8×8を選ぶので、16×16として読むには `--size 16` を指定する。
- **色**は、白黒なら黒が前景。透明背景では不透明な色が前景。16×16の不透明なカラーPNGでは、外周60マスで多い色を背景、もう一方を前景にする。同数なら左上の色が背景。不透明な単色のカラーPNGは全面を前景にする。前景を自分で選ぶには `--foreground '#rrggbb'` を指定する。8×8で白黒以外の不透明色を使う場合はこの指定が必要。多色画像やアンチエイリアス付きの画像は、どのマスを前景とするか確認してから2色の原画を用意する。

外周の色から前景を推定した16×16の画像で完全一致しなかった場合は、指定された色の役割と残りの探索予算を確認する。色の指定がなく、制限時間や候補数に余裕があれば、`target.json` の `background` のRGB値を `--foreground` に指定して元の不透明2色PNGを新しい出力先で再探索する。どちらの色を前景にして一致したかは、その結果の `target.json` で確認できる。

Python 3.10以降と検証用のNode.js 18以降を使う。PNGにはPillowも必要で、例えば `uv run --with pillow python scripts/dotfold.py input.png --out-dir work/result` で実行できる。8×8では初回に固定版のdotFoldSolverをC++17コンパイラ（`c++` または `CXX`）でビルドする。16×16の探索は同梱のPythonコードで動く。重なり順の計算には固定版のFlat-Folderを使う。`--cache-dir` でキャッシュの保存先を指定できる。取得済みのソースを使うときは、dotFoldSolverに `--source-dir`、Flat-Folderに `--flat-folder-dir` を指定する。[dotFoldSolver](https://github.com/sakusaku858/dotFoldSolver/tree/96e04662b6b981c5baae11420a825086a47352b8)・[Flat-Folder](https://github.com/origamimagiro/flat-folder/tree/d50004815fb738d009e5b87b2307fbaefa717ef0)

## 探索の範囲

**16×16**では、まず角や辺を折り返す組み合わせを試す。次に、紙の四辺を各16等分した外周が、元絵の輪郭を計64歩でたどる経路を探す。内側15×15の格子点には、隣同士で折り線がつながるタイルを置く。1マスの辺を1歩として輪郭が64歩より短い場合は、同じ線を二度たどる経路を最大2本加えて64歩になる場合も試す。輪郭だけで64歩を超えると、このタイル探索の対象外になる。候補の折り線を平面に折り畳み、面の重なり順と見える色を検査する。

`--timeout` は16×16の探索全体に使う秒数（準備時間を除き、既定60秒）。`--max-candidates` は16×16で検査する候補数（既定64）、`--max-states` は候補ごとに調べる層状態数（既定512）。探索する経路とタイル配置にも制限があるため、候補の有無は今回調べた範囲についての結果となる。

**8×8**では、dotFoldSolverが元絵の境界をたどる32歩の経路を探す。穴や離れた領域を含む場合は、それらをつなぐ経路も計算する。`--timeout` は各計算の秒数、`--max-states` は照合する層状態数の上限になる。

## 結果の読み方

- **`exact`** は、折り上がりで見える前景を元絵と重ね、はみ出した部分と欠けた部分の合計面積が数値許容誤差内でゼロになった状態。透明背景では透明なマスに紙が掛からないことも確認する。不透明な背景では紙のもう一方の色を背景色と同じ色として見る。折り線のない一枚の正方形は、唯一の面を直接照合する。
- **`candidate_only`** は、展開図の候補があり、見える色の完全一致は未確認の状態。`unassigned.fold` を開くと山谷未指定の折り線を編集できる。
- **`no_candidate`** は今回の探索範囲で候補が得られなかった状態。`timeout` は候補を得る前の時間切れ。8×8で上流の探索条件から外れると `unsupported` になる。元のマス目は `target.json` に残る。

`report.json` に判定と理由が入り、完全一致時は観察した側、回転、位置合わせ、面積差も記録される。16×16では停止理由と試した候補数も記録される。採用した候補の生成方法は `solver.json` で確認できる。完全一致時の `assigned.fold` は山谷付きの編集用データ、`folded.fold` は層順序付きの折り上がり。CLIは完全一致時に終了コード0を返す。折り順や実際の紙での折りやすさは別途確かめる。
