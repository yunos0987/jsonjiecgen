# 変更履歴 / Changelog

このファイルは、jsonjiecgen の利用者に影響する変更を記録します。

## [0.1.0] - 2026-11-01

### 初回リリース / Initial release

- JSON データまたは JSON Schema から、JSON と構造体を相互変換する IEC 61131-3 ST 言語コード（関数コード）を生成します。`--test` を指定すると、JiecUnit のテストコードを同時に生成します。
- 生成コード（関数コード・JiecUnit テストコード）は Jiecc 9.2.0 以降を必要とします。生成コードの先頭に、Jiecc 9.2.0 未満では `{#error}` で前処理が止まるバージョンガードを出力します。
- 生成コードに `{st}` / `{end}` を出力しません。Jiecc 9.2.0 以降は POU の本体に ST の文を直接書けるためです。
- 生成テストコードは `{#include <jiecunit.iec>}` を使います。JiecUnit 6.0.0 以降と組み合わせてください。コンパイル時は `-I` に JiecUnit のルートと `<JiecUnit のルート>/sys` を渡します。
