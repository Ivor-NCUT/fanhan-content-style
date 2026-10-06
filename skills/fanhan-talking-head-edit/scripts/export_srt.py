#!/usr/bin/env python3
"""Export final bilingual frame-based cues; reject unsafe text/timing, never rewrite."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import unicodedata


def render(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    try:
        fps = Fraction(str(data['fps']))
    except (KeyError, ValueError, ZeroDivisionError) as exc:
        raise ValueError('fps must be a positive rational number') from exc
    total = data.get('total_frames')
    if fps <= 0 or type(total) is not int or total <= 0:
        raise ValueError('fps and integer total_frames must be positive')
    cues = data.get('cues')
    if not isinstance(cues, list) or not cues:
        raise ValueError('cues must be a nonempty list')

    def milliseconds(frame):
        value = Fraction(frame * 1000, 1) / fps
        return (2 * value.numerator + value.denominator) // (2 * value.denominator)

    def stamp(ms):
        seconds, ms = divmod(ms, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'

    result, previous_end = [], 0
    for i, cue in enumerate(cues, 1):
        if not isinstance(cue, dict):
            raise ValueError(f'cue {i}: expected object')
        start, end = cue.get('start_frame'), cue.get('end_frame')
        if type(start) is not int or type(end) is not int:
            raise ValueError(f'cue {i}: frame bounds must be integers')
        if not 0 <= previous_end <= start < end <= total:
            raise ValueError(f'cue {i}: overlapping, unordered or out-of-range timing')
        texts = []
        for lang in ('zh', 'en'):
            text = cue.get(lang)
            if not isinstance(text, str) or not text.strip() or text != text.strip():
                raise ValueError(f'cue {i}: {lang} missing or has edge whitespace')
            if any(unicodedata.category(c).startswith(('P', 'C', 'Zl', 'Zp')) for c in text):
                raise ValueError(f'cue {i}: {lang} has punctuation, control or line break')
            texts.append(text)
        a, b = milliseconds(start), milliseconds(end)
        if a >= b:
            raise ValueError(f'cue {i}: timing collapses at millisecond precision')
        result.append(f'{i}\n{stamp(a)} --> {stamp(b)}\n' + '\n'.join(texts))
        previous_end = end
    return '\n\n'.join(result) + '\n'


def self_test():
    data = {'fps': '30000/1001', 'total_frames': 60, 'cues': [
        {'start_frame': 0, 'end_frame': 30, 'zh': '先介绍我自己', 'en': 'Let me introduce myself'},
        {'start_frame': 30, 'end_frame': 60, 'zh': '再说具体服务', 'en': 'Then explain our services'}]}
    output = render(data)
    assert '00:00:00,000 --> 00:00:01,001' in output
    assert '00:00:01,001 --> 00:00:02,002' in output
    assert all(len(block.splitlines()) == 4 for block in output.strip().split('\n\n'))
    for key, value in [('start_frame', 29), ('end_frame', 61), ('end_frame', True),
                       ('zh', '一点一倍。'), ('zh', '分成\n两行'), ('en', ''),
                       ('en', "I'm here"), ('zh', '包含\u2028换行')]:
        changed = json.loads(json.dumps(data))
        changed['cues'][1][key] = value
        try:
            render(changed)
        except ValueError:
            continue
        raise AssertionError(f'Failed to reject {key}={value!r}')
    print('Self-test passed: fractional fps, bilingual rows and invalid timing/text')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('output', nargs='?', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.input is None or args.output is None:
        parser.error('input and output are required')
    try:
        output = render(json.loads(args.input.read_text(encoding='utf-8-sig')))
        with args.output.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Cannot export: {exc}\n')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
