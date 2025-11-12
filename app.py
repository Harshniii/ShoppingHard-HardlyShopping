from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import joblib
import random

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =======================
# Database Models
# =======================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    device = db.Column(db.String(50))
    traffic_source = db.Column(db.String(50), default="Direct")
    past_visits = db.Column(db.Integer, default=1)
    total_pages_viewed = db.Column(db.Integer, default=0)
    time_per_page_sec = db.Column(db.Float, default=0.0)
    visit_duration_min = db.Column(db.Float, default=0.0)
    cart_opened = db.Column(db.Integer, default=0)
    purchase_made = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0.0)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime, nullable=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Float)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    product_id = db.Column(db.Integer)
    product_name = db.Column(db.String(100))
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer, default=1)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    product_id = db.Column(db.Integer)
    product_name = db.Column(db.String(100))
    price = db.Column(db.Float)
    order_time = db.Column(db.DateTime, default=datetime.utcnow)



# =======================
# Initialize sample products
# =======================
def init_products():
    if Product.query.count() == 0:
        sample_products = [
            {"name": "T-Shirt", "description": "Comfortable cotton t-shirt", "price": 20},
            {"name": "Jeans", "description": "Stylish denim jeans", "price": 40},
            {"name": "Sunglasses", "description": "UV protection sunglasses", "price": 30},
            {"name": "Men Jacket", "description": "Warm winter jacket", "price": 60},
            {"name": "Smartphone", "description": "Latest model smartphone", "price": 800},
            {"name": "Headphones", "description": "Noise-cancelling headphones", "price": 150}
        ]
        for p in sample_products:
            prod = Product(**p)
            db.session.add(prod)
        db.session.commit()

# =======================
# Routes
# =======================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please login.", "danger")
            return redirect(url_for("login"))

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if email == "admin@admin.com" and password == "admin":
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session["user"] = user.name
            session["login_time"] = datetime.now().timestamp()

            # Count past visits
            past_visits = UserActivity.query.filter_by(username=user.name).count()
            session["past_visits"] = past_visits + 1

            flash(f"Welcome {user.name}! This is your visit #{past_visits + 1}", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template("dashboard.html", name=session["user"])
    flash("Please login first.", "warning")
    return redirect(url_for("login"))

# -------------------
# Shop Page
# -------------------
@app.route("/shop")
def shop():
    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    products = Product.query.all()
    return render_template("shop.html", products=products)

@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def product_detail(product_id):
    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    product = Product.query.get_or_404(product_id)

    if "page_start_time" not in session:
        session["page_start_time"] = datetime.now().timestamp()

    if request.method == "POST":
        action = request.form["action"]
        activity = UserActivity.query.filter_by(username=session["user"]).order_by(UserActivity.id.desc()).first()
        if not activity:
            activity = UserActivity(username=session["user"], device="Mobile", past_visits=session.get("past_visits", 1))
            db.session.add(activity)
            db.session.commit()

        # Update user activity
        time_spent = round((datetime.now().timestamp() - session.get("page_start_time", datetime.now().timestamp())), 2)
        activity.time_per_page_sec += time_spent
        activity.total_pages_viewed += 1

        if action == "cart":
            # Add to cart
            existing_item = CartItem.query.filter_by(username=session["user"], product_id=product.id).first()
            if existing_item:
                existing_item.quantity += 1
            else:
                cart_item = CartItem(
                    username=session["user"],
                    product_id=product.id,
                    product_name=product.name,
                    price=product.price
                )
                db.session.add(cart_item)
            activity.cart_opened += 1
            flash(f"{product.name} added to cart!", "success")

        elif action == "buy":
            # Place order directly
            order = Order(
                username=session["user"],
                product_id=product.id,
                product_name=product.name,
                price=product.price
            )
            db.session.add(order)
            activity.purchase_made += 1
            activity.revenue += product.price
            flash(f"{product.name} purchased successfully!", "success")
            return redirect(url_for("shop"))

        db.session.commit()
        session["page_start_time"] = datetime.now().timestamp()
        return redirect(url_for("shop"))

    return render_template("product_details.html", product=product)


@app.route("/cart")
def cart():
    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    items = CartItem.query.filter_by(username=session["user"]).all()
    total = sum([item.price * item.quantity for item in items])
    return render_template("cart.html", items=items, total=total)




# -------------------
# Admin Dashboard
# -------------------
@app.route("/admin_dashboard", methods=["GET", "POST"])
def admin_dashboard():
    if "admin" not in session:
        flash("Admin access only.", "danger")
        return redirect(url_for("login"))

    users = User.query.all()
    user_list = [{"Name": u.name, "Email": u.email} for u in users]

    activities = UserActivity.query.all()
    clustering_data = []
    selected_cluster = "All"
    clusters = ["All"]

    if activities:
        rows = []
        for a in activities:
            rows.append({
                "User": a.username,
                "Device": a.device,
                "TrafficSource": a.traffic_source,
                "PastVisits": a.past_visits,
                "TotalPagesViewed": a.total_pages_viewed,
                "TimePerPage_sec": a.time_per_page_sec,
                "VisitDuration_min": a.visit_duration_min,
                "CartOpened": a.cart_opened,
                "PurchaseMade": a.purchase_made,
                "Revenue": a.revenue
            })
        df = pd.DataFrame(rows)

        try:
            model = joblib.load("best_model.pkl")
            xtrain_columns = joblib.load("xtrain_columns.pkl")

            df_encoded = pd.get_dummies(df)
            df_encoded = df_encoded.reindex(columns=xtrain_columns, fill_value=0)

            df["Cluster"] = model.predict(df_encoded)

            cluster_names = {
                0: "Mobile Window Shopping – largest, low revenue.",
                1: "Enticed to Buy – smaller, high revenue.",
                2: "Examining an Offer – email-driven, low purchases.",
                3: "Online Window Shopping – desktop, low purchases.",
                4: "Visiting with a Purpose – very small, but highest revenue.",
                5: "Impulsive Trying – social media-driven, medium revenue."
            }
            df["ClusterName"] = df["Cluster"].map(cluster_names)

            clusters = ["All"] + list(cluster_names.values())
            clustering_data = df.to_dict(orient="records")
        except Exception as e:
            print("Model prediction error:", e)
            df["ClusterName"] = "Model Error"
            clustering_data = df.to_dict(orient="records")

    if request.method == "POST":
        selected_cluster = request.form.get("cluster_filter", "All")
        if selected_cluster != "All" and clustering_data:
            clustering_data = [d for d in clustering_data if d["ClusterName"] == selected_cluster]

    return render_template(
        "admin_dashboard.html",
        users=user_list,
        clustering_data=clustering_data,
        clusters=clusters,
        selected_cluster=selected_cluster
    )

# -------------------
# Logout
# -------------------
@app.route("/logout")
def logout():
    if "user" in session:
        activity = UserActivity.query.filter_by(username=session["user"]).order_by(UserActivity.id.desc()).first()
        if activity:
            activity.logout_time = datetime.now()
            activity.visit_duration_min = round((activity.logout_time.timestamp() - session["login_time"]) / 60, 2)
            db.session.commit()

    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

# =======================
# Run App
# =======================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        init_products()  # Add sample products
    app.run(debug=True)
