import pathlib
import bcrypt
import os
import json
from flask import Flask, jsonify, render_template, request, session, redirect, send_file, abort
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId
from datetime import datetime, timedelta
from datetime import datetime, timedelta, timezone
import logging
import threading
import uuid
import csv
from io import StringIO, BytesIO
from dotenv import load_dotenv
from functools import wraps # Ensure this is present for decorators
import re # New: For regex matching in autosuggest if needed, but primarily MongoDB's regex is used.
import secrets
import smtplib
from email.message import EmailMessage
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    FLASK_LIMITER_AVAILABLE = True
except Exception:
    # Graceful fallback when Flask-Limiter isn't installed in the active environment.
    FLASK_LIMITER_AVAILABLE = False
    def get_remote_address():
        try:
            # Best-effort: prefer X-Forwarded-For, then remote_addr
            return request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr or 'unknown'
        except Exception:
            return 'unknown'

    class Limiter:
        """No-op fallback Limiter so the app can run without the package installed.

        This provides `.init_app()` and a `.limit()` decorator that returns the
        original function unchanged.
        """
        def __init__(self, *args, **kwargs):
            pass
        def init_app(self, app):
            return None
        def limit(self, *a, **kw):
            def _decorator(fn):
                return fn
            return _decorator
from recommendation_engine import RecommendationEngine
from gridfs import GridFS
from uuid import uuid4


# Defer heavy ML imports (numpy, sentence-transformers) so the web app can start
# even when those packages are not installed on the host. Functions that need
# embeddings will import them lazily and fail gracefully if unavailable.
FAISS_AVAILABLE = False
try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False
    print("FAISS not available. ML/vector features will be disabled if numpy/sentence-transformers are missing.")

load_dotenv()

# Basic logging configuration for debugging server-side errors
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")
CORS(app)

# Rate limiter (development-friendly defaults). For production use a Redis backend.
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"]) 
limiter.init_app(app)

# MongoDB connection
# Prefer MONGO_URI from environment; fallback to the provided Atlas URI when not set.
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://iit22089_db_user:Yy36tAuCRbaTfNg0@cluster0.h1fuoxy.mongodb.net/?appName=Cluster0")
try:
    # Use ServerApi('1') to be explicit for Atlas server API compatibility
    client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    # Verify connection by pinging the server once at startup
    try:
        client.admin.command('ping')
        print("Pinged your deployment. Successfully connected to MongoDB.")
    except Exception as e:
        print(f"Warning: connected client could not ping MongoDB: {e}")
except Exception as e:
    # If Atlas connection fails for any reason, fall back to a local MongoDB URI if provided
    print(f"Warning: could not create MongoClient with provided MONGO_URI: {e}")
    fallback = os.getenv("FALLBACK_MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(fallback)

db = client["citizen_portal"]

# Existing collections
services_col = db["services"]       # Stores Super Category documents
admins_col = db["admins"]           # Admin users
eng_col = db["engagements"]         # User engagement logs

# New collections for Task 07
categories_col = db["categories"]   # New: category groups (e.g., Governance, Economic)
officers_col = db["officers"]       # New: officers metadata
ads_col = db["ads"]                 # New: ads & training program announcements
users_col = db["users"]             # New: progressive profile / accounts

# Jobs collection for durable index job status
index_jobs_col = db["index_jobs"]

# E-commerce collections (store)
products_col = db["products"]
orders_col = db["orders"]
payments_col = db["payments"]

# Audit logs for GDPR / admin actions
audit_logs_col = db["audit_logs"]
# Deletion confirmations (two-step) for destructive GDPR operations
deletion_confirmations_col = db["deletion_confirmations"]

# Initialize recommendation engine
recommendation_engine = RecommendationEngine(db)


def is_db_available(timeout_seconds: int = 2) -> bool:
    """Return True if the MongoDB server appears reachable (ping), False otherwise.

    We keep this fast and conservative: do a single ping and return False on any
    exception. This allows the app to continue running in degraded mode when
    the remote DB (Atlas) is temporarily unreachable.
    """
    try:
        client.admin.command('ping')
        return True
    except Exception:
        return False

# AI / embeddings
EMBED_MODEL = None
INDEX_PATH = pathlib.Path("./data/faiss.index")
META_PATH = pathlib.Path("./data/faiss_meta.json")
VECTOR_DIM = 384  # for all-MiniLM-L6-v2 model used by SentenceTransformer

def get_embedding_model():
    """Initializes and returns the SentenceTransformer model for embeddings."""
    global EMBED_MODEL
    if EMBED_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            # Model not available on this host. Inform and re-raise as RuntimeError so callers can handle it.
            print(f"sentence-transformers not available: {e}")
            raise RuntimeError("sentence-transformers is not installed on this environment")
        EMBED_MODEL = SentenceTransformer(os.getenv("EMBED_MODEL","sentence-transformers/all-MiniLM-L6-v2"))
    return EMBED_MODEL


# --- Helpers ---
def admin_required(fn):
    """
    Decorator to protect admin routes, ensuring only logged-in admins can access them.
    Checks for 'admin_logged_in' in the Flask session.
    """
    @wraps(fn) # This is essential for Flask routing
    def wrapper(*a, **kw):
        if not session.get("admin_logged_in"):
            # For API routes, return JSON error; for page routes, redirect to login
            if request.path.startswith("/api/admin"):
                return jsonify({"error":"unauthorized"}), 401
            else:
                return redirect("/admin/login") # Redirect for HTML pages
        return fn(*a, **kw)
    return wrapper


def user_or_admin_required(fn):
    """Decorator to ensure the requester is either the user referenced or an admin.
    Expects the endpoint to receive a user_id either as a URL path param or in JSON payload.
    """
    @wraps(fn)
    def wrapper(*a, **kw):
        # Admins are always allowed
        if session.get("admin_logged_in"):
            return fn(*a, **kw)

        # Try to find a user_id in URL params (kw) or JSON body
        req_user_id = None
        if 'user_id' in kw:
            req_user_id = kw.get('user_id')
        else:
            try:
                payload = request.json or {}
                req_user_id = payload.get('user_id') or request.view_args.get('user_id')
            except Exception:
                req_user_id = None

        # If session has user_id and matches requested id, allow
        session_user = session.get('user_id')
        if session_user and req_user_id and str(session_user) == str(req_user_id):
            return fn(*a, **kw)

        return jsonify({"error":"unauthorized"}), 401
    return wrapper


def now_utc():
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)



# --- Public pages ---
@app.route("/")
def home():
    """Renders the main public portal homepage."""
    # Landing page (home) shows introduction and CTA; keep portal available at /index
    return render_template("home.html")


# Keep the original portal available at /index so authenticated users land here
@app.route("/index")
def portal_index():
    """Render the interactive services portal (previously served at /)."""
    return render_template("index.html")


@app.route("/store")
def store():
    """Render the public store page."""
    return render_template("store.html")


@app.route("/dashboard")
@admin_required
def dashboard():
    """Render an enhanced dashboard page for admins with analytics summary."""
    # Call the analytics endpoint function and get its JSON payload
    try:
        analytics_resp = get_dashboard_analytics()
        # analytics_resp is a Flask Response; extract JSON
        analytics = analytics_resp.get_json() if hasattr(analytics_resp, 'get_json') else analytics_resp
    except Exception:
        analytics = {}

    total_users = analytics.get("user_metrics", {}).get("total_users") if isinstance(analytics, dict) else None
    total_engagements = analytics.get("engagement_metrics", {}).get("total_engagements") if isinstance(analytics, dict) else None

    return render_template("dashboard.html",
                           analytics=analytics,
                           total_users=total_users,
                           total_engagements=total_engagements)

# New: Ministry services details page
@app.route("/ministry/<ministry_id>")
def ministry_services(ministry_id):
    # Find the ministry by ID from the DB
    super_categories = list(services_col.find({}, {"_id":0}))
    ministry = None
    for sc in super_categories:
        for min in sc.get("ministries", []):
            if min.get("id") == ministry_id:
                ministry = min
                break
        if ministry:
            break
    if not ministry:
        # If not found, show a friendly list of available ministries to help navigation
        ministries = []
        for sc in super_categories:
            for m in sc.get("ministries", []):
                ministries.append({"id": m.get("id"), "name": getLocalizedName(m.get("name")), "super_category": getLocalizedName(sc.get("name"))})
        return render_template("ministry_list.html", ministries=ministries, query_id=ministry_id)

    return render_template("ministry_services.html", ministry=ministry)

@app.route("/admin")
def admin_page():
    """Renders the admin dashboard page. If not logged in, redirects to login."""
    if not session.get("admin_logged_in"):
        return redirect("/admin/login")
    # Populate basic analytics so the template can show totals without extra XHR
    try:
        analytics_resp = get_dashboard_analytics()
        analytics = analytics_resp.get_json() if hasattr(analytics_resp, 'get_json') else analytics_resp
    except Exception:
        analytics = {}

    total_users = analytics.get("user_metrics", {}).get("total_users") if isinstance(analytics, dict) else None
    total_engagements = analytics.get("engagement_metrics", {}).get("total_engagements") if isinstance(analytics, dict) else None

    return render_template("admin.html", analytics=analytics, total_users=total_users, total_engagements=total_engagements)

@app.route("/admin/manage")
@admin_required
def manage_page():
    """Renders the admin service management page. Requires admin login."""
    return render_template("manage.html")


@app.route("/admin/categories")
@admin_required
def admin_categories_page():
    """Render the admin categories management page."""
    return render_template("manage_categories.html")


@app.route("/admin/officers")
@admin_required
def admin_officers_page():
    """Render the admin officers management page."""
    return render_template("manage_officers.html")


@app.route("/admin/ads")
@admin_required
def admin_ads_page():
    """Render the admin ads management page."""
    return render_template("manage_ads.html")


