import psycopg2

from src.utils.config import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)


def get_postgres_connection():
    """
    Create a connection to the TimescaleDB/PostgreSQL database.

    This is reused by scripts that need to create tables,
    load data, or query the serving database.
    """

    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )