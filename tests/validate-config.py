#!/usr/bin/env python3
"""Standalone config validation — entry point referenced by config files.

Usage: python3 tests/validate-config.py [--root PATH]

See validate_config.py (underscore) for the module form.
"""
import sys, os
# Add this directory to sys.path so the import works
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_config import main
sys.exit(main())