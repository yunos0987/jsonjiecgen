# 変更履歴 / Changelog

このファイルは、jsonjiecgen の利用者に影響する変更を記録します。

## [0.2.0] - 2026-11-15

### 修正 / Fixed

- 複数の生成物を 1 つのプロジェクトにまとめてコンパイルすると、Jiecc 9.6.0 で共通の補助関数（`json_escape` など）が `DUPLICATE_SYMBOL` になる問題を直しました。補助関数を `{#ifndef JSON_HELPERS_DEFINED}`、補助関数のテストを `{#ifndef JSON_TEST_HELPERS_DEFINED}` で囲み、2 つ目以降の生成物では出さないようにしました。
- 生成テストコードの `_JIEC_TESTNAMES_LIST_` に渡すテスト名を、文字列リテラル（`'test_...'`）から識別子（`test_...`）に変えました。文字列リテラルのままだと、jier（`jiecc --run`）では `INVALID_SYNTAX_FOR_NAME` で止まり、PLC 向けではテスト名に引用符が含まれていました。
- `json_bytes_insert_text` が呼ぶ `json_asciicharcode` を、呼び出し元より前に出すようにしました。jier は呼び出しより前に定義された関数しか呼べません。
- 補助関数の `uint_to_dint(len(...))` を `len(...)` にしました。jier では `len` が DINT を返すため、`TYPE_ERROR` で止まっていました。
- 小数点の無い指数表記の数値（`1e3` など）を REAL / LREAL のフィールドに読むと、jier では 0.0 になっていました。IEC の実数の表記は指数の前に小数部が要るので、新しい補助関数 `json_real_text` で `1.0e3` の形に直してから `string_to_lreal` / `string_to_real` に渡します。
- 補助関数のテスト `test_json_extract_scalar` が、深さ 2 のキー（`[{"x":3}]` の `x`）を見つかるものとして検査していた誤りを直しました。`json_extract_scalar` は深さ 1 のキーだけを探します。
- `tests/inputs` の 10 件の JSON から生成したテストコードは、jier（Jiecc 9.6.0、JiecUnit 8.0.0）で全件合格します。
- README.md の「必要環境」に、確認した Jiecc と JiecUnit の版を書きました（`-t omron` のコンパイルは Jiecc 9.4.0・9.6.0 と JiecUnit 6.0.0・7.0.0・8.0.0、jier での実行は Jiecc 9.6.0 と JiecUnit 8.0.0）。

## [0.1.0] - 2026-11-01

### 初回リリース / Initial release

- JSON データまたは JSON Schema から、JSON と構造体を相互変換する IEC 61131-3 ST 言語コード（関数コード）を生成します。`--test` を指定すると、JiecUnit のテストコードを同時に生成します。
- 生成コード（関数コード・JiecUnit テストコード）は Jiecc 9.2.0 以降を必要とします。生成コードの先頭に、Jiecc 9.2.0 未満では `{#error}` で前処理が止まるバージョンガードを出力します。
- 生成コードに `{st}` / `{end}` を出力しません。Jiecc 9.2.0 以降は POU の本体に ST の文を直接書けるためです。
- 生成テストコードは `{#include <jiecunit.iec>}` を使います。JiecUnit 6.0.0 以降と組み合わせてください。コンパイル時は `-I` に JiecUnit のルートと `<JiecUnit のルート>/sys` を渡します。
