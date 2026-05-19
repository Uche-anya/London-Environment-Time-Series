import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOLD_STEPS = [
    "pipelines/create_gold_air_quality.py",
    "pipelines/create_gold_weather.py",
    "pipelines/create_gold_hourly_environment_metrics.py",
]


def run_script(script_path: str) -> None:
    try:
        subprocess.run(
            [sys.executable, script_path],
            cwd=PROJECT_ROOT,
            check=True,
        )
        print(f"Completed: {script_path}")

    except subprocess.CalledProcessError as error:
        print("\nFAILED")
        print(f"Script failed: {script_path}")
        print(f"Exit code: {error.returncode}")
        print("\nRun this script directly to see the full error:")
        print(f"python {script_path}")
        raise


def main() -> None:
    print("Starting gold layer creation...")

    for script in GOLD_STEPS:
        run_script(script)


if __name__ == "__main__":
    main()