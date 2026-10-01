#!/usr/bin/env python3
"""Local Writing Style adapter and GitHub sync. GitHub access exclusively via gh."""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import time

REPO = 'Ivor-NCUT/fanhan-content-style'
START = '<!-- fanhan-personal-style:begin -->\n'
END = '<!-- fanhan-personal-style:end -->'
NOTICE = '''## 泛函个人风格（本机同步）

本节及相邻的 `fanhan-content-style/` 是用户指定的风格来源，优先于下方通用检索流程。
写前完整读取 `fanhan-content-style/SKILL.md`，按其要求读取全部原文、参考与完整 Humanizer。
这些指定语料足够时直接使用；仅在当前任务需要额外样例时调用可用的检索工具。
规则修订写入本节或 `fanhan-content-style/SKILL.md`；语料与参考在共享目录原地编辑。
本机服务同步本节与 Skill 正文，并恢复插件升级后的接入；插件通用指令独立保留。
新增或修改语料只在本机同步，公开发布须另行核对授权。不要声称已经写入云端插件账户。

'''


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(data)
        tmp = f.name
    os.replace(tmp, path)


def body(data):
    text = data.decode()
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError('Skill front matter missing')
    header, text = text.split('\n---\n', 1)
    return header + '\n---\n', text


def block(text):
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError('Personal style block missing or duplicated')
    return text.split(START, 1)[1].split(END, 1)[0]


def merge(local, base, remote):
    if local == remote or remote == base:
        return local
    if local == base:
        return remote
    if None in (local, base, remote):
        raise ValueError('Concurrent creation/deletion conflict')
    with tempfile.TemporaryDirectory() as d:
        paths = [Path(d) / n for n in ('local', 'base', 'remote')]
        for p, data in zip(paths, (local, base, remote)):
            p.write_bytes(data)
        result = subprocess.run(['git', 'merge-file', '-p', *map(str, paths)], capture_output=True)
    if result.returncode:
        raise ValueError('Concurrent content conflict; originals preserved')
    return result.stdout


def gh(endpoint, payload=None, method=None, binary=False):
    args = [shutil.which('gh') or 'gh', 'api', endpoint]
    if method:
        args += ['--method', method]
    if payload is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(payload).encode() if payload is not None else None,
                            capture_output=True, timeout=45)
    if result.returncode:
        # Do not log response bodies, source text, or credentials.
        raise RuntimeError(f'gh failed ({result.returncode}) for {endpoint}')
    return result.stdout if binary else json.loads(result.stdout)


def snapshot(sha):
    archive = gh(f'repos/{REPO}/tarball/{sha}', binary=True)
    result = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        for item in tar.getmembers():
            parts = PurePosixPath(item.name).parts[1:]
            if not parts:
                continue
            if '..' in parts or item.issym() or item.islnk():
                raise ValueError('Unsafe archive member')
            if item.isfile():
                result['/'.join(parts)] = tar.extractfile(item).read()
    return result


