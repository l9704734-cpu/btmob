"""
Utility helpers — upload validation, slug generation, migration.
"""
import os
import re
import uuid
import hashlib
from PIL import Image
from flask import current_app
from app import db
from app.models import MediaAsset, AppListing, StoreSettings, Screenshot, Feature, Review, Permission, RelatedApp, ContentSection, ActivityLog

ALLOWED_IMAGE_MIMES = {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_APK_EXTENSIONS = {'.apk'}
ALLOWED_APK_MIMES = {'application/vnd.android.package-archive', 'application/octet-stream'}


def allowed_image_file(filename, mime):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS and mime in ALLOWED_IMAGE_MIMES


def allowed_apk_file(filename, mime):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_APK_EXTENSIONS and (mime in ALLOWED_APK_MIMES or mime == '')


def safe_filename(filename):
    """Generate a safe, unique filename preserving extension."""
    ext = os.path.splitext(filename)[1].lower()
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', os.path.splitext(filename)[0])[:80]
    return f"{safe_name}_{uuid.uuid4().hex[:8]}{ext}"


def save_upload(file_storage, asset_type='image'):
    """Save an uploaded file to disk and create a MediaAsset record.

    Returns (MediaAsset, error_str). On error returns (None, error_str).
    """
    if file_storage is None or file_storage.filename == '':
        return None, 'No file provided.'

    filename = file_storage.filename
    mime = file_storage.mimetype or ''
    upload_dir = current_app.config['UPLOAD_DIR']

    if asset_type == 'image':
        if not allowed_image_file(filename, mime):
            return None, 'Invalid image file. Allowed: PNG, JPEG, WebP, GIF.'
    elif asset_type == 'apk':
        if not allowed_apk_file(filename, mime):
            return None, 'Invalid APK file.'
    else:
        return None, 'Unknown asset type.'

    safe_name = safe_filename(filename)
    dest = os.path.join(upload_dir, safe_name)

    # Write file and compute hash
    hasher = hashlib.sha256()
    with open(dest, 'wb') as out:
        chunk = file_storage.read(4096)
        while chunk:
            hasher.update(chunk)
            out.write(chunk)
            chunk = file_storage.read(4096)
    file_storage.seek(0)

    file_size = os.path.getsize(dest)
    width = height = None
    if asset_type == 'image':
        try:
            with Image.open(dest) as img:
                width, height = img.size
        except Exception:
            pass

    asset = MediaAsset(
        filename=safe_name,
        original_filename=filename,
        mime_type=mime,
        file_size=file_size,
        width=width,
        height=height,
        asset_type=asset_type,
    )
    db.session.add(asset)
    db.session.commit()
    ActivityLog.log('upload', 'media', asset.id, f'Uploaded {filename}')
    return asset, None


def generate_slug(text):
    """Generate a URL-safe slug from text."""
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower().replace(' ', '-')
    slug = re.sub(r'-+', '-', slug)
    return slug[:80] if slug else 'untitled'


def slug_is_unique(slug, exclude_id=None):
    q = AppListing.query.filter_by(slug=slug)
    if exclude_id is not None:
        q = q.filter(AppListing.id != exclude_id)
    return q.first() is None


def hex_color(value):
    """Validate a hex color string; returns cleaned value or None."""
    if not value:
        return None
    v = value.strip()
    if re.match(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', v):
        return v
    return None


def get_store_settings():
    return StoreSettings.query.first()


def get_published_listing_by_slug(slug):
    return AppListing.query.filter_by(slug=slug, status='published').first_or_404()


def log_activity(action, entity_type='', entity_id='', message=''):
    ActivityLog.log(action, entity_type, entity_id, message)


def migrate_legacy_json(json_path='app_data.json'):
    """One-time migration of the old single-record app_data.json into a new listing.

    Returns the created AppListing or None if already migrated / no file.
    """
    import json as json_mod
    from datetime import date

    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, 'r') as f:
            old = json_mod.load(f)
    except Exception:
        return None

    # Check if we already migrated
    existing = AppListing.query.filter_by(slug='google-meet').first()
    if existing:
        return None

    images = old.get('images', {})
    links = old.get('links', {})

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
        release_date=date.today(),
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
    db.session.flush()  # get listing.id

    # Screenshots
    for i in range(1, 6):
        url = images.get(f'screenshot{i}', '')
        if url:
            db.session.add(Screenshot(listing_id=listing.id, url=url, sort_order=i, enabled=True,
                                       caption=f'Screenshot {i}', alt_text=f'Google Meet screenshot {i}'))

    # Features (migrate the fixed image keys)
    feature_map = [
        ('multidevice', 'Multi-Device Support', 'Works on iOS, Android, Windows, Mac, and web'),
        ('video', 'HD Video Calls', 'Up to 24 hours of group meetings with crystal clear video'),
        ('encryption', 'End-to-End Encryption', 'Your calls are encrypted for maximum privacy'),
        ('noise', 'Noise Cancellation', 'Advanced AI noise cancellation for crystal clear audio'),
        ('screen', 'Screen Sharing', 'Share your entire screen or specific windows instantly'),
        ('recording', 'Recording & Storage', 'Record meetings directly to Google Drive'),
    ]
    for idx, (key, title, desc) in enumerate(feature_map):
        url = images.get(key, '')
        db.session.add(Feature(listing_id=listing.id, icon_url=url, title=title, description=desc,
                                sort_order=idx, enabled=True))

    # Reviews
    review_map = [
        ('review1', 'John Doe', 5, "Works perfectly! Crystal clear audio and video. The noise cancellation is amazing - finally can take calls in busy environments. Best app for remote work. Highly recommend!"),
        ('review2', 'Alice Smith', 4, "Very reliable and feature-rich. Sometimes the screen sharing lags a bit on slower connections but overall excellent. Love the integration with Google Calendar!"),
        ('review3', 'Mark Johnson', 5, "Switched from Zoom and never looked back. The UI is clean, performance is smooth, and it's perfect for business meetings. Security is top-notch!"),
    ]
    for idx, (key, name, rating, text) in enumerate(review_map):
        url = images.get(key, '')
        db.session.add(Review(listing_id=listing.id, reviewer_name=name, avatar_url=url,
                               rating=rating, review_text=text, review_date=date.today(),
                               sort_order=idx, enabled=True))

    # Permissions
    perm_list = ['Record audio', 'Record video', 'Access camera', 'Access microphone',
                  'Wi-Fi information', 'Phone calls']
    for idx, p in enumerate(perm_list):
        db.session.add(Permission(listing_id=listing.id, name=p, explanation=f'{p} permission required',
                                  icon='lock', sort_order=idx, enabled=True))

    # Related apps (manual)
    related_map = [
        ('gmail', 'Gmail', 'Fast, secure email with powerful search', links.get('gmail', '')),
        ('youtube', 'YouTube', 'Watch, share & upload videos', links.get('youtube', '')),
        ('gdrive', 'Google Drive', 'Store, sync & share files safely', links.get('gdrive', '')),
    ]
    for idx, (key, name, desc, link) in enumerate(related_map):
        icon_url = images.get(key, '')
        if not link:
            link = f'https://play.google.com/store/apps/details?id=com.google.android.{key}'
        db.session.add(RelatedApp(listing_id=listing.id, manual_name=name,
                                   manual_icon_url=icon_url, manual_link=link,
                                   sort_order=idx, enabled=True))

    db.session.commit()
    ActivityLog.log('migrate', 'listing', listing.id, 'Migrated legacy app_data.json')
    return listing
