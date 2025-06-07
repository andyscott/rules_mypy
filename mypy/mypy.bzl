"Public API for interacting with the mypy rule."

load(
    "//mypy/private:mypy.bzl",
    _mypy = "mypy",
    _mypy_cli = "mypy_cli",
    _mypy_config = "mypy_config",
)

# re-export mypy aspect factory
mypy = _mypy

# export custom mypy_cli producer
mypy_cli = _mypy_cli

mypy_config = _mypy_config