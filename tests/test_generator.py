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
        out = gen({'x': 1, 'y': 2.0})
        assert 'JsonRoot_t: struct' in out
        assert 'x: dint;' in out
        assert 'y: lreal;' in out
        assert 'end_struct;' in out
        assert 'end_type' in out

    def test_nested_struct_leaf_first(self):
        out = gen({'pos': {'x': 1.0}})
        pos_idx = out.index('JsonRoot_pos_t: struct')
        root_idx = out.index('JsonRoot_t: struct')
        assert pos_idx < root_idx  # leaf-first order

    def test_array_type(self):
        out = gen({'tags': ['a', 'b']})
        assert 'tags: array[0..1] of string[256];' in out

    def test_single_element_array_bounds(self):
        out = gen({'nums': [42]})
        assert 'nums: array[0..0] of dint;' in out

    def test_helpers_always_included(self):
        out = gen({'n': 1, 'f': 2.0, 'b': True})
        assert 'function json_escape' in out
        assert 'function json_unescape' in out
        assert 'function json_char_from_asciicharcode' in out
        assert 'function json_asciicharcode' in out


class TestJsonHelpers:
    def test_escape_sequences_present(self):
        out = gen({'x': 1})
        assert "ch = '$t'  then result := concat(result, '\\t')" in out
        assert "ch = '$n'  then result := concat(result, '\\n')" in out

    def test_sv_uses_json_string_size(self):
        out = gen({'name': 'abc'})
        assert 'sv: string[JSON_STRING_SIZE];' in out

    def test_sv_uses_json_string_size_when_no_string_field(self):
        out = gen({'x': 1})
        assert 'sv: string[JSON_STRING_SIZE];' in out


class TestRawjsonFunctions:
    def test_data_to_jsonbytes_always_generated(self):
        assert 'function JsonRoot_data_to_jsonbytes' in gen({'x': 1})

    def test_jsonbytes_to_data_always_generated(self):
        assert 'function JsonRoot_jsonbytes_to_data' in gen({'x': 1})

    def test_data_to_jsonbytes_no_intermediate_string(self):
        out = gen({'x': 1})
        assert 'JsonRoot_data_to_jsonstr(data, json);' not in out
        assert 'json: string[' not in out.split('function JsonRoot_data_to_jsonbytes')[1].split('end_function')[0]

    def test_data_to_jsonbytes_uses_json_bytes_insert_str(self):
        assert 'json_bytes_insert_str(json,' in gen({'x': 1})

    def test_data_to_jsonbytes_null_terminates(self):
        assert 'json[raw_ci] := 0' in gen({'x': 1})

    def test_data_to_jsonbytes_numeric_field(self):
        out = gen({'x': 1})
        assert "raw_ci := json_bytes_insert_str(json, raw_ci, sv);" in out

    def test_data_to_jsonbytes_bool_field(self):
        out = gen({'flag': True})
        assert "raw_ci := json_bytes_insert_str(json, raw_ci, 'true');" in out
        assert "raw_ci := json_bytes_insert_str(json, raw_ci, 'false');" in out

    def test_data_to_jsonbytes_string_field(self):
        out = gen({'name': 'abc'})
        assert 'json_escape(data.name)' in out

    def test_jsonbytes_to_data_uses_char_from_code(self):
        fn = gen({'x': 1}).split('function JsonRoot_jsonbytes_to_data')[1].split('end_function')[0]
        assert 'json_char_from_asciicharcode(code:=byte_to_dint(json[raw_ci]), eno=>eno)' in fn

    def test_jsonbytes_to_data_no_intermediate_string(self):
        fn = gen({'x': 1}).split('function JsonRoot_jsonbytes_to_data')[1].split('end_function')[0]
        assert 'jstr:' not in fn
        assert 'JsonRoot_jsonstr_to_data' not in fn

    def test_jsonbytes_to_data_uses_bytes_find_key(self):
        fn = gen({'x': 1}).split('function JsonRoot_jsonbytes_to_data')[1].split('end_function')[0]
        assert "json_bytes_find_key(json, 'x')" in fn

    def test_data_to_jsonbytes_uses_root_type(self):
        out = gen({'x': 1})
        assert 'var_in_out data: JsonRoot_t; end_var' in out
        assert 'var_in_out json: array[*] of byte; end_var' in out