# Convenience redirect routes for admin in-page sections so links work as standalone URLs
@app.route("/admin/navigation")
@admin_required
def admin_navigation_redirect():
    return redirect('/admin')


@app.route("/admin/users")
@admin_required
def admin_users_redirect():
    return redirect('/admin#userManagement')


@app.route("/admin/services")
@admin_required
def admin_services_redirect():
    return redirect('/admin#services')


@app.route("/admin/ai-index")
@admin_required
def admin_ai_index_redirect():
    return redirect('/admin#ai-search-index')


@app.route("/admin/reports")
@admin_required
def admin_reports_redirect():
    return redirect('/admin#reports')


@app.route("/admin/export")
@admin_required
def admin_export_redirect():
    return redirect('/admin#exportData')


@app.route("/admin/backup-restore")
@admin_required
def admin_backup_redirect():
    return redirect('/admin#backupRestore')


# --- API: services & categories (public) ---
@app.route("/api/services")
def get_services():
    """
    Returns a JSON list of all original service documents (Super Categories),
    including their nested ministries, subservices and questions. Excludes MongoDB's internal _id.
    """
    docs = list(services_col.find({}, {"_id":0}))
    return jsonify(docs)

@app.route("/api/categories")
def get_categories():
    """
    Returns a JSON list of Super Category documents directly from services_col.
    This endpoint is used by the frontend to build the leftmost panel.
    """
    # Given our seed_data.py, services_col *directly stores* the Super Category documents.
    # The frontend is expecting these as its top-level "categories".
    return jsonify(list(services_col.find({}, {"_id":0})))

@app.route("/api/service/<service_id>")
def get_service(service_id):
    """
    Returns a JSON object for a specific Super Category by its 'id',
    excluding MongoDB's internal _id. This is primarily for fetching a full
    Super Category document.
    """
    doc = services_col.find_one({"id": service_id}, {"_id":0})
    return jsonify(doc or {})


@app.route("/api/search/autosuggest")
def autosuggest():
    """
    Provides quick search matches for typeahead functionality.
    Searches across super category names, ministry names and subservice names
    within the hierarchical services_col.
    """
    q = request.args.get("q","").strip()
    if not q:
        return jsonify([])

    # Escape the user query for safe regex usage to avoid ReDoS or unintended regex patterns
    safe_q = re.escape(q)

    # Use $regex in $match only, then filter in Python
    docs = list(services_col.find({
        "$or": [
            {"name.en": {"$regex": safe_q, "$options": "i"}},
            {"ministries.name.en": {"$regex": safe_q, "$options": "i"}},
            {"ministries.subservices.name.en": {"$regex": safe_q, "$options": "i"}}
        ]
    }, {"_id":0}))

    search_pattern = re.compile(re.escape(q), re.IGNORECASE)
    final_results = []
    seen_ids = set()
    for sc in docs:
        super_cat_id = sc.get("id")
        super_cat_name = getLocalizedName(sc.get("name"))
        for ministry in sc.get("ministries", []):
            ministry_id = ministry.get("id")
            ministry_name = getLocalizedName(ministry.get("name"))
            # Ministry match
            if ministry_name and search_pattern.search(ministry_name) and ministry_id not in seen_ids:
                final_results.append({
                    "id": ministry_id,
                    "name": {"en": ministry_name},
                    "super_category_id": super_cat_id,
                    "super_category_name": {"en": super_cat_name},
                    "type": "ministry"
                })
                seen_ids.add(ministry_id)
            # Subservice match
            for subservice in ministry.get("subservices", []):
                sub_id = subservice.get("id")
                sub_name = getLocalizedName(subservice.get("name"))
                if sub_name and search_pattern.search(sub_name) and sub_id not in seen_ids:
                    final_results.append({
                        "id": sub_id,
                        "name": subservice.get("name"),
                        "super_category_id": super_cat_id,
                        "super_category_name": {"en": super_cat_name},
                        "ministry_id": ministry_id,
                        "ministry_name": {"en": ministry_name},
                        "type": "subservice"
                    })
                    seen_ids.add(sub_id)
    return jsonify(final_results[:20])


@app.route("/api/engagement", methods=["POST"])
def log_engagement():
    """
    Logs user engagement data, now extended to optionally capture
    ad IDs and source of engagement.
    """
    payload = request.json or {}
    doc = {
        "user_id": payload.get("user_id") or None,
        "age": int(payload.get("age")) if payload.get("age") else None,
        "job": payload.get("job"),
        "desires": payload.get("desires") or [],
        "question_clicked": payload.get("question_clicked"),
        "service": payload.get("service"),
        "ad": payload.get("ad"),
        "source": payload.get("source"),
        "timestamp": now_utc()
    }
    eng_col.insert_one(doc)
    return jsonify({"status":"ok"})


@app.route("/api/engagement/enhanced", methods=["POST"])
def log_enhanced_engagement():
    """
    Enhanced engagement logging that captures device info and referral data.
    If consent flag 'consent_given' is present and False, avoid storing raw IP.
    """
    payload = request.json or {}

    user_agent = request.headers.get('User-Agent', '')
    # Try to mask the IP address for privacy by default (truncate last octet for IPv4)
    ip_address = request.remote_addr or request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    # simple anonymization for IPv4 addresses
    def mask_ip(ip):
        if not ip:
            return None
        try:
            parts = ip.split('.')
            if len(parts) == 4:
                parts[-1] = '0'
                return '.'.join(parts)
        except Exception:
            pass
        return ip

    consent_given = payload.get('consent_given', True)
    device_info = {
        "user_agent": user_agent,
        "ip_address": mask_ip(ip_address) if not payload.get('store_full_ip', False) else (ip_address or None),
        "screen_resolution": payload.get('screen_resolution')
    }

    doc = {
        "user_id": payload.get("user_id"),
        "session_id": payload.get("session_id"),
        "age": int(payload.get("age")) if payload.get("age") else None,
        "job": payload.get("job"),
        "desires": payload.get("desires", []),
        "question_clicked": payload.get("question_clicked"),
        "service": payload.get("service"),
        "ad": payload.get("ad"),
        "source": payload.get("source"),
        "time_spent": payload.get("time_spent"),
        "scroll_depth": payload.get("scroll_depth"),
        "clicks": payload.get("clicks", []),
        "searches": payload.get("searches", []),
        "device_info": device_info,
        "referral_data": {
            "referrer": request.headers.get('Referer', ''),
            "utm_source": payload.get("utm_source"),
            "utm_medium": payload.get("utm_medium"),
            "utm_campaign": payload.get("utm_campaign")
        },
        "timestamp": now_utc()
    }

    # Do not store IP if consent explicitly denied
    if not consent_given:
        doc['device_info']['ip_address'] = None

    eng_col.insert_one(doc)
    return jsonify({"status":"ok"})

@app.route("/api/profile/step", methods=["POST"])
def profile_step():
    """
    Saves partial user profile data step-by-step.
    Can upsert by anonymous profile_id or by email.
    """
    payload = request.json or {}
    profile_id = payload.get("profile_id")
    email = payload.get("email")
    data = payload.get("data",{})
    step_name = payload.get("step", "unknown")

    if profile_id:
        try:
            obj_id = ObjectId(profile_id)
            users_col.update_one({"_id": obj_id}, {"$set":
                                   {f"profile.{step_name}": data, "updated": datetime.utcnow()}}, upsert=True)
            return jsonify({"status":"ok", "profile_id":profile_id})
        except:
            pass
    
    if email:
        res = users_col.find_one_and_update({"email":email}, {"$set":
                               {f"profile.{step_name}": data, "updated": datetime.utcnow()}},
                               upsert=True, return_document=True)
        return jsonify({"status":"ok", "profile_id": str(res.get("_id"))})
    
    new_id = users_col.insert_one({"profile":
                           {step_name:data},
                           "created":datetime.utcnow()}).inserted_id
    return jsonify({"status":"ok", "profile_id": str(new_id)})


@app.route("/api/profile/extended", methods=["POST"])
def extended_profile():
    """
    Stores an extended profile object for a user.
    Expects JSON with 'profile_id' (Mongo ObjectId as string) and extended fields.
    """
    payload = request.json or {}
    profile_id = payload.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400

    try:
        obj_id = ObjectId(profile_id)
    except Exception:
        return jsonify({"error":"invalid profile_id"}), 400

    extended_data = {
        "family": {
            "marital_status": payload.get("marital_status"),
            "children": payload.get("children", []),
            "children_ages": payload.get("children_ages", []),
            "children_education": payload.get("children_education", []),
            "dependents": payload.get("dependents", 0)
        },
        "education": {
            "highest_qualification": payload.get("highest_qualification"),
            "institution": payload.get("institution"),
            "year_graduated": payload.get("year_graduated"),
            "field_of_study": payload.get("field_of_study")
        },
        "career": {
            "current_job": payload.get("current_job"),
            "years_experience": payload.get("years_experience"),
            "skills": payload.get("skills", []),
            "career_goals": payload.get("career_goals", [])
        },
        "interests": {
            "hobbies": payload.get("hobbies", []),
            "learning_interests": payload.get("learning_interests", []),
            "service_preferences": payload.get("service_preferences", [])
        },
        "consent": {
            "marketing_emails": payload.get("marketing_emails", False),
            "personalized_ads": payload.get("personalized_ads", False),
            "data_analytics": payload.get("data_analytics", False)
        }
    }

    res = users_col.update_one(
        {"_id": obj_id},
        {"$set": {"extended_profile": extended_data, "updated": datetime.utcnow()}}
    )

    if res.matched_count == 0:
        return jsonify({"error":"profile not found"}), 404

    return jsonify({"status":"ok"})

@app.route("/api/ads")
def get_ads():
    """Returns a JSON list of active advertisements/announcements."""
    ads = list(ads_col.find({}, {"_id":0}))
    return jsonify(ads)


