"""Verify that the required data-analysis packages are installed and importable."""

import importlib.metadata

packages = ["pandas", "numpy", "matplotlib", "jupyter"]

print("Verifying environment setup...\n")

for name in packages:
    try:
        version = importlib.metadata.version(name)
        print(f"{name:<12} OK  (version {version})")
    except importlib.metadata.PackageNotFoundError:
        print(f"{name:<12} MISSING - not installed in this environment")

# jupyter is a meta-package (no top-level "import jupyter" needed for its
# pieces), but pandas/numpy/matplotlib should import cleanly.
import pandas
import numpy
import matplotlib

print("\nImport check passed: pandas, numpy, and matplotlib all imported successfully.")
