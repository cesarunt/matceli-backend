from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

class Cake(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="tortas")  # tortas/cupcakes/bocaditos/combos
    short_desc = db.Column(db.String(220), nullable=True)

    price_from = db.Column(db.Float, nullable=True)  # opcional: precio "desde"
    servings_from = db.Column(db.Integer, nullable=True)  # opcional

    image_url = db.Column(db.String(400), nullable=True)  # URL pública (Vercel / Cloudinary / etc.)
    active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