@app.route("/api/recommendations/<user_id>")
def get_recommendations(user_id):
    """
    Returns personalized ads and education recommendations for a user.
    """
    try:
        ads = recommendation_engine.get_personalized_ads(user_id)
        # Serialize ads for JSON
        ads_s = [serialize_doc(ad) for ad in ads]
        edu_recommendations = recommendation_engine.generate_education_recommendations(user_id)
        user_segment = recommendation_engine.get_user_segment(user_id)
        return jsonify({
            "ads": ads_s,
            "education_recommendations": edu_recommendations,
            "user_segment": user_segment
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Store API ---
@app.route("/api/store/products")
def get_products():
    category = request.args.get("category")
    subcategory = request.args.get("subcategory")
    tags = request.args.get("tags", "").split(",") if request.args.get("tags") else []
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    sort = request.args.get("sort")

    query = {"in_stock": True}
    if category:
        query["category"] = category
    if subcategory:
        query["subcategory"] = subcategory
    if tags and tags[0]:
        query["tags"] = {"$in": tags}
    if min_price is not None or max_price is not None:
        price_q = {}
        if min_price is not None:
            price_q["$gte"] = min_price
        if max_price is not None:
            price_q["$lte"] = max_price
        query["price"] = price_q

    cursor = products_col.find(query, {"_id":0}).limit(50)
    products = list(cursor)

    # Basic sorting support
    if sort and products:
        if sort == 'price_low':
            products.sort(key=lambda p: p.get('price', 0))
        elif sort == 'price_high':
            products.sort(key=lambda p: p.get('price', 0), reverse=True)
        elif sort == 'rating':
            products.sort(key=lambda p: p.get('rating', 0), reverse=True)
        elif sort == 'newest':
            products.sort(key=lambda p: p.get('created', ''), reverse=True)

    return jsonify(products)


@app.route("/api/store/categories")
def get_store_categories():
    categories = products_col.distinct("category")
    subcategories = {}
    for cat in categories:
        subcategories[cat] = products_col.distinct("subcategory", {"category": cat})
    return jsonify({"categories": categories, "subcategories": subcategories})


@app.route("/api/store/order", methods=["POST"])
@user_or_admin_required
def create_order():
    payload = request.json or {}
    # Basic validation
    items = payload.get("items", [])
    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"error":"items required"}), 400

    total_amount = payload.get("total_amount", 0)
    order = {
        "order_id": f"ORD{now_utc().strftime('%Y%m%d%H%M%S')}",
        "user_id": payload.get("user_id"),
        "items": items,
        "total_amount": total_amount,
        "status": "pending",
        "shipping_address": payload.get("shipping_address", {}),
        "payment_method": payload.get("payment_method"),
        "created": now_utc(),
        "updated": now_utc()
    }
    orders_col.insert_one(order)
    return jsonify({"status":"ok", "order_id": order["order_id"]})


@app.route("/api/store/payment", methods=["POST"])
@user_or_admin_required
def process_payment():
    payload = request.json or {}
    payment = {
        "payment_id": f"PAY{now_utc().strftime('%Y%m%d%H%M%S')}",
        "order_id": payload.get("order_id"),
        "user_id": payload.get("user_id"),
        "amount": payload.get("amount", 0),
        "currency": payload.get("currency", "LKR"),
        "method": payload.get("method"),
        # start as 'pending' - integrations should verify with gateway webhook
        "status": "pending",
        "transaction_id": payload.get("transaction_id"),
        "created": now_utc()
    }

    # Insert payment record
    payments_col.insert_one(payment)

    # If caller included 'verified': True, mark order as paid (useful for dev/testing only)
    if payload.get("verified"):
        orders_col.update_one({"order_id": payload.get("order_id")}, {"$set": {"status": "paid", "updated": datetime.utcnow()}})
        payments_col.update_one({"payment_id": payment["payment_id"]}, {"$set": {"status": "completed"}})

    # Log engagement for recommendation system
    try:
        eng_col.insert_one({
            "user_id": payload.get("user_id"),
            "type": "purchase",
            "product_ids": [item.get("id") or item.get("product_id") for item in payload.get("items", [])],
            "amount": payload.get("amount", 0),
            "timestamp": now_utc()
        })
    except Exception:
        pass

    return jsonify({"status":"ok", "payment_id": payment["payment_id"]})

@app.route("/api/store/create_checkout_session", methods=["POST"])
@user_or_admin_required
def create_checkout_session():
    """Create a Stripe Checkout Session for a given Stripe Price ID.
    Expects JSON: {"price_id": "price_xxx", "quantity": 1, "success_url": "...", "cancel_url": "..."}
    STRIPE_SECRET_KEY must be set in environment. Returns JSON {url: <checkout_url>} on success.
    """
    payload = request.json or {}
    price_id = payload.get("price_id")
    try:
        quantity = int(payload.get("quantity", 1))
    except Exception:
        quantity = 1

    success_url = payload.get("success_url") or (request.host_url.rstrip('/') + '/store?checkout=success')
    cancel_url = payload.get("cancel_url") or (request.host_url.rstrip('/') + '/store?checkout=cancel')

    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        return jsonify({"error":"stripe_not_configured", "message":"Set STRIPE_SECRET_KEY in environment"}), 500

    # Support either a single price_id (legacy) or an array of line_items for cart checkout
    line_items = payload.get('line_items')
    try:
        import stripe
        stripe.api_key = stripe_secret

        if line_items and isinstance(line_items, list):
            # Expect items like [{'price': 'price_xxx', 'quantity': 1}, ...]
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='payment',
                line_items=line_items,
                success_url=success_url,
                cancel_url=cancel_url,
            )
        else:
            if not price_id:
                return jsonify({"error":"price_id required"}), 400
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='payment',
                line_items=[{'price': price_id, 'quantity': quantity}],
                success_url=success_url,
                cancel_url=cancel_url,
            )

        # Newer stripe library exposes session.url
        url = getattr(session, 'url', None) or (session.get('url') if isinstance(session, dict) else None)
        if not url:
            try:
                url = session['url']
            except Exception:
                url = None

        return jsonify({"status":"ok", "url": url, "session_id": getattr(session, 'id', None)})
    except Exception as e:
        err = str(e)
        logging.exception("Stripe checkout session error: %s", err)
        return jsonify({"error":"stripe_error", "detail": err}), 500

# --- Consent & Data Export/Delete ---
@app.route("/api/consent/update", methods=["POST"])
@user_or_admin_required
def update_consent():
    payload = request.json or {}
    user_id = payload.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    try:
        obj = ObjectId(user_id)
    except Exception:
        return jsonify({"error":"invalid user_id"}), 400

    consent_updates = {
        "extended_profile.consent.marketing_emails": payload.get("marketing_emails", False),
        "extended_profile.consent.personalized_ads": payload.get("personalized_ads", False),
        "extended_profile.consent.data_analytics": payload.get("data_analytics", False),
        "extended_profile.consent.updated": now_utc()
    }
    users_col.update_one({"_id": obj}, {"$set": consent_updates})
    # Record audit log entry
    try:
        audit_logs_col.insert_one({
            "action": "update_consent",
            "performed_by": session.get("admin_user") or session.get("user_id"),
            "target_user_id": user_id,
            "details": {k: bool(v) for k, v in {"marketing_emails": payload.get("marketing_emails", False), "personalized_ads": payload.get("personalized_ads", False), "data_analytics": payload.get("data_analytics", False)}.items()},
            "ip": request.remote_addr,
            "timestamp": now_utc()
        })
    except Exception:
        pass
    return jsonify({"status":"ok", "message": "Consent preferences updated"})


@app.route("/api/data/export/<user_id>")
@user_or_admin_required
def export_user_data(user_id):
    """GDPR-style export for a user. Returns profile and extended_profile only."""
    try:
        obj = ObjectId(user_id)
    except Exception:
        return jsonify({"error":"invalid user_id"}), 400
    user = users_col.find_one({"_id": obj})
    if not user:
        return jsonify({"error":"User not found"}), 404

    export_data = {
        "profile": user.get("profile", {}),
        "extended_profile": user.get("extended_profile", {}),
        "consent_preferences": user.get("extended_profile", {}).get("consent", {})
    }
    # Audit: record export event
    try:
        audit_logs_col.insert_one({
            "action": "export_user_data",
            "performed_by": session.get("admin_user") or session.get("user_id"),
            "target_user_id": user_id,
            "details": {"exported_fields": ["profile","extended_profile","consent_preferences"]},
            "ip": request.remote_addr,
            "timestamp": now_utc()
        })
    except Exception:
        pass
    return jsonify(export_data)


@app.route("/api/data/delete/<user_id>", methods=["DELETE"])
@user_or_admin_required
def delete_user_data(user_id):
    # Require a confirmation token created via /api/data/delete_request/<user_id>
    payload = request.json or {}
    token = payload.get("confirmation_token") or request.args.get("token")
    if not token:
        return jsonify({"error": "confirmation_token required"}), 400

    # Validate token
    rec = deletion_confirmations_col.find_one({"user_id": user_id, "token": token})
    if not rec:
        return jsonify({"error": "invalid_or_missing_token"}), 400
    # Check expiry if present
    try:
        expires = rec.get("expires")
        if expires and isinstance(expires, datetime) and expires < now_utc():
            return jsonify({"error": "token_expired"}), 400
    except Exception:
        pass

    try:
        obj = ObjectId(user_id)
    except Exception:
        return jsonify({"error":"invalid user_id"}), 400

    result = users_col.delete_one({"_id": obj})
    # Anonymize related engagements
    eng_col.update_many({"user_id": user_id}, {"$set": {"user_id": None, "anonymized": True}})

    # Remove used token
    try:
        deletion_confirmations_col.delete_one({"_id": rec.get("_id")})
    except Exception:
        pass

    # Record audit log for deletion (who performed it, target id, rows affected)
    try:
        audit_logs_col.insert_one({
            "action": "delete_user_data",
            "performed_by": session.get("admin_user") or session.get("user_id"),
            "target_user_id": user_id,
            "details": {"deleted_count": int(result.deleted_count)},
            "ip": request.remote_addr,
            "timestamp": now_utc()
        })
    except Exception:
        pass

    if result.deleted_count > 0:
        return jsonify({"status":"ok", "message":"User data deleted"})
    else:
        return jsonify({"error":"User not found"}), 404


