# Origami Codex Skill

折り紙の展開図を設計・検証するためのCodexスキルです。

8×8または16×16の2色ドット絵から、正方形の紙1枚で折れる展開図を探索できます。8×8はdotFoldSolverを使い、16×16は元の256マスを保って紙の境界と折り線を探索します。折り上がりの前景が元絵と一致すると、山谷付きの展開図をOrieditaに取り込めます。[PNG・テキストからの使い方](skills/origami-crease-pattern-generator/references/pixel-art.md)

## Skills

### `origami-crease-pattern-generator`

題材の特徴とフラップ構成を計画し、Oriedita互換の `.cp` を生成・編集して、必要な深さまで検証します。

動物・生物の創作では、題材の特徴抽出、複数の領域配置案、比率の決め方、紙と構造の相互作用、実紙試作、再現性までを扱います。

基本形のカドが足りないときや、閉じると内側に埋もれるときの[展開図の修正方法](skills/origami-crease-pattern-generator/references/design-revisions.md)を収録しています。[繰り返し構造の設計](skills/origami-crease-pattern-generator/references/repeating-structures.md)では、ひねり模様の接続、器の断面から求める蛇腹の寸法、ユニットの差し込みと配色を扱います。

「羽の生えた猫」などの指定では、まず[手元の展開図ライブラリ](skills/origami-crease-pattern-generator/references/pattern-library.md)から猫の原図を検索します。編集できるCP・FOLDと書籍の該当ページを引き、元の折り上がりを確認してから両翼を加えた候補をOrieditaで検証します。元図のファイルは各自の端末で登録できます。

条件に合う元図がないときは、鶴・カエル・魚・正方・風船・座布団・凧・風車の8基本形を比較し、頭や脚、尾に使う紙の位置と重なりを調べます。候補を選ぶと、角を開く、向きを変える、二つの先端に分けるといった操作を展開図に反映し、Orieditaで折り上がりを検証できます。

座布団の基本形から二つの耳と尾を作る[設計例](skills/origami-crease-pattern-generator/assets/examples/two-ear-study.json)、[改造手順](skills/origami-crease-pattern-generator/references/base-adaptation.md)、[各基本形の折り方](skills/origami-crease-pattern-generator/references/base-fold-sequences.md)を収録しています。

正方形一枚で作るキツネの顔では、耳の間隔と額の折り方を変えた4案を比較しました。採用した案は、紙の裏色が左右の頬に出ます。[4案の折り上がり](skills/origami-crease-pattern-generator/assets/examples/fox-face/paper.svg)・[採用案の折り図](skills/origami-crease-pattern-generator/assets/examples/fox-face/fold-guide.svg)・[作り方と比較結果](skills/origami-crease-pattern-generator/references/fox-face-study.md)

通常は1件の展開図を扱うStandardモードを使います。次の要求がある場合だけ、同じスキル内のProductionモードへ進みます。

- 複数候補の探索とバッチ評価
- 再現可能な検証記録
- DEFOX用の折り工程
- 紙厚予算と実紙向けの評価

## Install

必要なスキルフォルダをCodexの個人スキルディレクトリへコピーします。

```bash
git clone https://github.com/Unicorn-lovers/origami-codex-skills.git
cp -R origami-codex-skills/skills/origami-crease-pattern-generator ~/.codex/skills/
```

Codexを再起動すると、`$origami-crease-pattern-generator` として利用できます。

旧版の `$origami-crease-pattern-production` をインストール済みの場合は、統合後に `~/.codex/skills/origami-crease-pattern-production` を削除してからCodexを再起動してください。

## Requirements

- Python 3
- Node.js
- Orieditaのビルド済みJAR、または利用可能なOriedita MCP
- Productionモードの追加検証を使う場合は、各リファレンスに記載された外部検証器

Oriedita JARが自動検出されない場合は、`ORIEDITA_JAR` に絶対パスを設定します。

## Validation policy

各スキルは、構文妥当性、局所平坦折り可能性、計算されたレイヤー状態、題材との視覚的一致、実際の折りやすさを別々の主張として扱います。Orieditaで計算が完了しただけでは、題材への一致や実紙での折り工程まで証明されたことにはしません。
