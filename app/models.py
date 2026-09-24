"""
SQLAlchemy models for the multi-APK store.
"""
import os
import uuid
from datetime import datetime, timezone
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from app import db


def _uuid():
    return uuid.uuid4().hex


class StoreSettings(db.Model):
    __tablename__ = 'store_settings'
    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(200), nullable=False, default='Play Store')
    store_tagline = db.Column(db.String(300), default='')
    store_description = db.Column(db.Text, default='')
    store_icon_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    store_icon_url = db.Column(db.String(500), default='')  # optional external URL
    favicon_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    favicon_url = db.Column(db.String(500), default='')
    footer_text = db.Column(db.Text, default='')
    contact_email = db.Column(db.String(200), default='')
    contact_website = db.Column(db.String(500), default='')
    default_primary_color = db.Column(db.String(20), default='#0f9d58')
    default_secondary_color = db.Column(db.String(20), default='#34a853')
    default_bg_color = db.Column(db.String(20), default='#f8fafc')
    default_text_color = db.Column(db.String(20), default='#0f172a')
    default_seo_title = db.Column(db.String(200), default='Play Store')
    default_seo_description = db.Column(db.String(500), default='')
    default_download_button_label = db.Column(db.String(100), default='Install')
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    store_icon = db.relationship('MediaAsset', foreign_keys=[store_icon_asset_id])
    favicon = db.relationship('MediaAsset', foreign_keys=[favicon_asset_id])


class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AppListing(db.Model):
    __tablename__ = 'app_listings'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(32), unique=True, nullable=False, default=_uuid)
    app_name = db.Column(db.String(200), nullable=False)
    short_name = db.Column(db.String(100), default='')
    slug = db.Column(db.String(200), unique=True, nullable=False)
    developer_name = db.Column(db.String(200), default='')
    developer_website = db.Column(db.String(500), default='')
    category = db.Column(db.String(100), default='')
    tagline = db.Column(db.String(300), default='')
    description = db.Column(db.Text, default='')
    package_name = db.Column(db.String(200), default='')
    version = db.Column(db.String(50), default='')
    file_size = db.Column(db.String(50), default='')
    release_date = db.Column(db.Date, nullable=True)
    language = db.Column(db.String(100), default='English')
    age_rating = db.Column(db.String(20), default='Everyone')
    rating_value = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.String(50), default='')
    verified_label = db.Column(db.Boolean, default=False)
    verified_label_text = db.Column(db.String(200), default='Verified')
    status = db.Column(db.String(20), default='draft')  # draft, published, archived
    is_published = db.Column(db.Boolean, default=False)

    # Branding
    icon_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    icon_url = db.Column(db.String(500), default='')
    hero_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    hero_url = db.Column(db.String(500), default='')
    favicon_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    favicon_url = db.Column(db.String(500), default='')

    # Theme
    primary_color = db.Column(db.String(20), default='')
    secondary_color = db.Column(db.String(20), default='')
    bg_color = db.Column(db.String(20), default='')
    text_color = db.Column(db.String(20), default='')

    # Download
    apk_url = db.Column(db.String(500), default='')
    apk_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    download_filename = db.Column(db.String(200), default='')
    download_button_label = db.Column(db.String(100), default='Install')
    download_button_icon_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    download_button_icon_url = db.Column(db.String(500), default='')
    download_button_icon_position = db.Column(db.String(20), default='left')  # left, right, hidden
    use_uploaded_file = db.Column(db.Boolean, default=False)
    apk_checksum = db.Column(db.String(200), default='')

    # SEO
    seo_title = db.Column(db.String(200), default='')
    meta_description = db.Column(db.String(500), default='')
    canonical_url = db.Column(db.String(500), default='')
    social_image_url = db.Column(db.String(500), default='')
    social_image_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    custom_browser_title = db.Column(db.String(200), default='')
    no_index = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    icon = db.relationship('MediaAsset', foreign_keys=[icon_asset_id])
    hero = db.relationship('MediaAsset', foreign_keys=[hero_asset_id])
    favicon = db.relationship('MediaAsset', foreign_keys=[favicon_asset_id])
    apk_file = db.relationship('MediaAsset', foreign_keys=[apk_asset_id])
    download_button_icon = db.relationship('MediaAsset', foreign_keys=[download_button_icon_asset_id])
    social_image = db.relationship('MediaAsset', foreign_keys=[social_image_asset_id])

    screenshots = db.relationship('Screenshot', backref='listing', cascade='all, delete-orphan', order_by='Screenshot.sort_order')
    features = db.relationship('Feature', backref='listing', cascade='all, delete-orphan', order_by='Feature.sort_order')
    reviews = db.relationship('Review', backref='listing', cascade='all, delete-orphan', order_by='Review.sort_order')
    permissions = db.relationship('Permission', backref='listing', cascade='all, delete-orphan', order_by='Permission.sort_order')
    related_apps = db.relationship('RelatedApp', backref='listing', cascade='all, delete-orphan', order_by='RelatedApp.sort_order', foreign_keys='RelatedApp.listing_id')
    content_sections = db.relationship('ContentSection', backref='listing', cascade='all, delete-orphan', order_by='ContentSection.sort_order')


