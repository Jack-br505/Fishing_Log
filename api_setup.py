import base64
import os
import secrets
from datetime import date, datetime, time
from functools import wraps
from hashlib import sha256
from math import isfinite

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash


SPECIES_THRESHOLDS = {
    "Bluegill": 10,
    "Brook Trout": 14,
    "Brown Bullhead": 18,
    "Brown Trout": 24,
    "Bowfin": 27,
    "Burbot": 26,
    "Bullhead Catfish": 18,
    "Channel Catfish": 36,
    "Chinook Salmon": 40,
    "Coho Salmon": 28,
    "Crappie": 16,
    "Common Carp": 33,
    "Flathead Catfish": 40,
    "Freshwater Drum": 30,
    "Green Sunfish": 9,
    "Pumpkinseed": 9,
    "Lake Trout": 34,
    "Largemouth Bass": 21,
    "Longnose Gar": 32,
    "Longnose Sucker": 17,
    "Muskellunge": 46,
    "Northern Pike": 36,
    "Rainbow Trout": 24,
    "Rock Bass": 12,
    "Smallmouth Bass": 21,
    "Steelhead": 34,
    "Smelt":10,
    "Walleye": 29,
    "White Bass": 16,
    "Whitefish": 23,
    "Yellow Perch": 14,
}

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)
database_path = os.path.join(app.instance_path, "fishys.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "FISH_DATABASE_URL", f"sqlite:///{database_path}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    catches = db.relationship(
        "Catch", backref="angler", cascade="all, delete-orphan", lazy=True
    )
    locations = db.relationship(
        "Location", backref="angler", cascade="all, delete-orphan", lazy=True
    )
    sessions = db.relationship(
        "LoginSession", backref="angler", cascade="all, delete-orphan", lazy=True
    )


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    catches = db.relationship("Catch", backref="fishing_location", lazy=True)
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_location_per_user"),
    )


class Catch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    location_id = db.Column(
        db.Integer, db.ForeignKey("location.id"), nullable=False, index=True
    )
    species = db.Column(db.String(80), nullable=False, index=True)
    caught_at = db.Column(db.DateTime, nullable=False)
    length_inches = db.Column(db.Float, nullable=True)
    weight_lbs = db.Column(db.Float, nullable=True)
    gear = db.Column(db.String(160), nullable=True)
    picture = db.Column(db.Text, nullable=True)
    monster = db.Column(db.Boolean, nullable=False, default=False, index=True)


class LoginSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)


def json_error(message, status):
    return jsonify({"error": message}), status


def current_user():
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    token_hash = sha256(token.encode("utf-8")).hexdigest()
    session = LoginSession.query.filter_by(token_hash=token_hash).first()
    return session.angler if session else None


