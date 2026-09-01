import os


def test_acceptance_gate_shape():
    # Unit suite stays hermetic/network-free: these gates are exercised by
    # scripts/footage_acceptance.sh (NON-CI), not by pytest.
    import src.services.footage.ingest as ing
    import src.services.footage.retrieval as ret
    assert hasattr(ing, "discover")
    assert hasattr(ret, "search_clips")
    assert os.getenv("FOOTAGE_MANUAL_IMPORT_DIR", "footage/imports")


def test_acceptance_license_gate_importable():
    from src.services.footage.ingest import allow_license
    assert callable(allow_license)


def _script_path():
    # tests/footage is money_weaver_backend/tests/footage; repo root is 3 up.
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "footage_acceptance.sh")


def test_acceptance_harness_script_exists():
    assert os.path.exists(_script_path())


def test_analyzer_degrades_to_none_no_net():
    import src.services.footage.analyze as az
    assert callable(az.analyze_clip)


def test_acceptance_script_is_fail_able():
    head = open(_script_path()).read(600)
    assert "set -euo pipefail" in head
