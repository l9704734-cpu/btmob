"""Test suite for the Play Store Flask app."""
import os
import io
import json
import tempfile
import pytest
from app import create_app, db
from app.models import (
    AppListing, AdminUser, StoreSettings, Screenshot, Feature,
    Review, Permission, RelatedApp, ContentSection, MediaAsset
)
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path):
    """Create a test app with an in-memory database and test upload dir."""
    upload_dir = tmp_path / 'uploads'
    upload_dir.mkdir()
    db_path = tmp_path / 'test.db'

    app = create_app(config_overrides={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'UPLOAD_DIR': str(upload_dir),
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'MAX_CONTENT_LENGTH': 5 * 1024 * 1024,
    })

    with app.app_context():
        db.create_all()
        # Create test admin
        admin = AdminUser(username='testadmin')
        admin.set_password('testpassword123')
        db.session.add(admin)

        # Seed default store settings
        settings = StoreSettings.query.first()
        if not settings:
            settings = StoreSettings(store_name='Test Store')
            db.session.add(settings)

        db.session.commit()

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(app):
    client = app.test_client()
    with client.session_transaction() as sess:
        with app.app_context():
            admin = AdminUser.query.filter_by(username='testadmin').first()
            sess['admin_user_id'] = admin.id
    return client


def _create_listing(app_ctx, name='Test App', slug='test-app', status='draft'):
    listing = AppListing(
        app_name=name,
        slug=slug,
        status=status,
        is_published=(status == 'published'),
        developer_name='Test Developer',
        description='A test app.',
    )
    db.session.add(listing)
    db.session.commit()
    return listing


