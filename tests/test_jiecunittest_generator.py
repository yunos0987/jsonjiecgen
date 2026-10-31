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
        # Fact: generated test file includes the jiecunit header
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert '{#include <jiecunit.txt>}' in out

    def test_pou_include_uses_given_filename(self):
        # Fact: generated test file includes the given POU filename
        # Arrange / Act
        out = gen_test({'x': 1}, pou_file='simple.txt')
        # Assert
        assert '{#include <simple.txt>}' in out

    def test_pou_include_basename_only(self):
        # Fact: POU include uses only the basename without path separators
        # Arrange / Act
        out = gen_test({'x': 1}, pou_file='myfile.txt')
        # Assert
        assert '{#include <myfile.txt>}' in out
        assert '/' not in out.split('{#include <myfile.txt>}')[0].split('\n')[-1]

    def test_configuration_block_present(self):
        # Fact: generated test file contains a DEFINE_CONFIGURATION block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'DEFINE_CONFIGURATION(' in out

    def test_both_test_names_listed(self):
        # Fact: both json-to-data and data-to-json test names are listed in the configuration
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert "'test_JsonRoot_jsontext_to_iecdata'" in out
        assert "'test_JsonRoot_iecdata_to_jsontext'" in out


# ---------------------------------------------------------------------------
# test_jsonstr_to_data block
# ---------------------------------------------------------------------------

class TestTestJsonToData:
    def test_block_opens_and_closes(self):
        # Fact: TEST_S block for jsontext_to_iecdata opens and closes correctly
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'TEST_S(test_JsonRoot_jsontext_to_iecdata)' in out
        assert 'END_TEST_S' in out

    def test_var_json_declared(self):
        # Fact: json string variable is declared in the jsontext_to_iecdata test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'txt: string[4096];' in out

    def test_var_data_declared(self):
        # Fact: data struct variable is declared in the jsontext_to_iecdata test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'data: JsonRoot_t;' in out

    def test_json_assignment_present(self):
        # Fact: json string is assigned the serialized test value in the test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert "txt := '{\"x\":1}';" in out

    def test_jsonstr_to_data_call(self):
        # Fact: jsontext_to_iecdata is called in the test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'jsontext_to_iecdata(txt, data);' in out

    def test_no_st_start_marker(self):
        # Fact: the st start marker is not emitted in the test code
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert '{st}' not in out

    def test_no_st_end_marker(self):
        # Fact: the st end marker is not emitted in the test code
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert '{end}' not in out

    def test_version_guard_condition(self):
        # Fact: the test code has a jiepp condition rejecting Jiecc older than 9.2.0
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert '{#if _JIECC and (_JIECC_FULL_VER < 90200)}' in out

    def test_version_guard_error(self):
        # Fact: the test code has a jiepp error directive for old Jiecc
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert '{#error Generated code requires Jiecc 9.2.0 or later.}' in out

    def test_version_guard_before_include(self):
        # Fact: the version guard precedes the first include directive in the test code
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert out.index('_JIECC_FULL_VER < 90200') < out.index('{#include')

    def test_version_guard_once(self):
        # Fact: the version guard appears exactly once in the test code
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert out.count('_JIECC_FULL_VER < 90200') == 1

    def test_string_assertion(self):
        # Fact: string field value is asserted with EXPECT_EQ_STRING
        # Arrange / Act
        out = gen_test({'name': 'sensor1'})
        # Assert
        assert "EXPECT_EQ_STRING('sensor1', data.name);" in out

    def test_float_assertion_lreal(self):
        # Fact: float field value is asserted with EXPECT_NEAR
        # Arrange / Act
        out = gen_test({'v': 3.14})
        # Assert
        assert 'EXPECT_NEAR(3.14, data.v, 0.001);' in out

    def test_int_assertion_dint(self):
        # Fact: integer field value is asserted with EXPECT_EQ_DINT
        # Arrange / Act
        out = gen_test({'n': 42})
        # Assert
        assert 'EXPECT_EQ_DINT(42, data.n);' in out

    def test_int_assertion_lint(self):
        # Fact: integer field with lint type is asserted with EXPECT_EQ_LINT
        # Arrange / Act
        out = gen_test({'n': 42}, int_type='lint')
        # Assert
        assert 'EXPECT_EQ_LINT(42, data.n);' in out

    def test_bool_true_assertion(self):
        # Fact: true boolean field is asserted with EXPECT_TRUE
        # Arrange / Act
        out = gen_test({'active': True})
        # Assert
        assert 'EXPECT_TRUE(data.active);' in out

    def test_bool_false_assertion(self):
        # Fact: false boolean field is asserted with EXPECT_FALSE
        # Arrange / Act
        out = gen_test({'active': False})
        # Assert
        assert 'EXPECT_FALSE(data.active);' in out

    def test_nested_struct_assertion(self):
        # Fact: nested struct float fields are asserted with EXPECT_NEAR
        # Arrange / Act
        out = gen_test({'pos': {'x': 1.0, 'y': 2.0}})
        # Assert
        assert 'EXPECT_NEAR(1.0, data.pos.x, 0.001);' in out
        assert 'EXPECT_NEAR(2.0, data.pos.y, 0.001);' in out

    def test_array_string_assertion(self):
        # Fact: string array elements are each asserted with EXPECT_EQ_STRING
        # Arrange / Act
        out = gen_test({'tags': ['a', 'b', 'c']})
        # Assert
        assert "EXPECT_EQ_STRING('a', data.tags[0]);" in out
        assert "EXPECT_EQ_STRING('b', data.tags[1]);" in out
        assert "EXPECT_EQ_STRING('c', data.tags[2]);" in out

    def test_array_int_assertion(self):
        # Fact: integer array elements are each asserted with EXPECT_EQ_DINT
        # Arrange / Act
        out = gen_test({'counts': [10, 20, 30]})
        # Assert
        assert 'EXPECT_EQ_DINT(10, data.counts[0]);' in out
        assert 'EXPECT_EQ_DINT(20, data.counts[1]);' in out
        assert 'EXPECT_EQ_DINT(30, data.counts[2]);' in out


