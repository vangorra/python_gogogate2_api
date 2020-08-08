# Python gogogate2-api [![Build status](https://github.com/vangorra/python_gogogate2_api/workflows/Build/badge.svg?branch=master)](https://github.com/vangorra/python_gogogate2_api/actions?workflow=Build) [![codecov](https://codecov.io/gh/vangorra/python_gogogate2_api/branch/master/graph/badge.svg)](https://codecov.io/gh/vangorra/python_gogogate2_api) [![PyPI](https://img.shields.io/pypi/v/gogogate2-api)](https://pypi.org/project/gogogate2-api/)
Python library for controlling GogoGate2 and iSmartGate devices


## Installation

    pip install gogogate2-api

## Usage in Commands
```shell script
$ gogogate2 --help
Usage: gogogate2 [OPTIONS] COMMAND [ARGS]...

  Interact with the device API.

Options:
  --host TEXT      [required]
  --username TEXT  [required]
  --password TEXT  Omit for interactive prompt. Use '-' to read from stdin.
  --version        Show the version and exit.
  --help           Show this message and exit.

Commands:
  close  Close the door.
  info   Get info from device.
  open   Open the door.


$ ismartgate --help
Usage: ismartgate [OPTIONS] COMMAND [ARGS]...

  Interact with the device API.

Options:
  --host TEXT      [required]
  --username TEXT  [required]
  --password TEXT  Omit for interactive prompt. Use '-' to read from stdin.
  --version        Show the version and exit.
  --help           Show this message and exit.

Commands:
  close  Close the door.
  info   Get info from device.
  open   Open the door.
```

## Usage in Code
```python
from gogogate2_api import GogoGate2Api, ISmartGateApi

# GogoGate2 API
gogogate2_api = GogoGate2Api("10.10.0.23", "admin", "password")

# Get info about device and all doors.
gogogate2_api.info()

# Open/close door.
gogogate2_api.open_door(1)
gogogate2_api.close_door(1)


# iSmartGate API
ismartgate_api = ISmartGateApi("10.10.0.24", "admin", "password")

# Get info about device and all doors.
ismartgate_api.info()

# Open/close door.
ismartgate_api.open_door(1)
ismartgate_api.close_door(1)
```

## Building
Building, testing and linting of the project is all done with one script. You only need a few dependencies.

Dependencies:
- python3 in your path.
- The python3 `venv` module.

The build script will setup the venv, dependencies, test and lint and bundle the project.
```bash
./scripts/build.sh
```