@app.route("/api/data/delete_request/<user_id>", methods=["POST"])
@user_or_admin_required
@limiter.limit("3 per minute")
def create_delete_request(user_id):
    """Creates a short-lived confirmation token for deleting a user's data.
    Returns the token and expiry. Tokens are stored in `deletion_confirmations`.
    """
    try:
        # verify user_id looks like an ObjectId-ish string; we will also attempt to lookup the user
        obj = ObjectId(user_id)
    except Exception:
        return jsonify({"error":"invalid user_id"}), 400

    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=int(os.getenv("DELETE_TOKEN_MINUTES", "15")))

    rec = {
        "user_id": user_id,
        "token": token,
        "created": now,
        "expires": expires,
        "requested_by": session.get("admin_user") or session.get("user_id")
    }
    try:
        deletion_confirmations_col.insert_one(rec)
    except Exception:
        return jsonify({"error":"could_not_create_token"}), 500

    # Try to find user email and send token via SMTP if configured
    email_sent = False
    user_email = None
    try:
        u = users_col.find_one({"_id": obj}, {"email": 1})
        if u:
            user_email = u.get("email")
    except Exception:
        user_email = None

    if user_email:
        subject = "Citizen Portal: Data Deletion Confirmation"
        body = (
            f"A data deletion request was received for your account.\n\n"
            f"To confirm deletion of your data, use the following confirmation token:\n\n{token}\n\n"
            f"This token expires at {expires.isoformat()}. If you did not request this, please ignore."
        )
        html_body = (
            f"<p>A data deletion request was received for your account.</p>"
            f"<p>To confirm deletion of your data, use the following confirmation token:</p>"
            f"<pre style=\"font-size:16px;padding:8px;background:#f6f6f6;border-radius:4px\">{token}</pre>"
            f"<p>This token expires at {expires.isoformat()} UTC.</p>"
        )
        try:
            email_sent = send_email_smtp(user_email, subject, body, html_body=html_body)
        except Exception:
            email_sent = False

    # Record audit log for token creation (and whether we attempted to email it)
    try:
        audit_logs_col.insert_one({
            "action": "create_delete_request",
            "performed_by": session.get("admin_user") or session.get("user_id"),
            "target_user_id": user_id,
            "details": {"email_target": user_email, "email_sent": bool(email_sent)},
            "ip": request.remote_addr,
            "timestamp": datetime.now(timezone.utc)
        })
    except Exception:
        pass

    # If we successfully emailed the token, do not return the raw token in JSON for safety.
    if email_sent:
        return jsonify({"status": "ok", "email_sent": True, "expires": expires.isoformat()})

    # Fallback: return token in response (development mode)
    return jsonify({"status":"ok", "confirmation_token": token, "expires": expires.isoformat(), "email_sent": False})


# --- Simple user login/logout for session management (development-friendly) ---
@app.route('/api/user/login', methods=['POST'])
@limiter.limit("8 per minute")
def user_login():
    """Lightweight login to establish session['user_id'].
    Accepts JSON {"profile_id": "<ObjectId>"} or {"email": "..."}.
    This is a simple helper for development/testing to allow calling protected endpoints.
    In production, replace with a secure auth flow.
    """
    payload = request.json or {}
    profile_id = payload.get('profile_id')
    email = payload.get('email')
    password = payload.get('password')
    user = None
    # Password-based login: prefer email+password when provided
    if email and password:
        user = users_col.find_one({'email': email})
        if not user:
            return jsonify({'error':'user not found'}), 404
        stored = user.get('password')
        if not stored:
            return jsonify({'error':'password_not_set_for_user'}), 400
        try:
            ok = bcrypt.checkpw(password.encode('utf-8'), stored)
        except Exception:
            # stored may be string - ensure bytes
            stored_decoded = stored.encode('utf-8') if isinstance(stored, str) else stored
            ok = bcrypt.checkpw(password.encode('utf-8'), stored_decoded)
        if not ok:
            return jsonify({'error':'invalid_credentials'}), 401
    else:
        # Legacy/dev paths: profile_id or email without password
        if profile_id:
            try:
                obj = ObjectId(profile_id)
                user = users_col.find_one({'_id': obj})
            except Exception:
                return jsonify({'error': 'invalid profile_id'}), 400
        elif email:
            user = users_col.find_one({'email': email})
        else:
            return jsonify({'error':'profile_id or email required'}), 400

        if not user:
            return jsonify({'error':'user not found'}), 404

    session['user_id'] = str(user.get('_id'))
    return jsonify({'status':'ok', 'user_id': session['user_id']})


@app.route('/api/user/logout', methods=['POST'])
def user_logout():
    session.pop('user_id', None)
    return jsonify({'status':'ok'})


@app.route('/register')
def register_page():
    """Render a simple user registration page."""
    try:
        return render_template('register.html')
    except Exception:
        return "Register page not available", 500


@app.route('/login')
def login_page():
    """Render a simple user login page."""
    try:
        return render_template('login.html')
    except Exception:
        return "Login page not available", 500


@app.route('/api/user/register', methods=['POST'])
def api_user_register():
    """Creates a new user with email+password (hashed). Returns user_id and whether verification email was sent."""
    payload = request.json or {}
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password')
    name = payload.get('name')

    if not email or not password:
        return jsonify({'error': 'email_and_password_required'}), 400

    if users_col.find_one({'email': email}):
        return jsonify({'error': 'user_exists'}), 400

    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    except Exception as e:
        return jsonify({'error': 'password_hash_failed', 'detail': str(e)}), 500

    user_doc = {
        'email': email,
        'password': hashed,
        'profile': {'name': name or ''},
        'created': datetime.utcnow()
    }
    res = users_col.insert_one(user_doc)

    # Optionally send verification email (if SMTP configured)
    ver_sent = False
    try:
        token = secrets.token_urlsafe(16)
        db['email_verifications'].insert_one({
            'user_id': str(res.inserted_id), 'token': token,
            'created': datetime.utcnow(), 'expires': datetime.utcnow() + timedelta(hours=24)
        })
        subject = 'Please verify your Citizen Portal account'
        body = f"Verify your account using this token: {token}\n"
        html = f"<p>Verify your account using this token:</p><pre>{token}</pre>"
        ver_sent = send_email_smtp(email, subject, body, html_body=html)
    except Exception:
        ver_sent = False

    return jsonify({'status': 'ok', 'user_id': str(res.inserted_id), 'email_verification_sent': bool(ver_sent)})


@app.route('/verify')
def verify_page():
    token = request.args.get('token')
    result = None
    if token:
        # attempt server-side consume of token
        v = db['email_verifications'].find_one({'token': token})
        if not v:
            result = {'status': 'error', 'message': 'invalid token'}
            return render_template('verify.html', token=token, result=result)

        expires_raw = v.get('expires')
        try:
            expires = datetime.fromisoformat(expires_raw) if isinstance(expires_raw, str) else expires_raw
        except Exception:
            expires = expires_raw
        if isinstance(expires, datetime) and expires < datetime.now(timezone.utc):
            db['email_verifications'].delete_one({'_id': v.get('_id')})
            result = {'status': 'error', 'message': 'token expired'}
            return render_template('verify.html', token=token, result=result)

        user_id = v.get('user_id')
        try:
            db['users'].update_one({'_id': ObjectId(user_id)}, {'$set': {'email_verified': True}})
        except Exception:
            db['users'].update_one({'_id': user_id}, {'$set': {'email_verified': True}})

        db['email_verifications'].delete_one({'_id': v.get('_id')})
        try:
            db['audit_logs'].insert_one({
                'action': 'email_verified',
                'user_id': user_id,
                'token': token,
                'timestamp': datetime.now(timezone.utc),
            })
        except Exception:
            pass
        result = {'status': 'ok', 'message': 'email verified'}

    return render_template('verify.html', token=token, result=result)


@app.route('/api/user/verify', methods=['POST'])
@limiter.limit("6 per minute")
def api_user_verify():
    data = request.get_json(force=True)
    token = data.get('token')
    if not token:
        return jsonify({'status':'error', 'message': 'token required'}), 400

    v = db['email_verifications'].find_one({'token': token})
    if not v:
        return jsonify({'status':'error', 'message': 'invalid token'}), 400

    # check expiry
    expires_raw = v.get('expires')
    try:
        expires = datetime.fromisoformat(expires_raw) if isinstance(expires_raw, str) else expires_raw
    except Exception:
        expires = expires_raw
    if isinstance(expires, datetime) and expires < datetime.now(timezone.utc):
        db['email_verifications'].delete_one({'_id': v.get('_id')})
        return jsonify({'status':'error', 'message': 'token expired'}), 400

    user_id = v.get('user_id')
    try:
        db['users'].update_one({'_id': ObjectId(user_id)}, {'$set': {'email_verified': True}})
    except Exception:
        # fallback if user_id isn't a valid ObjectId
        db['users'].update_one({'_id': user_id}, {'$set': {'email_verified': True}})

    db['email_verifications'].delete_one({'_id': v.get('_id')})
    try:
        db['audit_logs'].insert_one({
            'action': 'email_verified',
            'user_id': user_id,
            'token': token,
            'timestamp': datetime.now(timezone.utc),
        })
    except Exception:
        pass
    return jsonify({'status': 'ok'})


