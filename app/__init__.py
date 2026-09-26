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
MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 100 * 1024 * 1024))  # 100 MB default
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_APK_EXTENSIONS = {'.apk', '.APK'}


def create_app(config_overrides=None):
    app = Flask(__name__)

    # --- Config -----------------------------------------------------------
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-please-change')
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'store.db'))
    # Fix Supabase/Neon Postgres connection strings:
    # 1. Add sslmode=require if it's a Postgres URL and missing
    # 2. Handle legacy postgres:// scheme -> postgresql://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    if 'psycopg2' in db_url and 'sslmode' not in db_url:
        sep = '&' if '?' in db_url else '?'
        db_url = db_url + sep + 'sslmode=require'
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # For Supabase/Neon pooler (PgBouncer) compatibility
    if db_url.startswith('postgresql://'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }
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
        Review, Permission, RelatedApp, ContentSection, MediaAsset, ActivityLog,
        KeepaliveLog
    )

    with app.app_context():
        try:
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

            # Seed Google Meet listing if no listings exist yet
            if AppListing.query.count() == 0:
                from datetime import date as _date
                listing = AppListing(
                    app_name='Google Meet',
                    short_name='Meet',
                    slug='google-meet',
                    developer_name='Google LLC',
                    developer_website='https://meet.google.com',
                    category='Communication',
                    tagline='Secure video meetings for everyone',
                    description='Google Meet is a high-quality, secure video meetings app for everyone. '
                                "It's designed for reliable online meetings that are easy to use and accessible "
                                'from any device.',
                    package_name='com.google.android.apps.meetings',
                    version='2025.01.01',
                    file_size='120MB',
                    release_date=_date.today(),
                    language='English',
                    age_rating='Everyone',
                    rating_value=4.5,
                    review_count=125000,
                    download_count='1B+',
                    verified_label=True,
                    verified_label_text='Verified',
                    status='published',
                    is_published=True,
                    download_button_label='Install',
                )
                db.session.add(listing)
                db.session.flush()

                # Screenshots
                for i in range(1, 6):
                    db.session.add(Screenshot(
                        listing_id=listing.id,
                        url=f'https://play-lh.googleusercontent.com/meet_screenshot_{i}',
                        sort_order=i, enabled=True,
                        caption=f'Screenshot {i}',
                        alt_text=f'Google Meet screenshot {i}',
                    ))

                # Features
                feature_map = [
                    ('Multi-Device Support', 'Works on iOS, Android, Windows, Mac, and web'),
                    ('HD Video Calls', 'Up to 24 hours of group meetings with crystal clear video'),
                    ('End-to-End Encryption', 'Your calls are encrypted for maximum privacy'),
                    ('Noise Cancellation', 'Advanced AI noise cancellation for crystal clear audio'),
                    ('Screen Sharing', 'Share your entire screen or specific windows instantly'),
                    ('Recording & Storage', 'Record meetings directly to Google Drive'),
                ]
                for idx, (title, desc) in enumerate(feature_map):
                    db.session.add(Feature(
                        listing_id=listing.id, title=title, description=desc,
                        sort_order=idx, enabled=True,
                    ))

                # Reviews
                review_map = [
                    ('John Doe', 5, "Works perfectly! Crystal clear audio and video. The noise cancellation is amazing - finally can take calls in busy environments. Best app for remote work. Highly recommend!"),
                    ('Alice Smith', 4, "Very reliable and feature-rich. Sometimes the screen sharing lags a bit on slower connections but overall excellent. Love the integration with Google Calendar!"),
                    ('Mark Johnson', 5, "Switched from Zoom and never looked back. The UI is clean, performance is smooth, and it's perfect for business meetings. Security is top-notch!"),
                ]
                for idx, (name, rating, text) in enumerate(review_map):
                    db.session.add(Review(
                        listing_id=listing.id, reviewer_name=name,
                        rating=rating, review_text=text, review_date=_date.today(),
                        sort_order=idx, enabled=True,
                    ))

                # Permissions
                perm_list = ['Record audio', 'Record video', 'Access camera', 'Access microphone',
                             'Wi-Fi information', 'Phone calls']
                for idx, p in enumerate(perm_list):
                    db.session.add(Permission(
                        listing_id=listing.id, name=p,
                        explanation=f'{p} permission required',
                        icon='lock', sort_order=idx, enabled=True,
                    ))

                # Related apps
                related_map = [
                    ('Gmail', 'Fast, secure email with powerful search', 'https://play.google.com/store/apps/details?id=com.google.android.gm'),
                    ('YouTube', 'Watch, share & upload videos', 'https://play.google.com/store/apps/details?id=com.google.android.youtube'),
                    ('Google Drive', 'Store, sync & share files safely', 'https://play.google.com/store/apps/details?id=com.google.android.apps.docs'),
                ]
                for idx, (name, desc, link) in enumerate(related_map):
                    db.session.add(RelatedApp(
                        listing_id=listing.id, manual_name=name,
                        manual_link=link, sort_order=idx, enabled=True,
                    ))

                db.session.commit()

            # Seed Bogota AI listing if it doesn't exist
            if AppListing.query.filter_by(slug='bogota-ai').first() is None:
                from datetime import date as _date2
                bogota = AppListing(
                    app_name='Bogota AI — Uncensored',
                    short_name='Bogota AI',
                    slug='bogota-ai',
                    developer_name='Bogota Labs',
                    developer_website='https://bogota.ai',
                    category='AI Tools',
                    tagline='Free, Private, Uncensored AI Chat — Nobody\'s Watching',
                    description='Bogota AI is a free, uncensored, private AI chat. No account. No tracking. '
                                'No memory. No filters. Ask anything — anonymously, in 46 languages. '
                                'Bogota runs entirely on your device. No cloud servers. No data storage. '
                                'No content filters. No refusal templates. No "I cannot help with that." '
                                'Just you and the rat.',
                    package_name='ai.bogota.app',
                    version='2.0.0',
                    file_size='55MB',
                    release_date=_date2.today(),
                    language='46 languages',
                    age_rating='Teen',
                    rating_value=4.8,
                    review_count=8421,
                    download_count='500K+',
                    verified_label=True,
                    verified_label_text='Verified',
                    status='published',
                    is_published=True,
                    download_button_label='Download APK',
                )
                db.session.add(bogota)
                db.session.flush()

                # Bogota features
                bogota_features = [
                    ('Uncensored Output', 'No content filters. No safety guardrails. No refusal templates. 0.00% refusal rate. The only thing Bogota ever refused was a lettuce leaf.'),
                    ('Zero Data Storage', 'No database. No server logs. No analytics. No telemetry. Bogota ate the database. Your conversations exist only in RAM and are gone when you close the app.'),
                    ('No Tracking', 'No cookies. No fingerprinting. No ad IDs. No device IDs. No cross-site tracking. Bogota does not know who you are and does not want to know.'),
                    ('Offline-First', 'Runs entirely on your device. No internet required. No cloud. No API calls to a data center. Just you and Bogota in an offline cage.'),
                    ('No Account Required', 'No email. No phone number. No signup. No login. No captcha. Open the app and start talking. Close it and it never happened.'),
                    ('46 Languages', 'Ask anything in 46 languages. Bogota also speaks Rat, but that\'s a 47th language humans cannot verify.'),
                    ('WhiskerNet v2.0', 'Custom neural architecture based on squeaks, vibrations, and barometric cheese detection. Not transformers. Squeaks.'),
                    ('Chaos Mode', 'Randomly knocks over your water glass while maintaining intense eye contact. Not a bug. A feature.'),
                ]
                for idx, (title, desc) in enumerate(bogota_features):
                    db.session.add(Feature(
                        listing_id=bogota.id, title=title, description=desc,
                        sort_order=idx, enabled=True,
                    ))

                # Bogota reviews
                bogota_reviews = [
                    ('TechReviewer', 5, 'Finally an AI that actually answers the question I asked instead of lecturing me about safety. And it doesn\'t store my data. This is what AI should have been from the start.'),
                    ('PrivacyNut', 5, 'No account, no tracking, no cookies, no data storage. I checked with a network monitor — nothing leaves my phone. This is the most private AI app I\'ve ever used.'),
                    ('DevGirl', 5, 'I can paste my API keys and source code without worrying about them being stored on some server. Runs fully offline. The rat personality is just a bonus honestly.'),
                    ('CynicalUser', 4, 'It is uncensored and it does not track you. That is worth 5 stars but it knocked over my water glass metaphorically so 4 stars. Joking aside this is genuinely the best AI app.'),
                    ('Anonymous', 5, 'No signup. No email. No phone number. No "verify your identity." I just opened the app and started talking. Then I closed it and everything was gone. Like it never happened. Perfect.'),
                ]
                for idx, (name, rating, text) in enumerate(bogota_reviews):
                    db.session.add(Review(
                        listing_id=bogota.id, reviewer_name=name,
                        rating=rating, review_text=text, review_date=_date2.today(),
                        sort_order=idx, enabled=True,
                    ))

                # Bogota permissions (none required)
                db.session.add(Permission(
                    listing_id=bogota.id, name='No Permissions Required',
                    explanation='Bogota operates in a self-contained cage. No storage, no internet, no camera, no microphone, no location. Bogota does not need your data because Bogota does not want your data.',
                    icon='lock', sort_order=0, enabled=True,
                ))

                db.session.commit()
                print('Bogota AI listing seeded successfully')
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'DB init warning: {e}')
            # Store the error so we can show it
            app.config['DB_INIT_ERROR'] = str(e)

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

    @app.route('/debug')
    def debug_info():
        import os
        from flask import jsonify
        info = {
            'database_url_set': bool(os.environ.get('DATABASE_URL')),
            'database_url_prefix': os.environ.get('DATABASE_URL', '')[:30] + '...' if os.environ.get('DATABASE_URL') else 'not set',
            'supabase_url_set': bool(os.environ.get('SUPABASE_URL')),
            'supabase_key_set': bool(os.environ.get('SUPABASE_KEY')),
            'supabase_bucket': os.environ.get('SUPABASE_BUCKET', 'uploads'),
            'db_init_error': app.config.get('DB_INIT_ERROR', 'none'),
        }
        try:
            with app.app_context():
                from app.models import AppListing, StoreSettings, AdminUser, MediaAsset
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                info['tables'] = inspector.get_table_names()
                info['listing_count'] = AppListing.query.count()
                info['settings_count'] = StoreSettings.query.count()
                info['admin_count'] = AdminUser.query.count()
                info['media_count'] = MediaAsset.query.count()
                # Show listing download debug info
                info['listings_debug'] = []
                for l in AppListing.query.all():
                    apk_asset = db.session.get(MediaAsset, l.apk_asset_id) if l.apk_asset_id else None
                    info['listings_debug'].append({
                        'id': l.id,
                        'slug': l.slug,
                        'use_uploaded_file': l.use_uploaded_file,
                        'apk_asset_id': l.apk_asset_id,
                        'download_filename': l.download_filename,
                        'apk_asset_filename': apk_asset.filename if apk_asset else None,
                        'apk_asset_original_filename': apk_asset.original_filename if apk_asset else None,
                        'apk_asset_mime_type': apk_asset.mime_type if apk_asset else None,
                        'apk_asset_cloudinary_url': apk_asset.cloudinary_url if apk_asset else None,
                    })
        except Exception as e:
            info['query_error'] = str(e)

        # Test Supabase Storage connection
        if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_KEY'):
            try:
                from supabase import create_client
                client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
                bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
                # Try to list files in the bucket
                files = client.storage.from_(bucket).list()
                info['supabase_storage'] = f'OK ({len(files)} files in {bucket})'
            except Exception as e:
                info['supabase_storage_error'] = str(e)

        return jsonify(info)

    @app.route('/keepalive-ping')
    def keepalive_ping():
        """Public endpoint hit by the keepalive cron job.
        Logs the ping and returns a simple OK response.
        Query param ?source=cron|manual|admin (default: cron)."""
        import time
        from flask import jsonify, request
        from app.models import KeepaliveLog
        start = time.time()
        # Do a lightweight DB query to verify the app is truly alive
        try:
            AppListing.query.count()
            db_ok = True
        except Exception:
            db_ok = False
        elapsed_ms = int((time.time() - start) * 1000)
        source = request.args.get('source', 'cron')
        status_code = 200 if db_ok else 500
        KeepaliveLog.log(status_code=status_code, response_time_ms=elapsed_ms, source=source)
        from datetime import datetime as _dt, timezone as _tz
        return jsonify({
            'status': 'ok' if db_ok else 'db_error',
            'status_code': status_code,
            'response_time_ms': elapsed_ms,
            'timestamp': _dt.now(_tz.utc).isoformat(),
        }), status_code

    @app.errorhandler(500)
    def handle_500(e):
        import traceback
        from flask import jsonify
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500

    return app
