from app.config import Settings


def test_credentials_never_appear_in_settings_repr():
    value = repr(Settings(password="private-db-secret", api_key="private-api-secret"))
    assert "private-db-secret" not in value and "private-api-secret" not in value
