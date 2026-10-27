"""Step 1: connect to MongoDB, inspect it, and extract documents (read only)."""
import os
from pprint import pprint
from pymongo import MongoClient


def extract_data():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    database = os.getenv("MONGODB_DATABASE", "sparta_week06")
    # The context manager closes the connection when extraction finishes.
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
        db = client[database]
        characters = list(db.characters.find())
        starships = list(db.starships.find())
    if not characters or not starships:
        raise ValueError(f"{database} must contain characters AND starships")
    return characters, starships


def inspect_collections():
    characters, starships = extract_data()
    print("MongoDB database:", os.getenv("MONGODB_DATABASE", "sparta_week06"))
    print("Total characters:", len(characters))
    print("Total starships:", len(starships))
    print("Unique models:", len({s["model"] for s in starships}))
    manufacturers = {name.strip() for s in starships
                     for name in s["manufacturer"].split(",") if name.strip()}
    print("Individual manufacturers:", len(manufacturers))
    print("Sample starship document:")
    pprint(starships[0])
    print("Field types in sample:")
    pprint({key: type(value).__name__ for key, value in starships[0].items()})


if __name__ == "__main__":
    inspect_collections()