# ---------------------------------------------------------------------------
# test_data_to_jsonstr block
# ---------------------------------------------------------------------------

class TestTestDataToJson:
    def test_block_opens_and_closes(self):
        # Fact: TEST_S block for iecdata_to_jsontext opens and closes correctly
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'TEST_S(test_JsonRoot_iecdata_to_jsontext)' in out
        assert 'END_TEST_S' in out

    def test_var_data_declared(self):
        # Fact: data struct variable is declared in the iecdata_to_jsontext test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'data: JsonRoot_t;' in out

    def test_var_data_rt_declared(self):
        # Fact: roundtrip data struct variable is declared in the test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'data_rt: JsonRoot_t;' in out

    def test_var_json_declared(self):
        # Fact: json string variable with custom size is declared in the test block
        # Arrange / Act
        out = gen_test({'x': 1}, json_len='1024')
        # Assert
        assert 'txt: string[1024];' in out

    def test_string_assignment(self):
        # Fact: string field is assigned the test value in the data struct
        # Arrange / Act
        out = gen_test({'name': 'sensor1'})
        # Assert
        assert "data.name := 'sensor1';" in out

    def test_float_assignment(self):
        # Fact: float field is assigned the test value in the data struct
        # Arrange / Act
        out = gen_test({'v': 3.14})
        # Assert
        assert 'data.v := 3.14;' in out

    def test_int_assignment(self):
        # Fact: integer field is assigned the test value in the data struct
        # Arrange / Act
        out = gen_test({'n': 42})
        # Assert
        assert 'data.n := 42;' in out

    def test_bool_true_assignment(self):
        # Fact: true boolean field is assigned true in the data struct
        # Arrange / Act
        out = gen_test({'active': True})
        # Assert
        assert 'data.active := true;' in out

    def test_bool_false_assignment(self):
        # Fact: false boolean field is assigned false in the data struct
        # Arrange / Act
        out = gen_test({'active': False})
        # Assert
        assert 'data.active := false;' in out

    def test_data_to_jsonstr_call(self):
        # Fact: iecdata_to_jsontext is called in the test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'iecdata_to_jsontext(data, txt);' in out

    def test_jsonstr_to_data_roundtrip_call(self):
        # Fact: jsontext_to_iecdata roundtrip call is present in the test block
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'jsontext_to_iecdata(txt, data_rt);' in out

    def test_roundtrip_assertions_on_data_rt(self):
        # Fact: roundtrip assertions are performed on data_rt after re-parsing the generated JSON
        # Arrange / Act
        out = gen_test({'n': 42, 'name': 'abc'})
        # Assert
        assert 'EXPECT_EQ_DINT(42, data_rt.n);' in out
        assert "EXPECT_EQ_STRING('abc', data_rt.name);" in out

    def test_nested_struct_assignment(self):
        # Fact: nested struct fields are assigned test values in the data struct
        # Arrange / Act
        out = gen_test({'pos': {'x': 1.0}})
        # Assert
        assert 'data.pos.x := 1.0;' in out

    def test_array_assignment(self):
        # Fact: array elements are assigned test values in the data struct
        # Arrange / Act
        out = gen_test({'tags': ['a', 'b']})
        # Assert
        assert "data.tags[0] := 'a';" in out
        assert "data.tags[1] := 'b';" in out

    def test_iecdata_to_jsonbytes_call_includes_start_index(self):
        # Fact: iecdata_to_jsonbytes call includes the start_index parameter
        # iecdata_to_jsonbytes has start_index param; call must include it
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'iecdata_to_jsonbytes(data, bytes, -1);' in out

    def test_jsonbytes_to_iecdata_call_includes_start_and_end_index(self):
        # Fact: jsonbytes_to_iecdata call includes both start_index and end_index parameters
        # jsonbytes_to_iecdata has start_index and end_index; call must include both
        # Arrange / Act
        out = gen_test({'x': 1})
        # Assert
        assert 'jsonbytes_to_iecdata(bytes, -1, -1, data_rt);' in out


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
        # Fact: generated test uses default value 0 for integer schema fields
        # Arrange / Act
        out = gen_test_schema(self._schema)
        # Assert
        assert 'EXPECT_EQ_DINT(0, data.id);' in out

    def test_string_default_assertion(self):
        # Fact: generated test uses default empty string for string schema fields
        # Arrange / Act
        out = gen_test_schema(self._schema)
        # Assert
        assert "EXPECT_EQ_STRING('', data.label);" in out

    def test_float_default_assertion(self):
        # Fact: generated test uses default value 0.0 for number schema fields
        # Arrange / Act
        out = gen_test_schema(self._schema)
        # Assert
        assert 'EXPECT_NEAR(0.0, data.score, 0.001);' in out

    def test_bool_default_assertion(self):
        # Fact: generated test uses EXPECT_FALSE for boolean schema fields
        # Arrange / Act
        out = gen_test_schema(self._schema)
        # Assert
        assert 'EXPECT_FALSE(data.enabled);' in out

    def test_array_default_assertion(self):
        # Fact: generated test uses default empty string for string array schema elements
        # Arrange / Act
        out = gen_test_schema(self._schema)
        # Assert
        assert "EXPECT_EQ_STRING('', data.items[0]);" in out
        assert "EXPECT_EQ_STRING('', data.items[1]);" in out

    def test_json_string_uses_defaults(self):
        # Fact: generated json string uses all default values when schema input is used
        # Arrange / Act
        out = gen_test_schema(self._schema)
        # Assert
        assert '{"id":0,"label":"","score":0.0,"enabled":false,"items":["",""]}' in out


