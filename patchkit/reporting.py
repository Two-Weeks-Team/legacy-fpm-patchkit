"""Exclusive reports preserve earlier successes and failures. Python 3.5+."""
import json
from pathlib import Path


def require_new(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError('report output must be new; choose another filename')


def write_new(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
