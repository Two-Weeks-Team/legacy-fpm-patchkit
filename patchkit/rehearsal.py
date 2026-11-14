"""Exercise file backup/replacement/restore only in a NEW synthetic directory."""
import os
from pathlib import Path
import shutil

from .sources import sha256


def run(candidate, destination):
    candidate, destination = Path(candidate), Path(destination)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError('candidate must be a regular file')
    if destination.exists() or destination.is_symlink():
        raise ValueError('rehearsal destination must be new; live paths are not accepted')
    digest = sha256(candidate)
    destination.mkdir(parents=True)
    current, backup, staged = [destination / x for x in ['current', 'backup', 'staged']]
    current.write_bytes(b'synthetic-original')
    current.chmod(0o755)
    original = sha256(current)
    shutil.copy2(current, backup)
    shutil.copy2(candidate, staged)
    if sha256(staged) != digest or sha256(backup) != original:
        raise ValueError('backup/candidate integrity failure')
    os.replace(staged, current)
    installed = sha256(current)
    shutil.copy2(backup, staged)
    os.replace(staged, current)
    if sha256(current) != original or installed != digest:
        raise ValueError('rehearsal verification failed')
    return {'result': 'REHEARSAL_PASS', 'candidate_sha256': digest,
            'restored_sha256': original, 'service_activation': 'NOT_PERFORMED',
            'scope': 'synthetic files only; not production rollback proof'}
