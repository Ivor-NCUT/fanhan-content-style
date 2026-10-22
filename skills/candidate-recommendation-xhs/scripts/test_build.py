"""Integration checks with synthetic data; no candidate material or network."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    binary = tmp / 'build'
    subprocess.run(['swiftc', str(root / 'scripts/build.swift'), '-o', str(binary)], check=True)
    spec = {'title': '来推荐一位后训练的候选人｜算法实习', 'body': '合成测试内容，不是真实候选人。', 'lines': ['算法实习', '做过模型蒸馏', '主攻后训练', '正在看机会'], 'subtitle': '国内地点按当次材料确认'}
    config = tmp / 'post.json'
    config.write_text(json.dumps(spec, ensure_ascii=False))
    out = tmp / 'output'
    def run(target):
        return subprocess.run([str(binary), str(config), str(target)], capture_output=True)
    result = run(out)
    assert result.returncode == 0, result.stderr.decode()
    png = (out / '01_候选人推荐封面.png').read_bytes()
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    assert int.from_bytes(png[16:20], 'big') == 1200 and int.from_bytes(png[20:24], 'big') == 1600
    assert (out / '02_招聘服务介绍.png').read_bytes() == (root / 'assets/recruiting-service.png').read_bytes()
    ET.parse(out / '01_候选人推荐封面.svg')
    assert (out / '标题与正文.txt').read_text().endswith((root / 'references/about-me.md').read_text())
    before = hashlib.sha256(png).digest()
    assert run(out).returncode != 0
    assert hashlib.sha256((out / '01_候选人推荐封面.png').read_bytes()).digest() == before
    spec['title'] = '长' * 21
    config.write_text(json.dumps(spec))
    assert run(tmp / 'invalid').returncode != 0 and not (tmp / 'invalid').exists()
    spec['title'] = '测试'
    spec['lines'][0] = '过长文字' * 10
    config.write_text(json.dumps(spec))
    assert run(tmp / 'overflow').returncode != 0 and not (tmp / 'overflow').exists()
print('PASS: output sizes, unchanged asset, fixed copy, no-overwrite, title limit, cover overflow')
