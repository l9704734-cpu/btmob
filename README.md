# Play Store CMS — Multi-APK Flask Admin

A professional content-management dashboard for managing multiple APK listings,
built with Flask, SQLAlchemy, and file-upload support.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Run the app
python run.py

# 3. Open http://localhost:5000 in your browser
# 4. First visit to /admin will prompt you to create an admin account
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-key-please-change` | Flask session secret key. **Set this in production.** |
| `DATABASE_URL` | `sqlite:///store.db` | SQLAlchemy database URI. |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded files. |
| `MAX_UPLOAD_SIZE` | `10485760` (10 MB) | Maximum upload file size in bytes. |
| `ADMIN_USERNAME` | `admin` | Pre-provisioned admin username (optional). |
| `ADMIN_PASSWORD` | *(none)* | Pre-provisioned admin password (optional). |
| `FLASK_DEBUG` | `0` | Set to `1` for debug mode. |
| `PORT` | `5000` | Server port. |
| `FLASK_COOKIE_SECURE` | `false` | Set `true` to enforce HTTPS-only cookies. |

## Admin Setup

On first launch, visiting `/admin` redirects to the admin setup page where you
create your first admin account. No default or demo credentials are exposed.

Alternatively, set `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables
before first run to auto-provision the admin user.

## Database

SQLite is used by default (`store.db` in the project directory). To use
PostgreSQL or MySQL, set `DATABASE_URL`:

```bash
export DATABASE_URL='postgresql://user:pass@localhost/playstore'
```

Tables are auto-created on startup. The `app_data.json` file from the old
prototype is auto-migrated into the first listing on first run.

## Admin Features

### Dashboard (`/admin`)
- Summary cards: total, published, draft, archived counts
- Recently updated listings table
- Recent activity log

### All APKs (`/admin/apps`)
- Searchable, filterable, sortable, paginated listing table
- Per-row actions: Edit, Preview, Duplicate, Publish/Unpublish, Archive/Restore, Delete
- Status badges (Published, Draft, Archived)

### APK Editor (`/admin/apps/new`, `/admin/apps/<id>/edit`)
Tabbed editor with 10 sections:

1. **Basic Info** — name, slug, developer, category, description, version, rating, status
2. **Download** — external URL or file upload, button label, button icon (upload/URL/position)
3. **Branding** — icon, hero, favicon (upload + URL), theme colors
4. **Screenshots** — repeatable items: add/remove/reorder, upload or URL, caption, alt text, visibility
5. **Features** — repeatable items: title, description, icon, sort order, visibility
6. **Reviews** — repeatable items: reviewer, avatar (upload/URL), rating 1-5, text, date
7. **Permissions** — repeatable items: name, explanation, icon, sort order
8. **Related Apps** — link to other listings or manual entries
9. **Custom Sections** — heading, body (text), optional image, sort order
10. **SEO & Advanced** — SEO title, meta description, canonical URL, social image, no-index

### Store Settings (`/admin/settings`)
- Store name, tagline, description
- Store icon (upload/URL) and favicon
- Default theme colors
- Footer text, contact email/website
- Default SEO title/description
- Default download button label

### Media Library (`/admin/media`)
- Upload images and APK files
- Search and filter by type
- View filename, dimensions, file size, upload date
- Copy URL, delete with confirmation
- Assets reusable across listings

### Activity Log (`/admin/activity`)
- Timestamped log of all admin actions

### Account & Security (`/admin/account`)
- View account info
- Change password (requires current password)

## Routes

### Public
| Method | Route | Description |
|---|---|---|
| GET | `/` | Store front page (all published listings) |
| GET | `/app/<slug>` | Single listing detail |
| GET | `/download/<slug>` | Download APK file |
| GET | `/media/<filename>` | Serve uploaded media |

### Auth
| Method | Route | Description |
|---|---|---|
| GET/POST | `/auth/login` | Login or initial setup |
| GET | `/auth/logout` | Logout |
| GET/POST | `/auth/change-password` | Change password |

### Admin (all require authentication)
| Method | Route | Description |
|---|---|---|
| GET | `/admin` | Dashboard |
| GET | `/admin/apps` | List all APKs (search, filter, paginate) |
| GET/POST | `/admin/apps/new` | Create new listing |
| GET/POST | `/admin/apps/<id>/edit` | Edit listing |
| GET | `/admin/apps/<id>/preview` | Preview listing |
| POST | `/admin/apps/<id>/duplicate` | Duplicate as draft |
| POST | `/admin/apps/<id>/publish` | Publish listing |
| POST | `/admin/apps/<id>/unpublish` | Set to draft |
| POST | `/admin/apps/<id>/archive` | Archive listing |
| POST | `/admin/apps/<id>/restore` | Restore from archive |
| POST | `/admin/apps/<id>/delete` | Delete listing |
| GET/POST | `/admin/settings` | Store-wide settings |
| GET/POST | `/admin/media` | Media library |
| POST | `/admin/media/upload` | Upload files (AJAX) |
| POST | `/admin/media/<id>/delete` | Delete media asset |
| GET | `/admin/activity` | Activity log |
| GET | `/admin/account` | Account settings |

## Security

- **No demo credentials** — admin account created on first visit or via env vars
- **Werkzeug password hashing** — passwords never stored in plaintext
- **CSRF protection** on all state-changing forms (Flask-WTF)
- **Session cookies** — HTTP-only, SameSite=Lax
- **Upload validation** — MIME type, extension, file size, safe filenames, path-traversal prevention
- **No Windows path** — the old `C:\inetpub\...` path is replaced with configurable upload directory
- **No admin link in public header** — the storefront does not expose the admin entry point

## Testing

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest tests/ -v
```

Tests cover:
- Authentication (unauthenticated access denied, login, logout, invalid login)
- Multi-listing creation and isolation
- Unique slug validation
- Draft/published/archived status lifecycle
- Screenshots, features, reviews, permissions, related apps, custom sections
- Upload validation (valid image, invalid file, APK upload)
- Legacy JSON migration
- Store settings
- Public storefront (only published, no admin link in header)
- CSRF token presence
- Data persistence across app restarts

## Migration from Legacy `app_data.json`

The old single-record `app_data.json` is automatically migrated on first run.
The existing Google Meet data becomes the first listing with slug `google-meet`.
Migration is idempotent — it won't re-create the listing if it already exists.

## File Structure

```
playstore/
├── app/
│   ├── __init__.py          # App factory, db init, csrf
│   ├── models.py            # SQLAlchemy models
│   ├── utils.py             # Upload validation, slug, migration
│   ├── views_auth.py        # Login, logout, password change
│   ├── views_public.py      # Storefront, listing, download
│   ├── views_admin.py       # Full CMS admin panel
│   ├── templates/
│   │   ├── admin/           # Admin templates (base, dashboard, apps, editor, etc.)
│   │   ├── auth/            # Login, setup, change password
│   │   └── public/          # Storefront, listing detail
│   └── static/
│       └── admin.css        # Admin CSS
├── tests/
│   └── test_playstore.py    # Full test suite
├── uploads/                 # Uploaded files (created at runtime)
├── run.py                   # Entry point
├── requirements.txt
└── README.md
```

## Known Limitations

- Drag-and-drop reordering uses sort-order numbers (no visual drag handles)
- Markdown rendering for custom sections is stored as plain text (not rendered as HTML for security)
- No rate limiting on login (lockout after 5 attempts, not time-based)
- SVG uploads are not sanitized server-side (treated as image type but not rendered as inline SVG)
- No thumbnail generation for media library (full-size images served)
