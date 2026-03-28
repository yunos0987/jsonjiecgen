# coding: utf-8
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzer import analyze_json, analyze_schema, AnalyzeError
from model import ScalarType, StructType, ArrayType


class TestAnalyzeJson:
    def test_flat_string(self):
        model = analyze_json({'name': 'abc'})
        assert model.root.name == 'JsonRoot_t'
        assert len(model.root.fields) == 1
        f = model.root.fields[0]
        assert f.name == 'name'
        assert isinstance(f.type, ScalarType)
        assert f.type.iec_type.startswith('string')

    def test_flat_integer(self):
        model = analyze_json({'count': 42})
        f = model.root.fields[0]
        assert f.type.iec_type == 'dint'

    def test_flat_number(self):
        model = analyze_json({'val': 3.14})
        f = model.root.fields[0]
        assert f.type.iec_type == 'lreal'

    def test_flat_bool(self):
        model = analyze_json({'active': True})
        f = model.root.fields[0]
        assert f.type.iec_type == 'bool'

    def test_bool_not_confused_with_int(self):
        # In Python, True is a subclass of int, so isinstance order matters
        model = analyze_json({'flag': True, 'count': 1})
        types = {f.name: f.type.iec_type for f in model.root.fields}
        assert types['flag'] == 'bool'
        assert types['count'] == 'dint'

    def test_nested_object(self):
        model = analyze_json({'pos': {'x': 1.0, 'y': 2.0}})
        assert len(model.all_structs) == 2
        # leaf-first: nested type must come before its parent
        assert model.all_structs[0].name == 'JsonRoot_pos_t'
        assert model.all_structs[1].name == 'JsonRoot_t'
        pos_field = model.root.fields[0]
        assert isinstance(pos_field.type, StructType)
        assert pos_field.type.name == 'JsonRoot_pos_t'

    def test_array_string(self):
        model = analyze_json({'tags': ['a', 'b', 'c']})
        f = model.root.fields[0]
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 3
        assert isinstance(f.type.element_type, ScalarType)
        assert f.type.element_type.iec_type.startswith('string')

    def test_array_int(self):
        model = analyze_json({'nums': [10, 20]})
        f = model.root.fields[0]
        assert f.type.size == 2
        assert f.type.element_type.iec_type == 'dint'

    def test_null_raises_error(self):
        with pytest.raises(AnalyzeError, match='null'):
            analyze_json({'x': None})

    def test_empty_array_raises_error(self):
        with pytest.raises(AnalyzeError, match='Empty'):
            analyze_json({'items': []})

    def test_custom_prefix_suffix(self):
        model = analyze_json({'val': 1}, prefix='Sensor', suffix='_data')
        assert model.root.name == 'Sensor_data'

    def test_custom_int_type(self):
        model = analyze_json({'n': 1}, int_type='lint')
        f = model.root.fields[0]
        assert f.type.iec_type == 'lint'

    def test_custom_num_type(self):
        model = analyze_json({'f': 1.0}, num_type='real')
        f = model.root.fields[0]
        assert f.type.iec_type == 'real'


    def test_negative_integer_at_root(self):
        model = analyze_json({'val': -42})
        f = model.root.fields[0]
        assert f.type.json_type == 'integer'
        assert f.type.iec_type == 'dint'

    def test_negative_float_at_root(self):
        model = analyze_json({'val': -3.14})
        f = model.root.fields[0]
        assert f.type.json_type == 'number'
        assert f.type.iec_type == 'lreal'

    def test_scientific_notation_at_root(self):
        model = analyze_json({'val': 1e-5})
        f = model.root.fields[0]
        assert f.type.json_type == 'number'

    def test_has_string_flag(self):
        model = analyze_json({'name': 'abc', 'count': 1})
        assert model.has_string is True
        model2 = analyze_json({'count': 1})
        assert model2.has_string is False


