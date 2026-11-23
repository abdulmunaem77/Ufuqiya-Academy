from flask import request
from flask_limiter import Limiter
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


def client_ip():
    # Behind a trusted proxy ProxyFix has already rewritten remote_addr.
    return request.remote_addr or "unknown"


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=client_ip, default_limits=["600 per hour", "60 per minute"])
