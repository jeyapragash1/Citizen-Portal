"""
Small CLI to build the vector index from the command line.
Run from project root or the `citizen-portal` folder:

python scripts/build_index.py

This imports the app's build_vector_index function and runs it.
"""

import os
import sys

# Ensure the application package/module path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app import build_vector_index
except Exception as e:
    print("Failed to import build_vector_index from app.py:", e)
    raise

if __name__ == '__main__':
    print("Building vector index...")
    res = build_vector_index()
    print("Result:", res)
