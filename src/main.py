# coding: utf-8
import argparse
import json
import os
import sys
import re

from analyzer import analyze_json, analyze_schema, AnalyzeError
from generator import IecGenerator
from jiecunittest_generator import JiecUnitGenerator
from config import VERSION

_STRING_TYPE_RE = re.compile(r'^string(\[(.+)\])?$', re.IGNORECASE)


def _parse_string_type(value: str) -> str:
    """Validate and return the string IEC type ('string' or 'string[N]')."""
    m = _STRING_TYPE_RE.match(value.strip())
    if not m:
        print(f'error: --string-type must be "string" or "string[N]" (got: {value!r})', file=sys.stderr)
        sys.exit(1)
    return value.strip()


def _rel(path: str) -> str:
    """Return a forward-slash relative path with ./ prefix."""
    rel = os.path.relpath(path).replace(os.sep, '/')
    return rel if rel.startswith('.') else './' + rel


def main():
    parser = argparse.ArgumentParser(
        description='Generate jiecc-compatible IEC 61131-3 text from JSON data or JSON Schema'
    )
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('input', nargs='?', help='Input JSON file (default: stdin)')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('--schema', action='store_true',
                        help='Treat the input as JSON Schema')
    parser.add_argument('--root-name', default='JsonRoot',
                        help='Root name used for type and function names (default: JsonRoot)')
    parser.add_argument('--json-string-size', default='JSON_STRING_SIZE', metavar='N',
                        help='Maximum length for JSON string buffer, or a jiecc macro name (default: JSON_STRING_SIZE)')
    #
    parser.add_argument('--integer-type', default='dint', metavar='TYPE',
                        help='IEC integer type for JSON integer (default: dint)')
    parser.add_argument('--number-type', default='lreal', metavar='TYPE',
                        help='IEC numeric type for JSON number (default: lreal)')
    parser.add_argument('--string-type', default='string[256]', metavar='TYPE',
                        help='IEC string type for JSON string fields (default: string[256])')
    parser.add_argument('--boolean-type', default='bool', metavar='TYPE',
                        help='IEC type for JSON boolean (default: bool)')
    #
    parser.add_argument('--type-name-suffix', default='_t',
                        help='Type name suffix (default: _t)')
    parser.add_argument('--test', metavar='FILE',
                        help='Write jiecunit test file to FILE')
    args = parser.parse_args()

    # Load input (file or stdin)
    try:
        if args.input:
            with open(args.input, encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    except FileNotFoundError:
        print(f'error: file not found: {args.input}', file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'error: failed to parse JSON: {e}', file=sys.stderr)
        sys.exit(1)

    # Auto-detect schema mode if filename contains "schema"
    is_schema = args.schema or (
        args.input is not None and 'schema' in os.path.basename(args.input).lower()
    )

    string_type = _parse_string_type(args.string_type)

    # Build type model
    try:
        if is_schema:
            model = analyze_schema(
                data, args.root_name, args.type_name_suffix,
                string_type, args.integer_type, args.number_type, args.boolean_type
            )
        else:
            model = analyze_json(
                data, args.root_name, args.type_name_suffix,
                string_type, args.integer_type, args.number_type, args.boolean_type
            )
    except AnalyzeError as e:
        print(f'error: {e}', file=sys.stderr)
        sys.exit(1)

    # Generate IEC 61131-3 text
    gen = IecGenerator(json_len=args.json_string_size)
    output = gen.generate(model)

    # Write output (UTF-8 without BOM, LF line endings)
    if args.output:
        jiecc_path = _rel(args.output)
        xml_out = _rel(os.path.splitext(args.output)[0] + '.omron.xml')
        jiecc_cmd = '$ jiecc ' + jiecc_path + ' -o ' + xml_out + ' -t omron'
    else:
        jiecc_cmd = '$ jiecc <filepath> -t omron'
    output_lf = '(* ' + jiecc_cmd + ' *)\n' + output.replace('\r\n', '\n').replace('\r', '\n')
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8', newline='\n') as f:
                f.write(output_lf)
                f.write('\n')
        except OSError as e:
            print(f'error: failed to write output file: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(output_lf)
        sys.stdout.write('\n')

    # Generate jiecunit test file if requested
    if args.test:
        pou_basename = os.path.basename(args.output) if args.output else 'output.txt'
        test_gen = JiecUnitGenerator(pou_filename=pou_basename, json_len=args.json_string_size)
        json_values = None if is_schema else data
        test_path = _rel(args.test)
        pou_dir = os.path.dirname(args.output) if args.output else '.'
        pou_inc = _rel(pou_dir)
        xml_out = './' + os.path.splitext(os.path.basename(args.test))[0] + '.xml'
        jiecc_cmd = '$ jiecc ' + test_path + ' -D_TEST_ -I' + pou_inc + ' -I<jiecunit root> -I<jiecunit root>/sys -o ' + xml_out + ' -t omron'
        test_output = test_gen.generate(model, json_values, command=jiecc_cmd)
        test_lf = test_output.replace('\r\n', '\n').replace('\r', '\n')
        try:
            with open(args.test, 'w', encoding='utf-8', newline='\n') as f:
                f.write(test_lf)
                f.write('\n')
        except OSError as e:
            print(f'error: failed to write test file: {e}', file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
