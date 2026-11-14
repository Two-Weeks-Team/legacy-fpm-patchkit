"""Prefer the running libc's own version over legacy Python ELF heuristics."""
import os
import platform


def libc_version():
    try:
        value = os.confstr('CS_GNU_LIBC_VERSION')
        if value and value.startswith('glibc '):
            return ['glibc', value.split(None, 1)[1]]
    except (AttributeError, OSError, ValueError):
        pass
    return list(platform.libc_ver())