# ---------------------------------------------------------------------------
# IEC string literal escaping
# ---------------------------------------------------------------------------

class TestIecStringEscaping:
    def test_single_quote_escaped(self):
        # Fact: single quotes in string values are escaped with $' in IEC string literals
        # Arrange / Act
        out = gen_test({'s': "it's"})
        # Assert
        assert "EXPECT_EQ_STRING('it$'s', data.s);" in out

    def test_dollar_sign_escaped(self):
        # Fact: dollar signs in string values are escaped with $$ in IEC string literals
        # Arrange / Act
        out = gen_test({'s': '$100'})
        # Assert
        assert "EXPECT_EQ_STRING('$$100', data.s);" in out

    def test_double_quote_not_escaped(self):
        # Fact: double quotes in string values do not need escaping in IEC string literals
        # Arrange / Act
        out = gen_test({'s': 'say "hi"'})
        # Assert
        assert '''EXPECT_EQ_STRING('say "hi"', data.s);''' in out

    def test_empty_string(self):
        # Fact: empty string values produce empty IEC string literals
        # Arrange / Act
        out = gen_test({'s': ''})
        # Assert
        assert "EXPECT_EQ_STRING('', data.s);" in out

    def test_json_string_single_quote_escaped(self):
        # Fact: single quotes in json assignment strings are escaped with $' in IEC notation
        # A string value containing ' must be escaped in the json assignment too
        # Arrange / Act
        out = gen_test({'s': "it's"})
        # The JSON string {"s":"it's"} must be represented as 'it$'s' in IEC
        # Assert
        assert "$'" in out


# ---------------------------------------------------------------------------
# Escape tests block
# ---------------------------------------------------------------------------