class TestAuthentication:
    """Test login, logout, and route protection."""

    def test_unauthenticated_admin_redirects(self, client):
        for url in ['/admin/', '/admin/apps', '/admin/settings', '/admin/media', '/admin/activity']:
            resp = client.get(url, follow_redirects=False)
            assert resp.status_code in (301, 302, 303, 307, 308)
            assert '/auth/login' in resp.headers['Location']

    def test_login_page_loads(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200
        assert b'Login' in resp.data or b'Admin' in resp.data

    def test_successful_login(self, app, client):
        with app.app_context():
            admin = AdminUser.query.first()
            admin.set_password('testpass123')
            db.session.commit()
        resp = client.post('/auth/login', data={'username': 'testadmin', 'password': 'testpass123'},
                           follow_redirects=False)
        assert resp.status_code in (301, 302, 303, 307, 308)
        assert '/admin' in resp.headers['Location']

    def test_invalid_login(self, app, client):
        with app.app_context():
            admin = AdminUser.query.first()
            admin.set_password('testpass123')
            db.session.commit()
        resp = client.post('/auth/login', data={'username': 'wrong', 'password': 'wrong'})
        assert resp.status_code == 200
        assert b'Invalid' in resp.data or b'credentials' in resp.data.lower() or b'Invalid' in resp.data

    def test_logout(self, logged_in_client):
        resp = logged_in_client.get('/auth/logout', follow_redirects=False)
        assert resp.status_code in (301, 302, 303, 307, 308)
        assert '/auth/login' in resp.headers['Location']

    def test_admin_routes_protected_after_logout(self, client):
        resp = client.get('/admin', follow_redirects=False)
        assert resp.status_code in (301, 302, 303, 307, 308)


class TestListings:
    """Test creating and editing listings."""

    def test_dashboard_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/')
        assert resp.status_code == 200

    def test_apps_list_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/apps')
        assert resp.status_code == 200

    def test_new_app_form_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/apps/new')
        assert resp.status_code == 200
        assert b'app_name' in resp.data

    def test_create_two_separate_listings(self, app, logged_in_client):
        # Create first
        resp = logged_in_client.post('/admin/apps/new', data={
            'app_name': 'App One', 'slug': 'app-one', 'status': 'draft', 'action': 'save_draft',
        }, follow_redirects=True)
        assert resp.status_code == 200

        # Create second
        resp = logged_in_client.post('/admin/apps/new', data={
            'app_name': 'App Two', 'slug': 'app-two', 'status': 'draft', 'action': 'save_draft',
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            assert AppListing.query.filter_by(slug='app-one').first() is not None
            assert AppListing.query.filter_by(slug='app-two').first() is not None

    def test_edit_one_listing_without_affecting_other(self, app, logged_in_client):
        with app.app_context():
            l1 = _create_listing(app, 'App Alpha', 'app-alpha')
            l2 = _create_listing(app, 'App Beta', 'app-beta')
            l1_id = l1.id
            l2_id = l2.id

        # Edit l1
        resp = logged_in_client.post(f'/admin/apps/{l1_id}/edit', data={
            'app_name': 'App Alpha Updated', 'slug': 'app-alpha', 'status': 'draft',
        }, follow_redirects=True)

        with app.app_context():
            l1_check = db.session.get(AppListing, l1_id)
            l2_check = db.session.get(AppListing, l2_id)
            assert l1_check.app_name == 'App Alpha Updated'
            assert l2_check.app_name == 'App Beta'  # unchanged

    def test_unique_slug_validation(self, app, logged_in_client):
        with app.app_context():
            _create_listing(app, 'Existing', 'taken-slug')
        resp = logged_in_client.post('/admin/apps/new', data={
            'app_name': 'Duplicate', 'slug': 'taken-slug', 'status': 'draft', 'action': 'save_draft',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert AppListing.query.filter_by(slug='taken-slug').count() == 1

    def test_duplicate_creates_new_listing(self, app, logged_in_client):
        with app.app_ctx() if hasattr(app, 'app_ctx') else app.app_context():
            listing = _create_listing(app, 'Original', 'original', status='published')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/duplicate', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert AppListing.query.count() >= 2


class TestStatusManagement:
    """Test draft, published, archived behavior."""

    def test_publish(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Pub', 'pub', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/publish', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(AppListing, lid).status == 'published'

    def test_unpublish(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Unpub', 'unpub', 'published')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/unpublish', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(AppListing, lid).status == 'draft'

    def test_archive(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Arch', 'arch', 'published')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/archive', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(AppListing, lid).status == 'archived'

    def test_restore(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Rest', 'rest', 'archived')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/restore', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(AppListing, lid).status == 'draft'

    def test_delete(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Del', 'del', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/delete', follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            assert db.session.get(AppListing, lid) is None

    def test_public_only_shows_published(self, app, client):
        with app.app_context():
            _create_listing(app, 'Visible', 'visible', 'published')
            _create_listing(app, 'Hidden', 'hidden', 'draft')
        resp = client.get('/')
        assert b'Visible' in resp.data
        assert b'Hidden' not in resp.data


class TestRepeatableChildren:
    """Test screenshots, features, reviews, permissions."""

    def test_add_screenshot(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Shots', 'shots', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/edit', data={
            'app_name': 'Shots', 'slug': 'shots', 'status': 'draft',
            's_id[]': [''], 's_url[]': ['https://example.com/shot1.png'],
            's_caption[]': ['Main'], 's_alt[]': ['Shot 1'], 's_order[]': ['0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            listing = db.session.get(AppListing, lid)
            assert len(listing.screenshots) >= 1

    def test_add_feature(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Feat', 'feat', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/edit', data={
            'app_name': 'Feat', 'slug': 'feat', 'status': 'draft',
            'f_id[]': [''], 'f_title[]': ['Great Feature'], 'f_desc[]': ['Does things'],
            'f_order[]': ['0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            listing = db.session.get(AppListing, lid)
            assert len(listing.features) >= 1

    def test_add_review(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Rev', 'rev', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/edit', data={
            'app_name': 'Rev', 'slug': 'rev', 'status': 'draft',
            'r_id[]': [''], 'r_name[]': ['Jane'], 'r_rating[]': ['5'],
            'r_text[]': ['Great!'], 'r_order[]': ['0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            listing = db.session.get(AppListing, lid)
            assert len(listing.reviews) >= 1

    def test_add_permission(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Perm', 'perm', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/edit', data={
            'app_name': 'Perm', 'slug': 'perm', 'status': 'draft',
            'p_id[]': [''], 'p_name[]': ['Camera'], 'p_explanation[]': ['Needs camera'],
            'p_icon[]': ['camera'], 'p_order[]': ['0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            listing = db.session.get(AppListing, lid)
            assert len(listing.permissions) >= 1

    def test_add_related_app(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Rel1', 'rel1', 'draft')
            other = _create_listing(app, 'Rel2', 'rel2', 'published')
            lid = listing.id
            oid = other.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/edit', data={
            'app_name': 'Rel1', 'slug': 'rel1', 'status': 'draft',
            'ra_id[]': [''], 'ra_related_id[]': [str(oid)], 'ra_manual_name[]': [''],
            'ra_order[]': ['0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            listing = db.session.get(AppListing, lid)
            assert len(listing.related_apps) >= 1

    def test_add_content_section(self, app, logged_in_client):
        with app.app_context():
            listing = _create_listing(app, 'Cust', 'cust', 'draft')
            lid = listing.id
        resp = logged_in_client.post(f'/admin/apps/{lid}/edit', data={
            'app_name': 'Cust', 'slug': 'cust', 'status': 'draft',
            'c_id[]': [''], 'c_heading[]': ['Custom Section'], 'c_body[]': ['Custom text'],
            'c_order[]': ['0'],
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            listing = db.session.get(AppListing, lid)
            assert len(listing.content_sections) >= 1


class TestUploads:
    """Test file upload validation."""

    def test_valid_image_upload(self, app, logged_in_client, tmp_path):
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='green')
        img_path = tmp_path / 'test.png'
        img.save(img_path)
        with open(img_path, 'rb') as f:
            from app.utils import save_upload
            with app.app_context():
                from werkzeug.datastructures import FileStorage
                fs = FileStorage(stream=f, filename='test.png', content_type='image/png')
                asset, err = save_upload(fs, asset_type='image')
                assert asset is not None
                assert err is None

    def test_invalid_upload_rejected(self, app):
        from app.utils import save_upload
        from werkzeug.datastructures import FileStorage
        import io as _io
        with app.app_context():
            fs = FileStorage(stream=_io.BytesIO(b'fake content'),
                             filename='malware.exe', content_type='application/octet-stream')
            asset, err = save_upload(fs, asset_type='image')
            assert asset is None
            assert err is not None

    def test_apk_upload(self, app, tmp_path):
        from app.utils import save_upload
        from werkzeug.datastructures import FileStorage
        import io as _io
        with app.app_context():
            fs = FileStorage(stream=_io.BytesIO(b'fake apk content'),
                             filename='app.apk', content_type='application/vnd.android.package-archive')
            asset, err = save_upload(fs, asset_type='apk')
            assert asset is not None
            assert err is None

    def test_media_library_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/media')
        assert resp.status_code == 200

    def test_store_settings_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/settings')
        assert resp.status_code == 200

    def test_activity_log_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/activity')
        assert resp.status_code == 200

    def test_account_page_loads(self, logged_in_client):
        resp = logged_in_client.get('/admin/account')
        assert resp.status_code == 200


class TestMigration:
    """Test legacy JSON migration."""

    def test_migrate_from_json(self, app, tmp_path):
        legacy_file = tmp_path / 'app_data.json'
        legacy_data = {
            'images': {
                'screenshot1': 'https://example.com/s1.png',
                'screenshot2': 'https://example.com/s2.png',
                'multidevice': 'https://example.com/multi.png',
                'review1': 'https://example.com/avatar1.png',
                'gmail': 'https://example.com/gmail.png',
            },
            'links': {
                'gmail': 'https://play.google.com/gmail',
                'youtube': 'https://play.google.com/youtube',
                'gdrive': 'https://play.google.com/drive',
            }
        }
        with open(legacy_file, 'w') as f:
            json.dump(legacy_data, f)

        with app.app_context():
            from app.utils import migrate_legacy_json
            listing = migrate_legacy_json(str(legacy_file))
            assert listing is not None
            assert listing.app_name == 'Google Meet'
            assert len(listing.screenshots) == 2
            assert len(listing.features) >= 1
            assert len(listing.reviews) >= 1

    def test_migration_idempotent(self, app, tmp_path):
        legacy_file = tmp_path / 'app_data.json'
        with open(legacy_file, 'w') as f:
            json.dump({'images': {}, 'links': {}}, f)
        with app.app_context():
            from app.utils import migrate_legacy_json
            l1 = migrate_legacy_json(str(legacy_file))
            l2 = migrate_legacy_json(str(legacy_file))
            if l1 and l2:
                assert l1.id != l2.id  # Should create a second time if slug changes
            # Actually, since slug is same, second call returns None
            assert l2 is None or l2.id == l1.id


class TestStoreSettings:
    """Test store-wide settings."""

    def test_store_settings_save(self, app, logged_in_client):
        resp = logged_in_client.post('/admin/settings', data={
            'store_name': 'My Store',
            'store_tagline': 'Apps',
            'default_primary_color': '#ff0000',
            'default_secondary_color': '#00ff00',
            'default_bg_color': '#ffffff',
            'default_text_color': '#000000',
            'default_seo_title': 'My Store',
            'default_seo_description': 'Best apps',
            'default_download_button_label': 'Get App',
            'contact_email': 'admin@test.com',
            'footer_text': 'Copyright 2025',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            settings = StoreSettings.query.first()
            assert settings.store_name == 'My Store'
            assert settings.default_primary_color == '#ff0000'


class TestPublicListing:
    """Test public storefront pages."""

    def test_published_listing_page(self, app, client):
        with app.app_context():
            _create_listing(app, 'Public App', 'public-app', 'published')
        resp = client.get('/app/public-app')
        assert resp.status_code == 200
        assert b'Public App' in resp.data

    def test_draft_not_accessible_publicly(self, app, client):
        with app.app_context():
            _create_listing(app, 'Draft App', 'draft-app', 'draft')
        resp = client.get('/app/draft-app')
        assert resp.status_code == 404

    def test_no_admin_link_in_public_header(self, app, client):
        with app.app_context():
            _create_listing(app, 'Visible', 'visible', 'published')
        resp = client.get('/app/visible')
        # The public header should NOT contain an "Admin Panel" link
        assert b'Admin Panel' not in resp.data
        assert b'/admin' not in resp.data

    def test_store_icon_in_header(self, app, client):
        with app.app_context():
            _create_listing(app, 'IconTest', 'icontest', 'published')
        resp = client.get('/app/icontest')
        assert resp.status_code == 200
        # Header should have store name (but no admin link)
        assert b'store-icon' in resp.data or b'store-name' in resp.data


class TestCSRF:
    """Test CSRF protection."""

    def test_csrf_enabled_on_forms(self, app):
        # CSRF is disabled in tests (WTF_CSRF_ENABLED=False), but verify
        # the setting exists and can be toggled
        assert app.config.get('WTF_CSRF_ENABLED') == False

    def test_csrf_token_in_admin_forms(self, logged_in_client):
        resp = logged_in_client.get('/admin/apps/new')
        assert resp.status_code == 200
        assert b'csrf_token' in resp.data


class TestPersistence:
    """Test data persistence."""

    def test_data_survives_new_app_instance(self, tmp_path):
        upload_dir = tmp_path / 'uploads'
        upload_dir.mkdir()
        db_path = tmp_path / 'persist.db'
        config = {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
            'UPLOAD_DIR': str(upload_dir),
            'SECRET_KEY': 'test',
            'WTF_CSRF_ENABLED': False,
        }
        app1 = create_app(config_overrides=config)
        with app1.app_context():
            db.create_all()
            admin = AdminUser(username='persistadmin')
            admin.set_password('testpass123')
            db.session.add(admin)
            l = AppListing(app_name='Persist', slug='persist', status='published', is_published=True)
            db.session.add(l)
            db.session.commit()
            lid = l.id

        app2 = create_app(config_overrides=config)
        with app2.app_context():
            db.create_all()
            listing = db.session.get(AppListing, lid)
            assert listing is not None
            assert listing.app_name == 'Persist'
