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


def _jblk_depth(t: AnyType) -> int:
    """Return the max number of jblk nesting levels needed to parse fields of type t."""
    if isinstance(t, StructType):
        depths = [
            1 + _jblk_depth(f.type) if isinstance(f.type, (StructType, ArrayType)) else 0
            for f in t.fields
        ]
        return max(depths) if depths else 0
    if isinstance(t, ArrayType):
        return 1 + _jblk_depth(t.element_type)
    return 0


def _jblk_var(depth: int) -> str:
    return 'jblk' + str(depth)


def _pos_var(depth: int) -> str:
    return 'pos' + str(depth)


class IecGenerator:
    def __init__(self, json_len: str = '1024'):
        self._json_len = json_len

    # ------------------------------------------------------------------ public

    def generate(self, model: TypeModel) -> str:
        parts = []
        parts.append(self._gen_type_defs(model))
        parts.append(_JSON_HELPERS)
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

    def _needs_depth(self, t: AnyType) -> bool:
        if isinstance(t, StructType):
            return any(
                isinstance(f.type, (StructType, ArrayType)) or self._needs_depth(f.type)
                for f in t.fields
            )
        if isinstance(t, ArrayType):
            return True
        return False

    def _needs_sub(self, t: AnyType) -> bool:
        if isinstance(t, StructType):
            return any(
                isinstance(f.type, (StructType, ArrayType)) or self._needs_sub(f.type)
                for f in t.fields
            )
        if isinstance(t, ArrayType):
            return True
        return False

    # --------------------------------------------------------- data_to_jsonstr

    def _gen_data_to_jsonstr(self, model: TypeModel) -> str:
        jlen = self._json_len
        pfx = model.prefix + '_'
        lines = [
            'function ' + pfx + 'data_to_jsonstr',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out data: ' + model.root.name + '; end_var',
            TAB + 'var_in_out json: string[' + jlen + ']; end_var',
        ]
        if self._has_numeric(model.root):
            lines.append(TAB + 'var_temp')
            lines.append(TAB + TAB + 'sv: string[JSON_STRING_SIZE];')
            lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')

        body = self._struct_to_json_body(model.root, 'data', first_assign=True)
        lines.extend(_indent(body))

        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _struct_to_json_body(self, st: StructType, path: str,
                              first_assign: bool = False) -> list:
        lines = []
        if first_assign:
            lines.append("json := '{';")
        else:
            lines.append("json := concat(json, '{');")
        for i, f in enumerate(st.fields):
            sep = '' if i == 0 else ','
            lines.append("json := concat(json, '" + sep + '"' + f.name + '":' + "');")
            lines.extend(self._field_to_json(f.type, path + '.' + f.name))
        lines.append("json := concat(json, '}');")
        return lines

    def _field_to_json(self, t: AnyType, path: str) -> list:
        if isinstance(t, ScalarType):
            return self._scalar_to_json(t, path)
        if isinstance(t, StructType):
            return self._struct_to_json_body(t, path)
        if isinstance(t, ArrayType):
            return self._array_to_json(t, path)
        return []

    def _scalar_to_json(self, t: ScalarType, path: str) -> list:
        if t.json_type == 'string':
            return [
                "json := concat(json, '\"');",
                'json := concat(json, json_escape(' + path + '));',
                "json := concat(json, '\"');",
            ]
        if t.json_type == 'boolean':
            return [
                'if ' + path + ' then',
                TAB + "json := concat(json, 'true');",
                'else',
                TAB + "json := concat(json, 'false');",
                'end_if;',
            ]
        func = _TO_STR.get(t.iec_type, t.iec_type + '_to_string')
        return [
            'sv := ' + func + '(' + path + ');',
            'json := concat(json, sv);',
        ]

    def _array_to_json(self, t: ArrayType, path: str, idx_parts: list = None) -> list:
        if idx_parts is None:
            idx_parts = []
        lines = ["json := concat(json, '[');"]
        for idx in range(t.size):
            if idx > 0:
                lines.append("json := concat(json, ',');")
            new_parts = idx_parts + [str(idx)]
            if isinstance(t.element_type, ArrayType):
                lines.extend(self._array_to_json(t.element_type, path, new_parts))
            else:
                lines.extend(self._field_to_json(t.element_type, path + '[' + ', '.join(new_parts) + ']'))
        lines.append("json := concat(json, ']');")
        return lines

    # --------------------------------------------------------- data_to_jsonbytes

    def _gen_data_to_jsonbytes(self, model: TypeModel) -> str:
        pfx = model.prefix + '_'
        lines = [
            'function ' + pfx + 'data_to_jsonbytes',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out data: ' + model.root.name + '; end_var',
            TAB + 'var_in_out json: array[*] of byte; end_var',
            TAB + 'var_temp',
        ]
        if self._has_numeric(model.root):
            lines.append(TAB + TAB + 'sv: string[JSON_STRING_SIZE];')
        lines.append(TAB + TAB + 'raw_ci: dint;')
        lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')
        lines.append(TAB + 'raw_ci := 0;')

        body = self._struct_to_jsonbytes_body(model.root, 'data')
        lines.extend(_indent(body))

        lines.append(TAB + 'json[raw_ci] := 0;')
        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    def _struct_to_jsonbytes_body(self, st: StructType, path: str) -> list:
        lines = ["raw_ci := json_bytes_insert_str(json, raw_ci, '{');"]
        for i, f in enumerate(st.fields):
            sep = '' if i == 0 else ','
            lines.append("raw_ci := json_bytes_insert_str(json, raw_ci, '" + sep + '"' + f.name + '":' + "');")
            lines.extend(self._field_to_jsonbytes(f.type, path + '.' + f.name))
        lines.append("raw_ci := json_bytes_insert_str(json, raw_ci, '}');")
        return lines

    def _field_to_jsonbytes(self, t: AnyType, path: str) -> list:
        if isinstance(t, ScalarType):
            return self._scalar_to_jsonbytes(t, path)
        if isinstance(t, StructType):
            return self._struct_to_jsonbytes_body(t, path)
        if isinstance(t, ArrayType):
            return self._array_to_jsonbytes(t, path)
        return []

    def _scalar_to_jsonbytes(self, t: ScalarType, path: str) -> list:
        if t.json_type == 'string':
            return [
                "raw_ci := json_bytes_insert_str(json, raw_ci, '\"');",
                'raw_ci := json_bytes_insert_str(json, raw_ci, json_escape(' + path + '));',
                "raw_ci := json_bytes_insert_str(json, raw_ci, '\"');",
            ]
        if t.json_type == 'boolean':
            return [
                'if ' + path + ' then',
                TAB + "raw_ci := json_bytes_insert_str(json, raw_ci, 'true');",
                'else',
                TAB + "raw_ci := json_bytes_insert_str(json, raw_ci, 'false');",
                'end_if;',
            ]
        func = _TO_STR.get(t.iec_type, t.iec_type + '_to_string')
        return [
            'sv := ' + func + '(' + path + ');',
            'raw_ci := json_bytes_insert_str(json, raw_ci, sv);',
        ]

    def _array_to_jsonbytes(self, t: ArrayType, path: str, idx_parts: list = None) -> list:
        if idx_parts is None:
            idx_parts = []
        lines = ["raw_ci := json_bytes_insert_str(json, raw_ci, '[');"]
        for idx in range(t.size):
            if idx > 0:
                lines.append("raw_ci := json_bytes_insert_str(json, raw_ci, ',');")
            new_parts = idx_parts + [str(idx)]
            if isinstance(t.element_type, ArrayType):
                lines.extend(self._array_to_jsonbytes(t.element_type, path, new_parts))
            else:
                lines.extend(self._field_to_jsonbytes(t.element_type, path + '[' + ', '.join(new_parts) + ']'))
        lines.append("raw_ci := json_bytes_insert_str(json, raw_ci, ']');")
        return lines

    # --------------------------------------------------------- jsonbytes_to_data

    def _scalar_from_json_bytes(self, t: ScalarType, data_path: str,
                                 json_bytes_var: str, key: str) -> list:
        """Generate code to extract a scalar field directly from a byte array."""
        bv = json_bytes_var
        call = "json_bytes_find_key(" + bv + ", '" + key + "')"
        if t.json_type == 'string':
            return [
                '// ' + key + ': string',
                'raw_ci := ' + call + ';',
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
                'raw_ci := ' + call + ';',
                'if raw_ci = -1 then eno := false; return; end_if;',
                data_path + ' := byte_to_dint(' + bv + '[raw_ci]) = 116;  // 116 = t (true)',
            ]
        from_str = _FROM_STR.get(t.iec_type, 'string_to_' + t.iec_type)
        return [
            '// ' + key + ': ' + t.iec_type,
            'raw_ci := ' + call + ';',
            'if raw_ci = -1 then eno := false; return; end_if;',
            "sv := '';",
            # 44=',', 125='}', 93=']', 0=NUL
            'while ' + bv + '[raw_ci] <> 44 and ' + bv + '[raw_ci] <> 125 and ' + bv + '[raw_ci] <> 93 and ' + bv + '[raw_ci] <> 0 do',
            TAB + 'sv := concat(sv, json_char_from_asciicharcode(code:=byte_to_dint(' + bv + '[raw_ci]), eno=>eno));',
            TAB + 'if not eno then return; end_if;',
            TAB + 'raw_ci := raw_ci + 1;',
            'end_while;',
            data_path + ' := ' + from_str + '(sv);',
        ]

    def _extract_block_from_bytes(self, json_bytes_var: str, key: str,
                                   open_ch: str, close_ch: str,
                                   out_str_var: str, out_len_var: str) -> list:
        """Extract a {..} or [..] block from a byte array into a string variable."""
        bv = json_bytes_var
        open_byte = ord(open_ch)    # { = 123, [ = 91
        close_byte = ord(close_ch)  # } = 125, ] = 93
        kind = 'struct' if open_ch == '{' else 'array'
        return [
            '// ' + key + ': ' + kind,
            "raw_ci := json_bytes_find_key(" + bv + ", '" + key + "');",
            'if raw_ci = -1 then eno := false; return; end_if;',
            'raw_qos := raw_ci;',
            'raw_depth := 1;',
            'while raw_depth > 0 do',
            TAB + 'raw_qos := raw_qos + 1;',
            TAB + 'if ' + bv + '[raw_qos] = 34 then',
            TAB + TAB + '// skip string literal',
            TAB + TAB + 'raw_qos := raw_qos + 1;',
            TAB + TAB + 'while ' + bv + '[raw_qos] <> 34 do',
            TAB + TAB + TAB + 'if ' + bv + '[raw_qos] = 92 then raw_qos := raw_qos + 1; end_if;',
            TAB + TAB + TAB + 'raw_qos := raw_qos + 1;',
            TAB + TAB + 'end_while;',
            TAB + 'elsif ' + bv + '[raw_qos] = ' + str(open_byte) + ' then raw_depth := raw_depth + 1;',
            TAB + 'elsif ' + bv + '[raw_qos] = ' + str(close_byte) + ' then raw_depth := raw_depth - 1;',
            TAB + 'end_if;',
            'end_while;',
            out_str_var + " := '';",
            'while raw_ci <= raw_qos do',
            TAB + out_str_var + ' := concat(' + out_str_var + ', json_char_from_asciicharcode(code:=byte_to_dint(' + bv + '[raw_ci]), eno=>eno));',
            TAB + 'if not eno then return; end_if;',
            TAB + 'raw_ci := raw_ci + 1;',
            'end_while;',
            out_len_var + ' := len(' + out_str_var + ');',
        ]

    def _gen_jsonbytes_to_data(self, model: TypeModel) -> str:
        jlen = self._json_len
        pfx = model.prefix + '_'
        root = model.root
        has_nested = any(isinstance(f.type, (StructType, ArrayType)) for f in root.fields)

        lines = [
            'function ' + pfx + 'jsonbytes_to_data',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out json: array[*] of byte; end_var',
            TAB + 'var_in_out data: ' + root.name + '; end_var',
            TAB + 'var_temp',
            TAB + TAB + 'sv: string[JSON_STRING_SIZE];',
            TAB + TAB + 'raw_ci, raw_qos, raw_depth: dint;',
        ]
        if has_nested:
            lines.append(TAB + TAB + 'pos, qos, qp: dint;')
            max_d = _jblk_depth(root)
            extra = ', '.join(_pos_var(d) for d in range(1, max_d + 1))
            lines.append(TAB + TAB + extra + ': dint;')
            for d in range(1, max_d + 1):
                v = _jblk_var(d)
                lines.append(TAB + TAB + v + ': string[' + jlen + '];')
                lines.append(TAB + TAB + v + '_len: dint;')
                lines.append(TAB + TAB + v + '_sub: string[' + jlen + '];')
            if self._needs_depth(root):
                lines.append(TAB + TAB + 'depth: dint;')
        lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')

        body = []
        for f in root.fields:
            if isinstance(f.type, ScalarType):
                body.extend(self._scalar_from_json_bytes(f.type, 'data.' + f.name, 'json', f.name))
            elif isinstance(f.type, StructType):
                v1 = _jblk_var(1)
                body.extend(self._extract_block_from_bytes('json', f.name, '{', '}', v1, v1 + '_len'))
                body.extend(self._struct_from_json_body(f.type, 'data.' + f.name, v1, 2))
            elif isinstance(f.type, ArrayType):
                v1 = _jblk_var(1)
                body.extend(self._extract_block_from_bytes('json', f.name, '[', ']', v1, v1 + '_len'))
                body.extend(self._array_elems_from_sub(f.type, 'data.' + f.name, v1, v1 + '_len', v1 + '_sub', 1))
        lines.extend(_indent(body))

        lines.append('(*{end}*)')
        lines.append('end_function')
        return '\n'.join(lines)

    # --------------------------------------------------------- jsonstr_to_data

    def _gen_jsonstr_to_data(self, model: TypeModel) -> str:
        jlen = self._json_len
        pfx = model.prefix + '_'
        lines = [
            'function ' + pfx + 'jsonstr_to_data',
            TAB + '_DEFINE_ENENO_()',
            TAB + 'var_in_out json: string[' + jlen + ']; end_var',
            TAB + 'var_in_out data: ' + model.root.name + '; end_var',
            TAB + 'var_temp',
            TAB + TAB + 'pos, qos, qp: dint;',
        ]
        max_d = _jblk_depth(model.root)
        if max_d >= 1:
            extra = ', '.join(_pos_var(d) for d in range(1, max_d + 1))
            lines.append(TAB + TAB + extra + ': dint;')
        for d in range(1, max_d + 1):
            v = _jblk_var(d)
            lines.append(TAB + TAB + v + ': string[' + jlen + '];')
            lines.append(TAB + TAB + v + '_len: dint;')
            lines.append(TAB + TAB + v + '_sub: string[' + jlen + '];')
        if self._needs_depth(model.root):
            lines.append(TAB + TAB + 'depth: dint;')
        lines.append(TAB + 'end_var')
        lines.append('(*{st}*)')

        body = self._struct_from_json_body(model.root, 'data', 'json', 1)
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
        jlen = self._json_len
        in_block = (json_var != 'json')
        len_expr = json_var + '_len' if in_block else 'uint_to_dint(len(' + json_var + '))'
        sub_var  = json_var + '_sub'
        if t.json_type == 'string':
            offset = len(key) + 4  # length of '"key":"' + 1 (1-indexed start of value)
            return [
                '// ' + key + ': string',
                "pos := json_find_key(" + json_var + ", '" + key + "');",
                'if pos = 0 then eno := false; return; end_if;',
                'pos := pos + ' + str(offset) + ';',
                'qos := pos;',
                'while qos <= ' + len_expr + ' do',
                TAB + "if mid(" + json_var + ", 1, dint_to_uint(qos)) = '\\' then qos := qos + 2;",
                TAB + "elsif mid(" + json_var + ", 1, dint_to_uint(qos)) = '\"' then exit;",
                TAB + 'else qos := qos + 1;',
                TAB + 'end_if;',
                'end_while;',
                data_path + ' := json_unescape(in:=mid(' + json_var + ', dint_to_uint(qos - pos), dint_to_uint(pos)), eno=>eno);',
                'if not eno then return; end_if;',
            ]
        if t.json_type == 'boolean':
            val_offset = len(key) + 3  # position of first char of value (after "key":)
            return [
                '// ' + key + ': ' + t.iec_type,
                'pos := json_find_key(' + json_var + ", '" + key + "');",
                'if pos = 0 then eno := false; return; end_if;',
                data_path + ' := mid(' + json_var + ', 4, dint_to_uint(pos + ' + str(val_offset) + ")) = 'true';",
            ]
        offset = len(key) + 3  # length of '"key":' + 1 (1-indexed)
        from_str = _FROM_STR.get(t.iec_type, 'string_to_' + t.iec_type)
        if in_block:
            return [
                '// ' + key + ': ' + t.iec_type,
                'pos := json_find_key(' + json_var + ", '" + key + "');",
                'if pos = 0 then eno := false; return; end_if;',
                'pos := pos + ' + str(offset) + ';',
                sub_var + ' := mid(' + json_var + ', dint_to_uint(' + json_var + '_len - pos + 1), dint_to_uint(pos));',
                "qp := find(" + sub_var + ", ',');",
                "if qp = 0 then qp := find(" + sub_var + ", '}'); end_if;",
                "if qp = 0 then qp := find(" + sub_var + ", ']'); end_if;",
                'if qp = 0 then eno := false; return; end_if;',
                data_path + ' := ' + from_str + '(mid(' + json_var + ', dint_to_uint(qp - 1), dint_to_uint(pos)));',
            ]
        return [
            '// ' + key + ': ' + t.iec_type,
            'pos := json_find_key(' + json_var + ", '" + key + "');",
            'if pos = 0 then eno := false; return; end_if;',
            'pos := pos + ' + str(offset) + ';',
            'qp := find(mid(' + json_var + ', dint_to_uint(len(' + json_var + ') - pos + 1), dint_to_uint(pos)), \',\');',
            'if qp = 0 then qp := find(mid(' + json_var + ', dint_to_uint(len(' + json_var + ') - pos + 1), dint_to_uint(pos)), \'}\'); end_if;',
            'if qp = 0 then qp := find(mid(' + json_var + ', dint_to_uint(len(' + json_var + ') - pos + 1), dint_to_uint(pos)), \']\'); end_if;',
            'if qp = 0 then eno := false; return; end_if;',
            data_path + ' := ' + from_str + '(mid(' + json_var + ', dint_to_uint(qp - 1), dint_to_uint(pos)));',
        ]

    def _extract_sub_block(self, json_var: str, key: str,
                            open_ch: str, close_ch: str,
                            out_var: str, out_len_var: str) -> list:
        """Extract the block ({...} or [...]) for the given key into out_var.
        String literals in the JSON are skipped so their content cannot
        interfere with the bracket depth counter.
        """
        offset = len(key) + 3  # length of '"key":' + 1
        return [
            'pos := json_find_key(' + json_var + ", '" + key + "');",
            'if pos = 0 then eno := false; return; end_if;',
            'pos := pos + ' + str(offset) + ';',
            'qos := pos;',
            'depth := 1;',
            'while depth > 0 do',
            TAB + 'qos := qos + 1;',
            TAB + "if mid(" + json_var + ", 1, dint_to_uint(qos)) = '\"' then",
            TAB + TAB + '// skip string literal to avoid false bracket matches',
            TAB + TAB + 'qos := qos + 1;',
            TAB + TAB + "while mid(" + json_var + ", 1, dint_to_uint(qos)) <> '\"' do",
            TAB + TAB + TAB + "if mid(" + json_var + ", 1, dint_to_uint(qos)) = '\\' then qos := qos + 1; end_if;",
            TAB + TAB + TAB + 'qos := qos + 1;',
            TAB + TAB + 'end_while;',
            TAB + "elsif mid(" + json_var + ", 1, dint_to_uint(qos)) = '" + open_ch + "' then depth := depth + 1;",
            TAB + "elsif mid(" + json_var + ", 1, dint_to_uint(qos)) = '" + close_ch + "' then depth := depth - 1;",
            TAB + 'end_if;',
            'end_while;',
            out_var + ' := mid(' + json_var + ', dint_to_uint(qos - pos + 1), dint_to_uint(pos));',
            out_len_var + ' := len(' + out_var + ');',
        ]

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

    def _struct_from_json(self, st: StructType, data_path: str,
                           json_var: str, key: str, depth: int) -> list:
        v = _jblk_var(depth)
        lines = ['// ' + key + ': struct']
        lines.extend(self._extract_sub_block(json_var, key, '{', '}', v, v + '_len'))
        lines.extend(self._struct_from_json_body(st, data_path, v, depth + 1))
        return lines

    def _array_from_json(self, t: ArrayType, data_path: str,
                          json_var: str, key: str, depth: int) -> list:
        v = _jblk_var(depth)
        lines = ['// ' + key + ': array']
        lines.extend(self._extract_sub_block(json_var, key, '[', ']', v, v + '_len'))
        lines.extend(self._array_elems_from_sub(t, data_path, v, v + '_len', v + '_sub', depth))
        return lines

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

        # Array of structs
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
                lines.extend(self._struct_from_json_body(elem, elem_path, next_v, depth + 2))
                lines.append(outer_cursor + ' := ' + outer_cursor + ' + ' + next_len + ' + 1;')
            return lines

        return lines
