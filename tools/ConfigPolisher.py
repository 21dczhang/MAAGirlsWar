#!/usr/bin/env python3
"""
JSONC 格式化工具
- 保留注释（包括数组内的行注释）
- 维护字段顺序（可自定义 FIELD_ORDER）
- 只自动补全缺失的 focus 字段（值为 null），其他字段不补
- 自动扫描 SCAN_DIR 目录下所有 .json / .jsonc 文件并原地修改
"""

import re
import sys
import json
import os
from pathlib import Path
from collections import OrderedDict

# ============================================================
# 🔧 自动扫描目录（相对于脚本所在目录）
# ============================================================
SCAN_DIR = r"assets\resource\pipeline"

# ============================================================
# 🔧 自定义字段顺序
# 列表中未出现的字段将按原始顺序追加到末尾
# ============================================================
FIELD_ORDER = [
    "recognition",
    "expected",
    "template",
    "roi",
    "threshold",
    "order_by",
    "action",
    "target",
    "target_offset",
    "max_hit",
    "post_delay",
    "timeout",
    "next",
    "focus"
]

# ============================================================
# 扫描的文件后缀
# ============================================================
SCAN_EXTENSIONS = {".json", ".jsonc"}


class JSONCFormatter:
    def __init__(self, text, field_order=None, indent=4):
        self.original = text
        self.field_order = field_order or []
        self.indent = indent

    def _remove_line_comment(self, line):
        in_string = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == '\\' and in_string:
                i += 2
                continue
            if c == '"':
                in_string = not in_string
            if not in_string and i + 1 < len(line) and line[i:i+2] == '//':
                return line[:i]
            i += 1
        return line

    def _strip_to_plain_json(self, text):
        lines = [self._remove_line_comment(l) for l in text.split('\n')]
        plain = '\n'.join(lines)
        plain = re.sub(r',\s*([}\]])', r'\1', plain)
        return plain

    def parse(self):
        plain = self._strip_to_plain_json(self.original)
        try:
            return json.loads(plain, object_pairs_hook=OrderedDict)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析错误: {e}")

    def extract_comments_before_keys(self):
        comment_map = {}
        lines = self.original.split('\n')
        pending = []
        depth = 0
        current_top = None

        for line in lines:
            s = line.strip()

            if s.startswith('//'):
                pending.append(s)
                continue

            if not s:
                if pending:
                    pending.append('')
                continue

            for ch in s:
                if ch in '{[':
                    depth += 1
                elif ch in '}]':
                    depth -= 1

            if depth == 1:
                m = re.match(r'^\s*"([^"]+)"\s*:', line)
                if m:
                    current_top = m.group(1)
                    if pending:
                        comment_map[f'top.{current_top}'] = [c for c in pending if c != '']
                    pending = []
            elif depth == 2 and current_top:
                m = re.match(r'^\s*"([^"]+)"\s*:', line)
                if m:
                    subkey = m.group(1)
                    if pending:
                        comment_map[f'{current_top}.{subkey}'] = [c for c in pending if c != '']
                    pending = []
            else:
                pending = []

        return comment_map

    def extract_array_comments(self, top_key, field_key):
        lines = self.original.split('\n')
        result = {}
        top_found = field_found = False
        depth = array_depth = element_index = 0
        pending = []

        for line in lines:
            s = line.strip()

            if not top_found:
                if re.match(rf'^\s*"{re.escape(top_key)}"\s*:', line):
                    top_found = True
                    depth = 0
                continue

            if not field_found:
                if re.match(rf'^\s*"{re.escape(field_key)}"\s*:\s*\[', line):
                    field_found = True
                    array_depth = 1
                    continue
                for ch in s:
                    if ch == '{': depth += 1
                    elif ch == '}': depth -= 1
                if depth < 0:
                    break
                continue

            for ch in s:
                if ch == '[': array_depth += 1
                elif ch == ']': array_depth -= 1

            if array_depth <= 0:
                break

            if s.startswith('//'):
                pending.append(s)
            elif s and s not in ('[', ']'):
                if pending:
                    result[element_index] = pending[:]
                    pending = []
                element_index += 1

        return result

    def reorder_fields(self, obj):
        """按 FIELD_ORDER 重排；只补 focus（若缺失），其余字段不补"""
        if not isinstance(obj, dict):
            return obj

        ordered = OrderedDict()
        for key in self.field_order:
            if key in obj:
                ordered[key] = obj[key]
        for key in obj:
            if key not in ordered:
                ordered[key] = obj[key]
        # 只补 focus
        if 'focus' not in ordered:
            ordered['focus'] = None

        return ordered

    def format_value(self, value, depth, arr_comments=None):
        ind  = ' ' * self.indent * depth
        ind1 = ' ' * self.indent * (depth + 1)

        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (int, float)):
            return json.dumps(value)
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, list):
            if not value and not arr_comments:
                return '[]'
            parts = ['[']
            for idx, item in enumerate(value):
                if arr_comments and idx in arr_comments:
                    for c in arr_comments[idx]:
                        parts.append(f'{ind1}{c}')
                comma = ',' if idx < len(value) - 1 else ''
                parts.append(f'{ind1}{self.format_value(item, depth + 1)}{comma}')
            parts.append(f'{ind}]')
            return '\n'.join(parts)
        if isinstance(value, dict):
            if not value:
                return '{}'
            parts = ['{']
            items = list(value.items())
            for idx, (k, v) in enumerate(items):
                comma = ',' if idx < len(items) - 1 else ''
                parts.append(f'{ind1}{json.dumps(k, ensure_ascii=False)}: {self.format_value(v, depth + 1)}{comma}')
            parts.append(f'{ind}}}')
            return '\n'.join(parts)
        return json.dumps(value, ensure_ascii=False)

    def format(self):
        data = self.parse()
        comment_map = self.extract_comments_before_keys()

        out = ['{']
        top_items = list(data.items())

        for top_idx, (top_key, top_val) in enumerate(top_items):
            for c in comment_map.get(f'top.{top_key}', []):
                out.append(f'    {c}')

            comma = ',' if top_idx < len(top_items) - 1 else ''

            if isinstance(top_val, dict):
                reordered = self.reorder_fields(top_val)
                obj_lines = ['{']
                sub_items = list(reordered.items())
                for sub_idx, (sub_key, sub_val) in enumerate(sub_items):
                    for c in comment_map.get(f'{top_key}.{sub_key}', []):
                        obj_lines.append(f'        {c}')

                    sub_comma = ',' if sub_idx < len(sub_items) - 1 else ''
                    arr_comments = (
                        self.extract_array_comments(top_key, sub_key)
                        if isinstance(sub_val, list) else None
                    )
                    fv = self.format_value(sub_val, 2, arr_comments)
                    obj_lines.append(f'        {json.dumps(sub_key, ensure_ascii=False)}: {fv}{sub_comma}')

                obj_lines.append('    }')
                obj_str = '\n'.join(obj_lines)
            else:
                obj_str = self.format_value(top_val, 1)

            out.append(f'    {json.dumps(top_key, ensure_ascii=False)}: {obj_str}{comma}')

        out.append('}')
        return '\n'.join(out)


