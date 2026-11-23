from django.conf import settings


def test_settings_smoke() -> None:
    assert settings.TIME_ZONE == "Asia/Kolkata"
    assert settings.USE_TZ is True
    assert "apps.core.apps.CoreConfig" in settings.INSTALLED_APPS
