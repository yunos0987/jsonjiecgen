# coding: utf-8
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzer import analyze_json, analyze_schema, AnalyzeError
from model import ScalarType, StructType, ArrayType


class TestAnalyzeJson:
    def test_flat_string(self):
        # Fact: analyze_json maps a top-level string field and sets root name to JsonRoot_t
        # Arrange / Act
        model = analyze_json({'name': 'abc'})
        # Assert
        assert model.root.name == 'JsonRoot_t'
        assert len(model.root.fields) == 1
        f = model.root.fields[0]
        assert f.name == 'name'
        assert isinstance(f.type, ScalarType)
        assert f.type.iec_type.startswith('string')

    def test_flat_integer(self):
        # Fact: analyze_json maps an integer value to dint IEC type
        # Arrange / Act
        model = analyze_json({'count': 42})
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'dint'

    def test_flat_number(self):
        # Fact: analyze_json maps a float value to lreal IEC type
        # Arrange / Act
        model = analyze_json({'val': 3.14})
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'lreal'

    def test_flat_bool(self):
        # Fact: analyze_json maps a boolean value to bool IEC type
        # Arrange / Act
        model = analyze_json({'active': True})
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'bool'

    def test_bool_not_confused_with_int(self):
        # Fact: bool fields are mapped to bool type, not dint, even though bool is a subclass of int
        # In Python, True is a subclass of int, so isinstance order matters
        # Arrange / Act
        model = analyze_json({'flag': True, 'count': 1})
        types = {f.name: f.type.iec_type for f in model.root.fields}
        # Assert
        assert types['flag'] == 'bool'
        assert types['count'] == 'dint'

    def test_nested_object(self):
        # Fact: analyze_json creates nested struct types and orders them leaf-first
        # Arrange / Act
        model = analyze_json({'pos': {'x': 1.0, 'y': 2.0}})
        # Assert
        assert len(model.all_structs) == 2
        # leaf-first: nested type must come before its parent
        assert model.all_structs[0].name == 'JsonRoot_pos_t'
        assert model.all_structs[1].name == 'JsonRoot_t'
        pos_field = model.root.fields[0]
        assert isinstance(pos_field.type, StructType)
        assert pos_field.type.name == 'JsonRoot_pos_t'

    def test_array_string(self):
        # Fact: analyze_json maps a string array to ArrayType with correct size and element type
        # Arrange / Act
        model = analyze_json({'tags': ['a', 'b', 'c']})
        f = model.root.fields[0]
        # Assert
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 3
        assert isinstance(f.type.element_type, ScalarType)
        assert f.type.element_type.iec_type.startswith('string')

    def test_array_int(self):
        # Fact: analyze_json maps an integer array to ArrayType with correct size
        # Arrange / Act
        model = analyze_json({'nums': [10, 20]})
        f = model.root.fields[0]
        # Assert
        assert f.type.size == 2
        assert f.type.element_type.iec_type == 'dint'

    def test_null_raises_error(self):
        # Fact: analyze_json raises AnalyzeError when a null value is encountered
        # Act / Assert
        with pytest.raises(AnalyzeError, match='null'):
            analyze_json({'x': None})

    def test_empty_array_raises_error(self):
        # Fact: analyze_json raises AnalyzeError for an empty array
        # Act / Assert
        with pytest.raises(AnalyzeError, match='Empty'):
            analyze_json({'items': []})

    def test_custom_prefix_suffix(self):
        # Fact: analyze_json applies custom prefix and suffix to the root struct name
        # Arrange / Act
        model = analyze_json({'val': 1}, prefix='Sensor', suffix='_data')
        # Assert
        assert model.root.name == 'Sensor_data'

    def test_custom_int_type(self):
        # Fact: analyze_json uses a custom integer IEC type when int_type is specified
        # Arrange / Act
        model = analyze_json({'n': 1}, int_type='lint')
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'lint'

    def test_custom_num_type(self):
        # Fact: analyze_json uses a custom number IEC type when num_type is specified
        # Arrange / Act
        model = analyze_json({'f': 1.0}, num_type='real')
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'real'


    def test_negative_integer_at_root(self):
        # Fact: analyze_json maps a negative integer to dint with json_type integer
        # Arrange / Act
        model = analyze_json({'val': -42})
        f = model.root.fields[0]
        # Assert
        assert f.type.json_type == 'integer'
        assert f.type.iec_type == 'dint'

    def test_negative_float_at_root(self):
        # Fact: analyze_json maps a negative float to lreal with json_type number
        # Arrange / Act
        model = analyze_json({'val': -3.14})
        f = model.root.fields[0]
        # Assert
        assert f.type.json_type == 'number'
        assert f.type.iec_type == 'lreal'

    def test_scientific_notation_at_root(self):
        # Fact: analyze_json maps a scientific notation float to json_type number
        # Arrange / Act
        model = analyze_json({'val': 1e-5})
        f = model.root.fields[0]
        # Assert
        assert f.type.json_type == 'number'

    def test_has_string_flag(self):
        # Fact: has_string flag is true when string fields are present, false otherwise
        # Arrange
        model = analyze_json({'name': 'abc', 'count': 1})
        assert model.has_string is True
        # Act
        model2 = analyze_json({'count': 1})
        # Assert
        assert model2.has_string is False


