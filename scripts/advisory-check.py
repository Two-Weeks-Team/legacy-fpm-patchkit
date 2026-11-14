#!/usr/bin/env python3
"""Run the named ACL/filter real Linux binary checks; no service installation."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchkit.advisory_runtime import main
raise SystemExit(main())
