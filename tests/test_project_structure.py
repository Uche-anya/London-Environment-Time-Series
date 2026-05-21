from pathlib import Path


def test_required_project_files_exist():
    required_files = [
        "dags/london_environment_pipeline.py",
        "pipelines/extract_raw_s3.py",
        "pipelines/extract_weather.py",
        "pipelines/create_bronze_air_quality.py",
        "pipelines/create_bronze_weather.py",
        "pipelines/create_silver_air_quality.py",
        "pipelines/create_silver_weather.py",
        "pipelines/create_gold.py",
        "pipelines/create_timescale_tables.py",
        "pipelines/load_gold_to_timescale.py",
        "data_quality/validate_gold_gx.py",
        "terraform/main.tf",
        "terraform/variables.tf",
        "terraform/outputs.tf",
        "terraform/versions.tf",
        "terraform/terraform.tfvars.example",
    ]

    for file_path in required_files:
        assert Path(file_path).exists(), f"Missing required file: {file_path}"