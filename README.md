# Python gogogate2-api [![Build status](https://github.com/vangorra/python_gogogate2_api/workflows/Build/badge.svg?branch=master)](https://github.com/vangorra/python_gogogate2_api/actions?workflow=Build) [![codecov](https://codecov.io/gh/vangorra/python_gogogate2_api/branch/master/graph/badge.svg)](https://codecov.io/gh/vangorra/python_gogogate2_api) [![PyPI](https://img.shields.io/pypi/v/gogogate2-api)](https://pypi.org/project/gogogate2-api/)
Python library for controlling gogogate2 devices


## Installation

    pip install gogogate2-api

## Usage
For a complete example, checkout the integration test in `scripts/integration_test.py`. It has a working example on how to use the API.
```python
from gogogate2_api import GogoGate2Api
api = GogoGate2Api("10.10.0.23", "admin", "password")

# Get info about device and all doors.
api.info()

# Open/close door.
api.open_door(1)
api.close_door(1)
```

## Building
Building, testing and lintings of the project is all done with one script. You only need a few dependencies.

Dependencies:
- python3 in your path.
- The python3 `venv` module.

The build script will setup the venv, dependencies, test and lint and bundle the project.
```bash
./scripts/build.sh
```
