"""
Admin blueprint — full CMS dashboard for managing APK listings.
"""
import os
import re
from datetime import date, datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                    session, abort, jsonify, current_app, flash)
from app import db
from app.models import (
    AppListing, StoreSettings, AdminUser, Screenshot, Feature, Review,
    Permission, RelatedApp, ContentSection, MediaAsset, ActivityLog
)
from app.utils import (
    save_upload, generate_slug, slug_is_unique, hex_color,
    get_store_settings, log_activity, allowed_image_file, allowed_apk_file
)
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__)

ITEMS_PER_PAGE = 12


# --- Decorator: require login -------------------------------------------

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_user_id' not in session:
            return redirect(url_for('auth.login'))
        admin = db.session.get(AdminUser, session.get('admin_user_id'))
        if not admin:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# --- Dashboard ----------------------------------------------------------

@admin_bp.route('/')
@login_required
def dashboard():
    total = AppListing.query.count()
    published = AppListing.query.filter_by(status='published').count()
    drafts = AppListing.query.filter_by(status='draft').count()
    archived = AppListing.query.filter_by(status='archived').count()
    recently_updated = AppListing.query.order_by(AppListing.updated_at.desc()).limit(5).all()
    recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    settings = get_store_settings()
    return render_template('admin/dashboard.html', total=total, published=published,
                           drafts=drafts, archived=archived, recently_updated=recently_updated,
                           recent_activity=recent_activity, settings=settings)


# --- All APKs -----------------------------------------------------------

@admin_bp.route('/apps')
@login_required
def list_apps():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    sort = request.args.get('sort', 'updated')

    q = AppListing.query
    if search:
        q = q.filter(db.or_(AppListing.app_name.ilike(f'%{search}%'),
                             AppListing.slug.ilike(f'%{search}%')))
    if status_filter in ('draft', 'published', 'archived'):
        q = q.filter_by(status=status_filter)

    if sort == 'name':
        q = q.order_by(AppListing.app_name.asc())
    else:
        q = q.order_by(AppListing.updated_at.desc())

    total = q.count()
    listings = q.offset((page - 1) * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE).all()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    settings = get_store_settings()
    return render_template('admin/apps.html', listings=listings, page=page,
                           total_pages=total_pages, total=total,
                           search=search, status_filter=status_filter, sort=sort,
                           settings=settings)


# --- Create / Edit / Duplicate ------------------------------------------

@admin_bp.route('/apps/new', methods=['GET', 'POST'])
@login_required
def new_app():
    if request.method == 'POST':
        return save_app_form(None)
    settings = get_store_settings()
    return render_template('admin/editor.html', listing=None, settings=settings,
                           all_listings=AppListing.query.order_by(AppListing.app_name).all())


