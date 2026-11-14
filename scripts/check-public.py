#!/usr/bin/env python3
"""Check tracked/public files for private metadata, broken local links and syntax."""
import ast
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
files = [root / f for f in files if f]
failures = []
private = [re.compile(x) for x in [r'/Users/[A-Za-z0-9_-]+/', r'49\.247\.2\.(?:205|211)',
           r'APPROVE DDENGLE-', r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----', r'gh[pousr]_[A-Za-z0-9]{30,}']]
for path in files:
    if path.is_symlink():
        failures.append(str(path.relative_to(root)) + ': symlink not allowed')
        continue
    if path.suffix in ['.py', '.md', '.json', '.yml', '.svg', '.patch', '.txt'] or path.name in ['LICENSE', '.gitignore']:
        text = path.read_text()
        # The privacy checker contains detection expressions, not operational data.
        if path != Path(__file__).resolve():
            for pattern in private:
                if pattern.search(text):
                    failures.append(str(path.relative_to(root)) + ': private metadata pattern')
        if path.suffix == '.py':
            ast.parse(text, filename=str(path))
        if path.suffix == '.svg':
            ET.fromstring(text)
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
                if '://' in target or target.startswith('#'):
                    continue
                target = urllib.parse.unquote(target.split('#')[0])
                if target and not (path.parent / target).exists():
                    failures.append(str(path.relative_to(root)) + ': broken link ' + target)
if failures:
    print('\n'.join(failures), file=sys.stderr)
    raise SystemExit(1)
print('Public metadata, local links, Python and SVG checks passed for ' + str(len(files)) + ' tracked files.')
