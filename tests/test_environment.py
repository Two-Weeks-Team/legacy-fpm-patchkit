import unittest
from unittest.mock import patch
from patchkit import environment


class EnvironmentTests(unittest.TestCase):
    def test_glibc_uses_runtime_query_instead_of_old_python_elf_guess(self):
        with patch('os.confstr', return_value='glibc 2.23'), patch('platform.libc_ver', return_value=('glibc', '2.9')):
            self.assertEqual(environment.libc_version(), ['glibc', '2.23'])

    def test_unsupported_confstr_falls_back_to_platform(self):
        with patch('os.confstr', side_effect=ValueError), patch('platform.libc_ver', return_value=('libc', 'other')):
            self.assertEqual(environment.libc_version(), ['libc', 'other'])
