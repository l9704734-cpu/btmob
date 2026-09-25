"""
Public storefront blueprint — listing pages and downloads.
"""
import os
import re
from flask import (Blueprint, render_template, request, redirect,
                    url_for, session, abort, send_from_directory, current_app,
                    send_file)
from app import db
from app.models import AppListing, StoreSettings, MediaAsset
from app.utils import get_store_settings
import os

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    """Show the published apps as a store front page."""
    settings = get_store_settings()
    listings = AppListing.query.filter_by(status='published').order_by(AppListing.updated_at.desc()).all()
    return render_template('public/index.html', settings=settings, listings=listings)


@public_bp.route('/app/<slug>')
def listing_detail(slug):
    """Show a single published app listing."""
    settings = get_store_settings()
    listing = AppListing.query.filter_by(slug=slug, status='published').first_or_404()
    related = []
    for ra in listing.related_apps:
        if ra.enabled and ra.related_listing_id:
            r = db.session.get(AppListing, ra.related_listing_id)
            if r and r.status == 'published' and r.id != listing.id:
                related.append(r)
            else:
                related.append({'manual_name': ra.manual_name, 'manual_icon_url': ra.manual_icon_url,
                               'manual_link': ra.manual_link, 'manual': True})
        elif ra.enabled and ra.manual_name:
            related.append({'manual_name': ra.manual_name, 'manual_icon_url': ra.manual_icon_url,
                           'manual_link': ra.manual_link, 'manual': True})

    return render_template('public/listing.html', listing=listing, settings=settings, related=related)


@public_bp.route('/download/<slug>')
def download(slug):
    """Serve the APK file for a published listing with tight headers."""
    listing = AppListing.query.filter_by(slug=slug, status='published').first_or_404()

    # If using uploaded file and we have an asset, serve it
    if listing.use_uploaded_file and listing.apk_asset_id:
        asset = db.session.get(MediaAsset, listing.apk_asset_id)
        if asset:
            # If the APK is on Supabase/Cloudinary, redirect there for the download
            if asset.cloudinary_url:
                return redirect(asset.cloudinary_url)
            # Otherwise serve from local disk
            upload_dir = current_app.config['UPLOAD_DIR']
            filepath = os.path.join(upload_dir, asset.filename)
            if os.path.exists(filepath):
                # Force uppercase .APK extension everywhere to prevent Android Chrome
                # from appending .zip (Android sees lowercase .apk as a ZIP container)
                filename = listing.download_filename or asset.original_filename or 'app.APK'
                # Strip any existing extension
                base = filename
                for ext in ['.zip', '.ZIP', '.apk', '.APK', '.apks', '.APKS']:
                    if base.endswith(ext):
                        base = base[:-len(ext)]
                        break
                filename = base + '.APK'

                # Build response with explicit Content-Type AND Content-Disposition
                # Use octet-stream so Android doesn't inspect the file as a ZIP archive
                with open(filepath, 'rb') as f:
                    file_data = f.read()
                response = current_app.response_class(
                    file_data,
                    mimetype='application/octet-stream',
                )
                response.headers['Content-Type'] = 'application/octet-stream'
                response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.headers['Content-Length'] = str(len(file_data))
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Download-Options'] = 'noopen'
                return response

    # Fall back to external URL
    if listing.apk_url:
        return redirect(listing.apk_url)

    abort(404)


@public_bp.route('/media/<path:filename>')
def serve_media(filename):
    """Serve uploaded media assets (images, etc.)."""
    upload_dir = current_app.config['UPLOAD_DIR']
    # Prevent path traversal
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        abort(404)
    return send_from_directory(upload_dir, filename)
