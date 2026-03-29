# coding: utf-8
import pathlib as _pathlib
from model import ScalarType, StructType, ArrayType, AnyType, StructField, TypeModel

TAB = '\t'

_FROM_STR = {
    'sint':  'string_to_sint',
    'int':   'string_to_int',
    'dint':  'string_to_dint',
    'lint':  'string_to_lint',
    'usint': 'string_to_usint',
    'uint':  'string_to_uint',
    'udint': 'string_to_udint',
    'ulint': 'string_to_ulint',
    'real':  'string_to_real',
    'lreal': 'string_to_lreal',
}

_TO_STR = {
    'sint':  'sint_to_string',
    'int':   'int_to_string',
    'dint':  'dint_to_string',
    'lint':  'lint_to_string',
    'usint': 'usint_to_string',
    'uint':  'uint_to_string',
    'udint': 'udint_to_string',
    'ulint': 'ulint_to_string',
    'real':  'real_to_string',
    'lreal': 'lreal_to_string',
}

def _read_src(name: str) -> str:
    return (_pathlib.Path(__file__).parent / name).read_text(encoding='utf-8').rstrip('\n')


_JSON_HELPERS = _read_src('json_helpers.txt')


def _indent(lines: list, n: int = 1) -> list:
    prefix = TAB * n
    return [prefix + line for line in lines]


def _jblk_depth_v2(t: AnyType) -> int:
    """jblk nesting depth needed when per-struct sub-functions handle nested structs.
    Struct fields only need depth 1 in the caller; array depth is unchanged."""
    if isinstance(t, StructType):
        depths = []
        for f in t.fields:
            if isinstance(f.type, StructType):
                depths.append(1)
            elif isinstance(f.type, ArrayType):
                depths.append(1 + _jblk_array_depth_v2(f.type))
        return max(depths) if depths else 0
    return 0


def _jblk_array_depth_v2(t: ArrayType) -> int:
    """jblk depth needed within array element processing, using per-struct sub-functions."""
    elem = t.element_type
    if isinstance(elem, StructType):
        return 1  # element block; struct sub-function handles deeper nesting
    if isinstance(elem, ArrayType):
        return 1 + _jblk_array_depth_v2(elem)
    return 0  # scalar elements need no jblk


def _jblk_var(depth: int) -> str:
    return 'jblk' + str(depth)


def _pos_var(depth: int) -> str:
    return 'pos' + str(depth)


