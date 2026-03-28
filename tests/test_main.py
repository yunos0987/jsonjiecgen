# coding: utf-8
import subprocess
import sys
from pathlib import Path

import pytest

INPUTS_DIR  = Path(__file__).parent / 'inputs'
OUTPUTS_DIR = Path(__file__).parent / 'outputs'
MAIN        = Path(__file__).parent.parent / 'src' / 'main.py'

# Each entry: (stem, extra_args)
# extra_args is passed directly to main.py before the input file path.
_CASES = [
    ('simple',          ['--root-name', 'Simple']),
    ('various',         ['--root-name', 'Various']),
    ('simple_schema',   ['--schema', '--root-name', 'SimpleSchema']),
    ('various_schema',  ['--schema', '--root-name', 'VariousSchema']),
    ('simple_schema',   ['--root-name', 'SimpleSchema']),   # auto-detect via filename
    ('various_schema',  ['--root-name', 'VariousSchema']),  # auto-detect via filename
    ('nested_obj_3',    ['--root-name', 'NestedObj3']),
    ('multiple_ary_3',  ['--root-name', 'MultipleAry3']),
    ('simple_ary',      ['--root-name', 'SimpleAry']),
    ('structure_ary',   ['--root-name', 'StructureAry']),
    ('struct_ary_3',    ['--root-name', 'StructAry3']),
    ('multi_ary_struct', ['--root-name', 'MultiAryStruct']),
]


def _strip_cmd_comment(text: str) -> str:
    """Remove the leading (* command *) comment line if present."""
    if text.startswith('(*'):
        return text.split('\n', 1)[1] if '\n' in text else ''
    return text


# ---------------------------------------------------------------------------
# Parametrized: inputs/<stem>.json -> inputs/<stem>.txt, inputs/test_<stem>.txt
#               compared against outputs/<stem>.txt, outputs/test_<stem>.txt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('stem,extra_args', _CASES, ids=[c[0] for c in _CASES])
def test_output_matches(stem, extra_args):
    input_file    = INPUTS_DIR / (stem + '.json')
    pou_expected  = OUTPUTS_DIR / (stem + '.txt')
    test_expected = OUTPUTS_DIR / ('test_' + stem + '.txt')
    pou_out       = INPUTS_DIR / (stem + '.txt')
    test_out      = INPUTS_DIR / ('test_' + stem + '.txt')
    assert input_file.exists(),    f'Missing: {input_file}'
    assert pou_expected.exists(),  f'Missing: {pou_expected}'
    assert test_expected.exists(), f'Missing: {test_expected}'

    result = subprocess.run(
        [sys.executable, str(MAIN)] + extra_args + [
            str(input_file),
            '-o', str(pou_out),
            '--test', str(test_out),
        ],
        capture_output=True, text=True, encoding='utf-8',
    )
    assert result.returncode == 0, result.stderr
    assert _strip_cmd_comment(pou_out.read_text(encoding='utf-8'))  == _strip_cmd_comment(pou_expected.read_text(encoding='utf-8'))
    assert _strip_cmd_comment(test_out.read_text(encoding='utf-8')) == _strip_cmd_comment(test_expected.read_text(encoding='utf-8'))


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_error_on_null_field(tmp_path):
    f = tmp_path / 'x.json'
    f.write_text('{"x": null}', encoding='utf-8')
    r = subprocess.run(
        [sys.executable, str(MAIN), str(f)],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert 'null' in r.stderr.lower()


def test_error_on_invalid_json(tmp_path):
    f = tmp_path / 'x.json'
    f.write_text('{bad json', encoding='utf-8')
    r = subprocess.run(
        [sys.executable, str(MAIN), str(f)],
        capture_output=True, text=True,
    )
    assert r.returncode != 0


def test_error_on_missing_file():
    r = subprocess.run(
        [sys.executable, str(MAIN), 'nonexistent.json'],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
