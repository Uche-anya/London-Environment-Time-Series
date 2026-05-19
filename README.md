## Project Overview

This project builds an end-to-end environmental time-series pipeline for London Bloomsbury using DEFRA UK-AIR air-quality data and Open-Meteo historical weather data.

The pipeline processes multi-year air-quality CSV files from 2022 to 2025 as the historical baseline, enriches the data with hourly weather observations, validates the final outputs with GX Core, loads curated metrics into TimescaleDB, and visualises trends in Grafana.

The project is also designed to support 2026 current-year updates, where newly available DEFRA CSV data can be processed through the same bronze, silver and gold layers and incrementally upserted into TimescaleDB without duplicating existing records.