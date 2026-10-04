import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).parents[1] / 'scripts/audit_timeline.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def snapshot(spans, fps=25):
    entries = []
    cursor = 0
    for s, e in spans:
        length = round((e - s) * fps)
        entries.append({'kind': 'item', 'trackAlias': 'A1', 'asset': {'id': 'source'},
                        'timelineRange': {'fromFrame': cursor, 'toFrame': cursor + length},
                        'sourceRange': {'start': round(s * 1e6), 'end': round(e * 1e6)}})
        cursor += length
    return {'state': {'id': 'synthetic', 'fps': fps, 'durationFrames': cursor}, 'entries': entries}


class AuditTests(unittest.TestCase):
    def test_exact_difference_and_seek_at_non_30_fps(self):
        result = module.audit(snapshot([(0, 10)]), snapshot([(0, 2), (3, 5), (5.4, 10)]))
        self.assertEqual([(c['sourceStartSeconds'], c['sourceEndSeconds']) for c in result['cuts']], [(2, 3), (5, 5.4)])
        self.assertAlmostEqual(result['netShorterSeconds'], 1.4)
        self.assertEqual(result['cuts'][0]['editedAtSeconds'], 2)
        self.assertEqual(result['cuts'][1]['editedAtSeconds'], 4)

    def test_restored_pause_reduces_cut_and_moves_later_seeks(self):
        result = module.audit(snapshot([(0, 2), (3, 10)]), snapshot([(0, 2.32), (3, 10)]))
        self.assertEqual(result['cuts'], [])
        self.assertAlmostEqual(result['additionalRetainedSourceSeconds'], .32)
        self.assertAlmostEqual(result['netShorterSeconds'], -.32)

    def test_reject_incomplete_page(self):
        value = snapshot([(0, 10)]); value['nextOffset'] = 100
        with self.assertRaisesRegex(ValueError, 'paginated'):
            module.audit(value, snapshot([(0, 10)]))

    def test_reject_gap_overlap_reorder_and_rate(self):
        original = snapshot([(0, 10)])
        cases = []
        gap = snapshot([(0, 2), (3, 10)]); gap['entries'][1]['timelineRange']['fromFrame'] += 1; cases.append(gap)
        overlap = copy.deepcopy(gap); overlap['entries'][1]['timelineRange']['fromFrame'] -= 2; cases.append(overlap)
        cases.extend([snapshot([(3, 5), (0, 2)]), snapshot([(0, 5), (4, 10)])])
        rate = snapshot([(0, 10)]); rate['entries'][0]['sourceRange']['end'] = 20000000; cases.append(rate)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                module.audit(original, case)

    def test_reject_multi_source_and_effects(self):
        original = snapshot([(0, 10)])
        multiple = snapshot([(0, 5), (5, 10)]); multiple['entries'][1]['asset']['id'] = 'other'
        transition = snapshot([(0, 10)]); transition['entries'].append({'kind': 'transition', 'trackAlias': 'A1'})
        for case in (multiple, transition):
            with self.assertRaises(ValueError): module.audit(original, case)

    def test_explicit_range_only_mode_reports_ignored_transition(self):
        original = snapshot([(0, 10)])
        decorated = snapshot([(0, 2), (3, 10)])
        decorated['entries'].append({'kind': 'transition', 'trackAlias': 'A1'})
        result = module.audit(original, decorated, ranges_only=True)
        self.assertEqual(result['ignoredDecorations'], {'baseline': 0, 'edited': 1})
        self.assertEqual(len(result['cuts']), 1)


if __name__ == '__main__':
    unittest.main()
