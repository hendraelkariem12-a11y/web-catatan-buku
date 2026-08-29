import os
import json
from flask import Flask, send_from_directory
from models import db, Tema, TongSampah

app = Flask(__name__)
app.secret_key = 'karya-dede-suhendra-secret-key-2026-upgraded'

# Konfigurasi Database Vercel Serverless
db_path = os.path.join('/tmp', 'karya_buku.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 86400

# Hubungkan SQLAlchemy dengan aplikasi Flask
db.init_app(app)

ADMIN_USER = "dede"
ADMIN_PASS = "suhendra123"

with app.app_context():
    db.create_all()
    if Tema.query.count() == 0:
        db.session.add_all([
            Tema(nama='Filsafat'),
            Tema(nama='Keuangan'),
            Tema(nama='Komunikasi')
        ])
        db.session.commit()

@app.route('/profile.jpg')
def serve_profile():
    return send_from_directory('.', 'profile.jpg')

def masukkan_sampah(tipe, data_dict):
    item = TongSampah(tipe=tipe, data_json=json.dumps(data_dict, ensure_ascii=False))
    db.session.add(item)
    db.session.commit()

# Daftarkan semua Blueprint fitur
from routes.esai import esai_bp
from routes.auth import auth_bp
from routes.buku import buku_bp
from routes.system import system_bp

app.register_blueprint(esai_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(buku_bp)
app.register_blueprint(system_bp)

if __name__ == '__main__':
    app.run(debug=True)
