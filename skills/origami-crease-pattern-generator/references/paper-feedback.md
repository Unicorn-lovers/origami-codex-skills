# 実紙で見つけた問題を次の試作に戻す

実際に展開図を折った人の観察が届いたら、試した版の `candidate.cp`、`plan.json`、`adaptation.json` を使う。文章だけなら `--photo` を省く。写真があれば正面の一枚から始められる。手を離すと耳が開くなど、どの部位がどう動いたかを記録する。厚みが関係するときは紙の一辺と材質も残す。

## 写真と紙面の位置を記録する

下記はキツネの試作を折った後に使う記入例。写真のパスと観察内容を実際のものに置き換える。出力先には自分の作業用フォルダの新しいディレクトリを指定する。`--photo` で選んだ写真がそこにコピーされる。

```sh
python3 scripts/record_fold_trial.py work/variants/ruff \
  --feature right_ear --photo work/photos/first-front.jpg \
  --observation "［右耳のどこがどうなったか］" --paper "［一辺・材質］" \
  --change /parameters/ear_slope 1.35 --expect "［次に同じ角度から見たときの違い］" \
  --out-dir work/trial-01
```

`--feature` には `adaptation.json` の `landmarks_normalized` にある部位名を使う。初期位置はその部位に登録された点。問題が耳の先端ではなく根元にある場合は、紙を開いて位置を特定し、`--point X Y` で指定する。左上が (0,0)、右下が (1,1)。写真上のピクセルをそのまま渡さず、`location.svg` に出た印を展開図と照合する。撮影方向を変えた写真は `--photo` を繰り返して追加できる。

`trial.json` に写真のハッシュ、試した展開図のハッシュ、部位、紙面上の位置、観察が残る。観察だけを記録する場合は `--change` と `--expect` を省く。

## 一点変え、もう一度折る

`--change` は生成時のプランにある数値を一つ選ぶ。`next-plan.json` に変更後のプランが出る。左右対称のキツネでは `ear_slope` を変えると両耳に作用するため、同じ紙を使い、反対側も一緒に確認する。生成器が新しい値を受け付けたら、その展開図を再検証して折る。

```sh
python3 scripts/fox_face.py --plan work/trial-01/next-plan.json --out-dir work/revised
python3 scripts/fox_fold_guide.py work/revised/plan.json --output work/revised/fold-guide.svg
node scripts/validate_cp.mjs work/revised/candidate.cp --isolated --out-dir work/revised/validation
python3 scripts/record_fold_trial.py work/revised \
  --feature right_ear --photo work/photos/second-front.jpg \
  --observation "［同じ部位を折り直した結果］" --paper "［今回の一辺・材質］" \
  --previous work/trial-01 --outcome improved --out-dir work/trial-02
```

判定は観察者が `improved`、`unchanged`、`worse`、`inconclusive` から選ぶ。写真の向きや紙を変え、原因を切り分けられないときは `inconclusive` が使える。比較記録には前回の観察、期待した効果、今回の観察と判定が並ぶ。同じ展開図を二度折った場合も記録できる。前回の候補とも前回提案したプランとも無関係な試作を指定すると、別の試作として登録するようエラーが出る。

従来の基本形改造では `--change /operations/1/fraction 0.55` のように対象の操作を選び、`python3 scripts/adapt_base.py work/trial-01/next-plan.json --out-dir work/revised` で再生成する。元のプランが別の場所にある場合は記録時に `--plan` で渡す。
