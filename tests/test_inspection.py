import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from patchkit import inspection


class InspectionTests(unittest.TestCase):
    def test_elf_inspection_does_not_execute_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'fpm'
            content = bytearray(64)
            content[:6] = b'\x7fELF\x02\x01'
            content[18:20] = (62).to_bytes(2, 'little')
            p.write_bytes(content)
            result = inspection.inspect(p)
            self.assertEqual(result['elf_machine'], 'x86_64')
            self.assertEqual(result['runtime'], 'NOT_EXECUTED')
            self.assertFalse(result['deployment_approved'])

    def test_non_elf_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'fpm'
            p.write_text('#!/bin/sh\necho unsafe\n')
            with self.assertRaises(ValueError):
                inspection.inspect(p)

    def test_wrong_artifact_record_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / 'fpm'
            data = bytearray(64); data[:6] = b'\x7fELF\x02\x01'
            data[18:20] = (62).to_bytes(2, 'little')
            p.write_bytes(data)
            record = root / 'build.json'
            record.write_text(json.dumps({'binaries': {'php-fpm': '0' * 64}}))
            with self.assertRaises(ValueError):
                inspection.inspect(p, record)


if __name__ == '__main__':
    unittest.main()
