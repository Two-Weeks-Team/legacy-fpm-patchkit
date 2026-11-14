#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patchkit.fpm_log_runtime import main
raise SystemExit(main())
