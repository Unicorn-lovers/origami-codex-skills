# 基本形を題材用の展開図に改造する

部位ごとに使う紙を決めたら、ランキング結果の `id` を `base` に、`suggested_assignments` を `assignments` に写す。座標の単位は元の紙の一辺。左上が (0,0)、右下が (1,1) になる。各部位の先端、根元、紙面上の予約領域は [regions.json](../assets/bases/regions.json) で確認できる。

## 耳を二つ作る例

座布団の基本形で頭に使う角を一度開き、その角に向きの異なる二本の折り線を入れる。反対の角を開いて尾にする。最初の角を閉じたまま分割した試作では、両耳の印が折り上がりの内側に来た。角を先に開いた版では、二つの耳の印が輪郭上の異なる位置に来る。[改造プラン](../assets/examples/two-ear-study.json)

スキルのフォルダから、出力先に新しいディレクトリ名を指定して実行する。

同梱の検証結果で、[展開図](../assets/examples/two-ear-result/candidate.cp)、[紙の上の部位](../assets/examples/two-ear-result/paper.svg)、[折り上がりの同じ部位](../assets/examples/two-ear-result/folded.svg)を見比べられる。

```bash
python3 scripts/adapt_base.py assets/examples/two-ear-study.json --out-dir two-ears
```

Orieditaのローカル制御に対応したJARは `--jar` または `ORIEDITA_JAR` で指定できる。コマンドは専用のOrieditaを起動して検証し、終了後に閉じる。途中の紙面だけを見たいときは `--geometry-only` で展開図を出力し、別のディレクトリで検証まで実行する。

## 選べる操作

| `op` | プランに入れる値 | 紙面の変化 |
|---|---|---|
| `shorten_tip` | `flap`, `fraction`（0より大きく1未満） | 先端から根元へ指定割合だけ戻した点を目標に、垂直二等分線で折り返す。 |
| `redirect_tip` | `flap`, `target: [x,y]` | 元の紙面で指定した目標点へ向けて、角を斜めに折り返す。 |
| `split_tip` | `flap`, `fraction`, 任意で `children: ["左耳","右耳"]` | 二辺が紙の縁に接する角に二本の折り線を作る。指定した範囲内に既存の折り線がある場合は、別の角や小さい範囲を試す。子の印は、新しくできた折り筋の肩と元の先端に付く。 |
| `release_corner` | `flap` | 折り線一本で閉じた角の、その折り線を取り除く。 |
| `border_graft` | `side`（left/right/top/bottom）, `width`（0より大きく0.5未満） | 新しい正方形の中で元の形を相似縮小し、指定側に幅を確保する。直交方向にも半幅ずつ余白を取り、既存の折り線を反射してつなぐ。最後に適用する。 |
| `hybrid_quadrant` | `quadrant`（nw/ne/sw/se）, `donor`（別の基本形ID） | 指定した四分の一に別の基本形の折り線を移す。境界上の折り線は受け側を維持する。置換した領域の部位は折り上がりで再確認する。 |

基本形ごとに使える角や面は異なる。短縮・向き変更では、折り返す線の両端が紙の縁に届く局所構造を扱う。奥の層を複数横切るヒダは、[折り上がりから折り線を戻す手順](novel-subject-workflow.md)で設計する。

## 出力を読む

- `candidate.cp` が改造後の展開図。`plan.json` と `adaptation.json` に入力、元と改造後のハッシュ、検証結果が残る。
- `paper.svg` には部位名と紙面の予約領域が出る。`source_region_conflicts` の面積は元の紙全体に占める割合。重なる部位の向きや根元を確かめる。グラフトや象限置換後の紙の使い方は、改造後の図で見直す。
- `folded.svg` では、同じ番号の部位を折り上がりで追える。層の領域と照合できた場合、`on_projected_outline` に各部位が外周に達したかが記録される。対称性で向きが一意に決まらない場合は、折り線で各面を反射した全層の投影図を使う。
- `validation/` にOrieditaの折り上がり画像、FOLD、層のデータ、検査記録が出る。部位の見え方や実紙での折りやすさは、重なり、指を入れる位置、紙厚を含めて別に確認する。
