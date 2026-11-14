"""Read binary metadata without running the binary or its interpreter."""
import json
from pathlib import Path
import platform

from .sources import sha256


def inspect(binary, build_record=None):
    binary = Path(binary)
    if binary.is_symlink() or not binary.is_file():
        raise ValueError('binary must be a regular file')
    with binary.open('rb') as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:4] != b'\x7fELF' or header[4] != 2 or header[5] not in (1, 2):
        raise ValueError('expected a 64-bit ELF binary')
    machine = int.from_bytes(header[18:20], 'little' if header[5] == 1 else 'big')
    names = {62: 'x86_64', 183: 'aarch64'}
    result = {'result': 'INSPECTED', 'sha256': sha256(binary), 'elf_machine': names.get(machine, str(machine)),
              'host_machine': platform.machine(), 'host_system': platform.system(),
              'runtime': 'NOT_EXECUTED', 'external_modules': 'NOT_TESTED',
              'build_record': 'NOT_PROVIDED', 'deployment_approved': False}
    if build_record:
        data = json.loads(Path(build_record).read_text())
        if data['binaries']['php-fpm'] != result['sha256']:
            raise ValueError('binary does not match build record')
        result['build_record'] = 'CHECKSUM_MATCHES'
        result['profile'] = data.get('profile')
    return result
