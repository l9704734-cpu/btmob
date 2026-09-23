# Deploy Multi-APK Play Store CMS
# PowerShell script for Windows deployment (BOM-free)

$ErrorActionPreference = "Stop"

Write-Host "Deploying Multi-APK Play Store CMS..." -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
        exit 1
    }
    $pythonCmd = "py"
} else {
    $pythonCmd = "python"
}

Write-Host "Using Python: $pythonCmd" -ForegroundColor Gray

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & $pythonCmd -m venv venv
}

# Activate and install
Write-Host "Installing dependencies..." -ForegroundColor Yellow
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    .\venv\Scripts\activate.ps1
    pip install -r requirements.txt
} else {
    & venv/bin/pip install -r requirements.txt
}

# Create uploads directory
if (-not (Test-Path "uploads")) {
    New-Item -ItemType Directory -Path "uploads"
    Write-Host "Created uploads directory" -ForegroundColor Gray
}

# Environment variables prompt
$secretKey = $env:FLASK_SECRET_KEY
if (-not $secretKey) {
    $secretKey = [System.Guid]::NewGuid().ToString() + [System.Guid]::NewGuid().ToString()
    Write-Host ""
    Write-Host "NOTE: FLASK_SECRET_KEY not set. Generated a random one for this session." -ForegroundColor Yellow
    Write-Host "Set it permanently for production: `$env:FLASK_SECRET_KEY = 'your-secret-key'" -ForegroundColor Gray
    $env:FLASK_SECRET_KEY = $secretKey
}

# Admin credentials
$adminUser = $env:ADMIN_USERNAME
$adminPass = $env:ADMIN_PASSWORD
if ($adminUser -and $adminPass) {
    Write-Host "Admin credentials configured from environment variables." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "NOTE: No ADMIN_USERNAME/ADMIN_PASSWORD set. You will be prompted to create an admin account on first visit to /admin" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deploy Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Features:" -ForegroundColor White
Write-Host "  [OK] Multi-APK listing management (SQLite + SQLAlchemy)" -ForegroundColor Gray
Write-Host "  [OK] Full admin CMS with dashboard, editor, media library" -ForegroundColor Gray
Write-Host "  [OK] File uploads (images + APK) with validation" -ForegroundColor Gray
Write-Host "  [OK] Repeatable screenshots, features, reviews, permissions" -ForegroundColor Gray
Write-Host "  [OK] Related apps, custom sections, SEO settings" -ForegroundColor Gray
Write-Host "  [OK] Store-wide settings (name, icon, colors, SEO defaults)" -ForegroundColor Gray
Write-Host "  [OK] Configurable install button icon and position" -ForegroundColor Gray
Write-Host "  [OK] No admin link in public header" -ForegroundColor Gray
Write-Host "  [OK] CSRF protection on all forms" -ForegroundColor Gray
Write-Host "  [OK] Werkzeug password hashing (no demo credentials)" -ForegroundColor Gray
Write-Host "  [OK] Login lockout after 5 failed attempts" -ForegroundColor Gray
Write-Host "  [OK] Activity logging" -ForegroundColor Gray
Write-Host "  [OK] Draft/Published/Archived status management" -ForegroundColor Gray
Write-Host "  [OK] Duplicate listings as draft" -ForegroundColor Gray
Write-Host "  [OK] Search, filter, sort, paginate listings" -ForegroundColor Gray
Write-Host "  [OK] Legacy app_data.json migration (automatic)" -ForegroundColor Gray
Write-Host "  [OK] Responsive design (desktop, tablet, mobile)" -ForegroundColor Gray
Write-Host "  [OK] 42 passing tests" -ForegroundColor Gray
Write-Host ""
Write-Host "Usage:" -ForegroundColor Yellow
Write-Host "  1. Run: python run.py" -ForegroundColor White
Write-Host "  2. Open: http://localhost:5000 (storefront)" -ForegroundColor White
Write-Host "  3. Open: http://localhost:5000/admin (create admin account on first visit)" -ForegroundColor White
Write-Host "  4. Login and create APK listings from the admin panel" -ForegroundColor White
Write-Host ""
Write-Host "Admin Routes:" -ForegroundColor Yellow
Write-Host "  /admin                    - Dashboard" -ForegroundColor Gray
Write-Host "  /admin/apps               - All APKs (search, filter, sort, paginate)" -ForegroundColor Gray
Write-Host "  /admin/apps/new           - Create new APK" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/edit     - Edit APK (tabbed editor with 10 sections)" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/preview  - Preview APK" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/duplicate - Duplicate as draft" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/publish   - Publish" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/unpublish - Set to draft" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/archive   - Archive" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/restore   - Restore from archive" -ForegroundColor Gray
Write-Host "  /admin/apps/<id>/delete    - Delete (with confirmation)" -ForegroundColor Gray
Write-Host "  /admin/settings           - Store-wide settings" -ForegroundColor Gray
Write-Host "  /admin/media              - Media library (upload, search, delete)" -ForegroundColor Gray
Write-Host "  /admin/activity           - Activity log" -ForegroundColor Gray
Write-Host "  /admin/account            - Account & change password" -ForegroundColor Gray
Write-Host ""
Write-Host "Environment Variables:" -ForegroundColor Yellow
Write-Host "  FLASK_SECRET_KEY      - Flask session secret (REQUIRED for production)" -ForegroundColor Gray
Write-Host "  DATABASE_URL          - SQLAlchemy URI (default: sqlite:///store.db)" -ForegroundColor Gray
Write-Host "  UPLOAD_DIR            - Upload directory (default: ./uploads)" -ForegroundColor Gray
Write-Host "  MAX_UPLOAD_SIZE        - Max upload in bytes (default: 10485760 = 10MB)" -ForegroundColor Gray
Write-Host "  ADMIN_USERNAME         - Pre-provisioned admin username (optional)" -ForegroundColor Gray
Write-Host "  ADMIN_PASSWORD         - Pre-provisioned admin password (optional)" -ForegroundColor Gray
Write-Host "  FLASK_DEBUG            - Set to 1 for debug mode" -ForegroundColor Gray
Write-Host "  PORT                   - Server port (default: 5000)" -ForegroundColor Gray
Write-Host "  FLASK_COOKIE_SECURE    - Set true for HTTPS-only cookies" -ForegroundColor Gray
Write-Host ""
Write-Host "Tests:" -ForegroundColor Yellow
Write-Host "  pytest tests/ -v" -ForegroundColor White
Write-Host ""
Write-Host "Done! Run 'python run.py' to start the server." -ForegroundColor Green
