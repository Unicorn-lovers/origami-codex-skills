# Origami Codex Skills

折り紙の展開図を設計・検証するためのCodexスキル集です。

## Skills

### `origami-crease-pattern-generator`

1件の展開図作成・編集向けです。題材の特徴とフラップ構成を計画し、Oriedita互換の `.cp` を生成して、平坦折り計算と折り上がりを検証します。

### `origami-crease-pattern-production`

複数候補の探索や納品品質の検証向けです。バッチ評価、DEFOX用の折り工程、紙厚予算、再現可能な検証記録まで扱います。

## Install

必要なスキルフォルダをCodexの個人スキルディレクトリへコピーします。

```bash
git clone https://github.com/Unicorn-lovers/origami-codex-skills.git
cp -R origami-codex-skills/skills/origami-crease-pattern-generator ~/.codex/skills/
cp -R origami-codex-skills/skills/origami-crease-pattern-production ~/.codex/skills/
```

Codexを再起動すると、`$origami-crease-pattern-generator` と `$origami-crease-pattern-production` として利用できます。

## Requirements

- Python 3
- Node.js
- Orieditaのビルド済みJAR、または利用可能なOriedita MCP
- production版の追加検証を使う場合は、各リファレンスに記載された外部検証器

Oriedita JARが自動検出されない場合は、`ORIEDITA_JAR` に絶対パスを設定します。

## Validation policy

各スキルは、構文妥当性、局所平坦折り可能性、計算されたレイヤー状態、題材との視覚的一致、実際の折りやすさを別々の主張として扱います。Orieditaで計算が完了しただけでは、題材への一致や実紙での折り工程まで証明されたことにはしません。