class TestAnalyzeSchema:
    def test_basic_schema(self):
        schema = {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'label': {'type': 'string'},
                'score': {'type': 'number'},
                'enabled': {'type': 'boolean'},
            }
        }
        model = analyze_schema(schema)
        types = {f.name: f.type.iec_type for f in model.root.fields}
        assert types['id'] == 'dint'
        assert types['label'].startswith('string')
        assert types['score'] == 'lreal'
        assert types['enabled'] == 'bool'

    def test_schema_array_requires_max_items(self):
        schema = {
            'type': 'object',
            'properties': {
                'items': {
                    'type': 'array',
                    'items': {'type': 'string'},
                }
            }
        }
        with pytest.raises(AnalyzeError, match='maxItems'):
            analyze_schema(schema)

    def test_schema_null_raises(self):
        schema = {
            'type': 'object',
            'properties': {'x': {'type': 'null'}}
        }
        with pytest.raises(AnalyzeError, match='null'):
            analyze_schema(schema)

    def test_schema_string_type(self):
        schema = {
            'type': 'object',
            'properties': {'name': {'type': 'string'}}
        }
        model = analyze_schema(schema, string_type='string[64]')
        f = model.root.fields[0]
        assert f.type.iec_type == 'string[64]'

    def test_top_level_not_object_raises(self):
        with pytest.raises(AnalyzeError):
            analyze_schema({'type': 'string'})

    def test_schema_integer_only(self):
        schema = {'type': 'object', 'properties': {'n': {'type': 'integer'}}}
        model = analyze_schema(schema)
        f = model.root.fields[0]
        assert f.type.iec_type == 'dint'
        assert f.type.json_type == 'integer'

    def test_schema_string_only(self):
        schema = {'type': 'object', 'properties': {'s': {'type': 'string'}}}
        model = analyze_schema(schema)
        f = model.root.fields[0]
        assert f.type.json_type == 'string'

    def test_schema_number_only(self):
        schema = {'type': 'object', 'properties': {'v': {'type': 'number'}}}
        model = analyze_schema(schema)
        f = model.root.fields[0]
        assert f.type.iec_type == 'lreal'
        assert f.type.json_type == 'number'

    def test_schema_boolean_only(self):
        schema = {'type': 'object', 'properties': {'b': {'type': 'boolean'}}}
        model = analyze_schema(schema)
        f = model.root.fields[0]
        assert f.type.json_type == 'boolean'
        assert f.type.iec_type == 'bool'


class TestSingleElementArray:
    def test_single_int_array(self):
        model = analyze_json({'nums': [42]})
        f = model.root.fields[0]
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert f.type.element_type.json_type == 'integer'

    def test_single_string_array(self):
        model = analyze_json({'tags': ['hello']})
        f = model.root.fields[0]
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert f.type.element_type.json_type == 'string'

    def test_single_bool_array(self):
        model = analyze_json({'flags': [True]})
        f = model.root.fields[0]
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert f.type.element_type.json_type == 'boolean'

    def test_single_object_array(self):
        model = analyze_json({'items': [{'x': 1}]})
        f = model.root.fields[0]
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert isinstance(f.type.element_type, StructType)


class TestArrayNumericTypeInference:
    def test_all_integers_maps_to_int_type(self):
        model = analyze_json({'nums': [1, 2, 3]})
        f = model.root.fields[0]
        assert f.type.element_type.iec_type == 'dint'

    def test_mixed_int_and_float_maps_to_num_type(self):
        model = analyze_json({'nums': [1, 2.5, 3]})
        f = model.root.fields[0]
        assert f.type.element_type.iec_type == 'lreal'

    def test_float_at_end_maps_to_num_type(self):
        model = analyze_json({'nums': [1, 2, 3.0]})
        f = model.root.fields[0]
        assert f.type.element_type.iec_type == 'lreal'

    def test_float_first_maps_to_num_type(self):
        model = analyze_json({'nums': [1.0, 2, 3]})
        f = model.root.fields[0]
        assert f.type.element_type.iec_type == 'lreal'

    def test_all_floats_maps_to_num_type(self):
        model = analyze_json({'nums': [1.0, 2.0, 3.0]})
        f = model.root.fields[0]
        assert f.type.element_type.iec_type == 'lreal'

    def test_bool_in_array_not_treated_as_int(self):
        # bool is a subclass of int in Python; must not be mapped to int type
        model = analyze_json({'flags': [True, False]})
        f = model.root.fields[0]
        assert f.type.element_type.iec_type == 'bool'


class TestFieldNameValidation:
    def test_space_in_key_raises(self):
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'m 1': 'x'})

    def test_hyphen_in_key_raises(self):
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'m-1': 'x'})

    def test_dot_in_key_raises(self):
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'m.1': 'x'})

    def test_nested_invalid_key_raises(self):
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'obj': {'m 2-1': 'x'}})

    def test_schema_space_in_key_raises(self):
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_schema({'type': 'object', 'properties': {'m 1': {'type': 'string'}}})

    def test_valid_key_accepted(self):
        model = analyze_json({'m1': 'x', 'M_2': 1, 'field3': True})
        assert len(model.root.fields) == 3


class TestArrayElementTypeValidation:
    def test_mixed_scalar_types_raises(self):
        with pytest.raises(AnalyzeError, match='same type'):
            analyze_json({'arr': [1, 'a']})

    def test_object_array_different_keys_raises(self):
        with pytest.raises(AnalyzeError, match='same keys'):
            analyze_json({'arr': [{'x': 1}, {'y': 2}]})

    def test_object_array_extra_key_raises(self):
        with pytest.raises(AnalyzeError, match='same keys'):
            analyze_json({'arr': [{'x': 1, 'y': 2}, {'x': 1}]})

    def test_object_array_same_keys_accepted(self):
        model = analyze_json({'arr': [{'x': 1}, {'x': 2}]})
        assert len(model.root.fields) == 1

    def test_string_array_accepted(self):
        model = analyze_json({'arr': ['a', 'b', 'c']})
        assert len(model.root.fields) == 1

    def test_bool_array_accepted(self):
        model = analyze_json({'arr': [True, False]})
        assert len(model.root.fields) == 1
