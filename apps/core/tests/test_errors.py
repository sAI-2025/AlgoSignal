import json

from apps.core.errors import error_response


def test_error_response_envelope_with_fields():
    response = error_response(
        "VALIDATION_ERROR",
        "Long SMA must exceed Short SMA.",
        status=422,
        fields={"long": ["must exceed short"]},
    )
    assert response.status_code == 422
    assert response["Content-Type"].startswith("application/json")
    assert json.loads(response.content) == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Long SMA must exceed Short SMA.",
            "fields": {"long": ["must exceed short"]},
        }
    }


def test_error_response_without_fields():
    response = error_response("NOT_FOUND", "company not found")
    assert response.status_code == 400
    assert json.loads(response.content) == {
        "error": {"code": "NOT_FOUND", "message": "company not found"}
    }