class TestAnalyzeSchema:
    def test_basic_schema(self):
        # Fact: analyze_schema maps schema property types to correct IEC types
        # Arrange
        schema = {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'label': {'type': 'string'},
                'score': {'type': 'number'},
                'enabled': {'type': 'boolean'},
            }
        }
        # Act
        model = analyze_schema(schema)
        types = {f.name: f.type.iec_type for f in model.root.fields}
        # Assert
        assert types['id'] == 'dint'
        assert types['label'].startswith('string')
        assert types['score'] == 'lreal'
        assert types['enabled'] == 'bool'

    def test_schema_array_requires_max_items(self):
        # Fact: analyze_schema raises AnalyzeError when an array property lacks maxItems
        # Arrange
        schema = {
            'type': 'object',
            'properties': {
                'items': {
                    'type': 'array',
                    'items': {'type': 'string'},
                }
            }
        }
        # Act / Assert
        with pytest.raises(AnalyzeError, match='maxItems'):
            analyze_schema(schema)

    def test_schema_null_raises(self):
        # Fact: analyze_schema raises AnalyzeError for a null type property
        # Arrange
        schema = {
            'type': 'object',
            'properties': {'x': {'type': 'null'}}
        }
        # Act / Assert
        with pytest.raises(AnalyzeError, match='null'):
            analyze_schema(schema)

    def test_schema_string_type(self):
        # Fact: analyze_schema applies a custom string_type to string fields
        # Arrange
        schema = {
            'type': 'object',
            'properties': {'name': {'type': 'string'}}
        }
        # Act
        model = analyze_schema(schema, string_type='string[64]')
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'string[64]'

    def test_top_level_not_object_raises(self):
        # Fact: analyze_schema raises AnalyzeError when the top-level type is not object
        # Act / Assert
        with pytest.raises(AnalyzeError):
            analyze_schema({'type': 'string'})

    def test_schema_integer_only(self):
        # Fact: analyze_schema maps integer type to dint with json_type integer
        # Arrange
        schema = {'type': 'object', 'properties': {'n': {'type': 'integer'}}}
        # Act
        model = analyze_schema(schema)
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'dint'
        assert f.type.json_type == 'integer'

    def test_schema_string_only(self):
        # Fact: analyze_schema maps string type with json_type string
        # Arrange
        schema = {'type': 'object', 'properties': {'s': {'type': 'string'}}}
        # Act
        model = analyze_schema(schema)
        f = model.root.fields[0]
        # Assert
        assert f.type.json_type == 'string'

    def test_schema_number_only(self):
        # Fact: analyze_schema maps number type to lreal with json_type number
        # Arrange
        schema = {'type': 'object', 'properties': {'v': {'type': 'number'}}}
        # Act
        model = analyze_schema(schema)
        f = model.root.fields[0]
        # Assert
        assert f.type.iec_type == 'lreal'
        assert f.type.json_type == 'number'

    def test_schema_boolean_only(self):
        # Fact: analyze_schema maps boolean type to bool IEC type
        # Arrange
        schema = {'type': 'object', 'properties': {'b': {'type': 'boolean'}}}
        # Act
        model = analyze_schema(schema)
        f = model.root.fields[0]
        # Assert
        assert f.type.json_type == 'boolean'
        assert f.type.iec_type == 'bool'


class TestSingleElementArray:
    def test_single_int_array(self):
        # Fact: a single-element integer array produces ArrayType with size 1
        # Arrange / Act
        model = analyze_json({'nums': [42]})
        f = model.root.fields[0]
        # Assert
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert f.type.element_type.json_type == 'integer'

    def test_single_string_array(self):
        # Fact: a single-element string array produces ArrayType with size 1
        # Arrange / Act
        model = analyze_json({'tags': ['hello']})
        f = model.root.fields[0]
        # Assert
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert f.type.element_type.json_type == 'string'

    def test_single_bool_array(self):
        # Fact: a single-element boolean array produces ArrayType with size 1
        # Arrange / Act
        model = analyze_json({'flags': [True]})
        f = model.root.fields[0]
        # Assert
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert f.type.element_type.json_type == 'boolean'

    def test_single_object_array(self):
        # Fact: a single-element object array produces ArrayType with a StructType element
        # Arrange / Act
        model = analyze_json({'items': [{'x': 1}]})
        f = model.root.fields[0]
        # Assert
        assert isinstance(f.type, ArrayType)
        assert f.type.size == 1
        assert isinstance(f.type.element_type, StructType)