class Sync:
    def __init__(self, root, plugins, state):
        self.root, self.plugins, self.state = root, plugins, state
        self.state.mkdir(parents=True, exist_ok=True)
        self.plugin_base = self.state / 'personal-body.txt'
        self.meta = self.state / 'remote.json'

    def write(self, path, data):
        old = path.read_bytes() if path.exists() else None
        if old == data:
            return
        if old is not None:
            digest = hashlib.sha256(old).hexdigest()
            atomic(self.state / 'backups' / digest, old)
        if data is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path, data)

    def local(self):
        entry = self.root / 'SKILL.md'
        original = entry.read_bytes()
        header, personal = body(original)
        baseline = self.plugin_base.read_bytes() if self.plugin_base.exists() else personal.encode()
        paths = sorted(self.plugins.glob('*/skills/write-like-me/SKILL.md'))
        candidates, originals = [], {}
        for path in paths:
            text = path.read_text()
            originals[path] = text
            if START in text:
                candidate = block(text).encode()
                if candidate != baseline:
                    candidates.append(candidate)
        changed = set(candidates)
        if len(changed) > 1:
            raise ValueError('Multiple plugin versions edited differently')
        merged = merge(personal.encode(), baseline, next(iter(changed), baseline))
        if entry.read_bytes() != original:
            raise ValueError('Skill changed during synchronization; retry')
        self.write(entry, header.encode() + merged)
        for path in paths:
            text = originals[path]
            if START in text:
                text = text.split(START, 1)[0] + START + merged.decode() + END + text.split(END, 1)[1]
            else:
                # Preserve proprietary upstream prose locally; never publish it to GitHub.
                _, upstream_body = body(text.encode())
                upstream_header, _ = body(text.encode())
                text = upstream_header + '\n' + NOTICE + START + merged.decode() + END + '\n\n' + upstream_body
            if path.read_text() != originals[path]:
                raise ValueError('Plugin changed during synchronization; retry')
            self.write(path, text.encode())
            link = path.parent / 'fanhan-content-style'
            if link.is_symlink():
                if link.resolve() != self.root.resolve():
                    raise ValueError('Unexpected shared-directory link')
            elif link.exists():
                raise ValueError('Shared-directory path already occupied')
            else:
                link.symlink_to(self.root, target_is_directory=True)
            # Embedded personal instructions retain the canonical relative links.
            for name in ('references', 'raw', 'materials', 'examples', '_meta', 'skills', 'scripts',
                         'AGENTS.md', 'context-os.json'):
                target = path.parent / name
                if target.is_symlink() and target.resolve() != (self.root / name).resolve():
                    raise ValueError('Unexpected resource link')
                if not target.exists() and not target.is_symlink():
                    target.symlink_to(self.root / name, target_is_directory=(self.root / name).is_dir())
        atomic(self.plugin_base, merged)
        return len(paths)

    def remote(self):
        commit = gh(f'repos/{REPO}/commits/main')
        sha = commit['sha']
        meta = json.loads(self.meta.read_text()) if self.meta.exists() else None
        if meta is None or meta['sha'] != sha:
            remote = snapshot(sha)
        else:
            remote = {name: (self.state / 'base' / meta['sha'] / name).read_bytes() for name in meta['paths']}
        base = {name: (self.state / 'base' / meta['sha'] / name).read_bytes() for name in meta['paths']} if meta else remote
        before, merged = {}, {}
        for name in sorted(set(base) | set(remote)):
            path = self.root / name
            if path.is_symlink():
                raise ValueError('Canonical source must not be a symlink')
            local = path.read_bytes() if path.exists() else None
            before[name] = local
            # Initial install fills missing remote files without interpreting them as local deletions.
            if meta is None and local is None:
                local = remote.get(name)
            try:
                merged[name] = merge(local, base.get(name), remote.get(name))
            except ValueError as e:
                raise ValueError(f'{name}: {e}') from e
        changes, pending = {}, []
        for name, content in merged.items():
            if content != remote.get(name):
                if name.startswith(('raw/', 'materials/', 'examples/', '_meta/')):
                    pending.append(name)
                else:
                    changes[name] = content
        # New local files stay private until explicitly published and approved upstream.
        for p in self.root.rglob('*'):
            if p.is_file() and not p.is_symlink():
                name = p.relative_to(self.root).as_posix()
                if name not in remote and not name.startswith('.') and '__pycache__' not in name:
                    pending.append(name)
        if any((self.root / n).read_bytes() != data if (self.root / n).exists() else data is not None
               for n, data in before.items()):
            raise ValueError('Local files changed during remote read; retry')
        if changes:
            tree = gh(f'repos/{REPO}/git/trees', {'base_tree': commit['commit']['tree']['sha'], 'tree': [
                {'path': n, 'mode': '100644', 'type': 'blob', **({'sha': None} if data is None else
                 {'content': data.decode('utf-8')})} for n, data in changes.items()]})
            new = gh(f'repos/{REPO}/git/commits', {'message': 'sync: personal writing style changes',
                     'tree': tree['sha'], 'parents': [sha]})
            gh(f'repos/{REPO}/git/refs/heads/main', {'sha': new['sha'], 'force': False}, 'PATCH')
            # Read back the exact published commit and its tree, even if main advanced again.
            verified = gh(f'repos/{REPO}/git/commits/{new["sha"]}')
            if verified['tree']['sha'] != tree['sha']:
                raise RuntimeError('Published tree verification failed')
            remote.update(changes)
            remote = {n: data for n, data in remote.items() if data is not None}
            sha = new['sha']
        for name, content in merged.items():
            path = self.root / name
            now = path.read_bytes() if path.exists() else None
            if now != before[name]:
                raise ValueError('Local file changed during publish; retry')
            self.write(path, content)
        for name, data in remote.items():
            atomic(self.state / 'base' / sha / name, data)
        atomic(self.meta, json.dumps({'sha': sha, 'paths': sorted(remote)}).encode())
        atomic(self.root / '.upstream-commit', (sha + '\n').encode())
        atomic(self.state / 'status.json', json.dumps({'checked_at': time.time(), 'commit': sha,
                'pending_publication': sorted(set(pending)), 'execution_mode': 'scheduled_once'}, ensure_ascii=False).encode())
        return sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Compatibility flag; every invocation runs once')
    parser.parse_args()
    home = Path.home()
    sync = Sync(Path(__file__).resolve().parents[1],
                home / '.codex/plugins/cache/openai-curated-remote/write-like-me',
                home / 'Library/Application Support/FanhanWritingSync')
    with (sync.state / 'lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Synchronization is already running')
        try:
            count = sync.local()
            sha = sync.remote()
            sync.local()
            atomic(sync.state / 'last-error.txt', b'')
            print(json.dumps({'plugins': count, 'commit': sha}))
        except Exception as e:
            atomic(sync.state / 'last-error.txt', f'{type(e).__name__}: {e}\n'.encode())
            raise


if __name__ == '__main__':
    main()
