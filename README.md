# jsonjiecgen — JSON ↔ IEC 61131-3 コードジェネレータ

JSON データまたは JSON Schema を入力として、PLC 上で実行時に JSON ↔ 構造体データを相互変換する IEC 61131-3 ST言語コードを生成するコマンドラインツールです。

生成されたST言語コードは [Jiecc](https://www.graviness.com/iec_61131-3/jiecc.html) でコンパイルして IEC 61131-10 XML に変換し、各 PLC メーカーのエンジニアリングツールに取り込むことが可能です。現在、OMRON社製Sysmac Studioのみをサポートしています。

```
Normal use:

  input.json ──┐
               │   jsonjiecgen        jiecc
  schema.json ─┴──► (main.py) ──► output.txt ──► output.xml
  (--schema)                       (IEC 61131-3)  (IEC 61131-10)


With testing (--test):

  input.json ──┐
               │   jsonjiecgen        jiecc
  schema.json ─┴──► (main.py) ──► output.txt ───────────────────────► output.xml
  (--schema)                       (IEC 61131-3)                       (IEC 61131-10)
                         │
                         └────► output_test.txt ──► jiecc ──► output_test.xml
                                  (jiecunit)                   (IEC 61131-10)
```

## 特徴

- JSON データまたは JSON Schema を入力として、IEC 61131-3 STプログラムコードを生成
- 入力の構造に特化した変換関数を生成（文字列版・バイト列版）
- ネストしたオブジェクト・配列・多次元配列に対応
- jiecunit 対応の単体テストファイルを `--test` で同時生成
- 外部ライブラリへの依存なし。生成ファイル単体で完結
- 型名・文字列型・整数型・実数型・論理型などをオプションで指定可能
- 不正 JSON データを PLC 実行時に検出して `eno = false` を返す

## 必要環境

- Python 3.10 以降
- [Jiecc](https://www.graviness.com/iec_61131-3/jiecc.html) 9.2.0 以降 — 生成コードのコンパイルに必要（生成コードの先頭に、9.2.0 未満では `{#error}` で止まるバージョンガードを出力します）
- [jiecunit](https://github.com/yunos0987/jiecunit) 6.0.0 以降 — 生成テストコード（`--test`）を使う場合に必要

## インストール

```bash
git clone <repository-url>
cd jsonjiecgen
```

標準ライブラリのみ使用するため、依存ライブラリはありません。

## 使い方

```
python src/main.py <input.json> [オプション]
```

### オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `input` | （標準入力） | 入力 JSON / JSON Schema ファイルのパス |
| `-o FILE` | 標準出力 | 出力ファイルのパス |
| `--schema` | — | 入力を JSON Schema として処理する |
| `--root-name NAME` | `JsonRoot` | 型名・関数名に使用するルート名 |
| `--type-name-suffix SUFFIX` | `_t` | 型名サフィックス |
| `--string-type TYPE` | `string[256]` | JSON 文字列に対応する IEC 文字列型。`string` または `string[N]` を指定 |
| `--integer-type TYPE` | `dint` | JSON 整数に対応する IEC 整数型 |
| `--number-type TYPE` | `lreal` | JSON 小数に対応する IEC 実数型 |
| `--boolean-type TYPE` | `bool` | JSON 論理値に対応する IEC 型 |
| `--json-string-size N` | `JSON_STRING_SIZE` | JSON 文字列バッファサイズ。jiecc マクロ名も指定可 |
| `--test FILE` | — | jiecunit テストファイルの出力先 |

> **スキーマ自動検出**: ファイル名に `schema` が含まれる場合、`--schema` を省略しても JSON Schema として処理されます。

## 使用例

### JSON データから生成

```bash
python src/main.py jsons/samples/simple.json -o output.txt
```

```json
// jsons/samples/simple.json
{
    "name": "sensor1",
    "value": 3.14,
    "count": 42,
    "active": true,
    "readings": [1.1, 2.2, 3.3],
    "tags": ["temp", "humidity"]
}
```

生成例（抜粋）:

```
type
    JsonRoot_t: struct
        name: string[256];
        value: lreal;
        count: dint;
        active: bool;
        readings: array[0..2] of lreal;
        tags: array[0..1] of string[256];
    end_struct;
end_type

function JsonRoot_iecdata_to_jsontext
    var_in_out data: JsonRoot_t; end_var
    var_in_out txt: string[JSON_STRING_SIZE]; end_var
    ...

function JsonRoot_jsontext_to_iecdata
    var_in_out txt: string[JSON_STRING_SIZE]; end_var
    var_in_out data: JsonRoot_t; end_var
    ...

function JsonRoot_iecdata_to_jsonbytes: dint
    var_in_out data: JsonRoot_t; end_var
    var_in_out bytes: array[*] of byte; end_var
    var_input start_index: dint := -1; end_var
    ...

function JsonRoot_jsonbytes_to_iecdata
    var_in_out bytes: array[*] of byte; end_var
    var_input start_index: dint := -1; end_var
    var_input end_index: dint := -1; end_var
    var_in_out data: JsonRoot_t; end_var
    ...
```

### ネストした JSON

```bash
python src/main.py jsons/samples/object.json -o output.txt
```

```json
// jsons/samples/object.json
{
    "name": "robot",
    "pos": { "x": 1.0, "y": 2.0, "z": 3.0 },
    "tags": ["a", "b", "c"],
    "counts": [10, 20, 30],
    "active": true
}
```

ネストしたオブジェクトは `JsonRoot_pos_t` のように名前が拡張されて型定義されます。型定義はリーフから順に出力されます。サブオブジェクト用の内部変換関数には `private_` プレフィックスが付きます。

### 多次元配列

```bash
python src/main.py jsons/samples/multiple_array.json -o output.txt
```

```json
// jsons/samples/multiple_array.json
{
    "matrix": [[1, 2, 3], [4, 5, 6]],
    "grid":   [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
}
```

生成例（抜粋）:

```
    matrix: array[0..1, 0..2] of dint;
    grid:   array[0..2, 0..1] of lreal;
```

### JSON Schema から生成

```bash
python src/main.py jsons/schema_samples/simple_schema.json -o output.txt
```

```json
// jsons/schema_samples/simple_schema.json
{
    "type": "object",
    "properties": {
        "name":     { "type": "string" },
        "value":    { "type": "number" },
        "count":    { "type": "integer" },
        "active":   { "type": "boolean" },
        "readings": { "type": "array", "items": { "type": "number" }, "maxItems": 3 },
        "tags":     { "type": "array", "items": { "type": "string" }, "maxItems": 2 }
    }
}
```

配列型には `maxItems` の指定が必須です。値は IEC 配列サイズとして使用されます。

### jiecunit テストファイルを同時生成

```bash
python src/main.py jsons/samples/simple.json \
    -o output.txt \
    --test output_test.txt
```

`--test` を指定すると、生成コードに対応する jiecunit テストスイートを別ファイルに出力します。
生成されたテストは `{#include <jiecunit.iec>}` を使うので、コンパイル時は `-I` に jiecunit のルートと `<jiecunit root>/sys` を渡してください（生成物冒頭のコマンドコメントと同じ指定です）。
テストには `TEST_S(test_JsonRoot_jsontext_to_iecdata)` 等、入力値に基づくアサーションが含まれます。

### オプション指定例

```bash
# ルート名を変更（型名・関数名に反映）
python src/main.py jsons/samples/simple.json --root-name Sensor

# 整数型を lint、実数型を real に変更
python src/main.py jsons/samples/simple.json --integer-type lint --number-type real

# 文字列型を string[128]、JSON バッファを 8192 に変更
python src/main.py jsons/samples/simple.json --string-type string[128] --json-string-size 8192

# 文字列型をサイズ指定なし（bare string）に変更
python src/main.py jsons/samples/simple.json --string-type string
```

## 生成されるコードの構成

### 型定義（`type` ブロック）

入力 JSON の構造に対応する `struct` 型を生成します。ネストした型はリーフから順に並びます。

### ヘルパー関数（常に生成）

| 関数 | 説明 |
|---|---|
| `json_escape` | 文字列を JSON 用にエスケープ。`"` → `\"` など |
| `json_unescape` | JSON エスケープを元に戻す |
| `json_char_from_asciicharcode` | ASCII コードから文字へ変換 |
| `json_asciicharcode` | 文字から ASCII コードへ変換 |
| `json_find_key` | JSON 文字列からキーの位置を検索 |
| `json_find_block` | JSON 文字列からブロック（`{}`・`[]`）を抽出 |
| `json_extract_scalar` | JSON 文字列からスカラー値を抽出 |
| `json_bytes_find_key` | JSON バイト列からキーの位置を検索 |
| `json_bytes_find_block` | JSON バイト列からブロックを抽出 |
| `json_bytes_extract_scalar` | JSON バイト列からスカラー値を抽出 |
| `json_bytes_insert_text` | バイト列バッファに文字列を書き込む |
| `json_bytes_to_str` | バイト列の範囲を文字列へ変換 |

### データ変換関数（`--root-name` で名前が変わる）

| 関数 | 説明 |
|---|---|
| `JsonRoot_iecdata_to_jsontext` | 構造体 → JSON 文字列 `string[N]` |
| `JsonRoot_jsontext_to_iecdata` | JSON 文字列 → 構造体 |
| `JsonRoot_iecdata_to_jsonbytes: dint` | 構造体 → JSON バイト列 `array[*] of byte`。戻り値は書き込みバイト数 |
| `JsonRoot_jsonbytes_to_iecdata` | JSON バイト列 → 構造体 |

`jsontext_to_iecdata` / `jsonbytes_to_iecdata` はキーが見つからない・値の区切り文字がないなど不正データを検出すると `eno = false` を返します。

ネストしたオブジェクトや構造体配列の内部処理用に `private_JsonRoot_xxx_t_jsontext_to_iecdata` / `private_JsonRoot_xxx_t_jsonbytes_to_iecdata` が生成されますが、外部からの直接呼び出しは想定していません。

### バイト列関数のパラメータ

`iecdata_to_jsonbytes` と `jsonbytes_to_iecdata` は開始・終了インデックスをオプションで指定できます。

```
JsonRoot_iecdata_to_jsonbytes(data:=data, bytes:=buf, start_index:=offset);
    // start_index = -1（デフォルト）: lower_bound(bytes, 1) から書き込み開始

JsonRoot_jsonbytes_to_iecdata(bytes:=buf, start_index:=si, end_index:=ei, data:=data);
    // start_index = -1（デフォルト）: lower_bound(bytes, 1) から読み込み開始
    // end_index   = -1（デフォルト）: upper_bound(bytes, 1) まで読み込み
```

## 型マッピング仕様

| JSON の値 | IEC 型（デフォルト） |
|---|---|
| `true` / `false` | `bool`。`--boolean-type` で変更可 |
| 整数（例: `42`） | `dint`。`--integer-type` で変更可 |
| 小数（例: `3.14`） | `lreal`。`--number-type` で変更可 |
| 文字列 | `string[256]`。`--string-type` で変更可 |
| オブジェクト | `struct` として新たな型を定義 |
| 配列 | `array[0..N-1] of <elem_type>` |

配列要素型の推論: 全要素が整数なら `--integer-type`、1 つでも小数を含むなら `--number-type`、それ以外は先頭要素の型に従います。

非対応の値: `null` および空配列 `[]` は生成時にエラーになります。

## ディレクトリ構成

```
jsonjiecgen/
├── jsons/
│   ├── samples/             # サンプル JSON ファイル（各 .json に対応する生成済み .txt を同梱）
│   │   ├── simple.json          # スカラー4型 + 配列
│   │   ├── object.json          # ネストオブジェクト + 配列
│   │   └── multiple_array.json  # 多次元配列
│   └── schema_samples/      # サンプル JSON Schema ファイル（同上）
│       ├── simple_schema.json   # simple.json に対応する JSON Schema
│       ├── object_schema.json   # object.json に対応する JSON Schema
│       └── multiple_array_schema.json  # multiple_array.json に対応する JSON Schema
├── src/
│   ├── main.py              # CLI エントリポイント
│   ├── analyzer.py          # JSON/Schema → TypeModel 変換
│   ├── generator.py         # TypeModel → IEC 61131-3 ST 生成
│   ├── jiecunittest_generator.py    # TypeModel → jiecunit テストファイル生成
│   ├── model.py             # データモデル（TypeModel, StructType 等）
│   ├── json_helpers.txt     # ヘルパー関数テンプレート
│   └── test_json_helpers.txt  # ヘルパー関数テストテンプレート
└── tests/
    ├── inputs/              # E2E テスト用 JSON 入力
    │   ├── simple.json
    │   ├── various.json
    │   ├── simple_schema.json
    │   ├── various_schema.json
    │   ├── nested_obj_3.json
    │   ├── multiple_ary_3.json
    │   ├── simple_ary.json
    │   ├── structure_ary.json
    │   ├── struct_ary_3.json
    │   └── multi_ary_struct.json
    ├── outputs/             # E2E テスト用期待出力（ゴールデンファイル）
    │   ├── simple.txt / test_simple.txt
    │   ├── various.txt / test_various.txt
    │   ├── simple_schema.txt / test_simple_schema.txt
    │   ├── various_schema.txt / test_various_schema.txt
    │   ├── nested_obj_3.txt / test_nested_obj_3.txt
    │   ├── multiple_ary_3.txt / test_multiple_ary_3.txt
    │   ├── simple_ary.txt / test_simple_ary.txt
    │   ├── structure_ary.txt / test_structure_ary.txt
    │   ├── struct_ary_3.txt / test_struct_ary_3.txt
    │   └── multi_ary_struct.txt / test_multi_ary_struct.txt
    ├── test_analyzer.py
    ├── test_generator.py
    ├── test_jiecunittest_generator.py
    └── test_main.py
```

## テスト実行

```bash
# 全テスト実行
python -m pytest tests/ -v

# テストファイル別に実行
python -m pytest tests/test_analyzer.py -v
python -m pytest tests/test_generator.py -v
python -m pytest tests/test_jiecunittest_generator.py -v
python -m pytest tests/test_main.py -v
```

### ゴールデンファイルの再生成

`src/generator.py` または `src/jiecunittest_generator.py` を変更した場合は、ゴールデンファイルを再生成してテストを通過させてください。

```bash
for entry in \
  "simple --root-name Simple" \
  "various --root-name Various" \
  "simple_schema --schema --root-name SimpleSchema" \
  "various_schema --schema --root-name VariousSchema" \
  "nested_obj_3 --root-name NestedObj3" \
  "multiple_ary_3 --root-name MultipleAry3" \
  "simple_ary --root-name SimpleAry" \
  "structure_ary --root-name StructureAry" \
  "struct_ary_3 --root-name StructAry3" \
  "multi_ary_struct --root-name MultiAryStruct"
do
  stem=$(echo $entry | awk '{print $1}')
  args=$(echo $entry | cut -d' ' -f2-)
  python src/main.py $args tests/inputs/${stem}.json \
    -o tests/outputs/${stem}.txt --test tests/outputs/test_${stem}.txt
done
```

## 開発・変更履歴

開発への参加方法とバージョン管理は [CONTRIBUTING.md](CONTRIBUTING.md)、リリースごとの変更は [CHANGELOG.md](CHANGELOG.md) を参照してください。

## ライセンス

[MIT License](LICENSE)

## 制約・注意事項

### コード生成時

- 入力 JSON のトップレベルはオブジェクト（`{}`）である必要があります
- JSON Schema モードではトップレベルが `"type": "object"` である必要があります
- JSON Schema の配列型には `maxItems` の指定が必須です
- 出力ファイルのエンコーディングは UTF-8（BOM なし）、改行コードは LF です

### PLC 実行時

#### JSON_STRING_SIZE マクロ

生成コードは `JSON_STRING_SIZE` マクロを文字列バッファサイズとして使用します。未定義の場合はデフォルト値 `1024` が自動で定義されます。プロジェクトに合わせて jiecc コンパイルオプションや上位インクルードファイルで事前定義してください。

```
(* 例: コンパイル時オプション -D で定義 *)
jiecc output.txt -DJSON_STRING_SIZE=4096 ...
```

`--json-string-size` オプションで指定した値はコンパイル時に `JSON_STRING_SIZE` の代わりに直接埋め込まれます。

#### テキスト版（jsontext）の文字列長

`iecdata_to_jsontext` の出力と `jsontext_to_iecdata` の入力はいずれも `string[JSON_STRING_SIZE]` 型です。生成される JSON 文字列がこのサイズを超えると PLC の `concat` により暗黙に切り詰められ、`jsontext_to_iecdata` は不正 JSON として `eno = false` を返します。入力 JSON が大きい場合は `JSON_STRING_SIZE` を十分大きく設定するか、バイト列版の使用を検討してください。

#### バイト列版（jsonbytes）のバッファサイズ

`iecdata_to_jsonbytes` と `jsonbytes_to_iecdata` の `bytes` パラメータは呼び出し側で確保した配列を渡します。`iecdata_to_jsonbytes` は配列境界チェックを行いません。バッファが不足すると配列外アクセスが発生します。`bytes` 配列は生成される JSON のバイト数より十分大きいサイズを確保してください。

`iecdata_to_jsonbytes` は書き込み完了後にヌルバイト（`0x00`）を末尾に追加し、書き込みバイト数（ヌル終端を除く）を戻り値として返します。

```
(* 戻り値を使った使用例 *)
written := JsonRoot_iecdata_to_jsonbytes(data:=data, bytes:=buf, start_index:=-1);
(* buf[lower_bound(buf,1) .. lower_bound(buf,1)+written-1] に JSON が格納される *)
(* buf[lower_bound(buf,1)+written] = 0x00 (ヌル終端) *)
```

#### eno パラメータ

`jsontext_to_iecdata` / `jsonbytes_to_iecdata` は以下の場合に `eno = false` を返して処理を中断します。

- 指定キーが JSON 内に見つからない
- 値の区切り文字（`,` `}` `]`）が見つからない
- ブラケットの対応が取れていない
- バイト列のインデックスが範囲外になった
- 文字コード変換に失敗した（非 ASCII 文字など）

呼び出し側では `eno` の値を確認し、`false` の場合はデータを使用しないようにしてください。

#### 入力 JSON の書式

PLC 実行時に渡す JSON データには余分な空白・タブ・改行を含めないでください。コンパクト形式（`{"key":value}`）のみ対応しています。

#### string 型のサイズ指定

jiecc の `string[N]` の `N` はヌル文字（NIL）を含むバイト数です。例えば最大 10 文字のフィールドを扱うには `string[11]` と指定します。`--string-type string[N]` で指定する `N` もこの規則に従ってください。