class TestDataToJson:
    def test_string_field(self):
        out = gen({'name': 'abc'})
        assert "json := '{';" in out
        assert "json := concat(json, '\"');" in out
        assert 'json_escape(data.name)' in out

    def test_numeric_field(self):
        out = gen({'val': 3.14})
        assert 'sv := lreal_to_string(data.val);' in out
        assert 'json := concat(json, sv);' in out

    def test_bool_field(self):
        out = gen({'flag': True})
        assert 'if data.flag then' in out
        assert "json := concat(json, 'true');" in out
        assert "json := concat(json, 'false');" in out

    def test_nested_object(self):
        out = gen({'pos': {'x': 1.0, 'y': 2.0}})
        assert "json := concat(json, '{');" in out
        assert 'sv := lreal_to_string(data.pos.x);' in out
        assert 'sv := lreal_to_string(data.pos.y);' in out

    def test_array_field(self):
        out = gen({'nums': [1, 2, 3]})
        assert "json := concat(json, '[');" in out
        assert 'sv := dint_to_string(data.nums[0]);' in out
        assert 'sv := dint_to_string(data.nums[2]);' in out
        assert "json := concat(json, ']');" in out

    def test_var_in_out_declared(self):
        out = gen({'x': 1})
        assert 'var_in_out data: JsonRoot_t; end_var' in out
        assert 'var_in_out json: string[1024]; end_var' in out

    def test_negative_int_field(self):
        out = gen({'val': -42})
        assert 'val: dint;' in out
        assert 'dint_to_string(data.val)' in out

    def test_scientific_notation_field(self):
        out = gen({'val': 1e-5})
        assert 'val: lreal;' in out
        assert 'lreal_to_string(data.val)' in out

    def test_function_name(self):
        out = gen({'x': 1})
        assert 'function JsonRoot_data_to_jsonstr' in out
        assert 'end_function' in out


class TestJsonToData:
    def test_string_extraction(self):
        out = gen({'name': 'abc'})
        assert "json_find_key(json, 'name')" in out
        assert 'json_unescape(in:=mid(json,' in out
        assert 'data.name :=' in out

    def test_numeric_extraction(self):
        out = gen({'count': 42})
        assert "json_find_key(json, 'count')" in out
        assert 'pos := pos + 8;' in out
        assert 'string_to_dint(mid(json,' in out

    def test_lreal_extraction(self):
        out = gen({'val': 1.0})
        assert 'string_to_lreal(mid(json,' in out

    def test_bool_extraction(self):
        out = gen({'flag': True})
        assert "json_find_key(json, 'flag')" in out
        assert "= 'true'" in out

    def test_nested_struct_extraction(self):
        out = gen({'pos': {'x': 1.0}})
        assert "json_find_key(json, 'pos')" in out
        assert 'depth := 1;' in out
        assert 'while depth > 0 do' in out
        assert 'jblk1 := mid(json,' in out
        assert "json_find_key(jblk1, 'x')" in out

    def test_array_extraction(self):
        out = gen({'tags': ['a', 'b']})
        assert "json_find_key(json, 'tags')" in out
        assert 'data.tags[0] :=' in out
        assert 'data.tags[1] :=' in out

    def test_var_temp_depth_when_nested(self):
        out = gen({'pos': {'x': 1.0}})
        # depth: dint; appears in jsonstr_to_data var_temp for nested struct
        jsonstr_fn = out.split('function JsonRoot_jsonstr_to_data')[1].split('end_function')[0]
        assert 'depth: dint;' in jsonstr_fn

    def test_var_temp_no_depth_when_flat(self):
        out = gen({'x': 1, 'name': 'a'})
        # flat struct: jsonstr_to_data should not declare depth in its own var_temp
        jsonstr_fn = out.split('function JsonRoot_jsonstr_to_data')[1].split('end_function')[0]
        assert 'depth: dint;' not in jsonstr_fn

    def test_var_in_out_declared(self):
        out = gen({'x': 1})
        assert 'var_in_out json: string[1024]; end_var' in out
        assert 'var_in_out data: JsonRoot_t; end_var' in out


class TestCustomOptions:
    def test_custom_prefix_suffix(self):
        out = gen({'x': 1}, prefix='Sensor', suffix='_data')
        assert 'Sensor_data: struct' in out

    def test_custom_int_type(self):
        out = gen({'n': 1}, int_type='lint')
        assert 'n: lint;' in out
        assert 'sv := lint_to_string(data.n);' in out
        assert 'string_to_lint(mid(json,' in out

    def test_custom_string_type(self):
        out = gen({'name': 'abc'}, string_type='string[128]')
        assert 'string[128]' in out

    def test_bare_string_type(self):
        out = gen({'name': 'abc'}, string_type='string')
        assert 'name: string;' in out
        assert 'string[' not in out.split('end_type')[0]

    def test_custom_json_len(self):
        model = analyze_json({'x': 1})
        out = IecGenerator(json_len='1024').generate(model)
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
        out = gen(_load(stem), prefix=root_name)
        assert root_name + '_t: struct' in out
        assert 'end_struct;' in out
        assert 'end_type' in out

    def test_functions_generated(self, stem, root_name):
        out = gen(_load(stem), prefix=root_name)
        assert 'function ' + root_name + '_data_to_jsonstr' in out
        assert 'function ' + root_name + '_jsonstr_to_data' in out
        assert 'function ' + root_name + '_data_to_jsonbytes' in out
        assert 'function ' + root_name + '_jsonbytes_to_data' in out

    def test_helper_functions_included(self, stem, root_name):
        out = gen(_load(stem), prefix=root_name)
        assert 'function json_escape' in out
        assert 'function json_unescape' in out
        assert 'function json_char_from_asciicharcode' in out
        assert 'function json_asciicharcode' in out