@admin_bp.route('/apps/<int:listing_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    if request.method == 'POST':
        return save_app_form(listing)
    settings = get_store_settings()
    return render_template('admin/editor.html', listing=listing, settings=settings,
                           all_listings=AppListing.query.filter(AppListing.id != listing.id).order_by(AppListing.app_name).all())


@admin_bp.route('/apps/<int:listing_id>/duplicate', methods=['POST'])
@login_required
def duplicate_app(listing_id):
    src = AppListing.query.get_or_404(listing_id)
    new_slug = f'{src.slug}-copy'
    # Ensure unique
    base = new_slug
    n = 1
    while not slug_is_unique(new_slug):
        n += 1
        new_slug = f'{base}-{n}'

    new_listing = AppListing(
        app_name=f'{src.app_name} (Copy)',
        short_name=src.short_name,
        slug=new_slug,
        developer_name=src.developer_name,
        developer_website=src.developer_website,
        category=src.category,
        tagline=src.tagline,
        description=src.description,
        package_name=src.package_name,
        version=src.version,
        file_size=src.file_size,
        release_date=src.release_date,
        language=src.language,
        age_rating=src.age_rating,
        rating_value=src.rating_value,
        review_count=src.review_count,
        download_count=src.download_count,
        verified_label=src.verified_label,
        verified_label_text=src.verified_label_text,
        status='draft',
        is_published=False,
        icon_url=src.icon_url,
        hero_url=src.hero_url,
        favicon_url=src.favicon_url,
        primary_color=src.primary_color,
        secondary_color=src.secondary_color,
        bg_color=src.bg_color,
        text_color=src.text_color,
        apk_url=src.apk_url,
        download_filename=src.download_filename,
        download_button_label=src.download_button_label,
        download_button_icon_url=src.download_button_icon_url,
        download_button_icon_position=src.download_button_icon_position,
        use_uploaded_file=src.use_uploaded_file,
        apk_checksum=src.apk_checksum,
        seo_title=src.seo_title,
        meta_description=src.meta_description,
        canonical_url=src.canonical_url,
        social_image_url=src.social_image_url,
        custom_browser_title=src.custom_browser_title,
        no_index=src.no_index,
    )
    db.session.add(new_listing)
    db.session.flush()

    # Copy children
    for s in src.screenshots:
        db.session.add(Screenshot(listing_id=new_listing.id, url=s.url, caption=s.caption,
                                  alt_text=s.alt_text, sort_order=s.sort_order, enabled=s.enabled))
    for f in src.features:
        db.session.add(Feature(listing_id=new_listing.id, icon_url=f.icon_url, title=f.title,
                               description=f.description, sort_order=f.sort_order, enabled=f.enabled))
    for r in src.reviews:
        db.session.add(Review(listing_id=new_listing.id, reviewer_name=r.reviewer_name,
                              avatar_url=r.avatar_url, rating=r.rating, review_text=r.review_text,
                              review_date=r.review_date, sort_order=r.sort_order, enabled=r.enabled))
    for p in src.permissions:
        db.session.add(Permission(listing_id=new_listing.id, name=p.name, explanation=p.explanation,
                                  icon=p.icon, sort_order=p.sort_order, enabled=p.enabled))
    for c in src.content_sections:
        db.session.add(ContentSection(listing_id=new_listing.id, heading=c.heading, body=c.body,
                                      image_url=c.image_url, sort_order=c.sort_order, enabled=c.enabled))

    db.session.commit()
    log_activity('duplicate', 'listing', new_listing.id, f'Duplicated from {src.app_name}')
    flash('Listing duplicated as draft.', 'success')
    return redirect(url_for('admin.edit_app', listing_id=new_listing.id))


# --- Save handler (handles new + edit) ----------------------------------

def _get_field(name, default=''):
    return request.form.get(name, default).strip()


def _get_int(name, default=0):
    try:
        return int(request.form.get(name, default))
    except (ValueError, TypeError):
        return default


def _get_float(name, default=0.0):
    try:
        return float(request.form.get(name, default))
    except (ValueError, TypeError):
        return default


def _get_bool(name):
    return request.form.get(name) in ('true', '1', 'on', 'yes')


def _get_date(name):
    val = request.form.get(name, '').strip()
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        return None


def save_app_form(listing):
    """Handle the multi-tab editor form submission.

    Supports: Save Draft, Save (publish), Preview, Cancel.
    Returns a Flask response.
    """
    is_new = listing is None

    # Collect all fields
    app_name = _get_field('app_name')
    slug = _get_field('slug') or generate_slug(app_name)
    developer_name = _get_field('developer_name')
    category = _get_field('category')
    tagline = _get_field('tagline')
    description = request.form.get('description', '').strip()
    package_name = _get_field('package_name')
    version = _get_field('version')
    file_size = _get_field('file_size')
    release_date = _get_date('release_date')
    language = _get_field('language', 'English')
    age_rating = _get_field('age_rating', 'Everyone')
    rating_value = _get_float('rating_value', 0.0)
    review_count = _get_int('review_count', 0)
    download_count = _get_field('download_count')
    verified_label = _get_bool('verified_label')
    verified_label_text = _get_field('verified_label_text', 'Verified')

    developer_website = _get_field('developer_website')

    # Branding
    icon_url = _get_field('icon_url')
    hero_url = _get_field('hero_url')
    favicon_url = _get_field('favicon_url')

    # Theme
    primary_color = _get_field('primary_color') or None
    secondary_color = _get_field('secondary_color') or None
    bg_color = _get_field('bg_color') or None
    text_color = _get_field('text_color') or None
    if primary_color and not hex_color(primary_color):
        primary_color = None
    if secondary_color and not hex_color(secondary_color):
        secondary_color = None
    if bg_color and not hex_color(bg_color):
        bg_color = None
    if text_color and not hex_color(text_color):
        text_color = None

    # Download
    apk_url = _get_field('apk_url')
    download_filename = _get_field('download_filename')
    download_button_label = _get_field('download_button_label', 'Install')
    download_button_icon_url = _get_field('download_button_icon_url')
    download_button_icon_position = _get_field('download_button_icon_position', 'left')
    if download_button_icon_position not in ('left', 'right', 'hidden'):
        download_button_icon_position = 'left'
    use_uploaded_file = _get_bool('use_uploaded_file')
    apk_checksum = _get_field('apk_checksum')

    # SEO
    seo_title = _get_field('seo_title')
    meta_description = _get_field('meta_description')
    canonical_url = _get_field('canonical_url')
    social_image_url = _get_field('social_image_url')
    custom_browser_title = _get_field('custom_browser_title')
    no_index = _get_bool('no_index')

    # Status
    action = request.form.get('action', 'save')
    if action == 'publish':
        status = 'published'
    elif action == 'archive':
        status = 'archived'
    else:
        status = _get_field('status', 'draft') or 'draft'
        if action == 'save_draft':
            status = 'draft'

    # Validation
    errors = []
    if not app_name:
        errors.append('App name is required.')
    if not slug:
        errors.append('Slug is required.')
    if slug and not slug_is_unique(slug, exclude_id=listing.id if listing else None):
        errors.append(f'Slug "{slug}" is already in use by another listing.')
    if rating_value < 0 or rating_value > 5:
        errors.append('Rating must be between 0 and 5.')

    # Handle file uploads (icon, hero, favicon, button icon, social, apk)
    def _upload_or_none(field_name, asset_type='image'):
        f = request.files.get(field_name)
        if f and f.filename:
            asset, err = save_upload(f, asset_type=asset_type)
            if err:
                errors.append(f'Upload error ({field_name}): {err}')
                return None
            return asset
        return None

    icon_asset = _upload_or_none('icon_file')
    hero_asset = _upload_or_none('hero_file')
    favicon_asset = _upload_or_none('favicon_file')
    button_icon_asset = _upload_or_none('download_button_icon_file')
    social_asset = _upload_or_none('social_image_file')
    apk_asset = _upload_or_none('apk_file', asset_type='apk')

    if errors:
        for e in errors:
            flash(e, 'error')
        # Re-render the form preserving the submitted data
        settings = get_store_settings()
        # Build a pseudo-listing from form data so the template can re-render
        return render_template('admin/editor.html', listing=None, settings=settings,
                               all_listings=AppListing.query.order_by(AppListing.app_name).all(),
                               form_errors=errors, form_data=request.form)

    # Create or update
    if is_new:
        listing = AppListing(slug=slug)
        db.session.add(listing)

    listing.app_name = app_name
    listing.short_name = _get_field('short_name')
    listing.slug = slug
    listing.developer_name = developer_name
    listing.developer_website = developer_website
    listing.category = category
    listing.tagline = tagline
    listing.description = description
    listing.package_name = package_name
    listing.version = version
    listing.file_size = file_size
    listing.release_date = release_date
    listing.language = language
    listing.age_rating = age_rating
    listing.rating_value = rating_value
    listing.review_count = review_count
    listing.download_count = download_count
    listing.verified_label = verified_label
    listing.verified_label_text = verified_label_text
    listing.status = status
    listing.is_published = (status == 'published')

    # Branding — asset takes priority over URL; if neither, clear old value
    if icon_asset:
        listing.icon_asset_id = icon_asset.id
        listing.icon_url = ''
    else:
        listing.icon_asset_id = None if not icon_url else listing.icon_asset_id
        listing.icon_url = icon_url
    if hero_asset:
        listing.hero_asset_id = hero_asset.id
        listing.hero_url = ''
    else:
        listing.hero_asset_id = None if not hero_url else listing.hero_asset_id
        listing.hero_url = hero_url
    if favicon_asset:
        listing.favicon_asset_id = favicon_asset.id
        listing.favicon_url = ''
    else:
        listing.favicon_asset_id = None if not favicon_url else listing.favicon_asset_id
        listing.favicon_url = favicon_url

    listing.primary_color = primary_color or ''
    listing.secondary_color = secondary_color or ''
    listing.bg_color = bg_color or ''
    listing.text_color = text_color or ''

    # Download — clear old values when field is emptied
    if apk_asset:
        listing.apk_asset_id = apk_asset.id
        listing.use_uploaded_file = True
    else:
        listing.apk_asset_id = None if not apk_url else listing.apk_asset_id
    listing.apk_url = apk_url
    listing.download_filename = download_filename
    listing.download_button_label = download_button_label
    if button_icon_asset:
        listing.download_button_icon_asset_id = button_icon_asset.id
        listing.download_button_icon_url = ''
    else:
        listing.download_button_icon_asset_id = None if not download_button_icon_url else listing.download_button_icon_asset_id
        listing.download_button_icon_url = download_button_icon_url
    listing.download_button_icon_position = download_button_icon_position
    listing.use_uploaded_file = use_uploaded_file or bool(apk_asset)
    listing.apk_checksum = apk_checksum

    # SEO — clear old values when field is emptied
    listing.seo_title = seo_title
    listing.meta_description = meta_description
    listing.canonical_url = canonical_url
    if social_asset:
        listing.social_image_asset_id = social_asset.id
        listing.social_image_url = ''
    else:
        listing.social_image_asset_id = None if not social_image_url else listing.social_image_asset_id
        listing.social_image_url = social_image_url
    listing.custom_browser_title = custom_browser_title
    listing.no_index = no_index

    db.session.flush()

    # --- Repeatable children: screenshots ---
    _save_screenshots(listing)
    _save_features(listing)
    _save_reviews(listing)
    _save_permissions(listing)
    _save_related_apps(listing)
    _save_content_sections(listing)

    db.session.commit()
    log_activity('save' if is_new else 'update', 'listing', listing.id,
                 f'{"Created" if is_new else "Updated"} {app_name}')

    if action == 'publish':
        flash('Listing published successfully.', 'success')
    elif action == 'archive':
        flash('Listing archived.', 'success')
    else:
        flash('Listing saved.', 'success')

    if request.form.get('action') == 'preview':
        return redirect(url_for('admin.preview_app', listing_id=listing.id))
    return redirect(url_for('admin.edit_app', listing_id=listing.id))


def _save_screenshots(listing):
    """Handle dynamic screenshot rows: s_id[], s_url[], s_caption[], s_alt[], s_order[], s_enabled[]"""
    ids = request.form.getlist('s_id[]')
    urls = request.form.getlist('s_url[]')
    captions = request.form.getlist('s_caption[]')
    alts = request.form.getlist('s_alt[]')
    orders = request.form.getlist('s_order[]')
    enableds = request.form.getlist('s_enabled[]')

    existing_ids = {s.id for s in listing.screenshots}
    seen = set()

    for i, _id in enumerate(ids):
        try:
            row_id = int(_id) if _id and _id.isdigit() else None
        except (ValueError, TypeError):
            row_id = None

        url = urls[i] if i < len(urls) else ''
        caption = captions[i] if i < len(captions) else ''
        alt = alts[i] if i < len(alts) else ''
        order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
        enabled = str(i) in enableds or (i < len(enableds) and enableds[i] == 'on')

        # Handle file upload for this screenshot
        file_key = f's_file_{i}'
        f = request.files.get(file_key)
        asset = None
        if f and f.filename:
            asset, _err = save_upload(f, asset_type='image')
            if asset:
                url = asset.url

        if row_id and row_id in existing_ids:
            s = db.session.get(Screenshot, row_id)
            if s and s.listing_id == listing.id:
                s.url = url
                s.caption = caption
                s.alt_text = alt
                s.sort_order = order
                s.enabled = enabled
                if asset:
                    s.asset_id = asset.id
                seen.add(row_id)

    # Add new screenshots (empty id rows)
    for i, _id in enumerate(ids):
        if not _id or not _id.isdigit():
            url = urls[i] if i < len(urls) else ''
            caption = captions[i] if i < len(captions) else ''
            alt = alts[i] if i < len(alts) else ''
            order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
            enabled = str(i) in enableds

            file_key = f's_file_{i}'
            f = request.files.get(file_key)
            asset = None
            if f and f.filename:
                asset, _err = save_upload(f, asset_type='image')
                if asset:
                    url = asset.url

            if url or asset:
                db.session.add(Screenshot(listing_id=listing.id, url=url,
                                          asset_id=asset.id if asset else None,
                                          caption=caption, alt_text=alt,
                                          sort_order=order, enabled=enabled))

    # Delete removed
    for old_id in existing_ids - seen:
        s = db.session.get(Screenshot, old_id)
        if s and s.listing_id == listing.id:
            db.session.delete(s)


def _save_features(listing):
    ids = request.form.getlist('f_id[]')
    titles = request.form.getlist('f_title[]')
    descs = request.form.getlist('f_desc[]')
    orders = request.form.getlist('f_order[]')
    enableds = request.form.getlist('f_enabled[]')
    icon_urls = request.form.getlist('f_icon_url[]')

    existing_ids = {f.id for f in listing.features}
    seen = set()

    for i, _id in enumerate(ids):
        try:
            row_id = int(_id) if _id and _id.isdigit() else None
        except (ValueError, TypeError):
            row_id = None
        title = titles[i] if i < len(titles) else ''
        desc = descs[i] if i < len(descs) else ''
        order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
        enabled = str(i) in enableds

        icon_url = icon_urls[i] if i < len(icon_urls) else ''
        file_key = f'f_icon_file_{i}'
        f = request.files.get(file_key)
        asset = None
        if f and f.filename:
            asset, _err = save_upload(f, asset_type='image')
            if asset:
                icon_url = asset.url

        if row_id and row_id in existing_ids:
            feat = db.session.get(Feature, row_id)
            if feat and feat.listing_id == listing.id:
                feat.title = title
                feat.description = desc
                feat.sort_order = order
                feat.enabled = enabled
                feat.icon_url = icon_url
                if asset:
                    feat.asset_id = asset.id
                seen.add(row_id)
        elif title:
            db.session.add(Feature(listing_id=listing.id, title=title, description=desc,
                                    icon_url=icon_url, asset_id=asset.id if asset else None,
                                    sort_order=order, enabled=enabled))

    for old_id in existing_ids - seen:
        feat = db.session.get(Feature, old_id)
        if feat and feat.listing_id == listing.id:
            db.session.delete(feat)


def _save_reviews(listing):
    ids = request.form.getlist('r_id[]')
    names = request.form.getlist('r_name[]')
    ratings = request.form.getlist('r_rating[]')
    texts = request.form.getlist('r_text[]')
    dates_list = request.form.getlist('r_date[]')
    orders = request.form.getlist('r_order[]')
    enableds = request.form.getlist('r_enabled[]')
    avatar_urls = request.form.getlist('r_avatar_url[]')

    existing_ids = {r.id for r in listing.reviews}
    seen = set()

    for i, _id in enumerate(ids):
        row_id = int(_id) if _id and _id.isdigit() else None
        name = names[i] if i < len(names) else ''
        rating = int(ratings[i]) if i < len(ratings) and ratings[i].isdigit() else 5
        rating = max(1, min(5, rating))
        text = texts[i] if i < len(texts) else ''
        r_date = None
        if i < len(dates_list) and dates_list[i]:
            try:
                r_date = datetime.strptime(dates_list[i], '%Y-%m-%d').date()
            except ValueError:
                pass
        order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
        enabled = str(i) in enableds
        avatar_url = avatar_urls[i] if i < len(avatar_urls) else ''

        file_key = f'r_avatar_file_{i}'
        f = request.files.get(file_key)
        asset = None
        if f and f.filename:
            asset, _err = save_upload(f, asset_type='image')
            if asset:
                avatar_url = asset.url

        if row_id and row_id in existing_ids:
            rev = db.session.get(Review, row_id)
            if rev and rev.listing_id == listing.id:
                rev.reviewer_name = name
                rev.rating = rating
                rev.review_text = text
                rev.review_date = r_date
                rev.sort_order = order
                rev.enabled = enabled
                rev.avatar_url = avatar_url
                if asset:
                    rev.avatar_asset_id = asset.id
                seen.add(row_id)
        elif name or text:
            db.session.add(Review(listing_id=listing.id, reviewer_name=name, rating=rating,
                                   review_text=text, review_date=r_date, sort_order=order,
                                   enabled=enabled, avatar_url=avatar_url,
                                   avatar_asset_id=asset.id if asset else None))

    for old_id in existing_ids - seen:
        rev = db.session.get(Review, old_id)
        if rev and rev.listing_id == listing.id:
            db.session.delete(rev)


def _save_permissions(listing):
    ids = request.form.getlist('p_id[]')
    names = request.form.getlist('p_name[]')
    explanations = request.form.getlist('p_explanation[]')
    icons = request.form.getlist('p_icon[]')
    orders = request.form.getlist('p_order[]')
    enableds = request.form.getlist('p_enabled[]')

    existing_ids = {p.id for p in listing.permissions}
    seen = set()

    for i, _id in enumerate(ids):
        row_id = int(_id) if _id and _id.isdigit() else None
        name = names[i] if i < len(names) else ''
        explanation = explanations[i] if i < len(explanations) else ''
        icon = icons[i] if i < len(icons) else 'lock'
        order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
        enabled = str(i) in enableds

        if row_id and row_id in existing_ids:
            perm = db.session.get(Permission, row_id)
            if perm and perm.listing_id == listing.id:
                perm.name = name
                perm.explanation = explanation
                perm.icon = icon
                perm.sort_order = order
                perm.enabled = enabled
                seen.add(row_id)
        elif name:
            db.session.add(Permission(listing_id=listing.id, name=name, explanation=explanation,
                                       icon=icon, sort_order=order, enabled=enabled))

    for old_id in existing_ids - seen:
        perm = db.session.get(Permission, old_id)
        if perm and perm.listing_id == listing.id:
            db.session.delete(perm)


def _save_related_apps(listing):
    ids = request.form.getlist('ra_id[]')
    related_ids = request.form.getlist('ra_related_id[]')
    manual_names = request.form.getlist('ra_manual_name[]')
    manual_icon_urls = request.form.getlist('ra_manual_icon_url[]')
    manual_links = request.form.getlist('ra_manual_link[]')
    orders = request.form.getlist('ra_order[]')
    enableds = request.form.getlist('ra_enabled[]')

    existing_ids = {r.id for r in listing.related_apps}
    seen = set()

    for i, _id in enumerate(ids):
        row_id = int(_id) if _id and _id.isdigit() else None
        related_id_raw = related_ids[i] if i < len(related_ids) else ''
        related_id = int(related_id_raw) if related_id_raw and related_id_raw.isdigit() else None
        if related_id == listing.id:
            continue  # Prevent self-reference
        m_name = manual_names[i] if i < len(manual_names) else ''
        m_icon = manual_icon_urls[i] if i < len(manual_icon_urls) else ''
        m_link = manual_links[i] if i < len(manual_links) else ''
        order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
        enabled = str(i) in enableds

        if row_id and row_id in existing_ids:
            ra = db.session.get(RelatedApp, row_id)
            if ra and ra.listing_id == listing.id:
                ra.related_listing_id = related_id if related_id else None
                ra.manual_name = m_name
                ra.manual_icon_url = m_icon
                ra.manual_link = m_link
                ra.sort_order = order
                ra.enabled = enabled
                seen.add(row_id)
        elif related_id or m_name:
            db.session.add(RelatedApp(listing_id=listing.id, related_listing_id=related_id,
                                      manual_name=m_name, manual_icon_url=m_icon,
                                      manual_link=m_link, sort_order=order, enabled=enabled))

    for old_id in existing_ids - seen:
        ra = db.session.get(RelatedApp, old_id)
        if ra and ra.listing_id == listing.id:
            db.session.delete(ra)


def _save_content_sections(listing):
    ids = request.form.getlist('c_id[]')
    headings = request.form.getlist('c_heading[]')
    bodies = request.form.getlist('c_body[]')
    images = request.form.getlist('c_image_url[]')
    orders = request.form.getlist('c_order[]')
    enableds = request.form.getlist('c_enabled[]')

    existing_ids = {c.id for c in listing.content_sections}
    seen = set()

    for i, _id in enumerate(ids):
        row_id = int(_id) if _id and _id.isdigit() else None
        heading = headings[i] if i < len(headings) else ''
        body = bodies[i] if i < len(bodies) else ''
        image_url = images[i] if i < len(images) else ''
        order = int(orders[i]) if i < len(orders) and orders[i].isdigit() else i
        enabled = str(i) in enableds

        file_key = f'c_image_file_{i}'
        f = request.files.get(file_key)
        asset = None
        if f and f.filename:
            asset, _err = save_upload(f, asset_type='image')
            if asset:
                image_url = asset.url

        if row_id and row_id in existing_ids:
            cs = db.session.get(ContentSection, row_id)
            if cs and cs.listing_id == listing.id:
                cs.heading = heading
                cs.body = body
                cs.image_url = image_url
                cs.sort_order = order
                cs.enabled = enabled
                seen.add(row_id)
        elif heading:
            db.session.add(ContentSection(listing_id=listing.id, heading=heading, body=body,
                                           image_url=image_url, sort_order=order, enabled=enabled))

    for old_id in existing_ids - seen:
        cs = db.session.get(ContentSection, old_id)
        if cs and cs.listing_id == listing.id:
            db.session.delete(cs)


# --- Status actions -----------------------------------------------------

@admin_bp.route('/apps/<int:listing_id>/preview')
@login_required
def preview_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    settings = get_store_settings()
    return render_template('public/listing.html', listing=listing, settings=settings,
                           related=[], preview=True)


@admin_bp.route('/apps/<int:listing_id>/publish', methods=['POST'])
@login_required
def publish_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    if not listing.app_name or not listing.slug:
        flash('Cannot publish: missing required fields.', 'error')
        return redirect(url_for('admin.edit_app', listing_id=listing.id))
    listing.status = 'published'
    listing.is_published = True
    db.session.commit()
    log_activity('publish', 'listing', listing.id, f'Published {listing.app_name}')
    flash('Listing published.', 'success')
    return redirect(url_for('admin.list_apps'))


@admin_bp.route('/apps/<int:listing_id>/unpublish', methods=['POST'])
@login_required
def unpublish_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    listing.status = 'draft'
    listing.is_published = False
    db.session.commit()
    log_activity('unpublish', 'listing', listing.id, f'Unpublished {listing.app_name}')
    flash('Listing unpublished (set to draft).', 'success')
    return redirect(url_for('admin.list_apps'))


@admin_bp.route('/apps/<int:listing_id>/archive', methods=['POST'])
@login_required
def archive_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    listing.status = 'archived'
    listing.is_published = False
    db.session.commit()
    log_activity('archive', 'listing', listing.id, f'Archived {listing.app_name}')
    flash('Listing archived.', 'success')
    return redirect(url_for('admin.list_apps'))


@admin_bp.route('/apps/<int:listing_id>/restore', methods=['POST'])
@login_required
def restore_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    listing.status = 'draft'
    listing.is_published = False
    db.session.commit()
    log_activity('restore', 'listing', listing.id, f'Restored {listing.app_name}')
    flash('Listing restored to draft.', 'success')
    return redirect(url_for('admin.list_apps'))


@admin_bp.route('/apps/<int:listing_id>/delete', methods=['POST'])
@login_required
def delete_app(listing_id):
    listing = AppListing.query.get_or_404(listing_id)
    name = listing.app_name
    db.session.delete(listing)
    db.session.commit()
    log_activity('delete', 'listing', listing_id, f'Deleted {name}')
    flash('Listing deleted.', 'success')
    return redirect(url_for('admin.list_apps'))


# --- Store Settings -----------------------------------------------------

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def store_settings():
    settings = get_store_settings()
    if request.method == 'POST':
        settings.store_name = _get_field('store_name', 'Play Store')
        settings.store_tagline = _get_field('store_tagline')
        settings.store_description = request.form.get('store_description', '').strip()
        settings.footer_text = request.form.get('footer_text', '').strip()
        settings.contact_email = _get_field('contact_email')
        settings.contact_website = _get_field('contact_website')
        settings.default_primary_color = _get_field('default_primary_color', '#0f9d58') or '#0f9d58'
        settings.default_secondary_color = _get_field('default_secondary_color', '#34a853') or '#34a853'
        settings.default_bg_color = _get_field('default_bg_color', '#f8fafc') or '#f8fafc'
        settings.default_text_color = _get_field('default_text_color', '#0f172a') or '#0f172a'
        settings.default_seo_title = _get_field('default_seo_title')
        settings.default_seo_description = _get_field('default_seo_description')
        settings.default_download_button_label = _get_field('default_download_button_label', 'Install')

        # Store icon upload — clear old value when field is emptied
        icon_file = request.files.get('store_icon_file')
        if icon_file and icon_file.filename:
            asset, err = save_upload(icon_file)
            if asset:
                settings.store_icon_asset_id = asset.id
                settings.store_icon_url = ''
            elif err:
                flash(f'Store icon error: {err}', 'error')
        icon_url = _get_field('store_icon_url')
        settings.store_icon_url = icon_url
        if icon_url:
            settings.store_icon_asset_id = None
        elif not icon_file or not icon_file.filename:
            settings.store_icon_asset_id = None

        # Favicon upload — clear old value when field is emptied
        fav_file = request.files.get('favicon_file')
        if fav_file and fav_file.filename:
            asset, err = save_upload(fav_file)
            if asset:
                settings.favicon_asset_id = asset.id
                settings.favicon_url = ''
            elif err:
                flash(f'Favicon error: {err}', 'error')
        fav_url = _get_field('favicon_url')
        settings.favicon_url = fav_url
        if fav_url:
            settings.favicon_asset_id = None
        elif not fav_file or not fav_file.filename:
            settings.favicon_asset_id = None

        db.session.commit()
        log_activity('settings_update', 'store_settings', settings.id, 'Store settings updated')
        flash('Store settings saved.', 'success')
        return redirect(url_for('admin.store_settings'))

    return render_template('admin/settings.html', settings=settings)


# --- Media Library -----------------------------------------------------

@admin_bp.route('/media')
@login_required
def media_library():
    search = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')
    q = MediaAsset.query
    if search:
        q = q.filter(MediaAsset.original_filename.ilike(f'%{search}%'))
    if type_filter in ('image', 'apk'):
        q = q.filter_by(asset_type=type_filter)
    assets = q.order_by(MediaAsset.created_at.desc()).all()
    settings = get_store_settings()
    return render_template('admin/media.html', assets=assets, search=search,
                           type_filter=type_filter, settings=settings)


@admin_bp.route('/media/upload', methods=['POST'])
@login_required
def upload_media():
    files = request.files.getlist('files')
    uploaded = []
    errors = []
    for f in files:
        if f and f.filename:
            asset, err = save_upload(f)
            if asset:
                uploaded.append({'id': asset.id, 'filename': asset.filename, 'url': asset.url})
            else:
                errors.append(f'{f.filename}: {err}')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    return jsonify({'success': True, 'assets': uploaded})


@admin_bp.route('/media/<int:asset_id>/delete', methods=['POST'])
@login_required
def delete_media(asset_id):
    asset = MediaAsset.query.get_or_404(asset_id)
    # Remove file from disk
    upload_dir = current_app.config['UPLOAD_DIR']
    filepath = os.path.join(upload_dir, asset.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(asset)
    db.session.commit()
    log_activity('media_delete', 'media', asset_id, f'Deleted {asset.original_filename}')
    flash('Asset deleted.', 'success')
    return redirect(url_for('admin.media_library'))


# --- Activity Log -------------------------------------------------------

@admin_bp.route('/activity')
@login_required
def activity_log():
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(100).all()
    settings = get_store_settings()
    return render_template('admin/activity.html', logs=logs, settings=settings)


# --- Account & Security -------------------------------------------------

@admin_bp.route('/account')
@login_required
def account():
    admin = db.session.get(AdminUser, session['admin_user_id'])
    settings = get_store_settings()
    return render_template('admin/account.html', admin=admin, settings=settings)
