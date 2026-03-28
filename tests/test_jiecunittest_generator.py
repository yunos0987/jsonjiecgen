# coding: utf-8
import subprocess
import sys
import os
from pathlib import Path

import pytest

_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, _SRC)

from analyzer import analyze_json, analyze_schema
from jiecunittest_generator import JiecUnitGenerator

INPUTS_DIR = Path(__file__).parent / 'inputs'
MAIN = Path(__file__).parent.parent / 'src' / 'main.py'


def gen_test(data_dict, pou_file='out.txt', json_len='4096', **kw):
    model = analyze_json(data_dict, **kw)
    return JiecUnitGenerator(pou_filename=pou_file, json_len=json_len).generate(model, data_dict)


def gen_test_schema(schema_dict, pou_file='out.txt', **kw):
    model = analyze_schema(schema_dict, **kw)
    return JiecUnitGenerator(pou_filename=pou_file).generate(model, None)


# ---------------------------------------------------------------------------
# Header and configuration
# ---------------------------------------------------------------------------

class TestHeader:
    def test_jiecunit_include_present(self):
        out = gen_test({'x': 1})
        assert '{#include <jiecunit.txt>}' in out

    def test_pou_include_uses_given_filename(self):
        out = gen_test({'x': 1}, pou_file='simple.txt')
        assert '{#include <simple.txt>}' in out

    def test_pou_include_basename_only(self):
        out = gen_test({'x': 1}, pou_file='myfile.txt')
        assert '{#include <myfile.txt>}' in out
        assert '/' not in out.split('{#include <myfile.txt>}')[0].split('\n')[-1]

    def test_configuration_block_present(self):
        out = gen_test({'x': 1})
        assert 'DEFINE_CONFIGURATION(' in out

    def test_both_test_names_listed(self):
        out = gen_test({'x': 1})
        assert "'test_JsonRoot_jsonstr_to_data'" in out
        assert "'test_JsonRoot_data_to_jsonstr'" in out


# ---------------------------------------------------------------------------
# test_jsonstr_to_data block
# ---------------------------------------------------------------------------

class TestTestJsonToData:
    def test_block_opens_and_closes(self):
        out = gen_test({'x': 1})
        assert 'TEST_S(test_JsonRoot_jsonstr_to_data)' in out
        assert 'END_TEST_S' in out

    def test_var_json_declared(self):
        out = gen_test({'x': 1})
        assert 'json: string[4096];' in out

    def test_var_data_declared(self):
        out = gen_test({'x': 1})
        assert 'data: JsonRoot_t;' in out

    def test_json_assignment_present(self):
        out = gen_test({'x': 1})
        assert "json := '{\"x\":1}';" in out

    def test_jsonstr_to_data_call(self):
        out = gen_test({'x': 1})
        assert 'jsonstr_to_data(json, data);' in out

    def test_st_delimiters(self):
        out = gen_test({'x': 1})
        assert '{st}' in out
        assert '{end}' in out

    def test_string_assertion(self):
        out = gen_test({'name': 'sensor1'})
        assert "EXPECT_EQ_STRING('sensor1', data.name);" in out

    def test_float_assertion_lreal(self):
        out = gen_test({'v': 3.14})
        assert 'EXPECT_NEAR(3.14, data.v, 0.001);' in out

    def test_int_assertion_dint(self):
        out = gen_test({'n': 42})
        assert 'EXPECT_EQ_DINT(42, data.n);' in out

    def test_int_assertion_lint(self):
        out = gen_test({'n': 42}, int_type='lint')
        assert 'EXPECT_EQ_LINT(42, data.n);' in out

    def test_bool_true_assertion(self):
        out = gen_test({'active': True})
        assert 'EXPECT_TRUE(data.active);' in out

    def test_bool_false_assertion(self):
        out = gen_test({'active': False})
        assert 'EXPECT_FALSE(data.active);' in out

    def test_nested_struct_assertion(self):
        out = gen_test({'pos': {'x': 1.0, 'y': 2.0}})
        assert 'EXPECT_NEAR(1.0, data.pos.x, 0.001);' in out
        assert 'EXPECT_NEAR(2.0, data.pos.y, 0.001);' in out

    def test_array_string_assertion(self):
        out = gen_test({'tags': ['a', 'b', 'c']})
        assert "EXPECT_EQ_STRING('a', data.tags[0]);" in out
        assert "EXPECT_EQ_STRING('b', data.tags[1]);" in out
        assert "EXPECT_EQ_STRING('c', data.tags[2]);" in out

    def test_array_int_assertion(self):
        out = gen_test({'counts': [10, 20, 30]})
        assert 'EXPECT_EQ_DINT(10, data.counts[0]);' in out
        assert 'EXPECT_EQ_DINT(20, data.counts[1]);' in out
        assert 'EXPECT_EQ_DINT(30, data.counts[2]);' in out