@app.route("/api/dashboard/analytics")
@admin_required
def get_dashboard_analytics():
    try:
        # User analytics
        total_users = users_col.count_documents({})
        active_users = users_col.count_documents({"last_active": {"$gte": datetime.utcnow() - timedelta(days=30)}})
        # Engagement analytics
        total_engagements = eng_col.count_documents({})
        recent_engagements = eng_col.count_documents({"timestamp": {"$gte": datetime.utcnow() - timedelta(days=7)}})
        # Store analytics
        total_orders = orders_col.count_documents({})
        total_revenue_cursor = payments_col.aggregate([
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ])
        revenue_result = list(total_revenue_cursor)
        total_revenue_amount = revenue_result[0]["total"] if revenue_result else 0

        # User segmentation (may be expensive for large user bases)
        user_segments = {}
        for user in users_col.find({}, {"_id":1}):
            try:
                segments = recommendation_engine.get_user_segment(str(user["_id"]))
                for seg in segments:
                    user_segments[seg] = user_segments.get(seg, 0) + 1
            except Exception:
                continue

        popular_products = list(products_col.find({}, {"_id":0}).sort([("rating", -1)]).limit(5))
        recent_activities = list(eng_col.find().sort("timestamp", -1).limit(10))

        return jsonify({
            "user_metrics": {
                "total_users": total_users,
                "active_users": active_users,
                "new_users_7d": users_col.count_documents({"created": {"$gte": datetime.utcnow() - timedelta(days=7)}})
            },
            "engagement_metrics": {
                "total_engagements": total_engagements,
                "recent_engagements": recent_engagements,
                "avg_session_duration": "5m 23s"
            },
            "store_metrics": {
                "total_orders": total_orders,
                "total_revenue": total_revenue_amount,
                "conversion_rate": "3.2%"
            },
            "user_segments": user_segments,
            "popular_products": popular_products,
            "recent_activities": [serialize_doc(a) for a in recent_activities]
        })
    except Exception as ex:
        err_id = uuid.uuid4().hex
        logging.exception("Error in get_dashboard_analytics (id=%s): %s", err_id, ex)
        return jsonify({"error": "internal_server_error", "error_id": err_id}), 500


# --- AI / vector index endpoints ---
def build_vector_index():
    """
    Build or rebuild a FAISS index from service content in services_col.
    Flattens service/subservice/question data into searchable documents.
    Saves index file + metadata JSON.
    This should be run via /api/admin/build_index by an admin after seeding/updating services.
    """
    global FAISS_AVAILABLE # Corrected: Declare global here at the start
    
    os.makedirs("data", exist_ok=True)

    docs = []
    
    for super_category_doc in services_col.find():
        super_category_id = super_category_doc.get("id")
        super_category_name = getLocalizedName(super_category_doc.get("name"), "en")

        for ministry in super_category_doc.get("ministries", []):
            ministry_id = ministry.get("id")
            ministry_name = getLocalizedName(ministry.get("name"), "en")

            for sub in ministry.get("subservices", []):
                sub_id = sub.get("id")
                sub_name = getLocalizedName(sub.get("name"), "en")

                for q in sub.get("questions", []):
                    q_text = getLocalizedName(q.get("q"), "en")
                    a_text = getLocalizedName(q.get("answer"), "en")
                    
                    content = " | ".join(filter(None, [super_category_name, ministry_name, sub_name, q_text, a_text]))
                    
                    docs.append({
                        "doc_id": f"{super_category_id}::{ministry_id}::{sub_id}::{q_text[:80]}",
                        "super_category_id": super_category_id,
                        "ministry_id": ministry_id,
                        "subservice_id": sub_id,
                        "title": q_text,
                        "content": content,
                        "metadata": {
                            "downloads": q.get("downloads", []),
                            "location": q.get("location"),
                            "instructions": q.get("instructions")
                        }
                    })

    if not docs:
        print("No documents found to build index.")
        return {"count":0}

    # Lazy import numpy and handle missing dependency gracefully
    try:
        import numpy as np
    except Exception as e:
        print(f"NumPy not available: {e}. Cannot build vector index.")
        return {"count": 0, "error": "numpy_not_installed"}

    try:
        model = get_embedding_model()
    except RuntimeError as e:
        print(f"Embedding model unavailable: {e}")
        return {"count": 0, "error": "sentence_transformers_not_installed"}

    texts = [d["content"] for d in docs]
    print(f"Encoding {len(texts)} documents...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms==0] = 1.0
    embeddings = embeddings / norms

    if FAISS_AVAILABLE:
        try:
            dim = embeddings.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(embeddings.astype(np.float32))
            faiss.write_index(index, str(INDEX_PATH))
            print(f"FAISS index built and saved to {INDEX_PATH}")
            # Persist FAISS index into MongoDB GridFS for portability
            try:
                fs = GridFS(db)
                with open(INDEX_PATH, 'rb') as f:
                    idx_bytes = f.read()
                # remove any previous 'faiss.index' files (optional)
                try:
                    for old in db.fs.files.find({"filename": {"$regex": "^faiss-"}}):
                        db.fs.delete(old['_id'])
                except Exception:
                    pass
                grid_id = fs.put(idx_bytes, filename=f"faiss-{now_utc().isoformat()}.index")
                # store metadata pointer
                try:
                    db['vector_meta'].replace_one({"name": "current"}, {"name": "current", "meta_count": len(docs), "gridfs_id": grid_id, "updated": now_utc()}, upsert=True)
                except Exception:
                    pass
            except Exception as e:
                print(f"Warning: could not persist FAISS index to GridFS: {e}")
        except Exception as e:
            print(f"Error during FAISS index creation: {e}. Falling back to NumPy for future searches.")
            FAISS_AVAILABLE = False
    else:
        # Save embeddings to disk as fallback
        np.save("data/embeddings.npy", embeddings)
        print(f"Embeddings saved to data/embeddings.npy (FAISS not available).")
        # Also persist embeddings and metadata in MongoDB (GridFS for embeddings blob + collection for meta)
        try:
            fs = GridFS(db)
            bio = BytesIO()
            # Save numpy array to bytes via np.save
            np.save(bio, embeddings)
            bio.seek(0)
            emb_grid_id = fs.put(bio.read(), filename=f"embeddings-{now_utc().isoformat()}.npy")
            # Persist metadata document list
            try:
                db['vector_meta'].replace_one({"name": "current"}, {"name": "current", "meta_count": len(docs), "embeddings_gridfs_id": emb_grid_id, "updated": now_utc(), "docs": docs}, upsert=True)
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: could not persist embeddings to GridFS: {e}")

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f"Metadata saved to {META_PATH}")

    # Ensure metadata is stored in MongoDB for quick retrieval
    try:
        db['vector_meta'].replace_one({"name": "current"}, {"name": "current", "meta_count": len(docs), "updated": now_utc(), "docs": docs}, upsert=True)
    except Exception as e:
        print(f"Warning: could not persist metadata to MongoDB: {e}")

    return {"count": len(docs), "faiss_available": FAISS_AVAILABLE}


# --- Background job management for long-running tasks (index build) ---
INDEX_JOB_STATUS = {}

def _run_build_index_background(job_id):
    """Run build_vector_index in a background thread and update job status."""
    try:
        # update in-memory and DB status
        INDEX_JOB_STATUS[job_id] = {"status": "running", "started_at": now_utc().isoformat()}
        try:
            index_jobs_col.update_one({"job_id": job_id}, {"$set": {"status": "running", "started_at": now_utc(), "updated_at": now_utc()}}, upsert=True)
            # append a lifecycle log entry
            try:
                index_jobs_col.update_one({"job_id": job_id}, {"$push": {"logs": {"ts": now_utc(), "msg": "job started"}}})
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: could not persist job running status to DB: {e}")

        res = build_vector_index()

        INDEX_JOB_STATUS[job_id] = {"status": "completed", "finished_at": now_utc().isoformat(), "result": res}
        try:
            index_jobs_col.update_one({"job_id": job_id}, {"$set": {"status": "completed", "finished_at": now_utc(), "result": res, "updated_at": now_utc()}}, upsert=True)
            try:
                index_jobs_col.update_one({"job_id": job_id}, {"$push": {"logs": {"ts": now_utc(), "msg": f"job completed: {res.get('count', 0)} docs"}}})
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: could not persist job completion to DB: {e}")

    except Exception as e:
        INDEX_JOB_STATUS[job_id] = {"status": "error", "error": str(e)}
        try:
            index_jobs_col.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e), "updated_at": now_utc()}}, upsert=True)
            try:
                index_jobs_col.update_one({"job_id": job_id}, {"$push": {"logs": {"ts": now_utc(), "msg": f"job error: {str(e)[:200]}"}}})
            except Exception:
                pass
        except Exception as e2:
            print(f"Warning: could not persist job error to DB: {e2}")


def _run_fake_job_background(job_id):
    """Simulate a short-running job for tests; persists to DB and updates in-memory status."""
    try:
        INDEX_JOB_STATUS[job_id] = {"status": "running", "started_at": now_utc().isoformat()}
        try:
            index_jobs_col.update_one({"job_id": job_id}, {"$set": {"status": "running", "started_at": now_utc(), "updated_at": now_utc()}}, upsert=True)
            try:
                index_jobs_col.update_one({"job_id": job_id}, {"$push": {"logs": {"ts": now_utc(), "msg": "fake job started"}}})
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: could not persist fake job running status to DB: {e}")

        # simulate work
        import time
        time.sleep(1)

        result = {"count": 0, "faiss_available": False, "note": "simulated job"}
        INDEX_JOB_STATUS[job_id] = {"status": "completed", "finished_at": now_utc().isoformat(), "result": result}
        try:
            index_jobs_col.update_one({"job_id": job_id}, {"$set": {"status": "completed", "finished_at": now_utc(), "result": result, "updated_at": now_utc()}}, upsert=True)
            try:
                index_jobs_col.update_one({"job_id": job_id}, {"$push": {"logs": {"ts": now_utc(), "msg": "fake job completed"}}})
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: could not persist fake job completion to DB: {e}")
    except Exception as e:
        INDEX_JOB_STATUS[job_id] = {"status": "error", "error": str(e)}
        try:
            index_jobs_col.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e), "updated_at": now_utc()}}, upsert=True)
            try:
                index_jobs_col.update_one({"job_id": job_id}, {"$push": {"logs": {"ts": now_utc(), "msg": f"fake job error: {str(e)[:200]}"}}})
            except Exception:
                pass
        except Exception as e2:
            print(f"Warning: could not persist fake job error to DB: {e2}")


