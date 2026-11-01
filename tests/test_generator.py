# coding: utf-8
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzer import analyze_json, analyze_schema
from generator import IecGenerator


def gen(data, **kw):
    model = analyze_json(data, **kw)
    return IecGenerator().generate(model)


def gen_schema(schema, **kw):
    model = analyze_schema(schema, **kw)
    return IecGenerator().generate(model)



class TestTypeDefs:
    def test_flat_struct_generated(self):
        # Fact: a flat struct generates a correct type definition with field declarations
        # Arrange / Act
        out = gen({'x': 1, 'y': 2.0})
        # Assert
        assert 'JsonRoot_t: struct' in out
        assert 'x: dint;' in out
        assert 'y: lreal;' in out
        assert 'end_struct;' in out
        assert 'end_type' in out

    def test_nested_struct_leaf_first(self):
        # Fact: nested struct types are output in leaf-first order
        # Arrange / Act
        out = gen({'pos': {'x': 1.0}})
        pos_idx = out.index('JsonRoot_pos_t: struct')
        root_idx = out.index('JsonRoot_t: struct')
        # Assert
        assert pos_idx < root_idx  # leaf-first order

    def test_array_type(self):
        # Fact: a string array field generates a correct array type declaration with bounds
        # Arrange / Act
        out = gen({'tags': ['a', 'b']})
        # Assert
        assert 'tags: array[0..1] of string[256];' in out

    def test_single_element_array_bounds(self):
        # Fact: a single-element integer array generates array[0..0] bounds
        # Arrange / Act
        out = gen({'nums': [42]})
        # Assert
        assert 'nums: array[0..0] of dint;' in out

    def test_helpers_always_included(self):
        # Fact: helper functions are always included in the generated output
        # Arrange / Act
        out = gen({'n': 1, 'f': 2.0, 'b': True})
        # Assert
        assert 'function json_escape' in out
        assert 'function json_unescape' in out
        assert 'function json_char_from_asciicharcode' in out
        assert 'function json_asciicharcode' in out


class TestJsonHelpers:
    def test_escape_sequences_present(self):
        # Fact: json_escape includes escape sequence mappings for tab and newline
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert "ch = '$t'  then result := concat(result, '\\t')" in out
        assert "ch = '$n'  then result := concat(result, '\\n')" in out

    def test_sv_in_generated_function_uses_string_type(self):
        # Fact: sv variable in generated functions uses the default string type string[256]
        # sv declared in generated functions uses the string_type option (default string[256])
        # Arrange / Act
        out = gen({'x': 1})
        fn = out.split('function JsonRoot_iecdata_to_jsontext')[1].split('end_function')[0]
        # Assert
        assert 'sv: string[256];' in fn

    def test_sv_in_generated_function_uses_custom_string_type(self):
        # Fact: sv variable uses the custom string type when string_type is specified
        # sv declared in generated functions uses the custom string_type when specified
        # Arrange / Act
        out = gen({'x': 1}, string_type='string[128]')
        fn = out.split('function JsonRoot_iecdata_to_jsontext')[1].split('end_function')[0]
        # Assert
        assert 'sv: string[128];' in fn


class TestVersionGuard:
    def test_guard_condition(self):
        # Fact: the function code has a jiepp condition rejecting Jiecc older than 9.2.0
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert '{#if _JIECC and (_JIECC_FULL_VER < 90200)}' in out

    def test_guard_error(self):
        # Fact: the function code has a jiepp error directive for old Jiecc
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert '{#error Generated code requires Jiecc 9.2.0 or later.}' in out

    def test_guard_once(self):
        # Fact: the version guard appears exactly once in the function code
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert out.count('_JIECC_FULL_VER < 90200') == 1

    def test_guard_first(self):
        # Fact: the version guard is the first line of the function code
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert out.startswith('{#if _JIECC and (_JIECC_FULL_VER < 90200)}\n')

    def test_no_st_markers(self):
        # Fact: the function code does not contain st start or end markers
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert '{st}' not in out
        assert '{end}' not in out