# ---------------------------------------------------------------------------
# test_data_to_jsonstr block
# ---------------------------------------------------------------------------

class TestTestDataToJson:
    def test_block_opens_and_closes(self):
        out = gen_test({'x': 1})
        assert 'TEST_S(test_JsonRoot_data_to_jsonstr)' in out
        assert 'END_TEST_S' in out

    def test_var_data_declared(self):
        out = gen_test({'x': 1})
        assert 'data: JsonRoot_t;' in out

    def test_var_data_rt_declared(self):
        out = gen_test({'x': 1})
        assert 'data_rt: JsonRoot_t;' in out

    def test_var_json_declared(self):
        out = gen_test({'x': 1}, json_len='1024')
        assert 'json: string[1024];' in out

    def test_string_assignment(self):
        out = gen_test({'name': 'sensor1'})
        assert "data.name := 'sensor1';" in out

    def test_float_assignment(self):
        out = gen_test({'v': 3.14})
        assert 'data.v := 3.14;' in out

    def test_int_assignment(self):
        out = gen_test({'n': 42})
        assert 'data.n := 42;' in out

    def test_bool_true_assignment(self):
        out = gen_test({'active': True})
        assert 'data.active := true;' in out

    def test_bool_false_assignment(self):
        out = gen_test({'active': False})
        assert 'data.active := false;' in out

    def test_data_to_jsonstr_call(self):
        out = gen_test({'x': 1})
        assert 'data_to_jsonstr(data, json);' in out

    def test_jsonstr_to_data_roundtrip_call(self):
        out = gen_test({'x': 1})
        assert 'jsonstr_to_data(json, data_rt);' in out

    def test_roundtrip_assertions_on_data_rt(self):
        out = gen_test({'n': 42, 'name': 'abc'})
        assert 'EXPECT_EQ_DINT(42, data_rt.n);' in out
        assert "EXPECT_EQ_STRING('abc', data_rt.name);" in out

    def test_nested_struct_assignment(self):
        out = gen_test({'pos': {'x': 1.0}})
        assert 'data.pos.x := 1.0;' in out

    def test_array_assignment(self):
        out = gen_test({'tags': ['a', 'b']})
        assert "data.tags[0] := 'a';" in out
        assert "data.tags[1] := 'b';" in out


# ---------------------------------------------------------------------------
# Schema input (json_values=None, use defaults)
# ---------------------------------------------------------------------------

