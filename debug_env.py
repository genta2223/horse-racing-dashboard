import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")
print("sys.path:")
for p in sys.path:
    print(f" - {p}")

try:
    import pandas
    print(f"Pandas Found: {pandas.__file__}")
except ImportError as e:
    print(f"Pandas Import Failed: {e}")

try:
    import lightgbm
    print(f"LightGBM Found: {lightgbm.__file__}")
except ImportError as e:
    print(f"LightGBM Import Failed: {e}")
