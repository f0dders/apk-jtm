# Makes the project root importable (so tests can `import server`, `import
# extractor`, etc.) and ensures the working directory is the project root,
# since server.py resolves paths like "static/" relative to cwd.
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)