class TestSchemaInput:
    _schema = {
        'type': 'object',
        'properties': {
            'id':      {'type': 'integer'},
            'label':   {'type': 'string'},
            'score':   {'type': 'number'},
            'enabled': {'type': 'boolean'},
            'items':   {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 2},
        },
    }

    def test_int_default_assertion(self):
        out = gen_test_schema(self._schema)
        assert 'EXPECT_EQ_DINT(0, data.id);' in out

    def test_string_default_assertion(self):
        out = gen_test_schema(self._schema)
        assert "EXPECT_EQ_STRING('', data.label);" in out

    def test_float_default_assertion(self):
        out = gen_test_schema(self._schema)
        assert 'EXPECT_NEAR(0.0, data.score, 0.001);' in out

    def test_bool_default_assertion(self):
        out = gen_test_schema(self._schema)
        assert 'EXPECT_FALSE(data.enabled);' in out

    def test_array_default_assertion(self):
        out = gen_test_schema(self._schema)
        assert "EXPECT_EQ_STRING('', data.items[0]);" in out
        assert "EXPECT_EQ_STRING('', data.items[1]);" in out

    def test_json_string_uses_defaults(self):
        out = gen_test_schema(self._schema)
        assert '{"id":0,"label":"","score":0.0,"enabled":false,"items":["",""]}' in out


# ---------------------------------------------------------------------------
# IEC string literal escaping
# ---------------------------------------------------------------------------

class TestIecStringEscaping:
    def test_single_quote_escaped(self):
        out = gen_test({'s': "it's"})
        assert "EXPECT_EQ_STRING('it$'s', data.s);" in out

    def test_dollar_sign_escaped(self):
        out = gen_test({'s': '$100'})
        assert "EXPECT_EQ_STRING('$$100', data.s);" in out

    def test_double_quote_not_escaped(self):
        out = gen_test({'s': 'say "hi"'})
        assert '''EXPECT_EQ_STRING('say "hi"', data.s);''' in out

    def test_empty_string(self):
        out = gen_test({'s': ''})
        assert "EXPECT_EQ_STRING('', data.s);" in out

    def test_json_string_single_quote_escaped(self):
        # A string value containing ' must be escaped in the json assignment too
        out = gen_test({'s': "it's"})
        # The JSON string {"s":"it's"} must be represented as 'it$'s' in IEC
        assert "$'" in out


# ---------------------------------------------------------------------------
# Escape tests block
# ---------------------------------------------------------------------------

