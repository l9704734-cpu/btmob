"""
Multi-APK Play Store — Flask application factory.
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()

UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'))
MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))  # 10 MB
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_APK_EXTENSIONS = {'.apk'}


def create_app(config_overrides=None):
    app = Flask(__name__)

    # --- Config -----------------------------------------------------------
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-please-change')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'store.db'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_DIR'] = UPLOAD_DIR
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_COOKIE_SECURE', 'false').lower() == 'true'
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600

    if config_overrides:
        app.config.update(config_overrides)

    # Ensure upload dir exists
    os.makedirs(app.config['UPLOAD_DIR'], exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    from .models import (
        StoreSettings, AdminUser, AppListing, Screenshot, Feature,
        Review, Permission, RelatedApp, ContentSection, MediaAsset, ActivityLog
    )

    with app.app_context():
        db.create_all()
        # Seed default store settings if absent
        if StoreSettings.query.first() is None:
            db.session.add(StoreSettings(
                store_name='Play Store',
                store_tagline='Apps & Games',
                store_description='',
                footer_text='',
                default_primary_color='#0f9d58',
                default_secondary_color='#34a853',
                default_bg_color='#f8fafc',
                default_text_color='#0f172a',
                default_seo_title='Play Store',
                default_seo_description='Discover apps and games.',
                default_download_button_label='Install',
                contact_email='',
                contact_website='',
            ))
            db.session.commit()

    # Register blueprints
    from .views_public import public_bp
    from .views_admin import admin_bp
    from .views_auth import auth_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    @app.template_filter('datetime')
    def _datetime_filter(value, fmt='%Y-%m-%d %H:%M'):
        if value is None:
            return ''
        return value.strftime(fmt)

    @app.template_filter('date')
    def _date_filter(value, fmt='%Y-%m-%d'):
        if value is None:
            return ''
        return value.strftime(fmt)

    return app