def authenticated(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return json_error("Sign in to access this resource.", 401)
        request.angler = user
        return handler(*args, **kwargs)

    return wrapped


def serialize_location(location):
    catches = location.catches
    return {
        "id": location.id,
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "num_caught": len(catches),
        "species": sorted({item.species for item in catches}),
    }


def serialize_catch(item):
    return {
        "id": item.id,
        "species": item.species,
        "date": item.caught_at.date().isoformat(),
        "time": item.caught_at.time().isoformat(timespec="minutes"),
        "length_inches": item.length_inches,
        "weight_lbs": item.weight_lbs,
        "gear": item.gear,
        "monster": item.monster,
        "picture": item.picture,
        "location_id": item.location_id,
        "location": item.fishing_location.name,
    }


def valid_coordinates(latitude, longitude):
    return (
        isinstance(latitude, (int, float))
        and isfinite(latitude)
        and -90 <= latitude <= 90
        and isinstance(longitude, (int, float))
        and isfinite(longitude)
        and -180 <= longitude <= 180
    )


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/species")
def species_catalog():
    return jsonify(
        [
            {"name": name, "monster_threshold_inches": threshold}
            for name, threshold in SPECIES_THRESHOLDS.items()
        ]
    )


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    email = str(data.get("email", "")).strip() or None
    if not username or len(username) > 80 or not isinstance(password, str) or len(password) < 8:
        return json_error("Choose a username and a password of at least 8 characters.", 400)
    if User.query.filter_by(username=username).first():
        return json_error("That username is already taken.", 409)
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Account created. You can now sign in."}), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    user = User.query.filter_by(username=username).first()
    if not user or not isinstance(password, str) or not check_password_hash(
        user.password_hash, password
    ):
        return json_error("Username or password is incorrect.", 401)
    token = secrets.token_urlsafe(32)
    db.session.add(LoginSession(user_id=user.id, token_hash=sha256(token.encode()).hexdigest()))
    db.session.commit()
    return jsonify({"token": token, "username": user.username})


@app.post("/api/logout")
@authenticated
def logout():
    authorization = request.headers.get("Authorization", "")
    token = authorization.partition(" ")[2]
    token_hash = sha256(token.encode("utf-8")).hexdigest()
    LoginSession.query.filter_by(token_hash=token_hash).delete()
    db.session.commit()
    return jsonify({"message": "Signed out."})


@app.get("/api/locations")
@authenticated
def list_locations():
    locations = Location.query.filter_by(user_id=request.angler.id).order_by(Location.name).all()
    return jsonify([serialize_location(location) for location in locations])


@app.post("/api/locations")
@authenticated
def create_location():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    if not name or len(name) > 120 or not valid_coordinates(latitude, longitude):
        return json_error("Enter a location name and valid latitude/longitude coordinates.", 400)
    if Location.query.filter_by(user_id=request.angler.id, name=name).first():
        return json_error("You already have a location with that name.", 409)
    location = Location(
        user_id=request.angler.id,
        name=name,
        latitude=latitude,
        longitude=longitude,
    )
    db.session.add(location)
    db.session.commit()
    return jsonify(serialize_location(location)), 201


@app.get("/api/catches")
@authenticated
def list_catches():
    items = (
        Catch.query.filter_by(user_id=request.angler.id)
        .order_by(Catch.caught_at.desc(), Catch.id.desc())
        .all()
    )
    return jsonify([serialize_catch(item) for item in items])


@app.post("/api/catches")
@authenticated
def create_catch():
    data = request.get_json(silent=True) or {}
    species = data.get("species")
    if species not in SPECIES_THRESHOLDS:
        return json_error("Choose a North American freshwater species from the catalog.", 400)
    try:
        caught_date = date.fromisoformat(data["date"])
        caught_time = time.fromisoformat(data["time"])
    except (KeyError, TypeError, ValueError):
        return json_error("Enter a valid catch date and time.", 400)

    length = data.get("length_inches")
    weight = data.get("weight_lbs")
    for label, value in (("Length", length), ("Weight", weight)):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < 0
        ):
            return json_error(f"{label} must be a positive number.", 400)

    picture = data.get("picture")
    if picture is not None and (
        not isinstance(picture, str)
        or not picture.startswith(
            ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
        )
        or len(picture) > 6_000_000
    ):
        return json_error("Upload a valid image smaller than 4 MB.", 400)
    if picture:
        try:
            base64.b64decode(picture.partition(",")[2], validate=True)
        except ValueError:
            return json_error("The uploaded image could not be read.", 400)

    location_id = data.get("location_id")
    if location_id is not None:
        location = Location.query.filter_by(
            id=location_id, user_id=request.angler.id
        ).first()
        if location is None:
            return json_error("Choose one of your saved locations.", 400)
    else:
        location_name = str(data.get("location_name", "")).strip()
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        if not location_name or not valid_coordinates(latitude, longitude):
            return json_error(
                "A new location needs a name and valid latitude/longitude coordinates.",
                400,
            )
        location = Location.query.filter_by(
            user_id=request.angler.id, name=location_name
        ).first()
        if location is None:
            location = Location(
                user_id=request.angler.id,
                name=location_name,
                latitude=latitude,
                longitude=longitude,
            )
            db.session.add(location)
            db.session.flush()

    monster = length is not None and length > SPECIES_THRESHOLDS[species]
    item = Catch(
        user_id=request.angler.id,
        location_id=location.id,
        species=species,
        caught_at=datetime.combine(caught_date, caught_time),
        length_inches=length,
        weight_lbs=weight,
        gear=str(data.get("gear", "")).strip() or None,
        picture=picture,
        monster=monster,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(serialize_catch(item)), 201


@app.get("/api/summary")
@authenticated
def summary():
    items = Catch.query.filter_by(user_id=request.angler.id).all()
    counts = {}
    for item in items:
        counts[item.species] = counts.get(item.species, 0) + 1
    return jsonify(
        {
            "total_catches": len(items),
            "species_count": len(counts),
            "monster_count": sum(item.monster for item in items),
            "species": [
                {"name": name, "count": count}
                for name, count in sorted(counts.items())
            ],
        }
    )


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("API_PORT", "5001")), debug=False)
