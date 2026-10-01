"""Isolated checks: no live plugin edits, account access, or GitHub writes."""
import json
from pathlib import Path
import tempfile
import writing_style_sync as s


def check():
    with tempfile.TemporaryDirectory() as d:
        root, plugins, state = [Path(d) / n for n in ('skill', 'plugins', 'state')]
        root.mkdir()
        content = b'---\nname: fanhan-content-style\ndescription: personal\n---\n# Personal\n\nRule A\n'
        (root / 'SKILL.md').write_bytes(content)
        for name in ('references', 'raw', 'materials', 'examples', '_meta', 'skills', 'scripts'):
            (root / name).mkdir()
        sample = root / 'raw/sample.md'
        sample.write_text('approved prose')
        plugin = plugins / '0.1/skills/write-like-me/SKILL.md'
        plugin.parent.mkdir(parents=True)
        original = '---\nname: write-like-me\ndescription: platform\n---\n# Official\nOriginal platform rules\n'
        plugin.write_text(original)
        sync = s.Sync(root, plugins, state)
        assert sync.local() == 1
        assert s.block(plugin.read_text()) == s.body(content)[1]
        assert 'Original platform rules' in plugin.read_text()
        linked = plugin.parent / 'fanhan-content-style/raw/sample.md'
        linked.write_text('edited through plugin')
        assert sample.read_text() == 'edited through plugin'
        # Plugin -> canonical and canonical -> plugin.
        plugin.write_text(plugin.read_text().replace('Rule A', 'Rule B'))
        sync.local()
        assert 'Rule B' in (root / 'SKILL.md').read_text()
        (root / 'SKILL.md').write_text((root / 'SKILL.md').read_text().replace('Rule B', 'Rule C'))
        sync.local()
        assert 'Rule C' in s.block(plugin.read_text())
        # Conflicting concurrent changes must leave both originals intact.
        plugin.write_text(plugin.read_text().replace('Rule C', 'Rule D'))
        (root / 'SKILL.md').write_text((root / 'SKILL.md').read_text().replace('Rule C', 'Rule E'))
        before = plugin.read_bytes(), (root / 'SKILL.md').read_bytes()
        try:
            sync.local()
        except ValueError:
            pass
        else:
            raise AssertionError('Conflict was overwritten')
        assert before == (plugin.read_bytes(), (root / 'SKILL.md').read_bytes())
        (root / 'SKILL.md').write_text((root / 'SKILL.md').read_text().replace('Rule E', 'Rule D'))
        sync.local()
        # Plugin upgrade retains new upstream rules and restores the adapter.
        new = plugins / '0.2/skills/write-like-me/SKILL.md'
        new.parent.mkdir(parents=True)
        new.write_text(original.replace('Original platform rules', 'New platform rules'))
        assert sync.local() == 2
        assert 'Rule D' in s.block(new.read_text()) and 'New platform rules' in new.read_text()
        # Exercise remote inbound/outbound and the corpus publication gate with a fake API.
        live = {'SKILL.md': (root / 'SKILL.md').read_bytes(), 'raw/sample.md': sample.read_bytes()}
        sha, calls = ['head1'], []
        def fake(endpoint, payload=None, method=None, binary=False):
            calls.append((endpoint, payload))
            if endpoint.endswith('/commits/main'):
                return {'sha': sha[0], 'commit': {'tree': {'sha': 'tree1'}}}
            if endpoint.endswith('/git/trees'):
                for item in payload['tree']:
                    assert not item['path'].startswith('raw/')
                    live[item['path']] = item['content'].encode()
                return {'sha': 'tree2'}
            if endpoint.endswith('/git/commits'):
                return {'sha': 'head3'}
            if endpoint.endswith('/git/refs/heads/main'):
                assert payload['force'] is False
                sha[0] = payload['sha']
                return {}
            if endpoint.endswith('/git/commits/head3'):
                return {'tree': {'sha': 'tree2'}}
            raise AssertionError(endpoint)
        old_gh, old_snapshot = s.gh, s.snapshot
        s.gh, s.snapshot = fake, lambda _: dict(live)
        try:
            sync.remote()
            live['SKILL.md'] = live['SKILL.md'].replace(b'Rule D', b'Rule F')
            sha[0] = 'head2'
            sync.remote()
            sync.local()
            assert 'Rule F' in s.block(new.read_text())
            (root / 'SKILL.md').write_bytes(live['SKILL.md'].replace(b'Rule F', b'Rule G'))
            sample.write_text('private added prose')
            (root / 'raw/new-private.md').write_text('private')
            assert sync.remote() == 'head3'
            assert b'Rule G' in live['SKILL.md']
            assert live['raw/sample.md'] == b'edited through plugin'
            status = json.loads((state / 'status.json').read_text())
            assert 'raw/sample.md' in status['pending_publication']
            assert 'raw/new-private.md' in status['pending_publication']
            assert not any('Original platform rules' in str(payload) for _, payload in calls)
        finally:
            s.gh, s.snapshot = old_gh, old_snapshot
    print('PASS: two-way rules, shared corpus, conflicts, upgrade, remote directions, privacy gate')


if __name__ == '__main__':
    check()
