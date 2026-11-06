import sys


def test_runtime_uses_python_3_12_3():
    assert sys.version_info[:3] == (3, 12, 3)
