"""
Authentication blueprint — login, logout, password management.
"""
import os
from flask import (Blueprint, render_template, request, redirect,
                    url_for, session, flash, abort)
from app import db
from app.models import AdminUser, ActivityLog
from app.utils import log_activity

auth_bp = Blueprint('auth', __name__)

MAX_LOGIN_ATTEMPTS = 5


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    admin = AdminUser.query.first()
    if admin is None:
        # Auto-provision if env vars set; otherwise create a default admin
        username = os.environ.get('ADMIN_USERNAME')
        password = os.environ.get('ADMIN_PASSWORD')
        if not username or not password:
            # No admin exists yet — show setup page
            if request.method == 'POST' and request.form.get('setup_username') and request.form.get('setup_password'):
                u = request.form['setup_username'].strip()
                p = request.form['setup_password']
                if len(p) < 8:
                    return render_template('auth/setup.html', error='Password must be at least 8 characters.')
                admin = AdminUser(username=u)
                admin.set_password(p)
                db.session.add(admin)
                db.session.commit()
                ActivityLog.log('admin_create', 'admin_user', admin.id, f'Admin user {u} created')
                session['admin_user_id'] = admin.id
                return redirect(url_for('admin.dashboard'))
            return render_template('auth/setup.html')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        attempts = session.get('login_attempts', 0)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            return render_template('auth/login.html', error='Too many failed attempts. Please try again later.',
                                   locked_out=True)

        admin = AdminUser.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session.clear()
            session['admin_user_id'] = admin.id
            session['login_attempts'] = 0
            ActivityLog.log('login', 'admin_user', admin.id, f'User {username} logged in')
            return redirect(url_for('admin.dashboard'))
        else:
            session['login_attempts'] = attempts + 1
            remaining = MAX_LOGIN_ATTEMPTS - session['login_attempts']
            return render_template('auth/login.html', error=f'Invalid credentials. {remaining} attempts remaining.')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    uid = session.get('admin_user_id')
    if uid:
        ActivityLog.log('logout', 'admin_user', uid, 'User logged out')
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'admin_user_id' not in session:
        return redirect(url_for('auth.login'))
    admin = db.session.get(AdminUser, session['admin_user_id'])
    if not admin:
        session.clear()
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if not admin.check_password(current):
            return render_template('auth/change_password.html', error='Current password is incorrect.')
        if len(new) < 8:
            return render_template('auth/change_password.html', error='New password must be at least 8 characters.')
        if new != confirm:
            return render_template('auth/change_password.html', error='Passwords do not match.')

        admin.set_password(new)
        db.session.commit()
        ActivityLog.log('password_change', 'admin_user', admin.id, 'Password changed')
        return render_template('auth/change_password.html', success=True)

    return render_template('auth/change_password.html')
