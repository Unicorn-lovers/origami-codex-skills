# Origami Codex Skill

折り紙の展開図を設計・検証するためのCodexスキルです。

## Skills

### `origami-crease-pattern-generator`

題材の特徴とフラップ構成を計画し、Oriedita互換の `.cp` を生成・編集して、必要な深さまで検証します。

動物・生物の創作では、題材の特徴抽出、複数の領域配置案、比率の決め方、紙と構造の相互作用、実紙試作、再現性までを扱います。

題材名だけから設計する場合は、検証済みのBird、Frog、Fish、Preliminary、Waterbomb、Blintz各基本形を先に比較し、局所的な改造で済む候補を優先します。必要なパーツを満たす基本形がない場合だけ、新しいフラップツリーから設計します。

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
