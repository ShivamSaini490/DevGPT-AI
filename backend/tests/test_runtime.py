import sys


def test_runtime_uses_python_3_12():
    assert sys.version_info[:2] == (3, 12)
