from __future__ import annotations

import re
from typing import Dict, List, Optional


EDITABLE_START = '"""以下为可以编辑的部分"""'
EDITABLE_END = '"""以上为可以编辑的部分"""'


def _safe_count(value: object, default: int = 1) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, parsed)


def _safe_identifier(value: object, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        return fallback
    text = re.sub(r'[^0-9a-zA-Z_]', '_', text)
    if not text:
        return fallback
    if text[0].isdigit():
        text = f'_{text}'
    return text


def _normalize_names(raw: object, count: int, prefix: str) -> List[str]:
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(',') if part.strip()]
    elif isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
    else:
        items = []

    normalized = [_safe_identifier(name, f'{prefix}_{idx + 1}') for idx, name in enumerate(items)]
    while len(normalized) < count:
        normalized.append(f'{prefix}_{len(normalized) + 1}')
    return normalized[:count]


def extract_editable_code(code: str) -> str:
    if not isinstance(code, str) or not code.strip():
        return ''

    start_idx = code.find(EDITABLE_START)
    end_idx = code.find(EDITABLE_END)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return code.strip('\n')

    body = code[start_idx + len(EDITABLE_START):end_idx]
    lines = body.splitlines()
    if lines and lines[0].strip() == '':
        lines = lines[1:]
    if lines and lines[-1].strip() == '':
        lines = lines[:-1]
    return '\n'.join(lines)


def _indent_lines(content: str, indent: str = '    ') -> str:
    content = content.rstrip('\n')
    if not content:
        return f'{indent}pass'
    return '\n'.join(f'{indent}{line}' if line else '' for line in content.splitlines())


def generate_python_prototype_spec(
    input_count: int,
    output_count: int,
    function_name: Optional[str] = None,
    input_names: Optional[object] = None,
    output_names: Optional[object] = None,
    editable_code: Optional[str] = None,
) -> Dict[str, object]:
    inputs = _safe_count(input_count, 1)
    outputs = _safe_count(output_count, 1)
    fn_name = _safe_identifier(function_name, 'process_generated')
    in_names = _normalize_names(input_names, inputs, 'input')
    out_names = _normalize_names(output_names, outputs, 'output')

    editable = str(editable_code or '').strip('\n')
    if not editable:
        primary_in = in_names[0]
        primary_out = out_names[0]
        editable_lines = [
            f'{primary_out} = np.asarray({primary_in}, dtype=float).copy()',
            f"print('{primary_out} shape:', {primary_out}.shape)",
        ]
        for idx in range(1, len(out_names)):
            editable_lines.append(f'{out_names[idx]} = {primary_out}.copy()')
            editable_lines.append(f"print('{out_names[idx]} shape:', {out_names[idx]}.shape)")
        editable = '\n'.join(editable_lines)

    signature = f"def {fn_name}({', '.join(in_names + ['params'])}):"
    prelude_lines = [
        '# 自动读取窗口 numpy array',
    ]
    for name in in_names:
        prelude_lines.append(f'{name} = np.asarray({name}, dtype=float)')
        prelude_lines.append(f"print('{name} shape:', {name}.shape)")

    footer_lines = [
        '# 自动生成返回前检查（输出必须保持与输入采样频率一致，返回窗口时会取最后一帧）',
        f"_expected_channels = int({in_names[0]}.shape[1]) if {in_names[0]}.ndim == 2 and {in_names[0]}.shape[1] > 0 else 0",
    ]
    for name in out_names:
        footer_lines.extend(
            [
                f'{name} = np.asarray({name}, dtype=float)',
                f'if {name}.ndim == 0:',
                f'    {name} = {name}.reshape(1, 1)',
                f'elif {name}.ndim == 1:',
                f'    {name} = {name}.reshape(1, -1)',
                f'else:',
                f'    {name} = {name}.reshape({name}.shape[0], -1)',
                f"assert _expected_channels == 0 or {name}.shape[1] == _expected_channels, '输出通道数必须与输入一致'",
            ]
        )
    footer_lines.append(f"return {', '.join(out_names)}")

    header_code = '\n'.join([signature] + [f'    {line}' if line else '' for line in prelude_lines])
    footer_code = '\n'.join([f'    {line}' if line else '' for line in footer_lines])
    full_code = (
        'import numpy as np\n\n'
        f'{header_code}\n'
        f'    {EDITABLE_START}\n'
        f"{_indent_lines(editable, indent='    ')}\n"
        f'    {EDITABLE_END}\n'
        f'{footer_code}\n'
    )

    return {
        'functionName': fn_name,
        'inputNames': in_names,
        'outputNames': out_names,
        'signature': signature,
        'editableCode': editable,
        'headerCode': header_code,
        'footerCode': footer_code,
        'code': full_code,
    }


def generate_python_prototype(input_count: int, output_count: int) -> str:
    spec = generate_python_prototype_spec(input_count, output_count)
    return str(spec.get('code', ''))


DEFAULT_CODE_LIBRARY: Dict[str, str] = {
    'CUSTOM_PYFUNC': generate_python_prototype(2, 1),
    'CUSTOM_CONV': (
        "import numpy as np\n\n"
        "def process(inputs, params):\n"
        "    x = np.asarray(inputs.get('in-1', np.array([])), dtype=float)\n"
        "    if x.ndim == 0:\n"
        "        x = np.array([float(x)])\n"
        "    kernel = np.asarray(params.get('kernel', [0.25, 0.5, 0.25]), dtype=float)\n"
        "    if kernel.size == 0:\n"
        "        kernel = np.array([1.0], dtype=float)\n"
        "    kernel = kernel / np.sum(kernel)\n"
        "    y = np.convolve(x, kernel, mode='same') if x.size > 0 else x\n"
        "    print('conv in shape:', x.shape)\n"
        "    print('conv out shape:', y.shape)\n"
        "    return {'out-1': y}\n"
    ),
}


def get_default_code_library() -> Dict[str, str]:
    return dict(DEFAULT_CODE_LIBRARY)