@app.route("/api/admin/build_index_async", methods=["POST"])
@admin_required
def admin_build_index_async():
    """Trigger an asynchronous index build job. Returns a job id to poll status."""
    job_id = uuid.uuid4().hex
    INDEX_JOB_STATUS[job_id] = {"status": "pending", "created_at": now_utc().isoformat()}
    # persist creation record
    try:
        index_jobs_col.update_one({"job_id": job_id}, {"$set": {"job_id": job_id, "status": "pending", "created_at": now_utc(), "updated_at": now_utc()}}, upsert=True)
    except Exception as e:
        print(f"Warning: could not persist job creation to DB: {e}")

    try:
        # initialize logs array for this job (only on insert)
        index_jobs_col.update_one({"job_id": job_id}, {"$setOnInsert": {"logs": []}}, upsert=True)
    except Exception:
        pass

    # support simulated job via query param or body for testing
    simulate = False
    try:
        if request.args.get('simulate', '').lower() in ('1', 'true'):
            simulate = True
        else:
            payload = request.json or {}
            if str(payload.get('simulate', '')).lower() in ('1', 'true'):
                simulate = True
    except Exception:
        simulate = False

    if simulate:
        t = threading.Thread(target=_run_fake_job_background, args=(job_id,))
    else:
        t = threading.Thread(target=_run_build_index_background, args=(job_id,))
    t.daemon = True
    t.start()
    return jsonify({"job_id": job_id, "status": INDEX_JOB_STATUS[job_id]})