class Screenshot(db.Model):
    __tablename__ = 'screenshots'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    url = db.Column(db.String(500), default='')
    caption = db.Column(db.String(300), default='')
    alt_text = db.Column(db.String(300), default='')
    sort_order = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    asset = db.relationship('MediaAsset', foreign_keys=[asset_id])


class Feature(db.Model):
    __tablename__ = 'features'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    icon_url = db.Column(db.String(500), default='')
    title = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    sort_order = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    asset = db.relationship('MediaAsset', foreign_keys=[asset_id])


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=False)
    reviewer_name = db.Column(db.String(200), default='')
    avatar_asset_id = db.Column(db.Integer, db.ForeignKey('media_assets.id'), nullable=True)
    avatar_url = db.Column(db.String(500), default='')
    rating = db.Column(db.Integer, default=5)  # 1–5
    review_text = db.Column(db.Text, default='')
    review_date = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    avatar = db.relationship('MediaAsset', foreign_keys=[avatar_asset_id])


class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=False)
    name = db.Column(db.String(200), default='')
    explanation = db.Column(db.Text, default='')
    icon = db.Column(db.String(100), default='lock')
    sort_order = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)


class RelatedApp(db.Model):
    __tablename__ = 'related_apps'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=False)
    related_listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=True)
    manual_name = db.Column(db.String(200), default='')
    manual_icon_url = db.Column(db.String(500), default='')
    manual_link = db.Column(db.String(500), default='')
    sort_order = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)


class ContentSection(db.Model):
    __tablename__ = 'content_sections'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('app_listings.id'), nullable=False)
    heading = db.Column(db.String(300), default='')
    body = db.Column(db.Text, default='')
    image_url = db.Column(db.String(500), default='')
    sort_order = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)


class MediaAsset(db.Model):
    __tablename__ = 'media_assets'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)  # safe unique filename on disk
    original_filename = db.Column(db.String(300), default='')
    mime_type = db.Column(db.String(100), default='')
    file_size = db.Column(db.Integer, default=0)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    alt_text = db.Column(db.String(300), default='')
    asset_type = db.Column(db.String(20), default='image')  # image, apk
    cloudinary_url = db.Column(db.String(1000), default='')  # full URL when stored on Cloudinary
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    @property
    def url(self):
        if self.cloudinary_url:
            return self.cloudinary_url
        return f'/media/{self.filename}'


class KeepaliveLog(db.Model):
    __tablename__ = 'keepalive_logs'
    id = db.Column(db.Integer, primary_key=True)
    status_code = db.Column(db.Integer, default=200)
    response_time_ms = db.Column(db.Integer, default=0)  # milliseconds
    source = db.Column(db.String(100), default='cron')  # cron, manual, admin
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    @staticmethod
    def log(status_code=200, response_time_ms=0, source='cron'):
        try:
            entry = KeepaliveLog(status_code=status_code, response_time_ms=response_time_ms, source=source)
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    @staticmethod
    def get_uptime_stats():
        """Return uptime stats: first ping time, total pings, successful pings, uptime %."""
        try:
            total = KeepaliveLog.query.count()
            if total == 0:
                return {'started_at': None, 'total_pings': 0, 'successful': 0, 'uptime_pct': 0}
            first = KeepaliveLog.query.order_by(KeepaliveLog.created_at.asc()).first()
            successful = KeepaliveLog.query.filter(KeepaliveLog.status_code.in_([200, 302])).count()
            pct = round((successful / total) * 100, 1) if total else 0
            return {
                'started_at': first.created_at,
                'total_pings': total,
                'successful': successful,
                'uptime_pct': pct,
            }
        except Exception:
            return {'started_at': None, 'total_pings': 0, 'successful': 0, 'uptime_pct': 0}


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(200), nullable=False)
    entity_type = db.Column(db.String(100), default='')
    entity_id = db.Column(db.String(100), default='')
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    @staticmethod
    def log(action, entity_type='', entity_id='', message=''):
        try:
            entry = ActivityLog(action=action, entity_type=entity_type, entity_id=str(entity_id), message=message)
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()