class TestArrayNumericTypeInference:
    def test_all_integers_maps_to_int_type(self):
        # Fact: an array of all integers maps element type to dint
        # Arrange / Act
        model = analyze_json({'nums': [1, 2, 3]})
        f = model.root.fields[0]
        # Assert
        assert f.type.element_type.iec_type == 'dint'

    def test_mixed_int_and_float_maps_to_num_type(self):
        # Fact: an array mixing integers and floats maps element type to lreal
        # Arrange / Act
        model = analyze_json({'nums': [1, 2.5, 3]})
        f = model.root.fields[0]
        # Assert
        assert f.type.element_type.iec_type == 'lreal'

    def test_float_at_end_maps_to_num_type(self):
        # Fact: a float as the last element promotes the array element type to lreal
        # Arrange / Act
        model = analyze_json({'nums': [1, 2, 3.0]})
        f = model.root.fields[0]
        # Assert
        assert f.type.element_type.iec_type == 'lreal'

    def test_float_first_maps_to_num_type(self):
        # Fact: a float as the first element promotes the array element type to lreal
        # Arrange / Act
        model = analyze_json({'nums': [1.0, 2, 3]})
        f = model.root.fields[0]
        # Assert
        assert f.type.element_type.iec_type == 'lreal'

    def test_all_floats_maps_to_num_type(self):
        # Fact: an array of all floats maps element type to lreal
        # Arrange / Act
        model = analyze_json({'nums': [1.0, 2.0, 3.0]})
        f = model.root.fields[0]
        # Assert
        assert f.type.element_type.iec_type == 'lreal'

    def test_bool_in_array_not_treated_as_int(self):
        # Fact: boolean values in arrays are mapped to bool, not int
        # bool is a subclass of int in Python; must not be mapped to int type
        # Arrange / Act
        model = analyze_json({'flags': [True, False]})
        f = model.root.fields[0]
        # Assert
        assert f.type.element_type.iec_type == 'bool'


class TestFieldNameValidation:
    def test_space_in_key_raises(self):
        # Fact: a field name containing a space raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'m 1': 'x'})

    def test_hyphen_in_key_raises(self):
        # Fact: a field name containing a hyphen raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'m-1': 'x'})

    def test_dot_in_key_raises(self):
        # Fact: a field name containing a dot raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'m.1': 'x'})

    def test_nested_invalid_key_raises(self):
        # Fact: an invalid field name in a nested object raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_json({'obj': {'m 2-1': 'x'}})

    def test_schema_space_in_key_raises(self):
        # Fact: analyze_schema raises AnalyzeError for a property name with a space
        # Act / Assert
        with pytest.raises(AnalyzeError, match='Field name must only contain'):
            analyze_schema({'type': 'object', 'properties': {'m 1': {'type': 'string'}}})

    def test_valid_key_accepted(self):
        # Fact: field names with alphanumeric characters and underscores are accepted
        # Arrange / Act
        model = analyze_json({'m1': 'x', 'M_2': 1, 'field3': True})
        # Assert
        assert len(model.root.fields) == 3


class TestArrayElementTypeValidation:
    def test_mixed_scalar_types_raises(self):
        # Fact: an array with mixed scalar types raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='same type'):
            analyze_json({'arr': [1, 'a']})

    def test_object_array_different_keys_raises(self):
        # Fact: an array of objects with different keys raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='same keys'):
            analyze_json({'arr': [{'x': 1}, {'y': 2}]})

    def test_object_array_extra_key_raises(self):
        # Fact: an array of objects where one element has an extra key raises AnalyzeError
        # Act / Assert
        with pytest.raises(AnalyzeError, match='same keys'):
            analyze_json({'arr': [{'x': 1, 'y': 2}, {'x': 1}]})

    def test_object_array_same_keys_accepted(self):
        # Fact: an array of objects with identical keys is accepted
        # Arrange / Act
        model = analyze_json({'arr': [{'x': 1}, {'x': 2}]})
        # Assert
        assert len(model.root.fields) == 1

    def test_string_array_accepted(self):
        # Fact: an array of strings is accepted without errors
        # Arrange / Act
        model = analyze_json({'arr': ['a', 'b', 'c']})
        # Assert
        assert len(model.root.fields) == 1

    def test_bool_array_accepted(self):
        # Fact: an array of booleans is accepted without errors
        # Arrange / Act
        model = analyze_json({'arr': [True, False]})
        # Assert
        assert len(model.root.fields) == 1
