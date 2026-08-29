from flask import Blueprint, request, redirect, render_template_string, session

auth_bp = Blueprint('auth', __name__)

from __main__ import ADMIN_USER, ADMIN_PASS, HTML_LOGIN

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            session['is_admin'] = True
            return redirect('/')
        else:
            return render_template_string(HTML_LOGIN, error="Username atau Password salah!")
    return render_template_string(HTML_LOGIN, error=None)

@auth_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')