class TestEscapeBlock:
    def test_json_escape_block_present_when_has_string(self):
        # Fact: TEST_S block for json_escape is generated when the model has string fields
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert 'TEST_S(test_json_escape)' in out

    def test_json_unescape_block_present_when_has_string(self):
        # Fact: TEST_S block for json_unescape is generated when the model has string fields
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert 'TEST_S(test_json_unescape)' in out

    def test_escape_blocks_always_present(self):
        # Fact: json_escape and json_unescape TEST_S blocks are always generated
        # Arrange / Act
        out = gen_test({'n': 1, 'f': 2.0, 'b': True})
        # Assert
        assert 'TEST_S(test_json_escape)' in out
        assert 'TEST_S(test_json_unescape)' in out
        

    def test_escape_test_names_in_configuration(self):
        # Fact: json_escape and json_unescape test names appear in the configuration block
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "'test_json_escape'" in out
        assert "'test_json_unescape'" in out
        

    def test_escape_test_names_always_present(self):
        # Fact: json_escape and json_unescape test names are always in the configuration
        # Arrange / Act
        out = gen_test({'n': 1})
        # Assert
        assert "'test_json_escape'" in out
        assert "'test_json_unescape'" in out
        

    def test_json_escape_doublequote(self):
        # Fact: json_escape maps double-quote to \"
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('\"');" in out
        assert "EXPECT_EQ_STRING('\\\"', res);" in out

    def test_json_escape_backslash(self):
        # Fact: json_escape maps backslash to \\
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('\\');" in out
        assert "EXPECT_EQ_STRING('\\\\', res);" in out

    def test_json_escape_tab(self):
        # Fact: json_escape maps IEC tab ($t) to \t
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('$t');" in out
        assert "EXPECT_EQ_STRING('\\t', res);" in out

    def test_json_escape_newline(self):
        # Fact: json_escape maps IEC newline ($n) to \n
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('$n');" in out
        assert "EXPECT_EQ_STRING('\\n', res);" in out

    def test_json_escape_cr(self):
        # Fact: json_escape maps IEC carriage return ($r) to \r
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('$r');" in out
        assert "EXPECT_EQ_STRING('\\r', res);" in out

    def test_json_escape_backspace(self):
        # Fact: json_escape maps IEC backspace ($08) to \b
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('$08');" in out
        assert "EXPECT_EQ_STRING('\\b', res);" in out

    def test_json_escape_formfeed(self):
        # Fact: json_escape maps IEC form feed ($0c) to \f
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('$0c');" in out
        assert "EXPECT_EQ_STRING('\\f', res);" in out

    def test_json_escape_control_uXXXX(self):
        # Fact: json_escape maps IEC BEL ($07) to \u0007
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_escape('$07');" in out
        assert "EXPECT_EQ_STRING('\\u0007', res);" in out

    def test_json_unescape_doublequote(self):
        # Fact: json_unescape maps \" back to double-quote
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\\"');" in out
        assert "EXPECT_EQ_STRING('\"', res);" in out

    def test_json_unescape_backslash(self):
        # Fact: json_unescape maps \\ back to backslash
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\\\');" in out
        assert "EXPECT_EQ_STRING('\\', res);" in out

    def test_json_unescape_tab(self):
        # Fact: json_unescape maps \t back to IEC tab ($t)
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\t');" in out
        assert "EXPECT_EQ_STRING('$t', res);" in out

    def test_json_unescape_newline(self):
        # Fact: json_unescape maps \n back to IEC newline ($n)
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\n');" in out
        assert "EXPECT_EQ_STRING('$n', res);" in out

    def test_json_unescape_cr(self):
        # Fact: json_unescape maps \r back to IEC carriage return ($r)
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\r');" in out
        assert "EXPECT_EQ_STRING('$r', res);" in out

    def test_json_unescape_backspace(self):
        # Fact: json_unescape maps \b back to IEC backspace ($08)
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\b');" in out
        assert "EXPECT_EQ_STRING('$08', res);" in out

    def test_json_unescape_formfeed(self):
        # Fact: json_unescape maps \f back to IEC form feed ($0c)
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\f');" in out
        assert "EXPECT_EQ_STRING('$0c', res);" in out

    def test_json_unescape_xHH_printable(self):
        # Fact: json_unescape maps \x41 to the printable character A
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\x41');" in out
        assert "EXPECT_EQ_STRING('A', res);" in out

    def test_json_unescape_uXXXX_printable(self):
        # Fact: json_unescape maps \u0041 to the printable character A
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\u0041');" in out
        assert "EXPECT_EQ_STRING('A', res);" in out

    def test_json_unescape_uXXXX_control(self):
        # Fact: json_unescape maps \u000a to IEC newline ($n)
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\u000a');" in out
        assert "EXPECT_EQ_STRING('$n', res);" in out

    def test_json_unescape_uXXXX_doublequote(self):
        # Fact: json_unescape maps \u0022 to double-quote
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # Assert
        assert "res := json_unescape('\\u0022');" in out
        assert "EXPECT_EQ_STRING('\"', res);" in out

    def test_string_type_stored_in_model(self):
        # Fact: custom string_type option is stored in the model field type
        # Arrange / Act
        model = analyze_json({'label': 'x'}, string_type='string[64]')
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'string[64]'

    def test_eleven_end_test_s_blocks(self):
        # Fact: 16 END_TEST_S blocks are generated for a model with string fields
        # Arrange / Act
        out = gen_test({'name': 'abc'})
        # jsonstr_to_data, data_to_jsonstr, jsonbytes_to_data, data_to_jsonbytes,
        # json_char_from_asciicharcode, json_asciicharcode,
        # json_bytes_insert_text, json_find_key, json_bytes_find_key,
        # json_escape, json_find_block, json_extract_scalar, json_bytes_find_block,
        # json_bytes_extract_scalar, json_bytes_to_str, json_unescape
        # Assert
        assert out.count('END_TEST_S') == 16