@app.route("/api/admin/index_status", methods=["GET"])
@admin_required
def admin_index_status():
    """Return current index / metadata status and any active/finished jobs."""
    faiss_ok = bool(FAISS_AVAILABLE)
    meta_exists = META_PATH.exists()
    index_exists = INDEX_PATH.exists()
    jobs = INDEX_JOB_STATUS.copy()
    # Also include basic stats when metadata exists
    docs_count = 0
    try:
        if meta_exists:
            with open(META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
                docs_count = len(meta)
    except Exception:
        docs_count = 0
    return jsonify({
        "faiss_available": faiss_ok,
        "meta_exists": meta_exists,
        "index_exists": index_exists,
        "documents": docs_count,
        "jobs": jobs
    })


@app.route('/api/admin/index_jobs', methods=['GET'])
@admin_required
def admin_index_jobs():
    """Return recent index jobs from the DB. Query param 'limit' optional."""
    try:
        limit = int(request.args.get('limit', 20))
    except Exception:
        limit = 20
    try:
        cursor = index_jobs_col.find().sort([('created_at', -1)]).limit(limit)
        jobs = []
        for j in cursor:
            j['_id'] = str(j.get('_id'))
            # created_at/started_at/finished_at are datetimes — convert
            for k in ('created_at','started_at','finished_at','updated_at'):
                if k in j and isinstance(j[k], datetime):
                    j[k] = j[k].isoformat()
            jobs.append(j)
        return jsonify({'jobs': jobs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/audit_logs', methods=['GET'])
@admin_required
def admin_get_audit_logs():
    """Return paginated audit logs. Query params: page (1-based), limit, action, target_user_id."""
    try:
        page = max(1, int(request.args.get('page', 1)))
    except Exception:
        page = 1
    try:
        limit = min(200, max(1, int(request.args.get('limit', 50))))
    except Exception:
        limit = 50

    action = request.args.get('action')
    target_user_id = request.args.get('target_user_id')

    query = {}
    if action:
        query['action'] = action
    if target_user_id:
        query['target_user_id'] = target_user_id

    try:
        skip = (page - 1) * limit
        cursor = audit_logs_col.find(query).sort('timestamp', -1).skip(skip).limit(limit)
        entries = []
        for e in cursor:
            # serialize basic fields
            serialized = serialize_doc(e)
            entries.append(serialized)

        total = audit_logs_col.count_documents(query)
        return jsonify({'page': page, 'limit': limit, 'total': total, 'entries': entries})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/index_job/<job_id>', methods=['GET'])
@admin_required
def admin_index_job_detail(job_id):
    """Return a single index job document (detailed) from MongoDB."""
    try:
        j = index_jobs_col.find_one({"job_id": job_id})
        if not j:
            return jsonify({'error': 'not found'}), 404
        j['_id'] = str(j.get('_id'))
        for k in ('created_at','started_at','finished_at','updated_at'):
            if k in j and isinstance(j[k], datetime):
                j[k] = j[k].isoformat()
        return jsonify({'job': j})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper function to get localized name from nested dict or plain string
def getLocalizedName(item_name_field, default_lang="en"):
    if isinstance(item_name_field, dict):
        return item_name_field.get(default_lang) or item_name_field.get("en")
    return item_name_field


# Rate limiting is handled by Flask-Limiter (initialized near app creation).
# The old in-memory `rate_limit` decorator was removed in favor of Flask-Limiter.


# --- Serialization helper ---
def serialize_doc(doc):
    """Return a JSON-safe copy of a MongoDB document (ObjectId/datetime -> str)."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    out = {}
    # keys that should never be exposed via API (redact)
    sensitive_keys = {"password", "passwd", "pwd", "secret", "token", "api_key", "apikey", "password_hash"}
    for k, v in doc.items():
        kl = k.lower() if isinstance(k, str) else k
        # redact known sensitive keys
        if isinstance(kl, str) and kl in sensitive_keys:
            out[k] = "<redacted>"
            continue

        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = serialize_doc(v)
        elif isinstance(v, list):
            out_list = []
            for i in v:
                if isinstance(i, (dict, list)):
                    out_list.append(serialize_doc(i))
                elif isinstance(i, ObjectId):
                    out_list.append(str(i))
                else:
                    out_list.append(i)
            out[k] = out_list
        elif isinstance(v, (bytes, bytearray)):
            # Avoid exposing byte blobs (e.g., hashed passwords). Try to decode, otherwise base64-encode.
            try:
                out[k] = v.decode("utf-8")
            except Exception:
                import base64
                out[k] = base64.b64encode(bytes(v)).decode("ascii")
        else:
            out[k] = v
    return out


# --- Email helper ---
def send_email_smtp(to_email, subject, body, html_body=None):
    """Send an email using SMTP settings from environment variables.
    Returns True on success, False on failure.
    """
    MAIL_HOST = os.getenv("MAIL_HOST")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM_ADDRESS") or os.getenv("MAIL_FROM")
    MAIL_ENCRYPTION = os.getenv("MAIL_ENCRYPTION", "tls").lower()

    if not (MAIL_HOST and MAIL_USERNAME and MAIL_PASSWORD and MAIL_FROM):
        print("SMTP config incomplete; skipping email send")
        return False

    try:
        msg = EmailMessage()
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        if html_body:
            msg.set_content(body)
            msg.add_alternative(html_body, subtype="html")
        else:
            msg.set_content(body)

        # Connect and send
        if MAIL_ENCRYPTION == "ssl":
            with smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT, timeout=30) as server:
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.send_message(msg)
        else:
            # Use STARTTLS
            with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email to {to_email}: {e}")
        return False


@app.route("/api/admin/build_index", methods=["POST"])
@admin_required
def admin_build_index():
    """Admin endpoint to build/rebuild the vector search index."""
    print("Admin requested to build vector index...")
    res = build_vector_index()
    return jsonify(res)


def search_vectors(query, top_k=5):
    """
    Performs a vector similarity search using the FAISS index or a NumPy fallback.
    Returns the top_k matching documents' metadata.
    """
    global FAISS_AVAILABLE # Corrected: Declare global here at the start

    # Lazy import numpy and embedding model; return empty if unavailable
    try:
        import numpy as np
    except Exception as e:
        print(f"NumPy not available: {e}. Vector search disabled.")
        return []

    # Try to get the embedding model; if not available, we'll fall back to text matching below
    model = None
    try:
        model = get_embedding_model()
    except RuntimeError as e:
        print(f"Embedding model unavailable: {e}. Will use textual fallback for search.")

    if model is not None:
        q_emb = model.encode([query], convert_to_numpy=True)
        q_emb = q_emb / (np.linalg.norm(q_emb, axis=1, keepdims=True) + 1e-10)

    if not META_PATH.exists():
        print(f"Metadata file not found at {META_PATH}")
        return []
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)

    hits = []
    if FAISS_AVAILABLE and INDEX_PATH.exists() and model is not None:
        try:
            index = faiss.read_index(str(INDEX_PATH))
            D, I = index.search(q_emb.astype(np.float32), top_k)
            for idx in I[0]:
                if idx < len(meta):
                    hits.append(meta[idx])
        except Exception as e:
            print(f"Error during FAISS search: {e}. Falling back to NumPy.")
            FAISS_AVAILABLE = False # Modify global variable if FAISS search failed
    
    # If FAISS is not available or model missing, try NumPy fallback if embeddings file exists
    if not FAISS_AVAILABLE and model is not None:
        if not (pathlib.Path("data/embeddings.npy").exists()):
            print("Embeddings file not found for NumPy fallback.")
            return []
        db_emb = np.load("data/embeddings.npy")
        sims = (db_emb @ q_emb[0]).tolist()
        idxs = np.argsort(sims)[::-1][:top_k]
        hits = [meta[int(i)] for i in idxs if int(i) < len(meta)]

    # If we still have no hits and either model is missing or embeddings missing, fallback to naive text search
    if not hits:
        q_low = query.lower()
        scored = []
        for i, m in enumerate(meta):
            # combine title+content
            text = " ".join(filter(None, [m.get('title',''), m.get('content','')]))
            if not text:
                continue
            t_low = text.lower()
            score = 0
            if q_low in t_low:
                score += 10
            # bonus for word overlap
            for w in q_low.split():
                if w and w in t_low:
                    score += 1
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = [m for s, m in scored[:top_k]]

    return hits

@app.route("/api/ai/search", methods=["POST"])
def ai_search():
    """
    Accepts a query, performs vector retrieval, and returns relevant sources.
    This endpoint is where an LLM could be integrated to generate a friendly answer.
    """
    payload = request.json or {}
    query = payload.get("query","").strip()
    top_k = int(payload.get("top_k", 5))

    if not query:
        return jsonify({"error":"empty query"}), 400

    # First, attempt a vector search to gather relevant sources (if embeddings exist)
    try:
        hits = search_vectors(query, top_k=top_k)
    except Exception as e:
        hits = []

    # Prepare simple sources for client-side display
    sources = []
    for h in hits:
        sources.append({
            "doc_id": h.get("doc_id") or h.get("title"),
            "title": h.get("title"),
            "content": h.get("content"),
            "metadata": h.get("metadata", {})
        })

    # Keep the existing OpenRouter / LLM call as an optional augmentation if configured.
    answer = None
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    if OPENROUTER_API_KEY:
        try:
            import requests
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://127.0.0.1:5000",
                    "X-Title": "Citizen Portal"
                },
                data=json.dumps({
                    "model": os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-prover-v2"),
                    "messages": [
                        {"role": "user", "content": query}
                    ]
                }),
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            else:
                answer = f"Error: {response.status_code}"
        except Exception as e:
            answer = f"Error: {str(e)}"

    return jsonify({"query": query, "answer": answer or "", "sources": sources, "hits_count": len(sources)})


def load_vector_index_from_db():
    """Load index/embeddings and metadata from MongoDB GridFS into local data files.
    Returns a summary dict describing what was loaded.
    """
    try:
        meta = db['vector_meta'].find_one({"name": "current"})
    except Exception:
        meta = None

    if not meta:
        return {"found": False, "message": "no vector_meta found in DB"}

    fs = GridFS(db)
    loaded = {"found": True, "meta_count": meta.get('meta_count', 0)}

    # Ensure data dir exists
    try:
        os.makedirs("data", exist_ok=True)
    except Exception:
        pass

    # Load FAISS index if present
    if meta.get('gridfs_id'):
        try:
            gfid = meta.get('gridfs_id')
            blob = fs.get(gfid).read()
            with open(INDEX_PATH, 'wb') as f:
                f.write(blob)
            loaded['faiss_index'] = True
        except Exception as e:
            loaded['faiss_index'] = False
            loaded['faiss_error'] = str(e)

    # Load embeddings numpy if present
    if meta.get('embeddings_gridfs_id'):
        try:
            egfid = meta.get('embeddings_gridfs_id')
            blob = fs.get(egfid).read()
            # write to embeddings.npy
            with open("data/embeddings.npy", 'wb') as f:
                f.write(blob)
            loaded['embeddings'] = True
        except Exception as e:
            loaded['embeddings'] = False
            loaded['embeddings_error'] = str(e)

    # Persist metadata JSON locally as well
    try:
        with open(META_PATH, 'w', encoding='utf-8') as f:
            json.dump(meta.get('docs', []), f, ensure_ascii=False, indent=2)
        loaded['meta_saved'] = True
    except Exception as e:
        loaded['meta_saved'] = False
        loaded['meta_error'] = str(e)

    return loaded


@app.route('/api/admin/load_index_from_db', methods=['POST'])
@admin_required
def admin_load_index_from_db():
    """Admin endpoint to load index/embeddings from MongoDB GridFS into local data files."""
    res = load_vector_index_from_db()
    return jsonify(res)


@app.route('/api/admin/vector_meta', methods=['GET'])
@admin_required
def admin_get_vector_meta():
    try:
        m = db['vector_meta'].find_one({"name": "current"})
        if not m:
            return jsonify({'meta': None})
        # serialize datetimes
        if 'updated' in m and isinstance(m['updated'], datetime):
            m['updated'] = m['updated'].isoformat()
        m['_id'] = str(m.get('_id'))
        return jsonify({'meta': m})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- Admin auth with bcrypt ---
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    """
    Handles admin login, now using bcrypt for secure password verification.
    """
    if request.method == "GET":
        # Serve standalone login page (not the full admin dashboard)
        return render_template("admin_login.html")
    
    data = request.form
    username = data.get("username")
    password = data.get("password", "").encode('utf-8')

    # If DB is unreachable, allow a fallback admin login using environment vars
    if not is_db_available():
        fallback_user = os.getenv("ADMIN_USER", "admin")
        fallback_pwd = os.getenv("ADMIN_PWD", "admin123")
        if username == fallback_user and password.decode('utf-8') == fallback_pwd:
            session["admin_logged_in"] = True
            session["admin_user"] = username
            return redirect("/admin")
        return "Login failed", 401

    admin = admins_col.find_one({"username": username})
    if admin:
        stored_password_hash = admin.get("password")
        try:
            ok = bcrypt.checkpw(password, stored_password_hash)
        except Exception:
            print("Warning: Stored admin password is not a bcrypt hash or comparison error. Falling back to plain text (development only).")
            stored_decoded = stored_password_hash.decode('utf-8') if isinstance(stored_password_hash, bytes) else stored_password_hash
            ok = stored_decoded == password.decode('utf-8')

        if ok:
            session["admin_logged_in"] = True
            session["admin_user"] = username
            return redirect("/admin")
    return "Login failed", 401

@app.route("/api/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    """Logs out the admin by clearing the Flask session."""
    session.clear()
    return jsonify({"status":"logged out"})


# --- Admin CRUD: services, categories, officers, ads ---
@app.route("/api/admin/services", methods=["GET","POST"])
@admin_required
def admin_services():
    """
    Handles CRUD for Super Category documents in services_col.
    GET: Returns all Super Category documents.
    POST: Creates/updates a Super Category document.
    """
    if request.method == "GET":
        return jsonify(list(services_col.find({}, {"_id":0})))
    
    payload = request.json
    sid = payload.get("id")
    if not sid:
        return jsonify({"error":"id required"}), 400
    services_col.update_one({"id": sid}, {"$set": payload}, upsert=True)
    return jsonify({"status":"ok"})

@app.route("/api/admin/services/<service_id>", methods=["DELETE"])
@admin_required
def delete_service(service_id):
    """Deletes a specific Super Category document by its ID."""
    services_col.delete_one({"id": service_id})
    return jsonify({"status":"deleted"})


@app.route("/api/admin/categories", methods=["GET","POST","DELETE"])
@admin_required
def manage_categories():
    """Admin CRUD for category group documents in categories_col."""
    if request.method == "GET":
        return jsonify(list(categories_col.find({}, {"_id":0})))
    if request.method == "POST":
        payload = request.json
        cid = payload.get("id")
        if not cid: return jsonify({"error":"id required"}), 400
        categories_col.update_one({"id":cid}, {"$set":payload}, upsert=True)
        return jsonify({"status":"ok"})
    if request.method == "DELETE":
        cid = request.args.get("id")
        if not cid: return jsonify({"error":"id required"}), 400
        categories_col.delete_one({"id":cid})
        return jsonify({"status":"deleted"})
    return abort(405)


@app.route("/api/admin/officers", methods=["GET","POST","DELETE"])
@admin_required
def manage_officers():
    """Admin CRUD for officer metadata in officers_col."""
    if request.method == "GET":
        return jsonify(list(officers_col.find({}, {"_id":0})))
    if request.method == "POST":
        payload = request.json
        oid = payload.get("id")
        if not oid: return jsonify({"error":"id required"}), 400
        officers_col.update_one({"id":oid}, {"$set":payload}, upsert=True)
        return jsonify({"status":"ok"})
    if request.method == "DELETE":
        oid = request.args.get("id")
        if not oid: return jsonify({"error":"id required"}), 400
        officers_col.delete_one({"id":oid})
        return jsonify({"status":"deleted"})
    return abort(405)


@app.route("/api/admin/ads", methods=["GET","POST","DELETE"])
@admin_required
def manage_ads():
    """Admin CRUD for ads/announcements in ads_col."""
    if request.method == "GET":
        return jsonify(list(ads_col.find({}, {"_id":0})))
    if request.method == "POST":
        payload = request.json or {}
        aid = payload.get("id")
        title = payload.get("title")
        if not aid:
            return jsonify({"error":"id required"}), 400
        if not title:
            return jsonify({"error":"title required"}), 400
        ads_col.update_one({"id":aid}, {"$set":payload}, upsert=True)
        return jsonify({"status":"ok"})
    if request.method == "DELETE":
        aid = request.args.get("id")
        if not aid: return jsonify({"error":"id required"}), 400
        ads_col.delete_one({"id":aid})
        return jsonify({"status":"deleted"})
    return abort(405)


# --- Admin insights (kept but extended) ---
@app.route("/api/admin/insights")
@admin_required
def admin_insights():
    """
    Provides aggregated insights for the admin dashboard,
    now also including top ads (clicks, if ad logging is implemented).
    """
    try:
        age_groups = {"<18":0,"18-25":0,"26-40":0,"41-60":0,"60+":0}
        for e in eng_col.find({}, {"age":1}):
            age = e.get("age")
            if not age:
                continue
            try:
                age = int(age)
                if age < 18: age_groups["<18"] += 1
                elif age <= 25: age_groups["18-25"] += 1
                elif age <= 40: age_groups["26-40"] += 1
                elif age <= 60: age_groups["41-60"] += 1
                else: age_groups["60+"] += 1
            except:
                continue

        jobs = {}
        services_engaged = {}
        questions = {}
        desires = {}
        ads_clicked = {}

        for e in eng_col.find({}, {"job":1,"service":1,"question_clicked":1,"desires":1,"ad":1}):
            j = (e.get("job") or "Unknown").strip()
            jobs[j] = jobs.get(j,0) + 1
            
            s = e.get("service") or "Unknown"
            services_engaged[s] = services_engaged.get(s,0) + 1
            
            q = e.get("question_clicked") or "Unknown"
            questions[q] = questions.get(q,0) + 1
            
            for d in e.get("desires") or []:
                desires[d] = desires.get(d,0) + 1

            ad_id = e.get("ad")
            if ad_id:
                ads_clicked[ad_id] = ads_clicked.get(ad_id, 0) + 1

        pipeline = [
            {"$group": {"_id":
                {"user":"$user_id","question":"$question_clicked"}, "count":{"$sum":1}}},
            {"$match": {"count": {"$gte": 2}}}
        ]
        repeated = list(eng_col.aggregate(pipeline))
        premium_suggestions = []
        for r in repeated:
            if r["_id"]["user"]:
                premium_suggestions.append({"user": r["_id"]["user"], "question":
                                            r["_id"]["question"], "count": r["count"]})

        return jsonify({
            "age_groups": age_groups,
            "jobs": jobs,
            "services": services_engaged,
            "questions": questions,
            "desires": desires,
            "premium_suggestions": premium_suggestions,
            "ads_clicked": ads_clicked
        })
    except Exception as ex:
        err_id = uuid.uuid4().hex
        logging.exception("Error in admin_insights (id=%s): %s", err_id, ex)
        return jsonify({"error": "internal_server_error", "error_id": err_id}), 500

@app.route("/api/admin/export_csv")
@admin_required
def export_csv():
    """
    Exports all user engagement data into a CSV file.
    Includes new 'ad' and 'source' fields in the header.
    """
    cursor = eng_col.find()
    si = StringIO()
    cw = csv.writer(si)
    
    cw.writerow(["user_id","age","job","desire","question","service","ad","source","timestamp"])
    
    for e in cursor:
        cw.writerow([
            e.get("user_id"),
            e.get("age"),
            e.get("job"),
            ",".join(e.get("desires") or []),
            e.get("question_clicked"),
            e.get("service"),
            e.get("ad"),
            e.get("source"),
            e.get("timestamp").isoformat() if e.get("timestamp") else ""
        ])
    
    output = BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="engagements.csv"
    )

@app.route("/api/admin/engagements")
@admin_required
def admin_engagements():
    """
    Returns engagements as JSON and supports timeframe filtering via query params.
    Query params:
      - timeframe: today|week|month|year|all (default: all)
      - start: ISO datetime string (optional)
      - end: ISO datetime string (optional)
      - limit: max number of records to return (default: 200)
    """
    try:
        timeframe = (request.args.get('timeframe') or 'all').lower()
        start_s = request.args.get('start')
        end_s = request.args.get('end')
        limit = int(request.args.get('limit') or 200)

        def parse_iso(s):
            if not s:
                return None
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                try:
                    # fallback: try stripping Z
                    if s.endswith('Z'):
                        dt = datetime.fromisoformat(s[:-1])
                    else:
                        return None
                except Exception:
                    return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        now = now_utc()
        start = parse_iso(start_s)
        end = parse_iso(end_s)

        if timeframe == 'today' and not start:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'week' and not start:
            start = now - timedelta(days=7)
        elif timeframe == 'month' and not start:
            start = now - timedelta(days=30)
        elif timeframe == 'year' and not start:
            start = now - timedelta(days=365)

        query = {}
        if start and end:
            query['timestamp'] = {'$gte': start, '$lte': end}
        elif start:
            query['timestamp'] = {'$gte': start}
        elif end:
            query['timestamp'] = {'$lte': end}

        cursor = eng_col.find(query).sort('timestamp', -1).limit(limit)
        out = []
        for e in cursor:
            out.append(serialize_doc(e))
        return jsonify(out)
    except Exception as ex:
        err_id = uuid.uuid4().hex
        logging.exception("Error in admin_engagements (id=%s): %s", err_id, ex)
        return jsonify({'error': 'internal_server_error', 'error_id': err_id}), 500


@app.route("/api/admin/export_profiles")
@admin_required
def export_profiles():
    """
    Exports basic user profile information as CSV for the admin dashboard.
    Columns: profile_id,name,age,email,phone,job,desires,created,updated
    """
    cursor = users_col.find()
    si = StringIO()
    cw = csv.writer(si)

    cw.writerow(["profile_id","name","age","email","phone","job","desires","created","updated"])

    for u in cursor:
        profile_id = str(u.get("_id"))
        profile = u.get("profile") or {}
        name = profile.get("name") or u.get("name") or ""
        age = profile.get("age") or u.get("age") or ""
        email = u.get("email") or ""
        phone = u.get("phone") or ""
        job = (profile.get("job") or u.get("job") or "")
        desires = ",".join(profile.get("desires") or u.get("desires") or [])
        created = u.get("created").isoformat() if u.get("created") else ""
        updated = u.get("updated").isoformat() if u.get("updated") else ""

        cw.writerow([profile_id, name, age, email, phone, job, desires, created, updated])

    output = BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="profiles.csv"
    )


@app.route("/api/admin/profiles")
@admin_required
def admin_profiles():
    """
    Returns user profiles as JSON and supports timeframe filtering by `created` timestamp.
    Query params: timeframe (today|week|month|year|all), start, end, limit
    """
    try:
        timeframe = (request.args.get('timeframe') or 'all').lower()
        start_s = request.args.get('start')
        end_s = request.args.get('end')
        limit = int(request.args.get('limit') or 200)

        def parse_iso(s):
            if not s:
                return None
            try:
                dt = datetime.fromisoformat(s)
            except Exception:
                try:
                    if s.endswith('Z'):
                        dt = datetime.fromisoformat(s[:-1])
                    else:
                        return None
                except Exception:
                    return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        now = now_utc()
        start = parse_iso(start_s)
        end = parse_iso(end_s)

        if timeframe == 'today' and not start:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'week' and not start:
            start = now - timedelta(days=7)
        elif timeframe == 'month' and not start:
            start = now - timedelta(days=30)
        elif timeframe == 'year' and not start:
            start = now - timedelta(days=365)

        query = {}
        if start and end:
            query['created'] = {'$gte': start, '$lte': end}
        elif start:
            query['created'] = {'$gte': start}
        elif end:
            query['created'] = {'$lte': end}

        cursor = users_col.find(query).sort('created', -1).limit(limit)
        out = []
        for u in cursor:
            try:
                # Use the shared serialize_doc helper to produce a JSON-safe representation
                out.append(serialize_doc(u))
            except Exception as doc_ex:
                # If a single document fails to serialize, log and provide a minimal fallback
                err_id = uuid.uuid4().hex
                logging.exception("Failed to serialize user document (id=%s) (error_id=%s): %s", u.get("_id"), err_id, doc_ex)
                try:
                    out.append({"_id": str(u.get("_id")), "error": f"could_not_serialize (error_id={err_id})"})
                except Exception:
                    out.append({"_id": None, "error": f"could_not_serialize (error_id={err_id})"})
        return jsonify(out)
    except Exception as ex:
        err_id = uuid.uuid4().hex
        logging.exception("Error in admin_profiles (id=%s): %s", err_id, ex)
        return jsonify({'error': 'internal_server_error', 'error_id': err_id}), 500


# --- Ensure initial admin user exists (Modified: uses bcrypt for hashing) ---
if __name__ == "__main__":
    admin_username = "admin"
    admin_pwd = os.getenv("ADMIN_PWD", "admin123")
    # Only try to touch the DB if it appears reachable; otherwise skip admin setup
    if is_db_available():
        try:
            existing_admin = admins_col.find_one({"username": admin_username})
            hashed_password = bcrypt.hashpw(admin_pwd.encode("utf-8"), bcrypt.gensalt())

            if existing_admin:
                try:
                    if not bcrypt.checkpw(admin_pwd.encode("utf-8"), existing_admin["password"]):
                        admins_col.update_one({"username": admin_username}, {"$set": {"password": hashed_password}})
                        print(f"Updated existing admin user '{admin_username}' with new hashed password.")
                    else:
                        print(f"Admin user '{admin_username}' already exists with correct hashed password.")
                except Exception:
                    admins_col.update_one({"username": admin_username}, {"$set": {"password": hashed_password}})
                    print(f"Updated existing admin user '{admin_username}' (from potentially plain text) with new hashed password.")
            else:
                admins_col.insert_one({"username": admin_username, "password": hashed_password})
                print(f"Created admin user '{admin_username}' with hashed password.")
        except Exception as e:
            err_id = uuid.uuid4().hex
            logging.exception("Error ensuring initial admin user (id=%s): %s", err_id, e)
            print(f"Warning: could not ensure initial admin user (error_id={err_id}). Continuing without DB admin setup.")
    else:
        print("Warning: MongoDB appears unreachable. Skipping initial admin user setup.")
    
    os.makedirs("data", exist_ok=True)

    # Optional: schedule periodic index rebuilds if APScheduler is available and ENABLE_INDEX_SCHEDULER is true
    ENABLE_SCHED = os.getenv("ENABLE_INDEX_SCHEDULER", "false").lower() in ("1","true","yes")
    if ENABLE_SCHED:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            scheduler = BackgroundScheduler()
            # Default: run daily (every 24 hours). Configure interval hours with INDEX_BUILD_INTERVAL_HOURS env var.
            try:
                hours = float(os.getenv("INDEX_BUILD_INTERVAL_HOURS", "24"))
            except Exception:
                hours = 24.0
            scheduler.add_job(build_vector_index, 'interval', hours=hours, id='daily_build_index', replace_existing=True)
            scheduler.start()
            print(f"Index build scheduler enabled: every {hours} hours")
        except Exception as e:
            print(f"APScheduler not available or failed to start: {e}")

    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT",5000)))