class TestRawjsonFunctions:
    def test_data_to_jsonbytes_always_generated(self):
        # Fact: iecdata_to_jsonbytes function is always generated
        # Act / Assert
        assert 'function JsonRoot_iecdata_to_jsonbytes' in gen({'x': 1})

    def test_jsonbytes_to_data_always_generated(self):
        # Fact: jsonbytes_to_iecdata function is always generated
        # Act / Assert
        assert 'function JsonRoot_jsonbytes_to_iecdata' in gen({'x': 1})

    def test_data_to_jsonbytes_no_intermediate_string(self):
        # Fact: iecdata_to_jsonbytes does not use an intermediate string variable
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert 'JsonRoot_iecdata_to_jsontext(data, txt);' not in out
        assert 'json: string[' not in out.split('function JsonRoot_iecdata_to_jsonbytes')[1].split('end_function')[0]

    def test_data_to_jsonbytes_uses_json_bytes_insert_text(self):
        # Fact: iecdata_to_jsonbytes uses json_bytes_insert_text for writing output
        # Act / Assert
        assert 'json_bytes_insert_text(dat:=bytes,' in gen({'x': 1})

    def test_data_to_jsonbytes_null_terminates(self):
        # Fact: iecdata_to_jsonbytes null-terminates the byte array
        # Act / Assert
        assert 'bytes[raw_ci] := 0' in gen({'x': 1})

    def test_data_to_jsonbytes_numeric_field(self):
        # Fact: iecdata_to_jsonbytes inserts numeric fields via json_bytes_insert_text
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert "raw_ci := json_bytes_insert_text(dat:=bytes, index:=raw_ci, str:=sv);" in out

    def test_data_to_jsonbytes_bool_field(self):
        # Fact: iecdata_to_jsonbytes inserts bool fields as true or false text
        # Arrange / Act
        out = gen({'flag': True})
        # Assert
        assert "raw_ci := json_bytes_insert_text(dat:=bytes, index:=raw_ci, str:='true');" in out
        assert "raw_ci := json_bytes_insert_text(dat:=bytes, index:=raw_ci, str:='false');" in out

    def test_data_to_jsonbytes_string_field(self):
        # Fact: iecdata_to_jsonbytes escapes string fields using json_escape
        # Arrange / Act
        out = gen({'name': 'abc'})
        # Assert
        assert 'json_escape(data.name)' in out

    def test_jsonbytes_to_data_uses_bytes_extract_scalar(self):
        # Fact: jsonbytes_to_iecdata uses json_bytes_extract_scalar for scalar fields
        # Arrange / Act
        fn = gen({'x': 1}).split('function JsonRoot_jsonbytes_to_iecdata')[1].split('end_function')[0]
        # Assert
        assert 'json_bytes_extract_scalar(dat:=bytes, key:=key_x, start_index:=si, end_index:=ei, sv:=sv, eno=>eno)' in fn

    def test_jsonbytes_to_data_no_intermediate_string(self):
        # Fact: jsonbytes_to_iecdata does not use an intermediate string variable
        # Arrange / Act
        fn = gen({'x': 1}).split('function JsonRoot_jsonbytes_to_iecdata')[1].split('end_function')[0]
        # Assert
        assert 'jstr:' not in fn
        assert 'JsonRoot_jsonstr_to_data' not in fn

    def test_jsonbytes_to_data_uses_bytes_find_key(self):
        # Fact: jsonbytes_to_iecdata uses json_bytes_find_key for key lookup
        # string fields use json_bytes_find_key with byte array key
        # Arrange / Act
        fn = gen({'name': 'abc'}).split('function JsonRoot_jsonbytes_to_iecdata')[1].split('end_function')[0]
        # Assert
        assert 'json_bytes_find_key(dat:=bytes, key:=key_name, start_index:=si, end_index:=ei, eno=>eno)' in fn

    def test_data_to_jsonbytes_uses_root_type(self):
        # Fact: iecdata_to_jsonbytes declares var_in_out parameters with the root type
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert 'var_in_out data: JsonRoot_t; end_var' in out
        assert 'var_in_out bytes: array[*] of byte; end_var' in out


