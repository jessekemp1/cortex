from health import doctor_namespace


def test_doctor_namespace_healthy_for_temp_namespace(tmp_path):
    report = doctor_namespace("kempos", config_dir=tmp_path)

    assert report["namespace"] == "kempos"
    assert report["status"] == "healthy"
    checks = {c["name"]: c["status"] for c in report["checks"]}
    assert checks["namespace.validate"] == "pass"
    assert checks["namespace.ensure"] == "pass"
    assert checks["events.write"] == "pass"
    assert checks["events.read"] == "pass"
    assert checks["capabilities.list"] == "pass"


def test_doctor_namespace_rejects_invalid_namespace(tmp_path):
    report = doctor_namespace("../kempos", config_dir=tmp_path)

    assert report["status"] == "unhealthy"
    assert report["checks"][0]["name"] == "namespace.validate"
    assert report["checks"][0]["status"] == "fail"
