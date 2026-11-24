"""Installed web-stack versions must be past the published advisories (issue #16)."""
from importlib.metadata import version


def _v(dist):
    return tuple(int(part) for part in version(dist).split(".")[:3])


def test_starlette_past_multipart_and_static_files_advisories():
    # PYSEC-2026-249 is the newest Starlette advisory pip-audit reports; fixed in 1.3.1.
    assert _v("starlette") >= (1, 3, 1)


def test_python_multipart_past_parser_advisories():
    # PYSEC-2026-3040 is the newest python-multipart advisory pip-audit reports; fixed in 0.0.31.
    assert _v("python-multipart") >= (0, 0, 31)


def test_fastapi_past_multipart_redos_advisory():
    # PYSEC-2024-38, fixed in FastAPI 0.109.1.
    assert _v("fastapi") >= (0, 109, 1)
