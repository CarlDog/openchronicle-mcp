pyproject.toml:
[tool.poetry.dependencies]
mypy = "^0.910"

mypy.ini:
[mypy]
ignore_missing_imports = True
strict = True
enable_error_code = True

tests/test_mypy_setup.py:
def test_mypy_setup():
    x: int = "string"
    assert x == "string"  # This should raise a type error with mypy.