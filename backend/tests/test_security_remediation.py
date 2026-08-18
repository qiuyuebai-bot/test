"""Regression tests for credential and personal-data handling."""

from fastapi.testclient import TestClient

from app.models import LearnerProfile, AnonymizedData


def test_login_sets_httponly_auth_cookies_and_cookie_auth_works(
    client: TestClient,
    sample_user,
):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": sample_user.username, "password": "test_password"},
    )

    assert response.status_code == 200
    set_cookies = response.headers.get_list("set-cookie")
    assert any(cookie.startswith("access_token=") and "HttpOnly" in cookie for cookie in set_cookies)
    assert any(cookie.startswith("refresh_token=") and "HttpOnly" in cookie for cookie in set_cookies)

    # TestClient keeps the cookies, so the endpoint must not require a JS-visible
    # Authorization header after login.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["user_id"] == sample_user.id


def test_anonymize_response_does_not_echo_original_values(
    client: TestClient,
    sample_learner_profile: LearnerProfile,
    auth_headers: dict,
    db_session,
):
    original_name = sample_learner_profile.real_name
    original_position = sample_learner_profile.current_position

    response = client.post(
        f"/api/v1/learners/{sample_learner_profile.id}/anonymize",
        json={"fields": ["real_name", "current_position"]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["before"] == {
        "real_name": "[REDACTED]",
        "current_position": "[REDACTED]",
    }
    assert original_name not in response.text
    if original_position:
        assert original_position not in response.text

    record = db_session.query(AnonymizedData).first()
    assert record is not None
    assert record.original_data_hash
    assert record.anonymized_data != original_name
