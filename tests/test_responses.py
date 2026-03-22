from blender_mcp.utils.responses import success, error


def test_success_response():
    result = success(faces=1000, vertices=500)
    assert result == {"status": "ok", "faces": 1000, "vertices": 500}


def test_error_response():
    result = error("ObjectNotFound", "No object 'Cube'", available=["Sphere"])
    assert result["status"] == "error"
    assert result["error"] == "ObjectNotFound"
    assert result["message"] == "No object 'Cube'"
    assert result["context"]["available"] == ["Sphere"]


def test_error_no_context():
    result = error("MeshError", "Empty mesh")
    assert "context" not in result or result["context"] == {}
