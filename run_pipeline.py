#!/usr/bin/env python3
"""
One-shot pipeline runner.

Runs the same stages as the Airflow DAG (dags/london_environment_pipeline.py)
in order, in a single process, with no scheduler. Airflow needs ~4 GB RAM and
won't fit a free-tier t3.micro, so this is the lightweight way to run the
pipeline once on the box. The DAG is kept for local development.

Run:  python run_pipeline.py
Exits non-zero if any stage fails.
"""

import importlib
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("run_pipeline")

# (module, callable) in dependency order — the DAG's edges flattened:
#   extract_raw_s3  -> bronze_aq -> silver_aq  ┐
#   extract_weather -> bronze_wx -> silver_wx  ┴-> gold -> validate -> tables -> load
STAGES = [
    ("pipelines.extract_raw_s3", "main"),
    ("pipelines.create_bronze_air_quality", "create_bronze_air_quality"),
    ("pipelines.create_silver_air_quality", "create_silver_air_quality"),
    ("pipelines.extract_weather", "main"),
    ("pipelines.create_bronze_weather", "create_bronze_weather"),
    ("pipelines.create_silver_weather", "create_silver_weather"),
    ("pipelines.create_gold", "main"),
    ("data_quality.validate_gold_gx", "main"),
    ("pipelines.create_timescale_tables", "create_tables"),
    ("pipelines.load_gold_to_timescale", "main"),
]


def main() -> int:
    # Pipeline modules resolve paths (data/raw, data/gold, ...) relative to CWD,
    # exactly as the DAG does via os.chdir(PROJECT_ROOT).
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    total = len(STAGES)
    started = time.monotonic()
    log.info("Starting pipeline: %d stages", total)

    for i, (module_name, callable_name) in enumerate(STAGES, start=1):
        label = f"[{i}/{total}] {module_name}.{callable_name}"
        log.info("START %s", label)
        stage_start = time.monotonic()
        try:
            module = importlib.import_module(module_name)
            getattr(module, callable_name)()
        except Exception:
            log.exception("FAILED %s", label)
            return 1
        log.info("DONE  %s (%.1fs)", label, time.monotonic() - stage_start)

    log.info("Pipeline finished OK in %.1fs", time.monotonic() - started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
