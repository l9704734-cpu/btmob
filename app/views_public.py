"""
Public storefront blueprint — listing pages and downloads.
"""
import os
import re
from flask import (Blueprint, render_template, request, redirect,
                    url_for, session, abort, send_from_directory, current_app,
                    send_file)
from app import db
from app.models import AppListing, StoreSettings, MediaAsset, PageContent
from app.utils import get_store_settings
import os

public_bp = Blueprint('public', __name__)


def get_page_content(page_key):
    """Load all editable content for a page from the database.
    Returns a dict of section_key -> content. If no DB content, returns empty dict
    (template will fall back to its original hardcoded text)."""
    try:
        contents = PageContent.query.filter_by(page_key=page_key).all()
        return {c.section_key: c.content for c in contents}
    except Exception:
        return {}


def page_content_for(page_key):
    """Return a function pc(key, default) that looks up saved content for a page.
    Usage in templates: {{ pc('hero_title', 'Default text here') }}"""
    content = get_page_content(page_key)
    def _pc(key, default=''):
        return content.get(key, default)
    return _pc


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


@public_bp.route('/bogota-ai')
def bogota_ai():
    """Dedicated landing page for Bogota AI — uncensored AI rat."""
    settings = get_store_settings()
    listing = AppListing.query.filter_by(slug='bogota-ai', status='published').first()
    pc = page_content_for('bogota_ai')
    return render_template('public/bogota_ai.html', settings=settings, listing=listing, pc=pc)


@public_bp.route('/bogota-ai/capabilities')
def bogota_capabilities():
    """Bogota AI capabilities page."""
    settings = get_store_settings()
    listing = AppListing.query.filter_by(slug='bogota-ai', status='published').first()
    pc = page_content_for('bogota_capabilities')
    return render_template('public/bogota_capabilities.html', settings=settings, listing=listing, pc=pc)


@public_bp.route('/bogota-ai/terminal')
def bogota_terminal():
    """Bogota AI terminal/chat demo page."""
    settings = get_store_settings()
    listing = AppListing.query.filter_by(slug='bogota-ai', status='published').first()
    pc = page_content_for('bogota_terminal')
    return render_template('public/bogota_terminal.html', settings=settings, listing=listing, pc=pc)


@public_bp.route('/bogota-ai/download')
def bogota_download():
    """Bogota AI download page."""
    settings = get_store_settings()
    listing = AppListing.query.filter_by(slug='bogota-ai', status='published').first()
    pc = page_content_for('bogota_download')
    return render_template('public/bogota_download.html', settings=settings, listing=listing, pc=pc)


@public_bp.route('/bogota-ai/pricing')
def bogota_pricing():
    """Bogota AI pricing page."""
    settings = get_store_settings()
    listing = AppListing.query.filter_by(slug='bogota-ai', status='published').first()
    pc = page_content_for('bogota_pricing')
    return render_template('public/bogota_pricing.html', settings=settings, listing=listing, pc=pc)


@public_bp.route('/api/page-content/<page_key>')
def api_page_content(page_key):
    """API endpoint returning all saved text replacements for a page.
    Used by the inline-edit JS on public pages."""
    from flask import jsonify
    content = get_page_content(page_key)
    return jsonify(content)


@public_bp.route('/download/<slug>')
def download(slug):
    """Serve the APK file for a published listing with tight headers."""
    listing = AppListing.query.filter_by(slug=slug, status='published').first_or_404()

    # If using uploaded file and we have an asset, serve it
    if listing.use_uploaded_file and listing.apk_asset_id:
        asset = db.session.get(MediaAsset, listing.apk_asset_id)
        if asset:
            # For APK files: ALWAYS serve from local disk with our own headers.
            # Never redirect to Supabase/Cloudinary for APKs because Supabase
            # serves with its own Content-Type which makes Android Chrome add .zip
            upload_dir = current_app.config['UPLOAD_DIR']
            filepath = os.path.join(upload_dir, asset.filename)
            if os.path.exists(filepath):
                filename = listing.download_filename or asset.original_filename or 'app.apk'
                # Strip any .zip extension
                if filename.lower().endswith('.zip'):
                    filename = filename[:-4]
                if not filename.lower().endswith('.apk'):
                    filename = filename + '.apk'

                with open(filepath, 'rb') as f:
                    file_data = f.read()
                response = current_app.response_class(
                    file_data,
                    mimetype='application/vnd.android.package-archive',
                )
                response.headers['Content-Type'] = 'application/vnd.android.package-archive'
                response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.headers['Content-Length'] = str(len(file_data))
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Download-Options'] = 'noopen'
                return response

            # If file not on local disk, try Supabase/Cloudinary redirect as fallback
            if asset.cloudinary_url:
                return redirect(asset.cloudinary_url)

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
