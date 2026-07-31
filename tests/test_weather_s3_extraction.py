from pipelines import extract_weather


def test_weather_s3_key_maps_to_existing_local_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_weather, "LOCAL_RAW_BASE", tmp_path)
    path = extract_weather.local_path_for_s3_key(
        "raw/open_meteo/year=2026/london_weather_2026.json", "raw"
    )
    assert path == tmp_path / "open_meteo/year=2026/london_weather_2026.json"


def test_weather_sync_refreshes_recent_years():
    assert extract_weather.is_recent_year_key(
        "raw/open_meteo/year=2030/london_weather_2030.json", 2030
    ) is True
    assert extract_weather.is_recent_year_key(
        "raw/open_meteo/year=2029/london_weather_2029.json", 2030
    ) is True
    assert extract_weather.is_recent_year_key(
        "raw/open_meteo/year=2028/london_weather_2028.json", 2030
    ) is False


def test_weather_sync_skips_only_matching_local_size(tmp_path):
    local_path = tmp_path / "weather.json"
    assert extract_weather.is_already_downloaded(local_path, {"Size": 2}) is False
    local_path.write_text("{}", encoding="utf-8")
    assert extract_weather.is_already_downloaded(local_path, {"Size": 2}) is True