class TestEscapeBlock:
    def test_json_escape_block_present_when_has_string(self):
        out = gen_test({'name': 'abc'})
        assert 'TEST_S(test_json_escape)' in out

    def test_json_unescape_block_present_when_has_string(self):
        out = gen_test({'name': 'abc'})
        assert 'TEST_S(test_json_unescape)' in out

    def test_escape_blocks_always_present(self):
        out = gen_test({'n': 1, 'f': 2.0, 'b': True})
        assert 'TEST_S(test_json_escape)' in out
        assert 'TEST_S(test_json_unescape)' in out
        

    def test_escape_test_names_in_configuration(self):
        out = gen_test({'name': 'abc'})
        assert "'test_json_escape'" in out
        assert "'test_json_unescape'" in out
        

    def test_escape_test_names_always_present(self):
        out = gen_test({'n': 1})
        assert "'test_json_escape'" in out
        assert "'test_json_unescape'" in out
        

    def test_json_escape_doublequote(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('\"');" in out
        assert "EXPECT_EQ_STRING('\\\"', res);" in out

    def test_json_escape_backslash(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('\\');" in out
        assert "EXPECT_EQ_STRING('\\\\', res);" in out

    def test_json_escape_tab(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('$t');" in out
        assert "EXPECT_EQ_STRING('\\t', res);" in out

    def test_json_escape_newline(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('$n');" in out
        assert "EXPECT_EQ_STRING('\\n', res);" in out

    def test_json_escape_cr(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('$r');" in out
        assert "EXPECT_EQ_STRING('\\r', res);" in out

    def test_json_escape_backspace(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('$08');" in out
        assert "EXPECT_EQ_STRING('\\b', res);" in out

    def test_json_escape_formfeed(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('$0c');" in out
        assert "EXPECT_EQ_STRING('\\f', res);" in out

    def test_json_escape_control_uXXXX(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_escape('$07');" in out
        assert "EXPECT_EQ_STRING('\\u0007', res);" in out

    def test_json_unescape_doublequote(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\\"');" in out
        assert "EXPECT_EQ_STRING('\"', res);" in out

    def test_json_unescape_backslash(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\\\');" in out
        assert "EXPECT_EQ_STRING('\\', res);" in out

    def test_json_unescape_tab(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\t');" in out
        assert "EXPECT_EQ_STRING('$t', res);" in out

    def test_json_unescape_newline(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\n');" in out
        assert "EXPECT_EQ_STRING('$n', res);" in out

    def test_json_unescape_cr(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\r');" in out
        assert "EXPECT_EQ_STRING('$r', res);" in out

    def test_json_unescape_backspace(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\b');" in out
        assert "EXPECT_EQ_STRING('$08', res);" in out

    def test_json_unescape_formfeed(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\f');" in out
        assert "EXPECT_EQ_STRING('$0c', res);" in out

    def test_json_unescape_xHH_printable(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\x41');" in out
        assert "EXPECT_EQ_STRING('A', res);" in out

    def test_json_unescape_uXXXX_printable(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\u0041');" in out
        assert "EXPECT_EQ_STRING('A', res);" in out

    def test_json_unescape_uXXXX_control(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\u000a');" in out
        assert "EXPECT_EQ_STRING('$n', res);" in out

    def test_json_unescape_uXXXX_doublequote(self):
        out = gen_test({'name': 'abc'})
        assert "res := json_unescape('\\u0022');" in out
        assert "EXPECT_EQ_STRING('\"', res);" in out

    def test_string_type_stored_in_model(self):
        model = analyze_json({'label': 'x'}, string_type='string[64]')
        f = model.root.fields[0]
        assert f.type.iec_type == 'string[64]'

    def test_eight_end_test_s_blocks(self):
        out = gen_test({'name': 'abc'})
        # jsonstr_to_data, data_to_jsonstr, jsonbytes_to_data, data_to_jsonbytes,
        # json_char_from_asciicharcode, json_asciicharcode,
        # json_bytes_insert_str, json_find_key, json_bytes_find_key,
        # json_escape, json_unescape
        assert out.count('END_TEST_S') == 11


# ---------------------------------------------------------------------------
# Extra perspectives merged into base TEST_S blocks (numbered vars)
# ---------------------------------------------------------------------------

class TestExtraBlocks:
    _data = {'name': 'sensor1', 'value': 3.14, 'count': 42, 'active': True}

    # --- extra names are NOT in configuration (merged into base block) ---

    def test_extra_names_not_in_configuration(self):
        out = gen_test(self._data)
        assert "'test_JsonRoot_jsonstr_to_data_str_escaped'" not in out
        assert "'test_JsonRoot_data_to_jsonstr_str_escaped'" not in out

    # --- numbered vars are declared ---

    def test_jtd_numbered_json_vars_declared(self):
        out = gen_test(self._data)
        assert 'json1: string[4096];' in out
        assert 'json6: string[4096];' in out

    def test_jtd_numbered_data_vars_declared(self):
        out = gen_test(self._data)
        assert 'data1: JsonRoot_t;' in out
        assert 'data6: JsonRoot_t;' in out

    def test_dtj_numbered_data_and_rt_vars_declared(self):
        out = gen_test(self._data)
        assert 'data1_rt: JsonRoot_t;' in out
        assert 'data6_rt: JsonRoot_t;' in out

    # --- no numbered vars when types are absent ---

    def test_no_numbered_vars_when_only_int_field(self):
        out = gen_test({'n': 1})
        # int alone → 1 extra (int_negative): json1 exists but json2 does not
        assert 'json1:' in out
        assert 'json2:' not in out

    def test_no_numbered_vars_when_no_optional_types(self):
        out = gen_test({'b': True})
        assert 'json1:' not in out

    # --- str_escaped (data1 / data1_rt) ---

    def test_jtd_str_escaped_json(self):
        out = gen_test(self._data)
        assert 'hello\\"world' in out  # JSON encoding of hello"world

    def test_jtd_str_escaped_assertion_on_data1(self):
        out = gen_test(self._data)
        assert "EXPECT_EQ_STRING('hello\"world', data1.name);" in out

    def test_dtj_str_escaped_assignment_on_data1(self):
        out = gen_test(self._data)
        assert "data1.name := 'hello\"world';" in out

    def test_dtj_str_escaped_assertion_on_data1_rt(self):
        out = gen_test(self._data)
        assert "EXPECT_EQ_STRING('hello\"world', data1_rt.name);" in out

    # --- str_empty (data2 / data2_rt) ---

    def test_jtd_str_empty_assertion_on_data2(self):
        out = gen_test(self._data)
        assert "EXPECT_EQ_STRING('', data2.name);" in out

    def test_dtj_str_empty_assignment_on_data2(self):
        out = gen_test(self._data)
        assert "data2.name := '';" in out

    # --- num_integer (data3 / data3_rt) ---

    def test_jtd_num_integer_assertion_on_data3(self):
        out = gen_test(self._data)
        assert 'EXPECT_NEAR(42.0, data3.value, 0.001);' in out

    def test_dtj_num_integer_assignment_on_data3(self):
        out = gen_test(self._data)
        assert 'data3.value := 42.0;' in out

    # --- num_exponential (data4 / data4_rt) ---

    def test_jtd_num_exponential_json_uses_1e3(self):
        out = gen_test(self._data)
        assert '1e3' in out

    def test_jtd_num_exponential_assertion_on_data4(self):
        out = gen_test(self._data)
        assert 'EXPECT_NEAR(1000.0, data4.value, 0.001);' in out

    def test_dtj_num_exponential_assignment_on_data4(self):
        out = gen_test(self._data)
        assert 'data4.value := 1000.0;' in out

    # --- num_negative (data5 / data5_rt) ---

    def test_jtd_num_negative_assertion_on_data5(self):
        out = gen_test(self._data)
        assert 'EXPECT_NEAR(-1.5, data5.value, 0.001);' in out

    def test_dtj_num_negative_assignment_on_data5(self):
        out = gen_test(self._data)
        assert 'data5.value := -1.5;' in out

    # --- int_negative (data6 / data6_rt) ---

    def test_jtd_int_negative_assertion_on_data6(self):
        out = gen_test(self._data)
        assert 'EXPECT_EQ_DINT(-42, data6.count);' in out

    def test_dtj_int_negative_assignment_on_data6(self):
        out = gen_test(self._data)
        assert 'data6.count := -42;' in out

    def test_dtj_int_negative_assertion_on_data6_rt(self):
        out = gen_test(self._data)
        assert 'EXPECT_EQ_DINT(-42, data6_rt.count);' in out

    # --- total block count (merged → only 4 TEST_S with strings) ---

    def test_total_end_test_s_count_with_string(self):
        out = gen_test(self._data)
        # 4 model tests + 7 helper tests = 11
        assert out.count('END_TEST_S') == 11

    def test_total_end_test_s_count_no_string(self):
        out = gen_test({'n': 1, 'v': 2.5})
        # same 11 blocks (helpers always included)
        assert out.count('END_TEST_S') == 11


# ---------------------------------------------------------------------------
# Custom options
# ---------------------------------------------------------------------------

class TestCustomOptions:
    def test_custom_json_len(self):
        out = gen_test({'x': 1}, json_len='1024')
        assert 'string[1024]' in out

    def test_custom_pou_filename(self):
        out = gen_test({'x': 1}, pou_file='sensor.txt')
        assert '{#include <sensor.txt>}' in out

    def test_custom_int_type_lint(self):
        out = gen_test({'n': 1}, int_type='lint')
        assert 'EXPECT_EQ_LINT(1, data.n);' in out

    def test_custom_int_type_udint(self):
        out = gen_test({'n': 5}, int_type='udint')
        assert 'EXPECT_EQ_UDINT(5, data.n);' in out

