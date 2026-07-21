from moodwave_mcp import config


def test_settings_loads_local_env_without_overriding_deployment_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LASTFM_API_KEY=local-key\nMUSICBRAINZ_USER_AGENT=Local/1.0\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.setenv("MUSICBRAINZ_USER_AGENT", "Deployment/1.0")

    settings = config.Settings.from_env()

    assert settings.lastfm_api_key == "local-key"
    assert settings.musicbrainz_user_agent == "Deployment/1.0"
