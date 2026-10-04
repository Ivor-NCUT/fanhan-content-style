"""Audit complete ChatCut snapshots for one continuous, normal-speed source track.

No editor mutations or uploads. sourceRange is in microseconds; timelineRange in
frames. The report supplies factual ranges, not semantic editing decisions.
"""
import argparse
import json
import math
from pathlib import Path


def read_track(snapshot, track, ranges_only=False):
    state = snapshot['state']
    fps = float(state['fps'])
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('Invalid fps')
    entries = snapshot.get('entries', snapshot.get('timeline', {}).get('entries'))
    if entries is None:
        raise ValueError('Missing complete entries array')
    if snapshot.get('nextOffset') is not None:
        raise ValueError('Snapshot is paginated; collect all pages first')
    selected = [x for x in entries if x.get('trackAlias') == track]
    decorations = [x for x in selected if x.get('kind') in ('effect', 'transition')]
    if any(x.get('kind') not in ('item', 'marker') and
           not (ranges_only and x.get('kind') in ('effect', 'transition')) for x in selected):
        raise ValueError('Gaps, effects or transitions need separate verification')
    items = sorted((x for x in selected if x.get('kind') == 'item'),
                   key=lambda x: x['timelineRange']['fromFrame'])
    if not items:
        raise ValueError('No items on requested track')
    cursor = 0
    previous_source_end = 0
    assets = set()
    for item in items:
        a, b = (item['timelineRange'][k] for k in ('fromFrame', 'toFrame'))
        s, e = (item['sourceRange'][k] for k in ('start', 'end'))
        if not all(isinstance(x, int) for x in (a, b, s, e)):
            raise ValueError('Frame and microsecond coordinates must be integers')
        if a != cursor or b <= a:
            raise ValueError('Track has an unintended gap, overlap or empty clip')
        if s < previous_source_end or s < 0 or e <= s:
            raise ValueError('Source is reordered, overlapping or invalid')
        if abs((e - s) / 1e6 - (b - a) / fps) > 1 / fps + 1e-6:
            raise ValueError('Source and timeline durations imply non-unit rate')
        if item.get('playbackRate', 1) != 1:
            raise ValueError('Non-unit playback rate is unsupported')
        assets.add(item['asset']['id'])
        cursor, previous_source_end = b, e
    if len(assets) != 1:
        raise ValueError('Multi-source tracks need per-asset/instance auditing')
    if cursor != state['durationFrames']:
        raise ValueError('Requested track does not cover complete timeline')
    return items, fps, next(iter(assets)), decorations


def difference(a, b):
    """Half-open integer interval subtraction, returning maximal intervals."""
    out = []
    for start, end in a:
        cursor = start
        for left, right in b:
            if right <= cursor:
                continue
            if left >= end:
                break
            if left > cursor:
                out.append((cursor, min(left, end)))
            cursor = max(cursor, right)
            if cursor >= end:
                break
        if cursor < end:
            out.append((cursor, end))
    merged = []
    for start, end in out:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def at(source_us, items, fps):
    for item in items:
        start = item['sourceRange']['start']
        end = item['sourceRange']['end']
        output = item['timelineRange']['fromFrame'] / fps
        if source_us <= start:
            return output
        if source_us < end:
            return output + (source_us - start) / 1e6
    return items[-1]['timelineRange']['toFrame'] / fps


def audit(baseline, edited, track='A1', ranges_only=False):
    before, old_fps, old_asset, old_decorations = read_track(baseline, track, ranges_only)
    after, fps, asset, decorations = read_track(edited, track, ranges_only)
    if old_asset != asset:
        raise ValueError('Snapshots refer to different source assets')
    old_ranges = [(x['sourceRange']['start'], x['sourceRange']['end']) for x in before]
    new_ranges = [(x['sourceRange']['start'], x['sourceRange']['end']) for x in after]
    removed = difference(old_ranges, new_ranges)
    restored = difference(new_ranges, old_ranges)
    def rows(intervals, prefix):
        return [{
            'id': f'{prefix}{i + 1:03d}', 'assetId': asset,
            'sourceStartMicroseconds': start, 'sourceEndMicroseconds': end,
            'sourceStartSeconds': start / 1e6, 'sourceEndSeconds': end / 1e6,
            'durationSeconds': (end - start) / 1e6,
            'baselineAtSeconds': at(start, before, old_fps),
            'editedAtSeconds': at(end, after, fps),
        } for i, (start, end) in enumerate(intervals)]
    old_duration = baseline['state']['durationFrames'] / old_fps
    duration = edited['state']['durationFrames'] / fps
    return {
        'baselineTimelineId': baseline['state'].get('id'),
        'timelineId': edited['state'].get('id'), 'track': track, 'fps': fps,
        'baselineDurationSeconds': old_duration, 'editedDurationSeconds': duration,
        'netShorterSeconds': old_duration - duration,
        'removedSourceSeconds': sum(e - s for s, e in removed) / 1e6,
        'additionalRetainedSourceSeconds': sum(e - s for s, e in restored) / 1e6,
        'cuts': rows(removed, 'R'), 'additionalRetained': rows(restored, 'B'),
        'checks': {'completeContinuousTrack': True, 'sourceOrderPreserved': True,
                   'singleSource': True, 'normalRateWithinFrameTolerance': True},
        'ignoredDecorations': {'baseline': len(old_decorations), 'edited': len(decorations)},
        'limitations': 'No semantic, fade, mix or listening quality verification. '
                       'IDs describe this comparison only; preserve mappings across revisions.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--edited', type=Path, required=True)
    parser.add_argument('--track', default='A1')
    parser.add_argument('--ranges-only', action='store_true',
                        help='Explicitly ignore effects/transitions for source-range comparison only')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(json.loads(args.baseline.read_text()),
                       json.loads(args.edited.read_text()), args.track, args.ranges_only)
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(result["cuts"])} new deletion ranges; '
          f'{result["netShorterSeconds"]:.3f}s shorter. See {args.out}')


if __name__ == '__main__':
    main()
