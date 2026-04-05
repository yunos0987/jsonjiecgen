# coding: utf-8
import re
from dataclasses import dataclass

from model import (
    ScalarType, StructField, StructType, ArrayType, AnyType, TypeModel, has_string_type
)


_VALID_FIELD_NAME = re.compile(r'^[A-Za-z0-9_]+$')


class AnalyzeError(Exception):
    pass


@dataclass
class _AnalyzeConfig:
    suffix: str
    str_type: str
    int_type: str
    num_type: str
    bool_type: str


def _validate_field_name(key: str) -> None:
    if not _VALID_FIELD_NAME.match(key):
        raise AnalyzeError(f"Field name must only contain A-Za-z0-9_: {key!r}")


def _infer_type(value, field_name: str, name_prefix: str, struct_name: str,
                cfg: _AnalyzeConfig, all_structs: list) -> AnyType:
    if value is None:
        raise AnalyzeError(f"JSON null is not supported (field: {field_name!r})")
    if isinstance(value, bool):
        return ScalarType(cfg.bool_type, 'boolean')
    if isinstance(value, int):
        return ScalarType(cfg.int_type, 'integer')
    if isinstance(value, float):
        return ScalarType(cfg.num_type, 'number')
    if isinstance(value, str):
        return ScalarType(cfg.str_type, 'string')
    if isinstance(value, list):
        if len(value) == 0:
            raise AnalyzeError(f"Empty arrays are not supported (field: {field_name!r})")
        # For numeric-only arrays, promote to float type if any element is a float.
        # bool must be excluded before int because bool is a subclass of int.
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            if any(isinstance(v, float) for v in value):
                elem_type = ScalarType(cfg.num_type, 'number')
            else:
                elem_type = ScalarType(cfg.int_type, 'integer')
        else:
            # All elements must have the same Python type
            first_type = type(value[0])
            for i, v in enumerate(value[1:], 1):
                if type(v) is not first_type:
                    raise AnalyzeError(
                        f"Array elements must all have the same type (field: {field_name!r},"
                        f" index {i}: expected {first_type.__name__!r},"
                        f" got {type(v).__name__!r})"
                    )
            # For object arrays, all elements must have identical keys
            if isinstance(value[0], dict):
                first_keys = set(value[0].keys())
                for i, v in enumerate(value[1:], 1):
                    if set(v.keys()) != first_keys:
                        raise AnalyzeError(
                            f"Array of objects must have the same keys in all elements"
                            f" (field: {field_name!r}, index {i})"
                        )
            elem_type = _infer_type(value[0], field_name, name_prefix, struct_name,
                                    cfg, all_structs)
        return ArrayType(elem_type, len(value))
    if isinstance(value, dict):
        return _build_struct(value, struct_name, name_prefix, cfg, all_structs)
    raise AnalyzeError(f"Unsupported type: {type(value).__name__} (field: {field_name!r})")


def _build_struct(data: dict, struct_name: str, name_prefix: str,
                  cfg: _AnalyzeConfig, all_structs: list) -> StructType:
    fields = []
    for key, value in data.items():
        _validate_field_name(key)
        child_prefix = f"{name_prefix}_{key}"
        child_struct_name = f"{child_prefix}{cfg.suffix}"
        field_type = _infer_type(value, key, child_prefix, child_struct_name,
                                 cfg, all_structs)
        fields.append(StructField(key, field_type))
    st = StructType(struct_name, fields)
    all_structs.append(st)
    return st


def analyze_json(data: dict, prefix: str = 'JsonRoot', suffix: str = '_t',
                 string_type: str = 'string[256]', int_type: str = 'dint',
                 num_type: str = 'lreal', bool_type: str = 'bool') -> TypeModel:
    if not isinstance(data, dict):
        raise AnalyzeError("Top-level value must be a JSON object")
    cfg = _AnalyzeConfig(suffix=suffix, str_type=string_type,
                         int_type=int_type, num_type=num_type, bool_type=bool_type)
    all_structs: list[StructType] = []
    root_name = f"{prefix}{suffix}"
    root = _build_struct(data, root_name, prefix, cfg, all_structs)
    # all_structs is already in leaf-first order (nested structs appended before parent)
    return TypeModel(
        prefix=prefix,
        suffix=suffix,
        root=root,
        all_structs=all_structs,
        has_string=has_string_type(root),
        string_type=string_type,
    )


def _schema_type(schema: dict, field_name: str, name_prefix: str, struct_name: str,
                 cfg: _AnalyzeConfig, all_structs: list) -> AnyType:
    t = schema.get('type')
    if t == 'string':
        return ScalarType(cfg.str_type, 'string')
    if t == 'integer':
        return ScalarType(cfg.int_type, 'integer')
    if t == 'number':
        return ScalarType(cfg.num_type, 'number')
    if t == 'boolean':
        return ScalarType(cfg.bool_type, 'boolean')
    if t == 'null':
        raise AnalyzeError(f"JSON null is not supported (field: {field_name!r})")
    if t == 'object':
        props = schema.get('properties', {})
        fields = []
        for key, sub_schema in props.items():
            _validate_field_name(key)
            child_prefix = f"{name_prefix}_{key}"
            child_struct_name = f"{child_prefix}{cfg.suffix}"
            field_type = _schema_type(sub_schema, key, child_prefix, child_struct_name,
                                      cfg, all_structs)
            fields.append(StructField(key, field_type))
        st = StructType(struct_name, fields)
        all_structs.append(st)
        return st
    if t == 'array':
        items = schema.get('items', {})
        max_items = schema.get('maxItems')
        if max_items is None:
            raise AnalyzeError(
                f"'maxItems' is required for array type (field: {field_name!r})"
            )
        elem_type = _schema_type(items, field_name, name_prefix, struct_name,
                                 cfg, all_structs)
        return ArrayType(elem_type, max_items)
    raise AnalyzeError(f"Unsupported schema type: {t!r} (field: {field_name!r})")


def analyze_schema(schema: dict, prefix: str = 'JsonRoot', suffix: str = '_t',
                   string_type: str = 'string[256]', int_type: str = 'dint',
                   num_type: str = 'lreal', bool_type: str = 'bool') -> TypeModel:
    if schema.get('type') != 'object':
        raise AnalyzeError("Top-level schema must have type: object")
    cfg = _AnalyzeConfig(suffix=suffix, str_type=string_type,
                         int_type=int_type, num_type=num_type, bool_type=bool_type)
    all_structs: list[StructType] = []
    root_name = f"{prefix}{suffix}"
    props = schema.get('properties', {})
    fields = []
    for key, sub_schema in props.items():
        _validate_field_name(key)
        child_prefix = f"{prefix}_{key}"
        child_struct_name = f"{child_prefix}{cfg.suffix}"
        field_type = _schema_type(sub_schema, key, child_prefix, child_struct_name,
                                  cfg, all_structs)
        fields.append(StructField(key, field_type))
    root = StructType(root_name, fields)
    all_structs.append(root)
    return TypeModel(
        prefix=prefix,
        suffix=suffix,
        root=root,
        all_structs=all_structs,
        has_string=has_string_type(root),
        string_type=string_type,
    )
