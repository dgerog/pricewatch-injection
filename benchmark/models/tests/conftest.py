# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""Make the model-study modules, and the agent and storefront they run, importable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "storefront"))