def process_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  ⚠️  读取失败: {e}")
        return False

    try:
        formatter = JSONCFormatter(text, field_order=FIELD_ORDER)
        result = formatter.format()
    except ValueError as e:
        print(f"  ❌ {e}")
        return False

    if result == text:
        return False

    path.write_text(result, encoding='utf-8')
    return True


def main():
    script_dir = Path(sys.argv[0]).resolve().parent
    scan_path = (script_dir / SCAN_DIR).resolve()

    if not scan_path.exists():
        print(f"❌ 目录不存在: {scan_path}")
        print(f"   请确认 SCAN_DIR = {SCAN_DIR!r} 配置是否正确")
        sys.exit(1)

    files = [
        p for p in scan_path.rglob('*')
        if p.is_file() and p.suffix.lower() in SCAN_EXTENSIONS
    ]

    if not files:
        print(f"⚠️  目录下未找到 JSON 文件: {scan_path}")
        sys.exit(0)

    print(f"📂 扫描目录: {scan_path}")
    print(f"   共找到 {len(files)} 个文件\n")

    changed = 0
    for f in sorted(files):
        rel = f.relative_to(scan_path)
        modified = process_file(f)
        if modified:
            print(f"  ✅ 已更新: {rel}")
            changed += 1
        else:
            print(f"  ─  无变化: {rel}")

    print(f"\n完成：{changed}/{len(files)} 个文件已更新")


if __name__ == '__main__':
    main()