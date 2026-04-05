# coding: utf-8
from dataclasses import dataclass
from typing import Union


@dataclass
class ScalarType:
    iec_type: str        # 'dint' | 'lint' | 'real' | 'lreal' | 'bool' | 'string' | 'string[N]'
    json_type: str = ''  # 'boolean' | 'integer' | 'number' | 'string'


@dataclass
class StructField:
    name: str
    type: 'AnyType'


@dataclass
class StructType:
    name: str                    # e.g. "JsonRoot_pos_t"
    fields: list['StructField']


@dataclass
class ArrayType:
    element_type: 'AnyType'
    size: int       # number of elements


AnyType = Union[ScalarType, StructType, ArrayType]


@dataclass
class TypeModel:
    prefix: str                  # e.g. "JsonRoot"
    suffix: str                  # e.g. "_t"
    root: StructType             # root STRUCT
    all_structs: list[StructType]  # all STRUCTs in output order (leaf-first)
    has_string: bool             # whether json_escape/unescape need to be generated
    string_type: str             # IEC string type for string fields (e.g. 'string[256]')


def has_string_type(t: AnyType) -> bool:
    """Recursively check whether the type tree contains a string field."""
    if isinstance(t, ScalarType):
        return t.json_type == 'string'
    if isinstance(t, StructType):
        return any(has_string_type(f.type) for f in t.fields)
    if isinstance(t, ArrayType):
        return has_string_type(t.element_type)
    return False
