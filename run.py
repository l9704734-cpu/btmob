#!/usr/bin/env python3
"""Entry point for the Play Store Flask application."""
import os
from app import create_app
from app.utils import migrate_legacy_json
from app.models import AppListing

app = create_app()

# Auto-migrate legacy app_data.json on first run
with app.app_context():
    try:
        migrate_legacy_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_data.json'))
    except Exception as e:
        print(f'Migration warning: {e}')

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
