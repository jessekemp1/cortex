from pathlib import Path

import pytest

from namespaces import InvalidNamespaceError, ensure_namespace, namespace_dir, validate_namespace


def test_valid_namespace_accepted():
    assert validate_namespace("kempos") == "kempos"
    assert validate_namespace("kempos_01") == "kempos_01"
    assert validate_namespace("kemp-os") == "kemp-os"


@pytest.mark.parametrize("value", ["", "KempOS", "../kempos", "kempos/private", ".kempos", "kempos space"])
def test_invalid_namespace_rejected(value):
    with pytest.raises(InvalidNamespaceError):
        validate_namespace(value)


def test_namespace_dir_under_config(tmp_path):
    path = namespace_dir("kempos", config_dir=tmp_path)
    assert path == (tmp_path / "namespaces" / "kempos").resolve()


def test_ensure_namespace_creates_directory(tmp_path):
    path = ensure_namespace("kempos", config_dir=tmp_path)
    assert path.exists()
    assert path.is_dir()
    assert Path(tmp_path).resolve() in path.parents
