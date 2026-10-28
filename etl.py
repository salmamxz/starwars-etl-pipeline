from urllib.parse import urlparse
import pandas as pd
import pymongo
from models import MONGO_DB_NAME, MONGO_URI


def clean_numeric(value):
    ##Strip out commas and handle 'unknown' strings from SWAPI numbers.
    if value is None or pd.isna(value):
        return None

    cleaned = str(value).replace(",", "").strip()
    if not cleaned or cleaned.lower() in {"unknown", "n/a", "none", "null"}:
        return None

    try:
        num = float(cleaned)
        return int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return None


def clean_text(value):
    ##Clean string whitespace and convert 'unknown' placeholders to None.
    if value is None:
        return None
    val = str(value).strip()
    if not val or val.lower() in {"unknown", "n/a", "none", "null"}:
        return None
    return val


def extract_reference_name(value):
    ##Get the name whether the value is stored as a raw string or embedded dict.
    if not value:
        return None
    if isinstance(value, dict):
        return clean_text(value.get("name")) or clean_text(value.get("title"))
    return clean_text(value)


def parse_date(value):
    ##Parse dates safely into Python date objects.
    if not value:
        return None
    try:
        return pd.to_datetime(value, errors="raise").date()
    except (ValueError, TypeError):
        return None


def extract_reference_id(value):

    ##Grab the integer ID from an API URL (e.g. 'https://swapi.dev/api/people/1/' -> 1).
    ##Avoids interpreting MongoDB ObjectId hex strings as numbers.

    if not value:
        return None

    if isinstance(value, dict):
        value = value.get("url") or value.get("_id")

    if value is None:
        return None

    val_str = str(value).strip()
    if val_str.isdigit():
        return int(val_str)

    # Split the URL path and pick the trailing ID digit
    parts = urlparse(val_str).path.strip("/").split("/")
    if parts and parts[-1].isdigit():
        return int(parts[-1])

    return None


def get_source_id(document, fallback_id):
    ##Check common ID keys first, then try the URL, else use the fallback loop counter.
    for key in ("id", "planet_id", "person_id", "film_id", "starship_id"):
        val = document.get(key)
        if val is not None:
            parsed = extract_reference_id(val)
            if parsed is not None:
                return parsed

    url_id = extract_reference_id(document.get("url"))
    if url_id is not None:
        return url_id

    return fallback_id