class IecGenerator:
    def __init__(self, json_len: str = 'JSON_STRING_SIZE'):
        self._json_len = json_len

    # ------------------------------------------------------------------ public

    def generate(self, model: TypeModel) -> str:
        self._string_type = model.string_type
        parts = []
        parts.append(self._gen_type_defs(model))
        parts.append(_JSON_HELPERS)
        parts.append(self._gen_per_struct_extractors(model))
        parts.append(self._gen_data_to_jsonstr(model))
        parts.append(self._gen_data_to_jsonbytes(model))
        parts.append(self._gen_jsonstr_to_data(model))
        parts.append(self._gen_jsonbytes_to_data(model))
        return '\n'.join(p for p in parts if p)

    # --------------------------------------------------------- type definitions

    def _gen_type_defs(self, model: TypeModel) -> str:
        lines = []
        for st in model.all_structs:
            lines.append('type')
            lines.append(TAB + st.name + ': struct')
            for f in st.fields:
                lines.append(TAB + TAB + f.name + ': ' + self._iec_type_str(f.type) + ';')
            lines.append(TAB + 'end_struct;')
            lines.append('end_type')
        return '\n'.join(lines)

    def _iec_type_str(self, t: AnyType) -> str:
        if isinstance(t, ScalarType):
            return t.iec_type
        if isinstance(t, StructType):
            return t.name
        if isinstance(t, ArrayType):
            dims = []
            inner = t
            while isinstance(inner, ArrayType):
                dims.append('0..' + str(inner.size - 1))
                inner = inner.element_type
            return 'array[' + ', '.join(dims) + '] of ' + self._iec_type_str(inner)
        raise ValueError('Unknown type: ' + repr(t))

    # ------------------------------------------------ helpers

    def _has_numeric(self, t: AnyType) -> bool:
        if isinstance(t, ScalarType):
            return t.json_type in ('integer', 'number')
        if isinstance(t, StructType):
            return any(self._has_numeric(f.type) for f in t.fields)
        if isinstance(t, ArrayType):
            return self._has_numeric(t.element_type)
        return False

    def _direct_has_non_string_scalar(self, t: AnyType) -> bool:
        """Whether t has direct boolean/integer/number fields (needs sv for json_extract_scalar)."""
        if isinstance(t, StructType):
            return any(
                isinstance(f.type, ScalarType) and f.type.json_type in ('boolean', 'integer', 'number')
                for f in t.fields
            )
        return False

    def _direct_has_string(self, t: AnyType) -> bool:
        """Whether t has direct string fields (needs pos/qos for string scanning)."""
        if isinstance(t, StructType):
            return any(
                isinstance(f.type, ScalarType) and f.type.json_type == 'string'
                for f in t.fields
            )
        return False

    def _has_array(self, t: AnyType) -> bool:
        """Whether t has direct array fields."""
        if isinstance(t, StructType):
            return any(isinstance(f.type, ArrayType) for f in t.fields)
        return False

    def _needs_depth_v2(self, t: AnyType) -> bool:
        """Whether depth var is needed for _extract_sub_block_at_cursor (array of non-scalars)."""
        if isinstance(t, StructType):
            for f in t.fields:
                if isinstance(f.type, ArrayType) and not isinstance(f.type.element_type, ScalarType):
                    return True
        return False

    def _has_string_array(self, t: AnyType) -> bool:
        """Whether t has a direct array field with string elements (needs qos for extraction)."""
        if isinstance(t, StructType):
            for f in t.fields:
                if (isinstance(f.type, ArrayType)
                        and isinstance(f.type.element_type, ScalarType)
                        and f.type.element_type.json_type == 'string'):
                    return True
        return False

    @staticmethod
    def _key_var_decl(key: str) -> str:
        """Generate a var_temp declaration for a fixed byte array holding key."""
        size = len(key) - 1
        byte_inits = ', '.join('byte#' + str(ord(ch)) for ch in key)
        return 'key_' + key + ': array[0..' + str(size) + '] of byte := [' + byte_inits + '];'

    # --------------------------------------------------------- data_to_jsonstr

    def _gen_data_to_jsonstr(self, model: TypeModel) -> str:
        jlen = self._json_len
        pfx = model.prefix + '_'
        lines = [
            'function ' + pfx + 'iecdata_to_jsontext',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out data: ' + model.root.name + '; end_var',
            TAB + 'var_in_out txt: string[' + jlen + ']; end_var',
        ]
        if self._has_numeric(model.root):
            lines.append(TAB + 'var_temp')
            lines.append(TAB + TAB + 'sv: ' + self._string_type + ';')
            lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')

        body = self._struct_to_json_body(model.root, 'data', jv='txt', first_assign=True)
        lines.extend(_indent(body))

        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _struct_to_json_body(self, st: StructType, path: str,
                              jv: str = 'json', first_assign: bool = False) -> list:
        lines = []
        if first_assign:
            lines.append(jv + " := '{';")
        else:
            lines.append(jv + " := concat(" + jv + ", '{');")
        for i, f in enumerate(st.fields):
            sep = '' if i == 0 else ','
            lines.append(jv + " := concat(" + jv + ", '" + sep + '"' + f.name + '":' + "');")
            lines.extend(self._field_to_json(f.type, path + '.' + f.name, jv))
        lines.append(jv + " := concat(" + jv + ", '}');")
        return lines

    def _field_to_json(self, t: AnyType, path: str, jv: str = 'json') -> list:
        if isinstance(t, ScalarType):
            return self._scalar_to_json(t, path, jv)
        if isinstance(t, StructType):
            return self._struct_to_json_body(t, path, jv)
        if isinstance(t, ArrayType):
            return self._array_to_json(t, path, jv=jv)
        return []

    def _scalar_to_json(self, t: ScalarType, path: str, jv: str = 'json') -> list:
        if t.json_type == 'string':
            return [
                jv + " := concat(" + jv + ", '\"');",
                jv + ' := concat(' + jv + ', json_escape(' + path + '));',
                jv + " := concat(" + jv + ", '\"');",
            ]
        if t.json_type == 'boolean':
            return [
                'if ' + path + ' then',
                TAB + jv + " := concat(" + jv + ", 'true');",
                'else',
                TAB + jv + " := concat(" + jv + ", 'false');",
                'end_if;',
            ]
        func = _TO_STR.get(t.iec_type, t.iec_type + '_to_string')
        return [
            'sv := ' + func + '(' + path + ');',
            jv + ' := concat(' + jv + ', sv);',
        ]

    def _array_to_json(self, t: ArrayType, path: str, idx_parts: list = None, jv: str = 'json') -> list:
        if idx_parts is None:
            idx_parts = []
        lines = [jv + " := concat(" + jv + ", '[');"]
        for idx in range(t.size):
            if idx > 0:
                lines.append(jv + " := concat(" + jv + ", ',');")
            new_parts = idx_parts + [str(idx)]
            if isinstance(t.element_type, ArrayType):
                lines.extend(self._array_to_json(t.element_type, path, new_parts, jv))
            else:
                lines.extend(self._field_to_json(t.element_type, path + '[' + ', '.join(new_parts) + ']', jv))
        lines.append(jv + " := concat(" + jv + ", ']');")
        return lines

    # --------------------------------------------------------- data_to_jsonbytes

    def _gen_data_to_jsonbytes(self, model: TypeModel) -> str:
        pfx = model.prefix + '_'
        lines = [
            'function ' + pfx + 'iecdata_to_jsonbytes: dint',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out data: ' + model.root.name + '; end_var',
            TAB + 'var_in_out bytes: array[*] of byte; end_var',
            TAB + 'var_input start_index: dint := -1; end_var',
            TAB + 'var_temp',
        ]
        if self._has_numeric(model.root):
            lines.append(TAB + TAB + 'sv: ' + self._string_type + ';')
        lines.append(TAB + TAB + 'raw_ci, si: dint;')
        lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')
        lines.append(TAB + 'if start_index < 0 then si := lower_bound(bytes, 1); else si := start_index; end_if;')
        lines.append(TAB + 'raw_ci := si;')

        body = self._struct_to_jsonbytes_body(model.root, 'data', 'bytes')
        lines.extend(_indent(body))

        lines.append(TAB + 'bytes[raw_ci] := 0;')
        lines.append(TAB + pfx + 'iecdata_to_jsonbytes := raw_ci - si;')
        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _struct_to_jsonbytes_body(self, st: StructType, path: str, json_var: str = 'dat') -> list:
        lines = [json_var + "[raw_ci] := byte#123;", "raw_ci := raw_ci + 1;"]
        for i, f in enumerate(st.fields):
            sep = '' if i == 0 else ','
            lines.append("raw_ci := json_bytes_insert_text(dat:=" + json_var + ", index:=raw_ci, str:='" + sep + '"' + f.name + '":' + "');")
            lines.extend(self._field_to_jsonbytes(f.type, path + '.' + f.name, json_var))
        lines.append(json_var + "[raw_ci] := byte#125;")
        lines.append("raw_ci := raw_ci + 1;")
        return lines

    def _field_to_jsonbytes(self, t: AnyType, path: str, json_var: str = 'dat') -> list:
        if isinstance(t, ScalarType):
            return self._scalar_to_jsonbytes(t, path, json_var)
        if isinstance(t, StructType):
            return self._struct_to_jsonbytes_body(t, path, json_var)
        if isinstance(t, ArrayType):
            return self._array_to_jsonbytes(t, path, json_var=json_var)
        return []

    def _scalar_to_jsonbytes(self, t: ScalarType, path: str, json_var: str = 'dat') -> list:
        if t.json_type == 'string':
            return [
                json_var + "[raw_ci] := byte#34;", "raw_ci := raw_ci + 1;",
                'raw_ci := json_bytes_insert_text(dat:=' + json_var + ', index:=raw_ci, str:=json_escape(' + path + '));',
                json_var + "[raw_ci] := byte#34;", "raw_ci := raw_ci + 1;",
            ]
        if t.json_type == 'boolean':
            return [
                'if ' + path + ' then',
                TAB + "raw_ci := json_bytes_insert_text(dat:=" + json_var + ", index:=raw_ci, str:='true');",
                'else',
                TAB + "raw_ci := json_bytes_insert_text(dat:=" + json_var + ", index:=raw_ci, str:='false');",
                'end_if;',
            ]
        func = _TO_STR.get(t.iec_type, t.iec_type + '_to_string')
        return [
            'sv := ' + func + '(' + path + ');',
            'raw_ci := json_bytes_insert_text(dat:=' + json_var + ', index:=raw_ci, str:=sv);',
        ]

    def _array_to_jsonbytes(self, t: ArrayType, path: str, idx_parts: list = None, json_var: str = 'dat') -> list:
        if idx_parts is None:
            idx_parts = []
        lines = [json_var + "[raw_ci] := byte#91;", "raw_ci := raw_ci + 1;"]
        for idx in range(t.size):
            if idx > 0:
                lines.append(json_var + "[raw_ci] := byte#44;")
                lines.append("raw_ci := raw_ci + 1;")
            new_parts = idx_parts + [str(idx)]
            if isinstance(t.element_type, ArrayType):
                lines.extend(self._array_to_jsonbytes(t.element_type, path, new_parts, json_var))
            else:
                lines.extend(self._field_to_jsonbytes(t.element_type, path + '[' + ', '.join(new_parts) + ']', json_var))
        lines.append(json_var + "[raw_ci] := byte#93;")
        lines.append("raw_ci := raw_ci + 1;")
        return lines

    # -------------------------------------------------- per-struct extractors

    def _gen_per_struct_extractors(self, model: TypeModel) -> str:
        parts = []
        # Generate for all non-root structs in leaf-first order
        for st in model.all_structs[:-1]:
            parts.append(self._gen_struct_extractor_jsonbytes(st))
            parts.append(self._gen_struct_extractor_jsonstr(st))
        return '\n'.join(p for p in parts if p)

    def _gen_struct_extractor_jsonbytes(self, st: StructType) -> str:
        jlen = self._json_len
        lines = [
            'function private_' + st.name + '_jsonbytes_to_iecdata',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out bytes: array[*] of byte; end_var',
            TAB + 'var_input start_index: dint; end_var',
            TAB + 'var_input end_index: dint; end_var',
            TAB + 'var_in_out data: ' + st.name + '; end_var',
        ]
        var_lines = self._jsonbytes_var_lines(st, jlen)
        if var_lines:
            lines.append(TAB + 'var_temp')
            for vl in var_lines:
                lines.append(TAB + TAB + vl)
            lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')
        body = self._struct_from_jsonbytes_body(st, 'data', 'bytes',
                                                 si_expr='start_index', ei_expr='end_index')
        lines.extend(_indent(body))
        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _jsonbytes_var_lines(self, t: StructType, jlen: str) -> list:
        """Build the var_temp lines for a jsonbytes_to_data function."""
        var_lines = []
        has_any_scalar = any(isinstance(f.type, ScalarType) for f in t.fields)
        has_string = self._direct_has_string(t)
        has_struct = any(isinstance(f.type, StructType) for f in t.fields)
        has_array = any(isinstance(f.type, ArrayType) for f in t.fields)
        for f in t.fields:
            if isinstance(f.type, (ScalarType, StructType, ArrayType)):
                var_lines.append(self._key_var_decl(f.name))
        if has_any_scalar or has_array:
            var_lines.append('sv: ' + self._string_type + ';')
        if has_string:
            var_lines.append('raw_ci: dint;')
        if has_struct or has_array:
            var_lines.append('jblk1_bsi, jblk1_bei: dint;')
        if has_array:
            max_d_array = max(
                (1 + _jblk_array_depth_v2(f.type) for f in t.fields if isinstance(f.type, ArrayType)),
                default=0
            )
            var_lines.append('qos: dint;')
            if max_d_array >= 1:
                pos_vars = ', '.join(_pos_var(d) for d in range(1, max_d_array + 1))
                var_lines.append(pos_vars + ': dint;')
            for d in range(2, max_d_array + 1):
                var_lines.append(_jblk_var(d) + '_bei: dint;')
            needs_depth = any(
                isinstance(f.type, ArrayType) and not isinstance(f.type.element_type, ScalarType)
                for f in t.fields
            )
            if needs_depth:
                var_lines.append('depth: dint;')
        return var_lines

    def _struct_from_jsonbytes_body(self, st: StructType, data_path: str,
                                     json_var: str,
                                     si_expr: str = '0', ei_expr: str = 'JSON_STRING_SIZE') -> list:
        lines = []
        for f in st.fields:
            if isinstance(f.type, ScalarType):
                lines.extend(self._scalar_from_json_bytes(f.type, data_path + '.' + f.name,
                                                           json_var, f.name,
                                                           si_expr=si_expr, ei_expr=ei_expr))
            elif isinstance(f.type, StructType):
                lines.append('// ' + f.name + ': struct')
                lines.append('json_bytes_find_block(dat:=' + json_var + ', key:=key_' + f.name + ''
                              + ', open_byte:=byte#123, close_byte:=byte#125'
                              + ', start_index:=' + si_expr + ', end_index:=' + ei_expr
                              + ', block_start_index:=jblk1_bsi, block_end_index:=jblk1_bei, eno=>eno);')
                lines.append('if not eno then return; end_if;')
                lines.append('private_' + f.type.name + '_jsonbytes_to_iecdata(bytes:=' + json_var
                              + ', start_index:=jblk1_bsi, end_index:=jblk1_bei'
                              + ', data:=' + data_path + '.' + f.name + ', eno=>eno);')
                lines.append('if not eno then return; end_if;')
            elif isinstance(f.type, ArrayType):
                v1_bsi = 'jblk1_bsi'
                v1_bei = 'jblk1_bei'
                lines.append('// ' + f.name + ': array')
                lines.append('json_bytes_find_block(dat:=' + json_var + ', key:=key_' + f.name + ''
                              + ', open_byte:=byte#91, close_byte:=byte#93'
                              + ', start_index:=' + si_expr + ', end_index:=' + ei_expr
                              + ', block_start_index:=' + v1_bsi + ', block_end_index:=' + v1_bei + ', eno=>eno);')
                lines.append('if not eno then return; end_if;')
                lines.extend(self._array_elems_from_json_bytes(
                    f.type, data_path + '.' + f.name, json_var, v1_bsi, v1_bei, 1))
        return lines

    def _gen_struct_extractor_jsonstr(self, st: StructType) -> str:
        jlen = self._json_len
        lines = [
            'function private_' + st.name + '_jsontext_to_iecdata',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out txt: string[' + jlen + ']; end_var',
            TAB + 'var_in_out data: ' + st.name + '; end_var',
        ]
        var_lines = self._jsonstr_var_lines(st, jlen)
        if var_lines:
            lines.append(TAB + 'var_temp')
            for vl in var_lines:
                lines.append(TAB + TAB + vl)
            lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')
        body = self._struct_from_json_body(st, 'data', 'txt', 1)
        lines.extend(_indent(body))
        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _jsonstr_var_lines(self, t: AnyType, jlen: str) -> list:
        """Build the var_temp lines for a jsonstr_to_data function."""
        var_lines = []
        needs_pos_qos = self._direct_has_string(t) or self._needs_depth_v2(t) or self._has_string_array(t)
        needs_qp = self._has_array(t)
        if needs_pos_qos and needs_qp:
            var_lines.append('pos, qos, qp: dint;')
        elif needs_pos_qos:
            var_lines.append('pos, qos: dint;')
        elif needs_qp:
            var_lines.append('qp: dint;')
        if self._direct_has_non_string_scalar(t):
            var_lines.append('sv: ' + self._string_type + ';')
        max_d = _jblk_depth_v2(t)
        if max_d >= 1:
            extra = ', '.join(_pos_var(d) for d in range(1, max_d + 1))
            var_lines.append(extra + ': dint;')
        for d in range(1, max_d + 1):
            v = _jblk_var(d)
            var_lines.append(v + ': string[' + jlen + '];')
            var_lines.append(v + '_len: dint;')
            var_lines.append(v + '_sub: string[' + jlen + '];')
        if self._needs_depth_v2(t):
            var_lines.append('depth: dint;')
        return var_lines

    # --------------------------------------------------------- jsonstr_to_data

    def _gen_jsonstr_to_data(self, model: TypeModel) -> str:
        jlen = self._json_len
        pfx = model.prefix + '_'
        root = model.root
        lines = [
            'function ' + pfx + 'jsontext_to_iecdata',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out txt: string[' + jlen + ']; end_var',
            TAB + 'var_in_out data: ' + root.name + '; end_var',
        ]
        var_lines = self._jsonstr_var_lines(root, jlen)
        if var_lines:
            lines.append(TAB + 'var_temp')
            for vl in var_lines:
                lines.append(TAB + TAB + vl)
            lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')

        body = self._struct_from_json_body(root, 'data', 'txt', 1)
        lines.extend(_indent(body))

        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _struct_from_json_body(self, st: StructType, data_path: str,
                                json_var: str, next_depth: int) -> list:
        lines = []
        for f in st.fields:
            lines.extend(
                self._field_from_json(f.type, data_path + '.' + f.name,
                                      json_var, f.name, next_depth)
            )
        return lines

    def _field_from_json(self, t: AnyType, data_path: str,
                          json_var: str, key: str, next_depth: int) -> list:
        if isinstance(t, ScalarType):
            return self._scalar_from_json(t, data_path, json_var, key)
        if isinstance(t, StructType):
            return self._struct_from_json(t, data_path, json_var, key, next_depth)
        if isinstance(t, ArrayType):
            return self._array_from_json(t, data_path, json_var, key, next_depth)
        return []

    def _scalar_from_json(self, t: ScalarType, data_path: str,
                           json_var: str, key: str) -> list:
        if t.json_type == 'string':
            offset = len(key) + 4  # length of '"key":"' + 1 (1-indexed start of value)
            return [
                '// ' + key + ': string',
                "pos := json_find_key(dat:=" + json_var + ", key:='" + key + "');",
                'if pos = 0 then eno := false; return; end_if;',
                'pos := pos + ' + str(offset) + ';',
                'qos := pos;',
                'while qos <= uint_to_dint(len(' + json_var + ')) do',
                TAB + "if mid(" + json_var + ", 1, dint_to_uint(qos)) = '\\' then qos := qos + 2;",
                TAB + "elsif mid(" + json_var + ", 1, dint_to_uint(qos)) = '\"' then exit;",
                TAB + 'else qos := qos + 1;',
                TAB + 'end_if;',
                'end_while;',
                data_path + ' := json_unescape(in:=mid(' + json_var + ', dint_to_uint(qos - pos), dint_to_uint(pos)), eno=>eno);',
                'if not eno then return; end_if;',
            ]
        if t.json_type == 'boolean':
            return [
                '// ' + key + ': ' + t.iec_type,
                "json_extract_scalar(dat:=" + json_var + ", key:='" + key + "', sv:=sv, eno=>eno);",
                'if not eno then return; end_if;',
                data_path + " := sv = 'true';",
            ]
        from_str = _FROM_STR.get(t.iec_type, 'string_to_' + t.iec_type)
        return [
            '// ' + key + ': ' + t.iec_type,
            "json_extract_scalar(dat:=" + json_var + ", key:='" + key + "', sv:=sv, eno=>eno);",
            'if not eno then return; end_if;',
            data_path + ' := ' + from_str + '(sv);',
        ]

    def _struct_from_json(self, st: StructType, data_path: str,
                           json_var: str, key: str, depth: int) -> list:
        v = _jblk_var(depth)
        return [
            '// ' + key + ': struct',
            "json_find_block(dat:=" + json_var + ", key:='" + key + "', open_ch:='{', close_ch:='}', block:=" + v + ", eno=>eno);",
            'if not eno then return; end_if;',
            v + '_len := len(' + v + ');',
            'private_' + st.name + '_jsontext_to_iecdata(txt:=' + v + ', data:=' + data_path + ', eno=>eno);',
            'if not eno then return; end_if;',
        ]

    def _array_from_json(self, t: ArrayType, data_path: str,
                          json_var: str, key: str, depth: int) -> list:
        v = _jblk_var(depth)
        lines = [
            '// ' + key + ': array',
            "json_find_block(dat:=" + json_var + ", key:='" + key + "', open_ch:='[', close_ch:=']', block:=" + v + ", eno=>eno);",
            'if not eno then return; end_if;',
            v + '_len := len(' + v + ');',
        ]
        lines.extend(self._array_elems_from_sub(t, data_path, v, v + '_len', v + '_sub', depth))
        return lines

    def _extract_sub_block_at_cursor(self, src_v: str, open_ch: str, close_ch: str,
                                      pos_v: str, out_v: str, out_len_v: str) -> list:
        """Extract the block (open_ch...close_ch) from src_v starting at pos_v into out_v.
        pos_v must point to the opening bracket. Uses string-literal-aware depth counting.
        """
        return [
            'qos := ' + pos_v + ';',
            'depth := 1;',
            'while depth > 0 do',
            TAB + 'qos := qos + 1;',
            TAB + "if mid(" + src_v + ", 1, dint_to_uint(qos)) = '\"' then",
            TAB + TAB + '// skip string literal to avoid false bracket matches',
            TAB + TAB + 'qos := qos + 1;',
            TAB + TAB + "while mid(" + src_v + ", 1, dint_to_uint(qos)) <> '\"' do",
            TAB + TAB + TAB + "if mid(" + src_v + ", 1, dint_to_uint(qos)) = '\\' then qos := qos + 1; end_if;",
            TAB + TAB + TAB + 'qos := qos + 1;',
            TAB + TAB + 'end_while;',
            TAB + "elsif mid(" + src_v + ", 1, dint_to_uint(qos)) = '" + open_ch + "' then depth := depth + 1;",
            TAB + "elsif mid(" + src_v + ", 1, dint_to_uint(qos)) = '" + close_ch + "' then depth := depth - 1;",
            TAB + 'end_if;',
            'end_while;',
            out_v + ' := mid(' + src_v + ', dint_to_uint(qos - ' + pos_v + ' + 1), dint_to_uint(' + pos_v + '));',
            out_len_v + ' := len(' + out_v + ');',
        ]

    def _array_elems_from_sub(self, t: ArrayType, data_path: str,
                               jblk_v: str, jblk_len_v: str, jblk_sub_v: str,
                               depth: int, idx_parts: list = None) -> list:
        """Extract array elements from jblk_v using a sequential cursor."""
        if idx_parts is None:
            idx_parts = []
        pos_v = _pos_var(depth)
        elem = t.element_type
        lines = []

        if isinstance(elem, ScalarType):
            if elem.json_type == 'string':
                # jblk_v = ["v0","v1",...]  extract each element between double quotes
                lines.append(pos_v + ' := 2;')
                for idx in range(t.size):
                    full_idx = idx_parts + [str(idx)]
                    lines.append('// [' + str(idx) + ']')
                    lines.append(jblk_sub_v + ' := mid(' + jblk_v + ', dint_to_uint(' + jblk_len_v + ' - ' + pos_v + ' + 1), dint_to_uint(' + pos_v + '));')
                    lines.append(pos_v + " := find(" + jblk_sub_v + ", '\"') + " + pos_v + ';')
                    lines.append('qos := ' + pos_v + ';')
                    lines.append('while qos <= ' + jblk_len_v + ' do')
                    lines.append(TAB + "if mid(" + jblk_v + ", 1, dint_to_uint(qos)) = '\\' then qos := qos + 2;")
                    lines.append(TAB + "elsif mid(" + jblk_v + ", 1, dint_to_uint(qos)) = '\"' then exit;")
                    lines.append(TAB + 'else qos := qos + 1;')
                    lines.append(TAB + 'end_if;')
                    lines.append('end_while;')
                    lines.append(data_path + '[' + ', '.join(full_idx) + '] := json_unescape(in:=mid(' + jblk_v + ', dint_to_uint(qos - ' + pos_v + '), dint_to_uint(' + pos_v + ')), eno=>eno);')
                    lines.append('if not eno then return; end_if;')
                    lines.append(pos_v + ' := qos + 2;')
                return lines
            if elem.json_type == 'boolean':
                lines.append(pos_v + ' := 2;')
                for idx in range(t.size):
                    full_idx = idx_parts + [str(idx)]
                    lines.append('// [' + str(idx) + ']')
                    lines.append(jblk_sub_v + ' := mid(' + jblk_v + ', dint_to_uint(' + jblk_len_v + ' - ' + pos_v + ' + 1), dint_to_uint(' + pos_v + '));')
                    lines.append("qp := find(" + jblk_sub_v + ", ',');")
                    lines.append("if qp = 0 then qp := find(" + jblk_sub_v + ", ']'); end_if;")
                    lines.append(data_path + '[' + ', '.join(full_idx) + "] := mid(" + jblk_v + ", 4, dint_to_uint(" + pos_v + ")) = 'true';")
                    lines.append(pos_v + ' := ' + pos_v + ' + qp;')
                return lines
            # numeric
            from_str = _FROM_STR.get(elem.iec_type, 'string_to_' + elem.iec_type)
            lines.append(pos_v + ' := 2;')
            for idx in range(t.size):
                full_idx = idx_parts + [str(idx)]
                lines.append('// [' + str(idx) + ']')
                lines.append(jblk_sub_v + ' := mid(' + jblk_v + ', dint_to_uint(' + jblk_len_v + ' - ' + pos_v + ' + 1), dint_to_uint(' + pos_v + '));')
                lines.append("qp := find(" + jblk_sub_v + ", ',');")
                lines.append("if qp = 0 then qp := find(" + jblk_sub_v + ", ']'); end_if;")
                lines.append(data_path + '[' + ', '.join(full_idx) + '] := ' + from_str + '(mid(' + jblk_v + ', dint_to_uint(qp - 1), dint_to_uint(' + pos_v + ')));')
                lines.append(pos_v + ' := ' + pos_v + ' + qp;')
            return lines

        # Array of arrays
        if isinstance(elem, ArrayType):
            next_v = _jblk_var(depth + 1)
            next_len = next_v + '_len'
            lines.append(pos_v + ' := 2;')
            for idx in range(t.size):
                lines.append('// [' + str(idx) + ']')
                lines.extend(self._extract_sub_block_at_cursor(jblk_v, '[', ']', pos_v, next_v, next_len))
                new_parts = idx_parts + [str(idx)]
                lines.extend(self._array_elems_from_sub(elem, data_path, next_v, next_len, next_v + '_sub', depth + 1, new_parts))
                lines.append(pos_v + ' := ' + pos_v + ' + ' + next_len + ' + 1;')
            return lines

        # Array of structs — call per-struct extractor function
        if isinstance(elem, StructType):
            next_v = _jblk_var(depth + 1)
            next_len = next_v + '_len'
            outer_cursor = _pos_var(depth + 1)
            lines.append(outer_cursor + ' := 2;')
            for idx in range(t.size):
                lines.append('// [' + str(idx) + ']')
                lines.extend(self._extract_sub_block_at_cursor(jblk_v, '{', '}', outer_cursor, next_v, next_len))
                new_parts = idx_parts + [str(idx)]
                elem_path = data_path + '[' + ', '.join(new_parts) + ']'
                lines.append('private_' + elem.name + '_jsontext_to_iecdata(txt:=' + next_v + ', data:=' + elem_path + ', eno=>eno);')
                lines.append('if not eno then return; end_if;')
                lines.append(outer_cursor + ' := ' + outer_cursor + ' + ' + next_len + ' + 1;')
            return lines

        return lines

    # --------------------------------------------------------- jsonbytes_to_data

    def _array_elems_from_json_bytes(self, t: 'ArrayType', data_path: str,
                                      json_var: str, bsi_v: str, bei_v: str,
                                      depth: int, idx_parts: list = None) -> list:
        """Generate pure byte array cursor code to extract array elements."""
        if idx_parts is None:
            idx_parts = []
        pos_v = _pos_var(depth)
        elem = t.element_type
        lines = []
        lines.append(pos_v + ' := ' + bsi_v + ' + 1;  // skip \'[\'')

        if isinstance(elem, ScalarType):
            if elem.json_type == 'string':
                for idx in range(t.size):
                    full_idx = idx_parts + [str(idx)]
                    lines.append('// [' + str(idx) + ']')
                    lines.append(pos_v + ' := ' + pos_v + ' + 1;  // skip opening \'\"\'')
                    lines.append('if ' + pos_v + ' > ' + bei_v + ' then eno := false; return; end_if;')
                    lines.append('qos := ' + pos_v + ';')
                    lines.append('while qos <= ' + bei_v + ' and ' + json_var + '[qos] <> 34 do  // 34 = \'\"\'')
                    lines.append(TAB + 'if ' + json_var + '[qos] = 92 then')
                    lines.append(TAB + TAB + 'qos := qos + 1;')
                    lines.append(TAB + TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                    lines.append(TAB + 'end_if;')
                    lines.append(TAB + 'qos := qos + 1;')
                    lines.append('end_while;')
                    lines.append('if qos > ' + bei_v + ' then eno := false; return; end_if;')
                    lines.append('json_bytes_to_str(dat:=' + json_var + ', start_index:=' + pos_v + ', end_index:=qos - 1, sv:=sv, eno=>eno);')
                    lines.append('if not eno then return; end_if;')
                    lines.append(data_path + '[' + ', '.join(full_idx) + '] := json_unescape(in:=sv, eno=>eno);')
                    lines.append('if not eno then return; end_if;')
                    lines.append(pos_v + ' := qos + 2;  // skip \'"\' and \',\'')
                return lines

            if elem.json_type == 'boolean':
                for idx in range(t.size):
                    full_idx = idx_parts + [str(idx)]
                    lines.append('// [' + str(idx) + ']')
                    lines.append(data_path + '[' + ', '.join(full_idx) + '] := ' + json_var + '[' + pos_v + '] = byte#116;  // 116 = \'t\'')
                    lines.append('qos := ' + pos_v + ';')
                    lines.append('while qos <= ' + bei_v + ' and ' + json_var + '[qos] <> 44 and ' + json_var + '[qos] <> 93 do  // 44 = \',\', 93 = \']\'')
                    lines.append(TAB + 'qos := qos + 1;')
                    lines.append('end_while;')
                    lines.append('if qos > ' + bei_v + ' then eno := false; return; end_if;')
                    lines.append(pos_v + ' := qos + 1;')
                return lines

            # numeric
            from_str = _FROM_STR.get(elem.iec_type, 'string_to_' + elem.iec_type)
            for idx in range(t.size):
                full_idx = idx_parts + [str(idx)]
                lines.append('// [' + str(idx) + ']')
                lines.append('qos := ' + pos_v + ';')
                lines.append('while qos <= ' + bei_v + ' and ' + json_var + '[qos] <> 44 and ' + json_var + '[qos] <> 93 do  // 44 = \',\', 93 = \']\'')
                lines.append(TAB + 'qos := qos + 1;')
                lines.append('end_while;')
                lines.append('if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append('json_bytes_to_str(dat:=' + json_var + ', start_index:=' + pos_v + ', end_index:=qos - 1, sv:=sv, eno=>eno);')
                lines.append('if not eno then return; end_if;')
                lines.append(data_path + '[' + ', '.join(full_idx) + '] := ' + from_str + '(sv);')
                lines.append(pos_v + ' := qos + 1;')
            return lines

        # Array of arrays
        if isinstance(elem, ArrayType):
            next_bei_v = _jblk_var(depth + 1) + '_bei'
            for idx in range(t.size):
                lines.append('// [' + str(idx) + ']')
                lines.append('qos := ' + pos_v + ';')
                lines.append('depth := 1;')
                lines.append('while depth > 0 do')
                lines.append(TAB + 'qos := qos + 1;')
                lines.append(TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append(TAB + 'if ' + json_var + '[qos] = 34 then  // \'\"\'')
                lines.append(TAB + TAB + 'qos := qos + 1;')
                lines.append(TAB + TAB + 'while qos <= ' + bei_v + ' and ' + json_var + '[qos] <> 34 do')
                lines.append(TAB + TAB + TAB + 'if ' + json_var + '[qos] = 92 then')
                lines.append(TAB + TAB + TAB + TAB + 'qos := qos + 1;')
                lines.append(TAB + TAB + TAB + TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append(TAB + TAB + TAB + 'end_if;')
                lines.append(TAB + TAB + TAB + 'qos := qos + 1;')
                lines.append(TAB + TAB + 'end_while;')
                lines.append(TAB + TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append(TAB + "elsif " + json_var + "[qos] = 91 then depth := depth + 1;  // '['")
                lines.append(TAB + "elsif " + json_var + "[qos] = 93 then depth := depth - 1;  // ']'")
                lines.append(TAB + 'end_if;')
                lines.append('end_while;')
                lines.append(next_bei_v + ' := qos;')
                new_parts = idx_parts + [str(idx)]
                lines.extend(self._array_elems_from_json_bytes(
                    elem, data_path, json_var, pos_v, next_bei_v, depth + 1, new_parts))
                lines.append(pos_v + ' := ' + next_bei_v + ' + 2;')
            return lines

        # Array of structs
        if isinstance(elem, StructType):
            for idx in range(t.size):
                full_idx = idx_parts + [str(idx)]
                lines.append('// [' + str(idx) + ']')
                lines.append('qos := ' + pos_v + ';')
                lines.append('depth := 1;')
                lines.append('while depth > 0 do')
                lines.append(TAB + 'qos := qos + 1;')
                lines.append(TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append(TAB + 'if ' + json_var + '[qos] = 34 then  // \'\"\'')
                lines.append(TAB + TAB + 'qos := qos + 1;')
                lines.append(TAB + TAB + 'while qos <= ' + bei_v + ' and ' + json_var + '[qos] <> 34 do')
                lines.append(TAB + TAB + TAB + 'if ' + json_var + '[qos] = 92 then')
                lines.append(TAB + TAB + TAB + TAB + 'qos := qos + 1;')
                lines.append(TAB + TAB + TAB + TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append(TAB + TAB + TAB + 'end_if;')
                lines.append(TAB + TAB + TAB + 'qos := qos + 1;')
                lines.append(TAB + TAB + 'end_while;')
                lines.append(TAB + TAB + 'if qos > ' + bei_v + ' then eno := false; return; end_if;')
                lines.append(TAB + "elsif " + json_var + "[qos] = 123 then depth := depth + 1;  // '{'")
                lines.append(TAB + "elsif " + json_var + "[qos] = 125 then depth := depth - 1;  // '}'")
                lines.append(TAB + 'end_if;')
                lines.append('end_while;')
                elem_path = data_path + '[' + ', '.join(full_idx) + ']'
                lines.append('private_' + elem.name + '_jsonbytes_to_iecdata(bytes:=' + json_var
                             + ', start_index:=' + pos_v + ', end_index:=qos'
                             + ', data:=' + elem_path + ', eno=>eno);')
                lines.append('if not eno then return; end_if;')
                lines.append(pos_v + ' := qos + 2;')
            return lines

        return lines

    def _scalar_from_json_bytes(self, t: ScalarType, data_path: str,
                                 json_bytes_var: str, key: str,
                                 si_expr: str = '0', ei_expr: str = 'JSON_STRING_SIZE') -> list:
        """Generate code to extract a scalar field directly from a byte array."""
        bv = json_bytes_var
        if t.json_type == 'string':
            return [
                '// ' + key + ': string',
                'raw_ci := json_bytes_find_key(dat:=' + bv + ', key:=key_' + key + ', start_index:=' + si_expr + ', end_index:=' + ei_expr + ', eno=>eno);',
                'if raw_ci = -1 then eno := false; return; end_if;',
                'raw_ci := raw_ci + 1;  // skip opening "',
                "sv := '';",
                'while ' + bv + '[raw_ci] <> 34 do  // 34 = double-quote',
                TAB + 'if ' + bv + '[raw_ci] = 92 then  // 92 = backslash',
                TAB + TAB + "sv := concat(sv, '\\');",
                TAB + TAB + 'raw_ci := raw_ci + 1;',
                TAB + 'end_if;',
                TAB + 'sv := concat(sv, json_char_from_asciicharcode(code:=byte_to_dint(' + bv + '[raw_ci]), eno=>eno));',
                TAB + 'if not eno then return; end_if;',
                TAB + 'raw_ci := raw_ci + 1;',
                'end_while;',
                data_path + ' := json_unescape(in:=sv, eno=>eno);',
                'if not eno then return; end_if;',
            ]
        if t.json_type == 'boolean':
            return [
                '// ' + key + ': ' + t.iec_type,
                'json_bytes_extract_scalar(dat:=' + bv + ', key:=key_' + key + ', start_index:=' + si_expr + ', end_index:=' + ei_expr + ', sv:=sv, eno=>eno);',
                'if not eno then return; end_if;',
                data_path + " := sv = 'true';",
            ]
        from_str = _FROM_STR.get(t.iec_type, 'string_to_' + t.iec_type)
        return [
            '// ' + key + ': ' + t.iec_type,
            'json_bytes_extract_scalar(dat:=' + bv + ', key:=key_' + key + ', start_index:=' + si_expr + ', end_index:=' + ei_expr + ', sv:=sv, eno=>eno);',
            'if not eno then return; end_if;',
            data_path + ' := ' + from_str + '(sv);',
        ]

    def _gen_jsonbytes_to_data(self, model: TypeModel) -> str:
        jlen = self._json_len
        pfx = model.prefix + '_'
        root = model.root

        lines = [
            'function ' + pfx + 'jsonbytes_to_iecdata',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out bytes: array[*] of byte; end_var',
            TAB + 'var_input start_index: dint := -1; end_var',
            TAB + 'var_input end_index: dint := -1; end_var',
            TAB + 'var_in_out data: ' + root.name + '; end_var',
        ]
        var_lines = self._jsonbytes_var_lines(root, jlen)
        var_lines_with_ei = ['si, ei: dint;'] + var_lines
        lines.append(TAB + 'var_temp')
        for vl in var_lines_with_ei:
            lines.append(TAB + TAB + vl)
        lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')
        lines.append(TAB + 'if start_index < 0 then si := lower_bound(bytes, 1); else si := start_index; end_if;')
        lines.append(TAB + 'if end_index < 0 then ei := upper_bound(bytes, 1); else ei := end_index; end_if;')

        body = self._struct_from_jsonbytes_body(root, 'data', 'bytes',
                                                si_expr='si', ei_expr='ei')
        lines.extend(_indent(body))

        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)
