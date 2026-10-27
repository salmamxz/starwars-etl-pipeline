"""Step 2: turn MongoDB documents into rows for eight related SQL tables.

This extension exports all starship fields and character identity (ID/name).
Full character attributes, homeworlds and species are outside its scope.
Unknown measures and ranges remain source text. A model must have one spec.
Manufacturer commas are assumed to separate organisations in this dataset.
"""
from inspecting_data import extract_data

MODEL_FIELDS = (
    "cost_in_credits", "length", "max_atmosphering_speed", "crew",
    "passengers", "cargo_capacity", "consumables", "hyperdrive_rating",
    "MGLT", "starship_class",
)
# Order matters: parent records must be loaded before their relationships.
COLUMNS = {
    "characters": ("character_id", "name"),
    "models": ("model", *MODEL_FIELDS),
    "manufacturers": ("name",),
    "model_manufacturers": ("model", "manufacturer"),
    "starships": ("starship_url", "name", "model", "created", "edited"),
    "starship_pilots": ("starship_url", "character_id"),
    "films": ("film_url",),
    "starship_films": ("starship_url", "film_url"),
}


def transform_data(characters, starships):
    tables = {name: [] for name in COLUMNS}
    character_ids = set()
    for character in characters:
        character_id = str(character["_id"])  # BSON ObjectId -> SQL text key
        if character_id in character_ids:
            raise ValueError("Duplicate character ID")
        character_ids.add(character_id)
        tables["characters"].append((character_id, character["name"]))

    models, manufacturers, suppliers, films, ship_urls = {}, set(), set(), set(), set()
    for ship in starships:
        url, model = ship["url"], ship["model"]
        if url in ship_urls:
            raise ValueError(f"Duplicate starship URL: {url}")
        ship_urls.add(url)
        spec = tuple(ship.get(field) for field in MODEL_FIELDS)
        names = frozenset(n.strip() for n in ship["manufacturer"].split(",") if n.strip())
        definition = (spec, names)
        if model in models and models[model] != definition:
            raise ValueError(f"Conflicting specifications for model: {model}")
        models[model] = definition
        manufacturers.update(names)
        suppliers.update((model, name) for name in names)
        tables["starships"].append((url, ship["name"], model,
                                   ship.get("created"), ship.get("edited")))
        for pilot in {str(p) for p in ship["pilots"]}:
            if pilot not in character_ids:
                raise ValueError(f"Unresolved pilot {pilot} on {ship['name']}")
            tables["starship_pilots"].append((url, pilot))
        for film in set(ship.get("films", [])):
            films.add(film)
            tables["starship_films"].append((url, film))

    tables["models"] = [(model, *spec) for model, (spec, _) in sorted(models.items())]
    tables["manufacturers"] = [(name,) for name in sorted(manufacturers)]
    tables["model_manufacturers"] = sorted(suppliers)
    tables["films"] = [(film,) for film in sorted(films)]
    return tables


if __name__ == "__main__":
    tables = transform_data(*extract_data())
    for name, rows in tables.items():
        print(f"{name}: {len(rows)} rows; example: {rows[:1]}")
