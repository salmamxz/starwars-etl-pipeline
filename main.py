import pandas as pd
from sqlalchemy import create_engine, text
from etl import extract_and_transform_data
from models import Base, connection_url, engine


def ensure_database_exists():
   ## Connect to master and create the starwars DB if it doesn't already exist.
    master_url = connection_url.set(database="master")
    temp_engine = create_engine(master_url, isolation_level="AUTOCOMMIT")

    try:
        with temp_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT database_id FROM sys.databases WHERE name = 'starwars'")
            ).scalar()

            if not exists:
                conn.execute(text("CREATE DATABASE starwars"))
                print("Database 'starwars' created.")
            else:
                print("Database 'starwars' already exists.")
    finally:
        temp_engine.dispose()


def test_sql_connection():
    ##Make sure we can talk to SQL Server.
    with engine.connect() as conn:
        version = conn.execute(text("SELECT @@VERSION")).scalar()
        print("Connected to SQL Server successfully!")
        print(f"Server version: {version}\n")


def recreate_tables():

    ##Drop foreign keys first to avoid constraint lockups when dropping tables,
    ##then recreate all tables defined in models.py.

    tables_to_drop = [
        "starship_pilots",
        "starship_films",
        "people",
        "starships",
        "films",
        "planets",
    ]

    with engine.begin() as conn:
        # Drop foreign key constraints dynamically before dropping tables
        conn.execute(text("""
            DECLARE @sql NVARCHAR(MAX) = N'';
            SELECT @sql = @sql
                + N'ALTER TABLE '
                + QUOTENAME(SCHEMA_NAME(t.schema_id))
                + N'.' + QUOTENAME(t.name)
                + N' DROP CONSTRAINT '
                + QUOTENAME(fk.name) + N';'
            FROM sys.foreign_keys AS fk
            INNER JOIN sys.tables AS t ON fk.parent_object_id = t.object_id
            INNER JOIN sys.schemas AS s ON t.schema_id = s.schema_id
            WHERE s.name = N'dbo';

            IF LEN(@sql) > 0
                EXEC sp_executesql @sql;
        """))

        for table in tables_to_drop:
            conn.execute(text(f"DROP TABLE IF EXISTS dbo.[{table}]"))

    Base.metadata.create_all(bind=engine)
    print("Schema recreated.\n")


def load_dataframe(df, table_name):
    ##Simple wrapper to load a DataFrame into SQL Server via pandas.
    if df is None or df.empty:
        print(f"Skipping {table_name}: empty dataset.")
        return

    # Keep IDs intact because models.py has autoincrement=False
    df.to_sql(table_name, con=engine, if_exists="append", index=False)
    print(f"Loaded {len(df)} rows into {table_name}.")


def load_to_sql():
    ## Run extraction, wipe old tables, and insert rows in FK-dependent order.
    print("Extracting and transforming data from MongoDB...")
    (
        planets_df,
        people_df,
        films_df,
        starships_df,
        starship_films_df,
        starship_pilots_df,
    ) = extract_and_transform_data()

    print("\nResetting SQL Server tables...")
    recreate_tables()

    print("Loading tables...")
    # Parent tables must be loaded before child/junction tables
    load_dataframe(planets_df, "planets")
    load_dataframe(people_df, "people")
    load_dataframe(films_df, "films")
    load_dataframe(starships_df, "starships")

    # Junction tables loaded last
    load_dataframe(starship_films_df, "starship_films")
    load_dataframe(starship_pilots_df, "starship_pilots")


def verify_relational_data():
    ##Run validation queries to check the foreign key relationships.
    with engine.connect() as conn:
        # Check starships and films
        film_query = text("""
            SELECT s.name AS starship_name, f.title AS film_title, f.episode_id
            FROM dbo.starships s
            INNER JOIN dbo.starship_films sf ON s.starship_id = sf.starship_id
            INNER JOIN dbo.films f ON sf.film_id = f.film_id
            ORDER BY f.episode_id, s.name
        """)
        film_res = pd.read_sql(film_query, conn)
        print("\n--- Verification: Starships <-> Films ---")
        if film_res.empty:
            print("No starship-film relationships found (films collection wasn't loaded).")
        else:
            print(film_res.head(10).to_string(index=False))

        # Check starships, pilots, and homeworlds
        pilot_query = text("""
            SELECT s.name AS starship_name, p.name AS pilot_name, pl.name AS pilot_homeworld
            FROM dbo.starships s
            INNER JOIN dbo.starship_pilots sp ON s.starship_id = sp.starship_id
            INNER JOIN dbo.people p ON sp.person_id = p.person_id
            LEFT JOIN dbo.planets pl ON p.homeworld_id = pl.planet_id
            ORDER BY s.name, p.name
        """)
        pilot_res = pd.read_sql(pilot_query, conn)
        print("\n--- Verification: Starships <-> Pilots <-> Homeworlds ---")
        if pilot_res.empty:
            print("No starship-pilot relationships found.")
        else:
            print(pilot_res.head(10).to_string(index=False))

        # Check table counts
        counts = conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM dbo.planets) AS planets,
                (SELECT COUNT(*) FROM dbo.people) AS people,
                (SELECT COUNT(*) FROM dbo.films) AS films,
                (SELECT COUNT(*) FROM dbo.starships) AS starships,
                (SELECT COUNT(*) FROM dbo.starship_films) AS starship_films,
                (SELECT COUNT(*) FROM dbo.starship_pilots) AS starship_pilots
        """)).mappings().one()

        print("\n--- Final Row Counts ---")
        for tbl, count in counts.items():
            print(f"{tbl}: {count}")


if __name__ == "__main__":
    try:
        ensure_database_exists()
        test_sql_connection()
        load_to_sql()
        verify_relational_data()
        print("\nETL finished successfully.")
    except Exception as err:
        print(f"\nPipeline failed: {err}")
        raise
    finally:
        engine.dispose()