#!/usr/bin/env python
"""
Plant Timelapse System - Simple entry point
Run from project root: python main.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.main import run_app

if __name__ == "__main__":
    run_app()
