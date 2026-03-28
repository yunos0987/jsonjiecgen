# coding: utf-8
import json as _json
import pathlib as _pathlib
from model import ScalarType, StructType, ArrayType, AnyType, StructField, TypeModel


_TEST_JSON_HELPERS = (
    (_pathlib.Path(__file__).parent / 'test_json_helpers.txt')
    .read_text(encoding='utf-8').rstrip('\n')
)

TAB = '\t'

# Maps IEC scalar type name -> jiecunit assertion macro suffix (UPPERCASE)
_ASSERT_SUFFIX = {
    'sint':  'SINT',
    'int':   'INT',
    'dint':  'DINT',
    'lint':  'LINT',
    'usint': 'USINT',
    'uint':  'UINT',
    'udint': 'UDINT',
    'ulint': 'ULINT',
}

_FLOAT_TYPES = {'real', 'lreal'}
_INT_TYPES   = set(_ASSERT_SUFFIX.keys())


def _string_iec_type(t: AnyType) -> str:
    """Return iec_type of the first string field found, or '' if none."""
    if isinstance(t, ScalarType):
        return t.iec_type if t.json_type == 'string' else ''
    if isinstance(t, StructType):
        for f in t.fields:
            r = _string_iec_type(f.type)
            if r:
                return r
    if isinstance(t, ArrayType):
        return _string_iec_type(t.element_type)
    return ''


def _default_value_for_type(t: AnyType):
    """Return a default Python value for the given type (used in schema mode)."""
    if isinstance(t, ScalarType):
        if t.json_type == 'string':
            return ''
        if t.json_type == 'boolean':
            return False
        if t.json_type == 'number':
            return 0.0
        return 0
    if isinstance(t, StructType):
        return {f.name: _default_value_for_type(f.type) for f in t.fields}
    if isinstance(t, ArrayType):
        return [_default_value_for_type(t.element_type) for _ in range(t.size)]
    return 0


def _first_scalar_field(root: StructType, iec_types: set):
    """Return (name, ScalarType) for the first root-level scalar field in iec_types."""
    for f in root.fields:
        if isinstance(f.type, ScalarType) and f.type.iec_type in iec_types:
            return (f.name, f.type)
    return None


def _first_string_field(root: StructType):
    """Return (name, ScalarType) for the first root-level string field."""
    for f in root.fields:
        if isinstance(f.type, ScalarType) and f.type.json_type == 'string':
            return (f.name, f.type)
    return None


