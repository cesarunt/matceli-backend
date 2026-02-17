import os
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from uuid import uuid4


from models import db, User, Cake

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "key-2026$")

    UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB
    ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}

    # SQLite (ligero). En producción puedes cambiar a Postgres con DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://")

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///matceli.db"
    #db_url = os.getenv("DATABASE_URL", "sqlite:///instance/matceli.db")
    #app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    
    # default_sqlite = "sqlite:///" + os.path.join(app.instance_path, "matceli.db").replace("\\", "/")
    # app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", default_sqlite)
    
    # asegura que exista la carpeta instance real de Flask
    os.makedirs(app.instance_path, exist_ok=True)

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # CORS para que tu front en Vercel consuma la API
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Crear BD + usuario admin inicial (solo si no existe)
    with app.app_context():
        #os.makedirs("instance", exist_ok=True)
        db.create_all()

        admin_user = os.getenv("ADMIN_USER", "admin")
        admin_pass = os.getenv("ADMIN_PASS", "admin2026$")

        if not User.query.filter_by(username=admin_user).first():
            u = User(username=admin_user)
            u.set_password(admin_pass)
            db.session.add(u)
            db.session.commit()
            print(f"[OK] Admin creado: {admin_user} / {admin_pass}")

    # -------------------------
    # API REST (para tu web)
    # -------------------------
    @app.get("/api/products")
    def api_products():
        category = request.args.get("category")  # tortas/cupcakes/bocaditos/combos
        q = Cake.query.filter_by(active=True)
        if category:
            q = q.filter_by(category=category)
        items = q.order_by(Cake.created_at.desc()).all()

        return jsonify([
            {
                "id": c.id,
                "name": c.name,
                "category": c.category,
                "short_desc": c.short_desc,
                "price_from": c.price_from,
                "servings_from": c.servings_from,
                "image_url": c.image_url,
            } for c in items
        ])

    @app.get("/api/products/<int:pid>")
    def api_product(pid: int):
        c = db.session.get(Cake, pid)
        if not c or not c.active:
            return jsonify({"error": "Not found"}), 404
        return jsonify({
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "short_desc": c.short_desc,
            "price_from": c.price_from,
            "servings_from": c.servings_from,
            "image_url": c.image_url,
        })

    # -------------------------
    # Admin (login + CRUD)
    # -------------------------
    @app.get("/login")
    def login():
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = User.query.filter_by(username=username).first()
        if not u or not u.check_password(password):
            flash("Credenciales incorrectas", "error")
            return redirect(url_for("login"))
        login_user(u)
        return redirect(url_for("cakes_admin"))

    @app.get("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.get("/admin/cakes")
    @login_required
    def cakes_admin():
        category = request.args.get("category", "")
        q = Cake.query
        if category:
            q = q.filter_by(category=category)
        cakes = q.order_by(Cake.created_at.desc()).all()
        return render_template("cakes_admin.html", cakes=cakes, category=category, user=current_user)

    @app.get("/admin/cakes/new")
    @login_required
    def cake_new():
        return render_template("cake_form.html", cake=None)

    @app.post("/admin/cakes/new")
    @login_required
    def cake_new_post():
        img_path = save_upload(request.files.get("image_file"))

        c = Cake(
            name=request.form.get("name", "").strip(),
            category=request.form.get("category", "tortas"),
            short_desc=request.form.get("short_desc", "").strip(),
            image_url=img_path,  # <- ruta del archivo subido
            active=(request.form.get("active") == "on"),
        )

        price = request.form.get("price_from", "").strip()
        servings = request.form.get("servings_from", "").strip()
        c.price_from = float(price) if price else None
        c.servings_from = int(servings) if servings else None

        db.session.add(c)
        db.session.commit()
        flash("Producto creado ✅", "ok")
        return redirect(url_for("cakes_admin"))


    @app.get("/admin/cakes/<int:cid>/edit")
    @login_required
    def cake_edit(cid: int):
        c = db.session.get(Cake, cid)
        if not c:
            flash("No existe", "error")
            return redirect(url_for("cakes_admin"))
        return render_template("cake_form.html", cake=c)

    @app.post("/admin/cakes/<int:cid>/edit")
    @login_required
    def cake_edit_post(cid: int):
        c = db.session.get(Cake, cid)
        if not c:
            flash("No existe", "error")
            return redirect(url_for("cakes_admin"))

        c.name = request.form.get("name", "").strip()
        c.category = request.form.get("category", "tortas")
        c.short_desc = request.form.get("short_desc", "").strip()
        c.active = (request.form.get("active") == "on")

        price = request.form.get("price_from", "").strip()
        servings = request.form.get("servings_from", "").strip()
        c.price_from = float(price) if price else None
        c.servings_from = int(servings) if servings else None

        # Si subieron una nueva imagen, reemplaza. Si no, conserva la actual.
        new_img = save_upload(request.files.get("image_file"))
        if new_img:
            c.image_url = new_img

        db.session.commit()
        flash("Producto actualizado ✅", "ok")
        return redirect(url_for("cakes_admin"))


    @app.post("/admin/cakes/<int:cid>/delete")
    @login_required
    def cake_delete(cid: int):
        c = db.session.get(Cake, cid)
        if c:
            db.session.delete(c)
            db.session.commit()
            flash("Producto eliminado ✅", "ok")
        return redirect(url_for("cakes_admin"))
    
    # -------------------------
    # Admin (Helper Function)
    # -------------------------
    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

    def save_upload(file_storage) -> str | None:
        if not file_storage or file_storage.filename == "":
            return None
        if not allowed_file(file_storage.filename):
            return None

        ext = file_storage.filename.rsplit(".", 1)[1].lower()
        filename = secure_filename(f"{uuid4().hex}.{ext}")
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file_storage.save(path)

        # Esto es lo que guardarás en BD (ruta pública)
        return f"/static/uploads/{filename}"


    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