class TestDataToJson:
    def test_string_field(self):
        # Fact: iecdata_to_jsontext generates correct string field serialization
        # Arrange / Act
        out = gen({'name': 'abc'})
        # Assert
        assert "txt := '{';" in out
        assert "txt := concat(txt, '\"');" in out
        assert 'json_escape(data.name)' in out

    def test_numeric_field(self):
        # Fact: iecdata_to_jsontext generates correct numeric field serialization
        # Arrange / Act
        out = gen({'val': 3.14})
        # Assert
        assert 'sv := lreal_to_string(data.val);' in out
        assert 'txt := concat(txt, sv);' in out

    def test_bool_field(self):
        # Fact: iecdata_to_jsontext generates correct boolean field serialization
        # Arrange / Act
        out = gen({'flag': True})
        # Assert
        assert 'if data.flag then' in out
        assert "txt := concat(txt, 'true');" in out
        assert "txt := concat(txt, 'false');" in out

    def test_nested_object(self):
        # Fact: iecdata_to_jsontext generates correct nested object serialization
        # Arrange / Act
        out = gen({'pos': {'x': 1.0, 'y': 2.0}})
        # Assert
        assert "txt := concat(txt, '{');" in out
        assert 'sv := lreal_to_string(data.pos.x);' in out
        assert 'sv := lreal_to_string(data.pos.y);' in out

    def test_array_field(self):
        # Fact: iecdata_to_jsontext generates correct array field serialization
        # Arrange / Act
        out = gen({'nums': [1, 2, 3]})
        # Assert
        assert "txt := concat(txt, '[');" in out
        assert 'sv := dint_to_string(data.nums[0]);' in out
        assert 'sv := dint_to_string(data.nums[2]);' in out
        assert "txt := concat(txt, ']');" in out

    def test_var_in_out_declared(self):
        # Fact: iecdata_to_jsontext declares var_in_out parameters with the root type
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert 'var_in_out data: JsonRoot_t; end_var' in out
        assert 'var_in_out txt: string[JSON_STRING_SIZE]; end_var' in out

    def test_negative_int_field(self):
        # Fact: iecdata_to_jsontext handles negative integer fields correctly
        # Arrange / Act
        out = gen({'val': -42})
        # Assert
        assert 'val: dint;' in out
        assert 'dint_to_string(data.val)' in out

    def test_scientific_notation_field(self):
        # Fact: iecdata_to_jsontext handles scientific notation float fields
        # Arrange / Act
        out = gen({'val': 1e-5})
        # Assert
        assert 'val: lreal;' in out
        assert 'lreal_to_string(data.val)' in out

    def test_function_name(self):
        # Fact: iecdata_to_jsontext function is generated with the correct name
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert 'function JsonRoot_iecdata_to_jsontext' in out
        assert 'end_function' in out


class TestJsonToData:
    def test_string_extraction(self):
        # Fact: jsontext_to_iecdata generates correct string field extraction
        # Arrange / Act
        out = gen({'name': 'abc'})
        # Assert
        assert "json_find_key(dat:=txt, key:='name')" in out
        assert 'json_unescape(in:=mid(txt,' in out
        assert 'data.name :=' in out

    def test_numeric_extraction(self):
        # Fact: jsontext_to_iecdata generates correct numeric field extraction using string_to_dint
        # Arrange / Act
        out = gen({'count': 42})
        # Assert
        assert "json_extract_scalar(dat:=txt, key:='count', sv:=sv, eno=>eno)" in out
        assert 'string_to_dint(sv)' in out

    def test_lreal_extraction(self):
        # Fact: jsontext_to_iecdata generates correct lreal field extraction using string_to_lreal
        # Arrange / Act
        out = gen({'val': 1.0})
        # Assert
        assert "json_extract_scalar(dat:=txt, key:='val', sv:=sv, eno=>eno)" in out
        assert 'string_to_lreal(sv)' in out

    def test_bool_extraction(self):
        # Fact: jsontext_to_iecdata generates correct boolean field extraction
        # Arrange / Act
        out = gen({'flag': True})
        # Assert
        assert "json_extract_scalar(dat:=txt, key:='flag', sv:=sv, eno=>eno)" in out
        assert "sv = 'true'" in out

    def test_nested_struct_extraction(self):
        # Fact: jsontext_to_iecdata handles nested struct extraction with a sub-function call
        # Arrange / Act
        out = gen({'pos': {'x': 1.0}})
        # root function uses json_find_block + sub-function call
        # Assert
        assert "json_find_block(dat:=txt, key:='pos', open_ch:='{', close_ch:='}', block:=jblk1, eno=>eno)" in out
        assert 'private_JsonRoot_pos_t_jsontext_to_iecdata(txt:=jblk1, data:=data.pos, eno=>eno)' in out
        # sub-function uses json_extract_scalar for the numeric field
        assert "json_extract_scalar(dat:=txt, key:='x', sv:=sv, eno=>eno)" in out

    def test_array_extraction(self):
        # Fact: jsontext_to_iecdata generates correct array element extraction
        # Arrange / Act
        out = gen({'tags': ['a', 'b']})
        # Assert
        assert "json_find_block(dat:=txt, key:='tags', open_ch:='[', close_ch:=']', block:=jblk1, eno=>eno)" in out
        assert 'data.tags[0] :=' in out
        assert 'data.tags[1] :=' in out

    def test_var_temp_depth_when_nested(self):
        # Fact: jsontext_to_iecdata does not declare a depth variable for struct nesting
        # Arrange / Act
        out = gen({'pos': {'x': 1.0}})
        # pure struct nesting no longer needs depth in root jsontext_to_data
        jsontext_fn = out.split('function JsonRoot_jsontext_to_iecdata')[1].split('end_function')[0]
        # Assert
        assert 'depth: dint;' not in jsontext_fn

    def test_var_temp_no_depth_when_flat(self):
        # Fact: jsontext_to_iecdata does not declare a depth variable for flat structures
        # Arrange / Act
        out = gen({'x': 1, 'name': 'a'})
        jsontext_fn = out.split('function JsonRoot_jsontext_to_iecdata')[1].split('end_function')[0]
        # Assert
        assert 'depth: dint;' not in jsontext_fn

    def test_var_in_out_declared(self):
        # Fact: jsontext_to_iecdata declares var_in_out parameters with the root type
        # Arrange / Act
        out = gen({'x': 1})
        # Assert
        assert 'var_in_out txt: string[JSON_STRING_SIZE]; end_var' in out
        assert 'var_in_out data: JsonRoot_t; end_var' in out


