import os
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    URL,
    create_engine,
)
from sqlalchemy.orm import declarative_base

# Mongo source config
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "starwars"

# Get SQL Server password from env
SQL_SERVER_PASSWORD = os.getenv("SQL_SERVER_PASSWORD")
if not SQL_SERVER_PASSWORD:
    raise RuntimeError("Missing SQL_SERVER_PASSWORD environment variable.")

# Build SQL Server connection string
connection_url = URL.create(
    "mssql+pyodbc",
    username="sa",
    password=SQL_SERVER_PASSWORD,
    host="localhost",
    port=1433,
    database="starwars",
    query={
        "driver": "ODBC Driver 18 for SQL Server",
        "Encrypt": "yes",
        "TrustServerCertificate": "yes",
    },
)

# fast_executemany speeds up bulk inserts from pandas
engine = create_engine(connection_url, fast_executemany=True)
Base = declarative_base()


# NOTE: autoincrement is set to False across these tables because we want to keep
# the original numeric IDs parsed from the SWAPI URLs rather than let SQL Server generate new ones.

class Planet(Base):
    __tablename__ = "planets"

    planet_id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(150), unique=True, nullable=False)
    rotation_period = Column(String(100))
    orbital_period = Column(String(100))
    diameter = Column(String(100))
    climate = Column(String(255))
    gravity = Column(String(255))
    terrain = Column(String(255))
    surface_water = Column(String(100))
    population = Column(String(100))


class Person(Base):
    __tablename__ = "people"

    person_id = Column(Integer, primary_key=True, autoincrement=False)
    homeworld_id = Column(Integer, ForeignKey("planets.planet_id"), nullable=True)
    name = Column(String(150), nullable=False)
    height = Column(String(100))
    mass = Column(String(100))
    hair_color = Column(String(150))
    skin_color = Column(String(150))
    eye_color = Column(String(100))
    birth_year = Column(String(100))
    gender = Column(String(100))


class Film(Base):
    __tablename__ = "films"

    film_id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(String(255), nullable=False)
    episode_id = Column(Integer)
    opening_crawl = Column(Text)
    director = Column(String(255))
    producer = Column(String(500))
    release_date = Column(Date)


class Starship(Base):
    __tablename__ = "starships"

    starship_id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(150), nullable=False)
    model = Column(String(255))
    manufacturer = Column(String(500))
    cost_in_credits = Column(BigInteger)
    length = Column(String(100))
    max_atmosphering_speed = Column(String(100))
    crew = Column(String(100))
    passengers = Column(String(100))
    cargo_capacity = Column(BigInteger)
    consumables = Column(String(100))
    hyperdrive_rating = Column(String(100))
    MGLT = Column(String(100))
    starship_class = Column(String(150))


# Junction table for starships <-> films (M:N)
class StarshipFilm(Base):
    __tablename__ = "starship_films"

    starship_id = Column(Integer, ForeignKey("starships.starship_id"), primary_key=True)
    film_id = Column(Integer, ForeignKey("films.film_id"), primary_key=True)


# Junction table for starships <-> pilots/people (M:N)
class StarshipPilot(Base):
    __tablename__ = "starship_pilots"

    starship_id = Column(Integer, ForeignKey("starships.starship_id"), primary_key=True)
    person_id = Column(Integer, ForeignKey("people.person_id"), primary_key=True)