# 作品の元図を探して改造する

指定を「元の題材」と「加える部位」に分ける。羽の生えた猫なら最初に猫を探す。左右の翼の構造を比較したいときは、鳥やコウモリの展開図も引く。以下はスキルのディレクトリから実行する。

```bash
python3 scripts/pattern_library.py search '羽の生えた猫' --limit 5
python3 scripts/pattern_library.py search '二本の尾を持つ狐' --base 狐
python3 scripts/pattern_library.py search 猫 --source book --sequences
python3 scripts/pattern_library.py show CP005122
```

検索結果には元図のID、形式、手元のファイルが出る。書籍はPDFの先頭を1とするページ番号と、ページ左上を原点とした図の範囲 `crop_box` で開く。例えば書籍の仔猫はPDFの5ページ上段に展開図があり、41–46ページで折る向きと成形を追える。顔だけのモデル、全身像、模様の名前が似ている場合は頭・胴・脚・尾を確認して候補を決める。作品名やIDの直接検索もできる。

元図を再作図した版や以前の改造が登録されている場合は `derived_pattern_ids` から開ける。手元でOrieditaの計算を終えた候補には `validation_report` が付く。該当する資料が少ないときは別名や英語名でも探す。

## 元図を検証して、必要な部分だけを変える

```bash
python3 scripts/pattern_library.py checkout CP005122 --out-dir winged-cat --validate-base
# Edit winged-cat/candidate.cp before running the next command.
node scripts/validate_cp.mjs winged-cat/candidate.cp --isolated --out-dir winged-cat/candidate-validation
```

- `source.json` に元のID・出所・ファイルのハッシュ、`base.cp` に検証時の原形、`candidate.cp` に編集用のコピーが入る。FOLDは平面上の距離の比と山谷を保って変換する。平らな補助辺（FOLDのF、CPの4）は検証用CPから省き、その本数を記録する。山谷未指定、画像、書籍の図を選ぶと、元ページや図を指す参照記録ができる。図から復元した場合は紙の外周・交点・山谷を照合し、復元図に新しいIDを与える。
- `cp_ready` は山谷付きの検証用CPに変換できる印。元図と派生図をそれぞれ計算し、違反数、計算完了、折り上がり画像、層データを確認する。動作するOriedita JARは `register DIRECTORY --jar /path/to/oriedita.jar` で端末に記憶できる。実行時の `ORIEDITA_JAR` または `--jar` でも指定できる。
- 猫では、頭・耳・脚・尾の紙の位置を記録してから、背の両側でつかめるフラップを探す。肩として残す折り線、翼面に出す紙、先端が来る位置を左右一組で決める。余る紙が少ない場合は別の猫や領域を足す案を比較する。鳥の翼を参考にする場合も、根元の幅、隣の山谷と層が猫の背へつながるように作図する。
- 元図と候補の折り上がりを同じ向き・縮尺で見比べる。耳や尾を翼と取り違えていないか、左右の翼に別々の面積があり、背から輪郭に出ているかを確かめる。左右の紙が同じ位置に重なった候補は、層を開く順序かフラップの配置に戻る。完成時の立体成形や羽ばたきが必要な場合はその状態も試す。派生図には元の作品と実際に変えた部分を明記する。

## 私用ライブラリの登録

登録済みなら上の検索をそのまま使える。別の端末では、同じ分冊ZIPと元のPDFから次のように作れる。

```bash
python3 scripts/import_pattern_archives.py --library ~/OrigamiLibrary /path/to/origami_crease_patterns_part*.zip
python3 scripts/import_pattern_book.py --library ~/OrigamiLibrary /path/to/origami_prince_sugowaza_origami_hq.pdf
python3 scripts/pattern_library.py register ~/OrigamiLibrary
```

ZIPは同梱のファイル目録と照合する。書籍は登録済みの版のハッシュを照合して図の位置と折り順を関連付ける。公開スキルには検索・変換用コードとページ索引があり、図や原本は私用ライブラリに保存される。端末の登録先は `CODEX_HOME`（通常は `~/.codex`）の `origami-pattern-library.json`。一時的に別のコレクションを使う場合は `ORIGAMI_PATTERN_LIBRARY` またはサブコマンドの前の `--library DIR` で選ぶ。