class TestCustomOptions:
    def test_custom_prefix_suffix(self):
        # Fact: custom prefix and suffix are applied to generated type and function names
        # Arrange / Act
        out = gen({'x': 1}, prefix='Sensor', suffix='_data')
        # Assert
        assert 'Sensor_data: struct' in out

    def test_custom_int_type(self):
        # Fact: custom integer type is used in field declarations and conversion functions
        # Arrange / Act
        out = gen({'n': 1}, int_type='lint')
        # Assert
        assert 'n: lint;' in out
        assert 'sv := lint_to_string(data.n);' in out
        assert 'string_to_lint(sv)' in out

    def test_custom_string_type(self):
        # Fact: custom string type is used in field declarations
        # Arrange / Act
        out = gen({'name': 'abc'}, string_type='string[128]')
        # Assert
        assert 'string[128]' in out

    def test_bare_string_type(self):
        # Fact: bare string type without brackets is applied to field declarations
        # Arrange / Act
        out = gen({'name': 'abc'}, string_type='string')
        # Assert
        assert 'name: string;' in out
        assert 'string[' not in out.split('end_type')[0]

    def test_custom_json_len(self):
        # Fact: custom json_len is reflected in the generated string size
        # Arrange
        model = analyze_json({'x': 1})
        # Act
        out = IecGenerator(json_len='1024').generate(model)
        # Assert
        assert 'string[1024]' in out


# ---------------------------------------------------------------------------
# Input file smoke tests — load tests/inputs/*.json and verify generation
# ---------------------------------------------------------------------------

import json as _json_mod
from pathlib import Path

_INPUTS_DIR = Path(__file__).parent / 'inputs'

_INPUT_CASES = [
    ('simple',         'Simple'),
    ('various',        'Various'),
    ('nested_obj_3',   'NestedObj3'),
    ('multiple_ary_3', 'MultipleAry3'),
    ('simple_ary',     'SimpleAry'),
    ('structure_ary',  'StructureAry'),
]


def _load(stem):
    """Load JSON file and return dict (whitespace/newlines stripped by json.load)."""
    return _json_mod.loads((_INPUTS_DIR / (stem + '.json')).read_text(encoding='utf-8'))


@pytest.mark.parametrize('stem,root_name', _INPUT_CASES, ids=[c[0] for c in _INPUT_CASES])
class TestInputFiles:
    def test_type_definition_generated(self, stem, root_name):
        # Fact: type definition is generated for each input file
        # Arrange / Act
        out = gen(_load(stem), prefix=root_name)
        # Assert
        assert root_name + '_t: struct' in out
        assert 'end_struct;' in out
        assert 'end_type' in out

    def test_functions_generated(self, stem, root_name):
        # Fact: all four IEC functions are generated for each input file
        # Arrange / Act
        out = gen(_load(stem), prefix=root_name)
        # Assert
        assert 'function ' + root_name + '_iecdata_to_jsontext' in out
        assert 'function ' + root_name + '_jsontext_to_iecdata' in out
        assert 'function ' + root_name + '_iecdata_to_jsonbytes' in out
        assert 'function ' + root_name + '_jsonbytes_to_iecdata' in out

    def test_helper_functions_included(self, stem, root_name):
        # Fact: helper functions are included for each input file
        # Arrange / Act
        out = gen(_load(stem), prefix=root_name)
        # Assert
        assert 'function json_escape' in out
        assert 'function json_unescape' in out
        assert 'function json_char_from_asciicharcode' in out
        assert 'function json_asciicharcode' in out