def extract_and_transform_data():
    ##Extract collections from Mongo and structure them into relational DataFrames.
    client = pymongo.MongoClient(MONGO_URI)
    try:
        db = client[MONGO_DB_NAME]
        raw_characters = list(db["characters"].find())
        raw_starships = list(db["starships"].find())

        cols = set(db.list_collection_names())
        raw_planets = list(db["planets"].find()) if "planets" in cols else []
        raw_films = list(db["films"].find()) if "films" in cols else []
    finally:
        client.close()

    # planets
    planet_docs = {}

    # If we have a planets collection, use that
    for idx, planet in enumerate(raw_planets, start=1):
        name = extract_reference_name(planet) or clean_text(planet.get("name"))
        if not name:
            continue

        p_id = get_source_id(planet, idx)
        planet_docs[name] = {
            "planet_id": p_id,
            "name": name,
            "rotation_period": clean_text(planet.get("rotation_period")),
            "orbital_period": clean_text(planet.get("orbital_period")),
            "diameter": clean_text(planet.get("diameter")),
            "climate": clean_text(planet.get("climate")),
            "gravity": clean_text(planet.get("gravity")),
            "terrain": clean_text(planet.get("terrain")),
            "surface_water": clean_text(planet.get("surface_water")),
            "population": clean_text(planet.get("population")),
        }

    # Otherwise collect homeworlds from characters so FK references don't fail
    for character in raw_characters:
        homeworld = character.get("homeworld")
        name = extract_reference_name(homeworld)
        if not name:
            continue

        if name not in planet_docs:
            p_id = extract_reference_id(homeworld)
            planet_docs[name] = {
                "planet_id": p_id,
                "name": name,
                "rotation_period": None,
                "orbital_period": None,
                "diameter": None,
                "climate": None,
                "gravity": None,
                "terrain": None,
                "surface_water": None,
                "population": None,
            }

    # Assign IDs for any homeworld that didn't have one in the URL
    used_planet_ids = set()
    for name in sorted(planet_docs):
        row = planet_docs[name]
        p_id = row["planet_id"]
        if p_id is None or p_id in used_planet_ids:
            p_id = 1
            while p_id in used_planet_ids:
                p_id += 1
            row["planet_id"] = p_id
        used_planet_ids.add(p_id)

    planets_df = pd.DataFrame(
        list(planet_docs.values()),
        columns=[
            "planet_id", "name", "rotation_period",
            "orbital_period", "diameter", "climate",
            "gravity", "terrain", "surface_water", "population",
        ],
    )
    planet_to_id = {r["name"]: r["planet_id"] for r in planets_df.to_dict("records")}

    # People / Characters
    people_rows = []
    mongo_char_to_person_id = {}

    for idx, char in enumerate(raw_characters, start=1):
        person_id = get_source_id(char, idx)
        mongo_char_to_person_id[str(char["_id"])] = person_id

        hw_name = extract_reference_name(char.get("homeworld"))
        people_rows.append({
            "person_id": person_id,
            "homeworld_id": planet_to_id.get(hw_name),
            "name": clean_text(char.get("name")),
            "height": clean_text(char.get("height")),
            "mass": clean_text(char.get("mass")),
            "hair_color": clean_text(char.get("hair_color")),
            "skin_color": clean_text(char.get("skin_color")),
            "eye_color": clean_text(char.get("eye_color")),
            "birth_year": clean_text(char.get("birth_year")),
            "gender": clean_text(char.get("gender")),
        })

    people_df = pd.DataFrame(
        people_rows,
        columns=[
            "person_id", "homeworld_id", "name", "height",
            "mass", "hair_color", "skin_color", "eye_color",
            "birth_year", "gender",
        ],
    ).drop_duplicates(subset=["person_id"])

    # --- Films ---
    film_rows = []
    film_id_by_ref = {}
    film_id_by_title = {}

    for idx, film in enumerate(raw_films, start=1):
        f_id = get_source_id(film, idx)
        title = clean_text(film.get("title"))

        film_rows.append({
            "film_id": f_id,
            "title": title,
            "episode_id": clean_numeric(film.get("episode_id")),
            "opening_crawl": clean_text(film.get("opening_crawl")),
            "director": clean_text(film.get("director")),
            "producer": clean_text(film.get("producer")),
            "release_date": parse_date(film.get("release_date")),
        })

        if title:
            film_id_by_title[title] = f_id
        if film.get("url"):
            film_id_by_ref[str(film["url"])] = f_id
        film_id_by_ref[str(f_id)] = f_id

    films_df = pd.DataFrame(
        film_rows,
        columns=[
            "film_id", "title", "episode_id", "opening_crawl",
            "director", "producer", "release_date",
        ],
    ).drop_duplicates(subset=["film_id"])

    #Starshipss
    starship_rows = []
    mongo_ship_to_sql_id = {}

    for idx, ship in enumerate(raw_starships, start=1):
        s_id = get_source_id(ship, idx)
        mongo_ship_to_sql_id[str(ship["_id"])] = s_id

        starship_rows.append({
            "starship_id": s_id,
            "name": clean_text(ship.get("name")),
            "model": clean_text(ship.get("model")),
            "manufacturer": clean_text(ship.get("manufacturer")),
            "cost_in_credits": clean_numeric(ship.get("cost_in_credits")),
            "length": clean_text(ship.get("length")),
            "max_atmosphering_speed": clean_text(ship.get("max_atmosphering_speed")),
            "crew": clean_text(ship.get("crew")),
            "passengers": clean_text(ship.get("passengers")),
            "cargo_capacity": clean_numeric(ship.get("cargo_capacity")),
            "consumables": clean_text(ship.get("consumables")),
            "hyperdrive_rating": clean_text(ship.get("hyperdrive_rating")),
            "MGLT": clean_text(ship.get("MGLT")),
            "starship_class": clean_text(ship.get("starship_class")),
        })

    starships_df = pd.DataFrame(
        starship_rows,
        columns=[
            "starship_id", "name", "model", "manufacturer",
            "cost_in_credits", "length", "max_atmosphering_speed",
            "crew", "passengers", "cargo_capacity", "consumables",
            "hyperdrive_rating", "MGLT", "starship_class",
        ],
    ).drop_duplicates(subset=["starship_id"])

    #Starship-Films Links
    sf_rows = []
    valid_film_ids = set(films_df["film_id"])

    for ship in raw_starships:
        s_id = mongo_ship_to_sql_id.get(str(ship["_id"]))

        for f_ref in ship.get("films", []):
            f_id = None
            if isinstance(f_ref, dict):
                f_id = extract_reference_id(f_ref.get("film_id")) or film_id_by_title.get(f_ref.get("title"))
                if not f_id and f_ref.get("url"):
                    f_id = film_id_by_ref.get(str(f_ref["url"]))
            else:
                f_id = film_id_by_ref.get(str(f_ref)) or extract_reference_id(f_ref)

            if s_id and f_id and f_id in valid_film_ids:
                sf_rows.append({"starship_id": s_id, "film_id": f_id})

    starship_films_df = pd.DataFrame(sf_rows, columns=["starship_id", "film_id"]).drop_duplicates()

    #Starship-Pilots Links
    sp_rows = []
    valid_person_ids = set(people_df["person_id"])

    for ship in raw_starships:
        s_id = mongo_ship_to_sql_id.get(str(ship["_id"]))

        for p_ref in ship.get("pilots", []):
            p_id = None
            if isinstance(p_ref, dict):
                # Handled whether pilots contain ObjectId references or raw URLs
                mongo_oid = str(p_ref.get("_id")) if p_ref.get("_id") else None
                p_id = mongo_char_to_person_id.get(mongo_oid) or extract_reference_id(p_ref.get("url"))
            else:
                p_id = mongo_char_to_person_id.get(str(p_ref)) or extract_reference_id(p_ref)

            # Only append if both IDs exist in their parent tables to satisfy FK constraint
            if s_id and p_id and p_id in valid_person_ids:
                sp_rows.append({"starship_id": s_id, "person_id": p_id})

    starship_pilots_df = pd.DataFrame(sp_rows, columns=["starship_id", "person_id"]).drop_duplicates()

    return (
        planets_df,
        people_df,
        films_df,
        starships_df,
        starship_films_df,
        starship_pilots_df,
    )