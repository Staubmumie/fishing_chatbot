"""SQLite persistence and query layer for the user's catch collection.

This module knows about SQLite, but not about LangChain or the chatbot.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "catches.db"

BUNDESLAENDER = [
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen",
    "Sachsen-Anhalt",
    "Schleswig-Holstein",
    "Thüringen",
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS catches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                location    TEXT,
                bundesland  TEXT,
                catch_date  TEXT    NOT NULL,
                weight      REAL    DEFAULT 0,
                length      REAL    DEFAULT 0,
                notes       TEXT,
                image       BLOB
            )
            """
        )


def add_catch(
    name,
    location,
    bundesland,
    catch_date,
    weight,
    length,
    notes,
    image,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO catches (
                name,
                location,
                bundesland,
                catch_date,
                weight,
                length,
                notes,
                image
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                location,
                bundesland,
                catch_date.isoformat(),
                weight,
                length,
                notes,
                image,
            ),
        )


def _to_iso_date(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return value


def _build_filter_clause(
    *,
    species: str | None = None,
    location: str | None = None,
    bundesland: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    min_length: float | None = None,
    max_length: float | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []

    if species:
        clauses.append("name LIKE ?")
        parameters.append(f"%{species}%")

    if location:
        clauses.append("location LIKE ?")
        parameters.append(f"%{location}%")

    if bundesland:
        clauses.append("bundesland = ?")
        parameters.append(bundesland)

    if date_from:
        clauses.append("catch_date >= ?")
        parameters.append(_to_iso_date(date_from))

    if date_to:
        clauses.append("catch_date <= ?")
        parameters.append(_to_iso_date(date_to))

    if min_length is not None:
        clauses.append("length >= ?")
        parameters.append(min_length)

    if max_length is not None:
        clauses.append("length <= ?")
        parameters.append(max_length)

    if min_weight is not None:
        clauses.append("weight >= ?")
        parameters.append(min_weight)

    if max_weight is not None:
        clauses.append("weight <= ?")
        parameters.append(max_weight)

    if not clauses:
        return "", parameters

    return " WHERE " + " AND ".join(clauses), parameters


def get_catches(
    species: str | None = None,
    bundesland: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    min_length: float | None = None,
    min_weight: float | None = None,
    sort_by: str = "date_desc",
    *,
    location: str | None = None,
    max_length: float | None = None,
    max_weight: float | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return catches matching the supplied optional filters.

    The original arguments are kept compatible with the existing inventory UI.
    Additional keyword-only filters are used by the chatbot tool.
    """
    where_clause, parameters = _build_filter_clause(
        species=species,
        location=location,
        bundesland=bundesland,
        date_from=date_from,
        date_to=date_to,
        min_length=min_length,
        max_length=max_length,
        min_weight=min_weight,
        max_weight=max_weight,
    )

    sort_options = {
        "date_desc": "catch_date DESC, id DESC",
        "date_asc": "catch_date ASC, id ASC",
        "length_desc": "length DESC, id DESC",
        "weight_desc": "weight DESC, id DESC",
        "name_asc": "name ASC, id ASC",
    }

    query = "SELECT * FROM catches" + where_clause
    query += f" ORDER BY {sort_options.get(sort_by, sort_options['date_desc'])}"

    if limit is not None:
        query += " LIMIT ?"
        parameters.append(max(1, int(limit)))

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


def get_catch_summary(
    *,
    species: str | None = None,
    location: str | None = None,
    bundesland: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    min_length: float | None = None,
    max_length: float | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
) -> dict[str, Any]:
    """Return aggregated catch statistics without loading every row."""
    where_clause, parameters = _build_filter_clause(
        species=species,
        location=location,
        bundesland=bundesland,
        date_from=date_from,
        date_to=date_to,
        min_length=min_length,
        max_length=max_length,
        min_weight=min_weight,
        max_weight=max_weight,
    )

    query = (
        "SELECT "
        "COUNT(*) AS count, "
        "AVG(length) AS average_length, "
        "MAX(length) AS max_length, "
        "AVG(weight) AS average_weight, "
        "MAX(weight) AS max_weight, "
        "MIN(catch_date) AS first_catch_date, "
        "MAX(catch_date) AS latest_catch_date "
        "FROM catches"
        + where_clause
    )

    with get_connection() as connection:
        row = connection.execute(query, parameters).fetchone()

    return dict(row) if row else {"count": 0}


def delete_catch(catch_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM catches WHERE id = ?",
            (catch_id,),
        )
