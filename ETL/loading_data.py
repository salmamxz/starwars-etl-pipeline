"""Step 3: extract, transform, then load a dedicated SQLite database.

Reruns replace only this exercise's SQL snapshot inside a transaction.
MongoDB is read only. The original starships-3nf.sqlite3 is not changed.
"""
import json
import sqlite3
import sys
from pathlib import Path

from inspecting_data import extract_data
from transforming_data import COLUMNS, transform_data

NEW_FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NEW_FOLDER / "SQL"))
from schema import create_tables  # noqa: E402

DESTINATION = NEW_FOLDER / "starships-etl.sqlite3"


def load_data(destination=DESTINATION):
    # Transform and validate everything before changing the SQL database.
    characters, starships = extract_data()
    tables = transform_data(characters, starships)
    with sqlite3.connect(destination) as connection:
        create_tables(connection)
        connection.execute("BEGIN")
        # Remove children first so foreign keys remain valid on repeat runs.
        for table in reversed(COLUMNS):
            connection.execute(f"DELETE FROM {table}")
        for table, columns in COLUMNS.items():
            placeholders = ", ".join("?" for _ in columns)
            connection.executemany(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                tables[table],
            )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"Broken SQL references: {violations}")
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in COLUMNS}
        pilots = connection.execute("""SELECT c.name FROM starships s
            JOIN starship_pilots p USING (starship_url)
            JOIN characters c USING (character_id)
            WHERE s.name = ? ORDER BY c.name""", ("Millennium Falcon",)).fetchall()
    print("SQL database:", Path(destination).resolve())
    print(json.dumps(counts, indent=2))
    print("Foreign key violations:", len(violations))
    print("Millennium Falcon pilots:", ", ".join(name for name, in pilots))
    return counts


if __name__ == "__main__":
    load_data()