class JiecUnitGenerator:
    def __init__(self, pou_filename: str = 'output.txt', json_len: str = '1024'):
        self._pou_filename = pou_filename
        self._json_len = json_len

    # ------------------------------------------------------------------ public

    def generate(self, model: TypeModel, json_values, command: str = '') -> str:
        """
        Generate jiecunit test file content.

        json_values: parsed JSON dict from the input (None for schema mode).
        """
        pfx = model.prefix + '_'
        all_names = [
            'test_' + pfx + 'jsonstr_to_data', 'test_' + pfx + 'data_to_jsonstr',
            'test_' + pfx + 'jsonbytes_to_data', 'test_' + pfx + 'data_to_jsonbytes',
            'test_json_char_from_asciicharcode', 'test_json_asciicharcode',
            'test_json_bytes_insert_str',
            'test_json_find_key', 'test_json_bytes_find_key',
            'test_json_escape', 'test_json_unescape',
        ]

        parts = [
            self._gen_header(command),
            self._gen_configuration(all_names),
            self._gen_test_jsonstr_to_data(model, json_values),
            self._gen_test_data_to_jsonstr(model, json_values),
            self._gen_test_jsonbytes_to_data(model, json_values),
            self._gen_test_data_to_jsonbytes(model, json_values),
        ]
        parts.append(_TEST_JSON_HELPERS)
        return '\n\n'.join(parts)

    # -------------------------------------------------------- header / config

    def _gen_header(self, command: str = '') -> str:
        lines = []
        if command:
            lines.append('(* ' + command + ' *)')
        lines += [
            '{#include <jiecunit.txt>}',
            '{#include <' + self._pou_filename + '>}',
        ]
        return '\n'.join(lines)

    def _gen_configuration(self, all_names: list) -> str:
        lines = ['{#ifdef _TEST_}', 'DEFINE_CONFIGURATION(', TAB + '_JIEC_TESTNAMES_LIST_(']
        for i, name in enumerate(all_names):
            suffix = ',' if i < len(all_names) - 1 else ''
            lines.append(TAB + TAB + "'" + name + "'" + suffix)
        lines += [TAB + ')', ')', '{#undef _TEST_}', '{#endif}']
        return '\n'.join(lines)

    # -------------------------------------------------------- base TEST_S blocks

    def _gen_test_jsonstr_to_data(self, model: TypeModel, json_values) -> str:
        jlen = self._json_len
        root_name = model.root.name
        values = json_values if json_values is not None else _default_value_for_type(model.root)
        json_str = self._build_json_string(model, json_values)

        var_decls = [
            'json: string[' + jlen + '];',
            'data: ' + root_name + ';',
        ]
        pfx = model.prefix + '_'
        body = [
            'json := ' + self._iec_str_literal(json_str) + ';',
            pfx + 'jsonstr_to_data(json, data);',
        ]
        body.extend(self._assertions_for_struct(model.root, 'data', values))

        for i, (jstr, assert_tmpls) in enumerate(self._jtd_extra_cases(model), 1):
            n = str(i)
            jn, dn = 'json' + n, 'data' + n
            var_decls.append(jn + ': string[' + jlen + '];')
            var_decls.append(dn + ': ' + root_name + ';')
            body.append(jn + ' := ' + self._iec_str_literal(jstr) + ';')
            body.append(pfx + 'jsonstr_to_data(' + jn + ', ' + dn + ');')
            body.extend(a.format(d=dn) for a in assert_tmpls)

        return self._make_test_s('test_' + pfx + 'jsonstr_to_data', var_decls, body)

    def _gen_test_data_to_jsonstr(self, model: TypeModel, json_values) -> str:
        jlen = self._json_len
        root_name = model.root.name
        values = json_values if json_values is not None else _default_value_for_type(model.root)

        var_decls = [
            'data: ' + root_name + ';',
            'data_rt: ' + root_name + ';',
            'json: string[' + jlen + '];',
        ]
        pfx = model.prefix + '_'
        body = self._assignments_for_struct(model.root, 'data', values)
        body += [pfx + 'data_to_jsonstr(data, json);', pfx + 'jsonstr_to_data(json, data_rt);']
        body.extend(self._assertions_for_struct(model.root, 'data_rt', values))

        for i, (assign_tmpl, assert_tmpl) in enumerate(self._dtj_extra_cases(model), 1):
            n = str(i)
            dn, jn, rn = 'data' + n, 'json' + n, 'data' + n + '_rt'
            var_decls.append(dn + ': ' + root_name + ';')
            var_decls.append(jn + ': string[' + jlen + '];')
            var_decls.append(rn + ': ' + root_name + ';')
            body.append(assign_tmpl.format(d=dn))
            body.append(pfx + 'data_to_jsonstr(' + dn + ', ' + jn + ');')
            body.append(pfx + 'jsonstr_to_data(' + jn + ', ' + rn + ');')
            body.append(assert_tmpl.format(r=rn))

        return self._make_test_s('test_' + pfx + 'data_to_jsonstr', var_decls, body)

    def _gen_test_jsonbytes_to_data(self, model: TypeModel, json_values) -> str:
        jlen = self._json_len
        root_name = model.root.name
        values = json_values if json_values is not None else _default_value_for_type(model.root)

        var_decls = [
            'data: ' + root_name + ';',
            'jsonbytes: array[0..' + jlen + '] of byte;',
            'data_rt: ' + root_name + ';',
        ]
        pfx = model.prefix + '_'
        body = self._assignments_for_struct(model.root, 'data', values)
        body += [pfx + 'data_to_jsonbytes(data, jsonbytes);', pfx + 'jsonbytes_to_data(jsonbytes, data_rt);']
        body.extend(self._assertions_for_struct(model.root, 'data_rt', values))

        return self._make_test_s('test_' + pfx + 'jsonbytes_to_data', var_decls, body)

    def _gen_test_data_to_jsonbytes(self, model: TypeModel, json_values) -> str:
        jlen = self._json_len
        root_name = model.root.name
        values = json_values if json_values is not None else _default_value_for_type(model.root)

        var_decls = [
            'data: ' + root_name + ';',
            'jsonbytes: array[0..' + jlen + '] of byte;',
            'data_rt: ' + root_name + ';',
        ]
        pfx = model.prefix + '_'
        body = self._assignments_for_struct(model.root, 'data', values)
        body += [pfx + 'data_to_jsonbytes(data, jsonbytes);', pfx + 'jsonbytes_to_data(jsonbytes, data_rt);']
        body.extend(self._assertions_for_struct(model.root, 'data_rt', values))

        return self._make_test_s('test_' + pfx + 'data_to_jsonbytes', var_decls, body)

    def _jtd_extra_cases(self, model: TypeModel) -> list:
        """Returns list of (json_str, [assertion_template with {d} placeholder]) for extra cases."""
        cases = []
        str_f = _first_string_field(model.root)
        flt_f = _first_scalar_field(model.root, _FLOAT_TYPES)
        int_f = _first_scalar_field(model.root, _INT_TYPES)

        if str_f:
            fn, _ = str_f
            cases.append((
                self._focused_json(model, fn, 'hello"world'),
                ["EXPECT_EQ_STRING('hello\"world', {d}." + fn + ");"],
            ))
            cases.append((
                self._focused_json(model, fn, ''),
                ["EXPECT_EQ_STRING('', {d}." + fn + ");"],
            ))

        if flt_f:
            fn, _ = flt_f
            cases.append((self._focused_json(model, fn, 42),
                           ['EXPECT_NEAR(42.0, {d}.' + fn + ', 0.001);']))
            cases.append((self._focused_json_raw(model, fn, '1e3'),
                           ['EXPECT_NEAR(1000.0, {d}.' + fn + ', 0.001);']))
            cases.append((self._focused_json(model, fn, -1.5),
                           ['EXPECT_NEAR(-1.5, {d}.' + fn + ', 0.001);']))

        if int_f:
            fn, ft = int_f
            suffix = _ASSERT_SUFFIX.get(ft.iec_type, 'DINT')
            cases.append((self._focused_json(model, fn, -42),
                           ['EXPECT_EQ_' + suffix + '(-42, {d}.' + fn + ');']))

        return cases

    def _dtj_extra_cases(self, model: TypeModel) -> list:
        """Returns list of (assign_template with {d}, assertion_template with {r}) for extra cases."""
        cases = []
        str_f = _first_string_field(model.root)
        flt_f = _first_scalar_field(model.root, _FLOAT_TYPES)
        int_f = _first_scalar_field(model.root, _INT_TYPES)

        if str_f:
            fn, _ = str_f
            cases.append(("{d}." + fn + " := 'hello\"world';",
                           "EXPECT_EQ_STRING('hello\"world', {r}." + fn + ");"))
            cases.append(("{d}." + fn + " := '';",
                           "EXPECT_EQ_STRING('', {r}." + fn + ");"))

        if flt_f:
            fn, _ = flt_f
            cases.append(("{d}." + fn + ' := 42.0;',   'EXPECT_NEAR(42.0, {r}.'   + fn + ', 0.001);'))
            cases.append(("{d}." + fn + ' := 1000.0;', 'EXPECT_NEAR(1000.0, {r}.' + fn + ', 0.001);'))
            cases.append(("{d}." + fn + ' := -1.5;',   'EXPECT_NEAR(-1.5, {r}.'   + fn + ', 0.001);'))

        if int_f:
            fn, ft = int_f
            suffix = _ASSERT_SUFFIX.get(ft.iec_type, 'DINT')
            cases.append(("{d}." + fn + ' := -42;',
                           'EXPECT_EQ_' + suffix + '(-42, {r}.' + fn + ');'))

        return cases

    # -------------------------------------------------------- TEST_S builder

    def _make_test_s(self, name: str, var_decls: list, body: list) -> str:
        lines = ['TEST_S(' + name + ')', TAB + 'var']
        lines.extend(TAB + TAB + v for v in var_decls)
        lines += [TAB + 'end', TAB + '{st}']
        lines.extend(TAB + line for line in body)
        lines += [TAB + '{end}', 'END_TEST_S']
        return '\n'.join(lines)

    # -------------------------------------------------------- focused JSON builders

    def _focused_json(self, model: TypeModel, field_name: str, value) -> str:
        """Build compact JSON with one root field set to value, others default."""
        defaults = _default_value_for_type(model.root)
        defaults[field_name] = value
        return _json.dumps(defaults, separators=(',', ':'), ensure_ascii=False)

    def _focused_json_raw(self, model: TypeModel, field_name: str, raw: str) -> str:
        """Build compact JSON with one root field replaced by a raw JSON value string."""
        defaults = _default_value_for_type(model.root)
        base = _json.dumps(defaults, separators=(',', ':'), ensure_ascii=False)
        key = '"' + field_name + '":'
        idx = base.find(key)
        if idx < 0:
            return base
        val_start = idx + len(key)
        for i, ch in enumerate(base[val_start:]):
            if ch in ',}]':
                return base[:val_start] + raw + base[val_start + i:]
        return base[:val_start] + raw

    # -------------------------------------------------------- assertions

    def _assertions_for_struct(self, st: StructType, data_path: str, values) -> list:
        lines = []
        for f in st.fields:
            v = values.get(f.name) if isinstance(values, dict) else None
            lines.extend(self._assertion_for_field(f.type, data_path + '.' + f.name, v))
        return lines

    def _assertion_for_field(self, t: AnyType, path: str, value, idx_parts: list = None) -> list:
        if isinstance(t, ScalarType):
            return self._assertion_scalar(t, path, value)
        if isinstance(t, StructType):
            return self._assertions_for_struct(t, path, value)
        if isinstance(t, ArrayType):
            if idx_parts is None:
                idx_parts = []
            lines = []
            for i in range(t.size):
                v = value[i] if isinstance(value, list) and i < len(value) else None
                new_parts = idx_parts + [str(i)]
                if isinstance(t.element_type, ArrayType):
                    lines.extend(self._assertion_for_field(t.element_type, path, v, new_parts))
                else:
                    full_path = path + '[' + ', '.join(new_parts) + ']'
                    lines.extend(self._assertion_for_field(t.element_type, full_path, v))
            return lines
        return []

    def _assertion_scalar(self, t: ScalarType, path: str, value) -> list:
        if value is None:
            value = _default_value_for_type(t)
        if t.json_type == 'boolean':
            if value:
                return ['EXPECT_TRUE(' + path + ');']
            return ['EXPECT_FALSE(' + path + ');']
        if t.json_type == 'number':
            return ['EXPECT_NEAR(' + repr(float(value)) + ', ' + path + ', 0.001);']
        if t.json_type == 'string':
            return ['EXPECT_EQ_STRING(' + self._iec_str_literal(str(value)) + ', ' + path + ');']
        suffix = _ASSERT_SUFFIX.get(t.iec_type, 'DINT')
        return ['EXPECT_EQ_' + suffix + '(' + str(int(value)) + ', ' + path + ');']

    # -------------------------------------------------------- assignments

    def _assignments_for_struct(self, st: StructType, data_path: str, values) -> list:
        lines = []
        for f in st.fields:
            v = values.get(f.name) if isinstance(values, dict) else None
            lines.extend(self._assignment_for_field(f.type, data_path + '.' + f.name, v))
        return lines

    def _assignment_for_field(self, t: AnyType, path: str, value, idx_parts: list = None) -> list:
        if isinstance(t, ScalarType):
            return self._assignment_scalar(t, path, value)
        if isinstance(t, StructType):
            return self._assignments_for_struct(t, path, value)
        if isinstance(t, ArrayType):
            if idx_parts is None:
                idx_parts = []
            lines = []
            for i in range(t.size):
                v = value[i] if isinstance(value, list) and i < len(value) else None
                new_parts = idx_parts + [str(i)]
                if isinstance(t.element_type, ArrayType):
                    lines.extend(self._assignment_for_field(t.element_type, path, v, new_parts))
                else:
                    full_path = path + '[' + ', '.join(new_parts) + ']'
                    lines.extend(self._assignment_for_field(t.element_type, full_path, v))
            return lines
        return []

    def _assignment_scalar(self, t: ScalarType, path: str, value) -> list:
        if value is None:
            value = _default_value_for_type(t)
        if t.json_type == 'boolean':
            return [path + ' := ' + ('true' if value else 'false') + ';']
        if t.json_type == 'string':
            return [path + ' := ' + self._iec_str_literal(str(value)) + ';']
        if t.json_type == 'number':
            return [path + ' := ' + repr(float(value)) + ';']
        return [path + ' := ' + str(int(value)) + ';']

    # -------------------------------------------------------- JSON string builder

    def _build_json_string(self, model: TypeModel, json_values) -> str:
        if json_values is not None:
            return _json.dumps(json_values, separators=(',', ':'), ensure_ascii=False)
        default = _default_value_for_type(model.root)
        return _json.dumps(default, separators=(',', ':'), ensure_ascii=False)

    # -------------------------------------------------------- IEC literal helper

    @staticmethod
    def _iec_str_literal(s: str) -> str:
        """Wrap a Python string in an IEC single-quoted string literal.
        Escapes $ as $$ and ' as $'.
        """
        escaped = s.replace('$', '$$').replace("'", "$'")
        return "'" + escaped + "'"
