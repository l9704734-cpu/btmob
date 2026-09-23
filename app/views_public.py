"""
Public storefront blueprint — listing pages and downloads.
"""
import os
import re
from flask import (Blueprint, render_template, request, redirect,
                    url_for, abort, send_from_directory, current_app)
from app import db
from app.models import AppListing, StoreSettings, MediaAsset
from app.utils import get_store_settings

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
    """Serve the APK file for a published listing."""
    listing = AppListing.query.filter_by(slug=slug, status='published').first_or_404()
    if not listing.use_uploaded_file or not listing.apk_asset_id:
        if listing.apk_url:
            return redirect(listing.apk_url)
        abort(404)

    from app.models import MediaAsset
    asset = db.session.get(MediaAsset, listing.apk_asset_id)
    if not asset:
        abort(404)
    upload_dir = current_app.config['UPLOAD_DIR']
    return send_from_directory(upload_dir, asset.filename, as_attachment=True,
                                download_name=listing.download_filename or asset.original_filename or 'app.apk')


@public_bp.route('/media/<path:filename>')
def serve_media(filename):
    """Serve uploaded media assets (images, etc.)."""
    upload_dir = current_app.config['UPLOAD_DIR']
    # Prevent path traversal
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        abort(404)
    return send_from_directory(upload_dir, filename)
