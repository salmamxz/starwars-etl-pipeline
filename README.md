# Star Wars ETL: MongoDB to 3NF SQL Server

## Project Overview

This project implements an end-to-end data pipeline that extracts Star Wars entity data staged in MongoDB, restructures the records into Third Normal Form (3NF), and loads them into a relational Microsoft SQL Server instance using SQLAlchemy and Pandas.

The pipeline is designed to maintain referential integrity across entities, resolve many-to-many relationships through junction tables, and validate relationships using multi-table SQL queries.

## What Was Done

### 1. Relational Remodelling (3NF Normalisation)

The raw MongoDB collections contain nested structures, stringified numbers, and document reference arrays. These records are remodelled into a relational schema following 3NF principles.

- **First Normal Form (1NF):** Array relationships, such as pilot references within starship records, are represented as individual rows in an associative junction table (`starship_pilots`).
- **Second Normal Form (2NF):** Entity attributes are separated so that non-key attributes depend on their entity's primary key. For example, `starships` stores starship specifications, while `people` stores character details.
- **Third Normal Form (3NF):** Planet and homeworld attributes are stored separately in a `planets` lookup table. Characters reference planets through the `homeworld_id` foreign key, reducing duplication and update anomalies.

### 2. Code Structure

The codebase is organised into three Python files to maintain a separation of concerns.

- **`models.py`:** Defines table schemas, primary keys, foreign key constraints, and database connection settings using SQLAlchemy. Primary-key generation must be configured consistently with the ETL's source-ID mapping strategy.
- **`etl.py`:** Extracts documents from MongoDB, cleans values such as formatted numbers and text placeholders like `"unknown"`, transforms the data, and returns Pandas DataFrames.
- **`main.py`:** Orchestrates database initialisation, recreates the SQL Server schema while handling foreign-key dependencies, loads DataFrames into SQL Server, and executes verification queries.

## Output Breakdown

The intended successful loading output is:

```text
Loaded 48 rows into planets.
Loaded 87 rows into people.
Skipping films: empty dataset.
Loaded 36 rows into starships.
Skipping starship_films: empty dataset.
Loaded 30 rows into starship_pilots.
```

**Note:** The latest execution successfully loaded the `planets`, `people`, and `starships` tables, but failed when inserting into `starship_pilots`. The foreign-key ID mapping must be corrected before the complete output above can be reported as verified.

- **`planets` (48 rows):** Extracted from unique homeworld occurrences across the staged character data.
- **`people` (87 rows):** Extracted from the staged character data and associated with their homeworlds.
- **`starships` (36 rows):** Starship specifications extracted and transformed for relational storage.
- **`starship_pilots` (30 expected links):** Represents the many-to-many relationship between starships and their pilots. The latest execution has not yet confirmed that all 30 links load successfully.
- **`films` and `starship_films` (0 rows):** No film documents were found by the current extraction process. Consequently, the films and starship-film relationship tables remain empty.

## Relational Verification

The following SQL query joins starships, pilots, and planets to inspect the relationships between them. An `INNER JOIN` retrieves matching starship-pilot relationships, while a `LEFT JOIN` retains pilots even when their homeworld is missing.

```sql
SELECT
    s.name AS starship_name,
    p.name AS pilot_name,
    pl.name AS pilot_homeworld
FROM dbo.starships AS s
INNER JOIN dbo.starship_pilots AS sp
    ON s.starship_id = sp.starship_id
INNER JOIN dbo.people AS p
    ON sp.person_id = p.person_id
LEFT JOIN dbo.planets AS pl
    ON p.homeworld_id = pl.planet_id
ORDER BY s.name, p.name;
```

### Verification Results

The following examples describe the expected relationships to inspect after the foreign-key mapping issue has been resolved.

| Starship Name | Pilot Name | Pilot Homeworld | Expected verification |
|---|---|---|---|
| A-wing | Arvel Crynyd | Unknown | Pilot link resolves; missing homeworld is retained by the `LEFT JOIN`. |
| Belbullab-22 starfighter | Grievous | Kalee | Starship, pilot, and planet relationships resolve. |
| Belbullab-22 starfighter | Obi-Wan Kenobi | Stewjon | Multiple pilots can be associated with a starship. |
| H-type Nubian yacht | Padmé Amidala | Naboo | Starship and pilot relationship resolves. |
| Imperial shuttle | Chewbacca | Kashyyyk | Multiple pilots can be associated with the same starship. |
| Imperial shuttle | Han Solo | Corellia | Multiple pilots can be associated with the same starship. |
| Imperial shuttle | Luke Skywalker | Tatooine | Multiple pilots can be associated with the same starship. |
| Jedi Interceptor | Anakin Skywalker | Tatooine | Starship and pilot relationship resolves. |
| Jedi Interceptor | Obi-Wan Kenobi | Stewjon | A pilot can be associated with multiple starships. |
| Jedi starfighter | Obi-Wan Kenobi | Stewjon | A pilot can be associated with multiple starships. |

**Verification status:** The schema has been recreated, and the three main entity tables have loaded successfully. The junction-table foreign-key mapping and final relationship verification remain to be completed.

## Key Learning Outcomes

- Transforming document-oriented MongoDB data into a relational schema.
- Applying 1NF, 2NF, and 3NF principles to reduce redundancy.
- Cleaning and transforming data using Pandas.
- Defining primary keys and foreign-key relationships with SQLAlchemy.
- Loading transformed DataFrames into Microsoft SQL Server.
- Handling missing source datasets and database schema dependencies.
- Using SQL joins to inspect relationships and validate referential integrity.