# ---------------------------------------------------------------------------
# Extra perspectives merged into base TEST_S blocks (numbered vars)
# ---------------------------------------------------------------------------

class TestExtraBlocks:
    _data = {'name': 'sensor1', 'value': 3.14, 'count': 42, 'active': True}

    # --- extra names are NOT in configuration (merged into base block) ---

    def test_extra_names_not_in_configuration(self):
        # Fact: extra perspective names are not listed separately in the configuration block
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert "'test_JsonRoot_jsonstr_to_data_str_escaped'" not in out
        assert "'test_JsonRoot_data_to_jsonstr_str_escaped'" not in out

    # --- numbered vars are declared ---

    def test_jtd_numbered_json_vars_declared(self):
        # Fact: numbered json string variables are declared for each extra perspective
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'txt1: string[4096];' in out
        assert 'txt6: string[4096];' in out

    def test_jtd_numbered_data_vars_declared(self):
        # Fact: numbered data struct variables are declared for each extra perspective
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'data1: JsonRoot_t;' in out
        assert 'data6: JsonRoot_t;' in out

    def test_dtj_numbered_data_and_rt_vars_declared(self):
        # Fact: numbered data_rt struct variables are declared for each extra perspective
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'data1_rt: JsonRoot_t;' in out
        assert 'data6_rt: JsonRoot_t;' in out

    # --- no numbered vars when types are absent ---

    def test_no_numbered_vars_when_only_int_field(self):
        # Fact: only one numbered variant is generated when the model has only integer fields
        # Arrange / Act
        out = gen_test({'n': 1})
        # int alone → 1 extra (int_negative): json1 exists but json2 does not
        # Assert
        assert 'txt1:' in out
        assert 'txt2:' not in out

    def test_no_numbered_vars_when_no_optional_types(self):
        # Fact: no numbered variants are generated when the model has only boolean fields
        # Arrange / Act
        out = gen_test({'b': True})
        # Assert
        assert 'txt1:' not in out

    # --- str_escaped (data1 / data1_rt) ---

    def test_jtd_str_escaped_json(self):
        # Fact: str_escaped extra perspective uses a JSON string with an escaped double-quote
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'hello\\"world' in out  # JSON encoding of hello"world

    def test_jtd_str_escaped_assertion_on_data1(self):
        # Fact: str_escaped assertion on data1 uses the unescaped double-quote string
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert "EXPECT_EQ_STRING('hello\"world', data1.name);" in out

    def test_dtj_str_escaped_assignment_on_data1(self):
        # Fact: str_escaped assignment on data1 uses the unescaped double-quote string
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert "data1.name := 'hello\"world';" in out

    def test_dtj_str_escaped_assertion_on_data1_rt(self):
        # Fact: str_escaped roundtrip assertion on data1_rt uses the unescaped double-quote string
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert "EXPECT_EQ_STRING('hello\"world', data1_rt.name);" in out

    # --- str_empty (data2 / data2_rt) ---

    def test_jtd_str_empty_assertion_on_data2(self):
        # Fact: str_empty assertion on data2 uses an empty string
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert "EXPECT_EQ_STRING('', data2.name);" in out

    def test_dtj_str_empty_assignment_on_data2(self):
        # Fact: str_empty assignment on data2 uses an empty string
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert "data2.name := '';" in out

    # --- num_integer (data3 / data3_rt) ---

    def test_jtd_num_integer_assertion_on_data3(self):
        # Fact: num_integer assertion on data3 uses an integer value for the float field
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'EXPECT_NEAR(42.0, data3.value, 0.001);' in out

    def test_dtj_num_integer_assignment_on_data3(self):
        # Fact: num_integer assignment on data3 uses an integer value for the float field
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'data3.value := 42.0;' in out

    # --- num_exponential (data4 / data4_rt) ---

    def test_jtd_num_exponential_json_uses_1e3(self):
        # Fact: num_exponential extra perspective uses 1e3 in the json string
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert '1e3' in out

    def test_jtd_num_exponential_assertion_on_data4(self):
        # Fact: num_exponential assertion on data4 expects 1000.0
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'EXPECT_NEAR(1000.0, data4.value, 0.001);' in out

    def test_dtj_num_exponential_assignment_on_data4(self):
        # Fact: num_exponential assignment on data4 uses 1000.0
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'data4.value := 1000.0;' in out

    # --- num_negative (data5 / data5_rt) ---

    def test_jtd_num_negative_assertion_on_data5(self):
        # Fact: num_negative assertion on data5 uses a negative float value
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'EXPECT_NEAR(-1.5, data5.value, 0.001);' in out

    def test_dtj_num_negative_assignment_on_data5(self):
        # Fact: num_negative assignment on data5 uses a negative float value
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'data5.value := -1.5;' in out

    # --- int_negative (data6 / data6_rt) ---

    def test_jtd_int_negative_assertion_on_data6(self):
        # Fact: int_negative assertion on data6 uses a negative integer value
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'EXPECT_EQ_DINT(-42, data6.count);' in out

    def test_dtj_int_negative_assignment_on_data6(self):
        # Fact: int_negative assignment on data6 uses a negative integer value
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'data6.count := -42;' in out

    def test_dtj_int_negative_assertion_on_data6_rt(self):
        # Fact: int_negative roundtrip assertion on data6_rt uses a negative integer value
        # Arrange / Act
        out = gen_test(self._data)
        # Assert
        assert 'EXPECT_EQ_DINT(-42, data6_rt.count);' in out

    # --- total block count (merged → only 4 TEST_S with strings) ---

    def test_total_end_test_s_count_with_string(self):
        # Fact: 16 END_TEST_S blocks are generated for a model with mixed field types
        # Arrange / Act
        out = gen_test(self._data)
        # 4 model tests + 12 helper tests = 16
        # Assert
        assert out.count('END_TEST_S') == 16

    def test_total_end_test_s_count_no_string(self):
        # Fact: 16 END_TEST_S blocks are generated for a model with only numeric fields
        # Arrange / Act
        out = gen_test({'n': 1, 'v': 2.5})
        # same 16 blocks (helpers always included)
        # Assert
        assert out.count('END_TEST_S') == 16


# ---------------------------------------------------------------------------
# Custom options
# ---------------------------------------------------------------------------

class TestCustomOptions:
    def test_custom_json_len(self):
        # Fact: custom json_len is reflected in the generated string size
        # Arrange / Act
        out = gen_test({'x': 1}, json_len='1024')
        # Assert
        assert 'string[1024]' in out

    def test_custom_pou_filename(self):
        # Fact: custom pou_file option sets the POU include filename
        # Arrange / Act
        out = gen_test({'x': 1}, pou_file='sensor.txt')
        # Assert
        assert '{#include <sensor.txt>}' in out

    def test_custom_int_type_lint(self):
        # Fact: custom int_type lint generates EXPECT_EQ_LINT assertions
        # Arrange / Act
        out = gen_test({'n': 1}, int_type='lint')
        # Assert
        assert 'EXPECT_EQ_LINT(1, data.n);' in out

    def test_custom_int_type_udint(self):
        # Fact: custom int_type udint generates EXPECT_EQ_UDINT assertions
        # Arrange / Act
        out = gen_test({'n': 5}, int_type='udint')
        # Assert
        assert 'EXPECT_EQ_UDINT(5, data.n);' in out

