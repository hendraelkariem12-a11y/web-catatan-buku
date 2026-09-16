import os 
import re
import json
import logging
import time
from collections import defaultdict
from io import BytesIO
from html import escape
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, session, Response, send_file, send_from_directory, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

# ReportLab, Docx, & Ebooklib untuk Fitur Ekspor Dokumen
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from docx import Document
from ebooklib import epub

app = Flask(__name__)
app.secret_key = 'karya-dede-suhendra-secret-key-2026-upgraded'

# ==================================================
# KONFIGURASI KEAMANAN CSRF & RATE LIMITING
# ==================================================
csrf = CSRFProtect(app)

login_attempts = defaultdict(list)

def cek_rate_limit_login(ip):
    sekarang = time.time()
    login_attempts[ip] = [t for t in login_attempts[ip] if sekarang - t < 60]
    if len(login_attempts[ip]) >= 5:
        return False
    login_attempts[ip].append(sekarang)
    return True

# Helper Pembersih Teks PDF (Prioritas Tinggi: Anti-Crash PDF)
def bersihkan_teks_pdf(teks):
    if not teks:
        return ""
    teks_bersih = re.sub(r'<[^>]+>', '', teks)
    return escape(teks_bersih).replace('\n', '<br/>')

# Helper Konversi Google Drive Link biasa ke Embed/Preview Stream Link
def convert_gdrive_url(url):
    if not url:
        return ""
    url = url.strip()
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/file/d/{file_id}/preview"
    return url

# ==================================================
# KONFIGURASI LOGGING SISTEM
# ==================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ==================================================
# KONFIGURASI FOLDER PENYIMPANAN PDF AMAN
# ==================================================
UPLOAD_PDF_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploaded_pdfs')
os.makedirs(UPLOAD_PDF_FOLDER, exist_ok=True)

# ==================================================
# KONFIGURASI DATABASE SUPABASE POSTGRESQL
# ==================================================
DEFAULT_SUPABASE_URL = "postgresql://postgres.mlzpbbvtufjvkpyddqvz:Sindanglaut74801@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"
DATABASE_URL = os.environ.get('DATABASE_URL', DEFAULT_SUPABASE_URL)

# Supabase terkadang memberikan URI postgres://, SQLAlchemy membutuhkan postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 86400

database_info = "Supabase PostgreSQL (Cloud Database)"

db = SQLAlchemy(app)

ADMIN_USER = "dede"
ADMIN_PASS_HASH = generate_password_hash("suhendra123")

# ==================================================
# MODEL DATABASE
# ==================================================
class Tema(db.Model):
    __tablename__ = 'tema'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    buku_list = db.relationship('Buku', backref='tema', lazy=True, cascade="all, delete-orphan")

class Buku(db.Model):
    __tablename__ = 'buku'
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    subjudul = db.Column(db.String(250), nullable=True)
    cover_url = db.Column(db.Text, nullable=True)
    kutipan = db.Column(db.Text, nullable=True)
    tema_id = db.Column(db.Integer, db.ForeignKey('tema.id'), nullable=False)
    status = db.Column(db.String(20), default='selesai')
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    catatan_list = db.relationship('Catatan', backref='buku', lazy=True, cascade="all, delete-orphan")

class Catatan(db.Model):
    __tablename__ = 'catatan'
    id = db.Column(db.Integer, primary_key=True)
    bagian = db.Column(db.String(100), nullable=True)
    judul_bab = db.Column(db.String(200), nullable=False)
    isi = db.Column(db.Text, nullable=False)
    urutan = db.Column(db.Integer, default=1)
    file_audio = db.Column(db.Text, nullable=True)
    buku_id = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    favorit = db.Column(db.Boolean, default=False)
    tag = db.Column(db.String(200), nullable=True)

class EsaiPenulis(db.Model):
    __tablename__ = 'esai_penulis'
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    kategori = db.Column(db.String(100), default="Refleksi Harian")
    isi = db.Column(db.Text, nullable=False)
    tanggal = db.Column(db.String(50), nullable=True)
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    favorit = db.Column(db.Boolean, default=False)

class Jurnal(db.Model):
    __tablename__ = 'jurnal'
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(250), nullable=False)
    penulis = db.Column(db.String(200), nullable=True)
    kategori = db.Column(db.String(100), default="Umum")
    file_pdf = db.Column(db.String(250), nullable=True)
    poin_penting = db.Column(db.Text, nullable=False)
    tanggal_baca = db.Column(db.DateTime, default=datetime.utcnow)

class TongSampah(db.Model):
    __tablename__ = 'tong_sampah'
    id = db.Column(db.Integer, primary_key=True)
    tipe = db.Column(db.String(20), nullable=False)
    data_json = db.Column(db.Text, nullable=False)
    dihapus_pada = db.Column(db.DateTime, default=datetime.utcnow)

class LogAktivitas(db.Model):
    __tablename__ = 'log_aktivitas'
    id = db.Column(db.Integer, primary_key=True)
    aksi = db.Column(db.String(200), nullable=False)
    keterangan = db.Column(db.Text, nullable=True)
    waktu = db.Column(db.DateTime, default=datetime.utcnow)

class PenandaBaca(db.Model):
    __tablename__ = 'penanda_baca'
    id = db.Column(db.Integer, primary_key=True)
    buku_id = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    catatan_id = db.Column(db.Integer, db.ForeignKey('catatan.id'), nullable=False)
    waktu_baca = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    buku = db.relationship('Buku', backref=db.backref('penanda', uselist=False, cascade="all, delete-orphan"))
    catatan = db.relationship('Catatan')

with app.app_context():
    db.create_all()
    if Tema.query.count() == 0:
        db.session.add_all([
            Tema(nama='Filsafat'),
            Tema(nama='Keuangan'),
            Tema(nama='Komunikasi')
        ])
        db.session.commit()
    
    if Buku.query.count() == 0 and os.path.exists('backup_karya.json'):
        try:
            with open('backup_karya.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                for t in data.get('tema', []):
                    if not Tema.query.get(t['id']):
                        db.session.add(Tema(id=t['id'], nama=t['nama']))
                for b in data.get('buku', []):
                    if not Buku.query.get(b['id']):
                        db.session.add(Buku(id=b['id'], judul=b['judul'], subjudul=b.get('subjudul'), cover_url=b.get('cover_url'), tema_id=b['tema_id'], kutipan=b.get('kutipan')))
                for c in data.get('catatan', []):
                    if not Catatan.query.get(c['id']):
                        db.session.add(Catatan(id=c['id'], bagian=c.get('bagian'), judul_bab=c['judul_bab'], isi=c['isi'], buku_id=c['buku_id'], urutan=c.get('urutan', 1), file_audio=c.get('file_audio')))
                for e in data.get('esai', []):
                    if not EsaiPenulis.query.get(e['id']):
                        db.session.add(EsaiPenulis(id=e['id'], judul=e['judul'], kategori=e.get('kategori', 'Refleksi'), isi=e['isi']))
                db.session.commit()
                app.logger.info("Auto-restore database ke Supabase dari file backup_karya.json berhasil dilakukan.")
        except Exception as err:
            db.session.rollback()
            app.logger.error(f"Gagal melakukan auto-restore: {str(err)}")

    app.logger.info(f"Database berhasil diinisialisasi menggunakan: {database_info}")

# ==================================================
# HELPER SYSTEM LOG & TRASH
# ==================================================
def masukkan_sampah(tipe, data_dict):
    item = TongSampah(tipe=tipe, data_json=json.dumps(data_dict, ensure_ascii=False))
    db.session.add(item)
    db.session.commit()

def catat_log(aksi, keterangan=""):
    log_baru = LogAktivitas(aksi=aksi, keterangan=keterangan)
    db.session.add(log_baru)
    db.session.commit()

# ==================================================
# ROUTE FILE MEDIA & STATIC
# ==================================================
@app.route('/profile.jpg')
def serve_profile():
    return send_from_directory('.', 'profile.jpg')

@app.route('/logo.png')
def serve_logo():
    return send_from_directory('static', 'logo.png')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.errorhandler(404)
def halaman_tidak_ditemukan(e):
    return """
    <!DOCTYPE html>
    <html lang="id">
    <head><meta charset="UTF-8"><title>404</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body style="background:#0b132b; color:#f8fafc; display:flex; justify-content:center; align-items:center; min-height:100vh; text-align:center;">
        <div style="max-width:450px; padding:30px; background:#1c2541; border:1px solid #334155; border-radius:18px;">
            <h1 class="text-warning fw-bold mb-2" style="font-size: 64px;">404</h1>
            <h4 class="mb-3 fw-bold">Halaman Tidak Ditemukan</h4>
            <a href="/" class="btn btn-outline-warning rounded-pill px-4 fw-bold text-white">&larr; Kembali ke Beranda</a>
        </div>
    </body>
    </html>
    """, 404

@app.errorhandler(500)
def kesalahan_server(e):
    return f"""
    <!DOCTYPE html>
    <html lang="id">
    <head><meta charset="UTF-8"><title>500</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body style="background:#0b132b; color:#f8fafc; display:flex; justify-content:center; align-items:center; min-height:100vh; text-align:center;">
        <div style="max-width:500px; padding:30px; background:#1c2541; border:1px solid #334155; border-radius:18px;">
            <h1 class="text-danger fw-bold mb-2" style="font-size: 64px;">500</h1>
            <h4 class="mb-3 fw-bold">Terjadi Kesalahan Server</h4>
            <div class="bg-dark p-2 rounded text-start small text-warning mb-4" style="max-height:120px; overflow-y:auto;">Detail: {escape(str(e))}</div>
            <a href="/" class="btn btn-outline-light rounded-pill px-4 fw-bold">&larr; Kembali ke Beranda</a>
        </div>
    </body>
    </html>
    """, 500

# ==================================================
# TEMPLATE CSS & JS SHARED
# ==================================================
CSS_SHARED = """
    :root { 
        --bg-paper: #f7f4ef; --card-paper: #ffffff; --text-main: #1e293b; --text-muted: #64748b;
        --gold-gradient: linear-gradient(135deg, #bf953f, #fcf6ba, #b38728, #fbf5b7);
        --border-color: rgba(212, 175, 55, 0.4); --input-bg: #ffffff; --input-text: #1e293b;
    }
    [data-theme="gelap"] {
        --bg-paper: #0b132b; --card-paper: #1c2541; --text-main: #f8fafc; --text-muted: #cbd5e1;
        --border-color: #334155; --input-bg: #1e293b; --input-text: #f8fafc;
    }
    body { background-color: var(--bg-paper) !important; font-family: 'Plus Jakarta Sans', sans-serif; color: var(--text-main) !important; transition: background-color 0.2s ease, color 0.2s ease; }
    h1, h2, h3, h4, h5, h6, p, div, label, span, small { color: inherit !important; }
    .text-muted { color: var(--text-muted) !important; }
    .header-title { font-family: 'Cinzel', serif; font-weight: 700; color: var(--text-main) !important; }
    .top-badge { background: #fcf8ec; color: #b38728 !important; border: 1px solid rgba(212,175,55,0.4); font-weight:700; padding:6px 16px; border-radius:30px; font-size:0.8rem; }
    .card-gold { background:var(--card-paper) !important; border-radius:18px; border:1px solid var(--border-color) !important; box-shadow:0 10px 25px rgba(0,0,0,0.03); transition:all 0.3s ease; position:relative; overflow:hidden; }
    .card-gold::before { content:''; position:absolute; top:0; left:0; width:100%; height:4px; background:var(--gold-gradient); }
    .card-gold:hover { transform:translateY(-4px); box-shadow:0 15px 30px rgba(212,175,55,0.18); }
    .btn-custom-outline { color: var(--text-main) !important; border-color: var(--border-color) !important; background: var(--card-paper) !important; }
    .btn-custom-outline:hover { background: #b38728 !important; color: #fff !important; }
    .search-box { position:relative; }
    .search-box input { padding-left:38px; background: var(--input-bg) !important; color: var(--input-text) !important; border-color: var(--border-color) !important; }
    .search-box i { position:absolute; left:12px; top:50%; transform:translateY(-50%); color:#888; }
    .badge-count { background:#b38728; color:white !important; border-radius:50%; width:22px; height:22px; display:inline-flex; align-items:center; justify-content:center; font-size:11px; margin-left:6px; }
    .btn-mode-toggle { position:fixed; top:15px; right:15px; z-index:100; border-radius:50%; width:44px; height:44px; display:flex; align-items:center; justify-content:center; background: var(--card-paper) !important; border: 2px solid #b38728 !important; color: #b38728 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
    
    .btn-to-top {
        position: fixed; bottom: 25px; right: 25px; z-index: 99;
        background: #b38728; color: white; border: none; border-radius: 50%;
        width: 48px; height: 48px; display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3); opacity: 0; transition: opacity 0.3s, transform 0.2s;
        cursor: pointer; pointer-events: none; text-decoration: none;
    }
    .btn-to-top.show { opacity: 1; pointer-events: auto; }
    .btn-to-top:hover { transform: scale(1.1); background: #96701f; color: white; }

    #reading-progress {
        position: fixed; top: 0; left: 0; height: 4px;
        background: linear-gradient(90deg, #bf953f, #fcf6ba, #b38728);
        width: 0%; z-index: 9999; transition: width 0.1s ease-out;
    }

    .note-card-badge { display: block; width: fit-content; background: rgba(56, 189, 248, 0.15); color: #38bdf8 !important; font-size: 11px; font-weight: 700; padding: 5px 12px; border-radius: 6px; text-transform: uppercase; margin-bottom: 8px; }
    .note-card-title { color: #b38728 !important; font-size: 20px; font-weight: 800; margin-top: 4px; margin-bottom: 12px; padding-right: 170px; }
    
    .markdown-body pre {
        background-color: #0f172a !important;
        color: #38bdf8 !important;
        padding: 14px 18px !important;
        border-radius: 12px !important;
        border: 1px solid #334155 !important;
        overflow-x: auto !important;
        margin: 15px 0 !important;
        box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.3);
    }

    .markdown-body code {
        font-family: 'Fira Code', 'Courier New', Consolas, monospace !important;
        font-size: 13.5px !important;
        color: inherit !important;
    }

    .markdown-body img {
        max-width: 100% !important;
        height: auto !important;
        border-radius: 12px;
        margin: 15px auto;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
        display: block;
    }

    .toc-box { background: rgba(179, 135, 40, 0.05); border: 1px dashed var(--border-color); border-radius: 12px; padding: 20px; margin-bottom: 25px; }
    .toc-section-title { font-size: 13px; font-weight: 800; text-transform: uppercase; color: #b38728; letter-spacing: 0.5px; margin-top: 14px; margin-bottom: 6px; border-bottom: 1px solid rgba(179, 135, 40, 0.2); padding-bottom: 3px; }
    .toc-section-title:first-child { margin-top: 0; }
    .toc-list { list-style-type: none; padding-left: 0; margin-bottom: 10px; }
    .toc-list li { margin-bottom: 5px; font-size: 13.5px; padding-left: 12px; }
    .toc-list a { color: var(--text-main); text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
    .toc-list a:hover { color: #b38728; text-decoration: underline; }

    .section-header-card { background: rgba(179, 135, 40, 0.12); border-left: 5px solid #b38728; border-radius: 10px; padding: 12px 18px; margin-top: 30px; margin-bottom: 15px; font-family: 'Cinzel', serif; font-weight: 800; color: #b38728 !important; font-size: 16px; text-transform: uppercase; }

    .audio-player-box {
        background: rgba(179, 135, 40, 0.08);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 12px 16px;
        margin-top: 15px;
        margin-bottom: 15px;
    }

    #splash-screen {
        position: fixed; top: 0; left: 0; width: 100%; height: 100vh;
        background: radial-gradient(circle at center, #1c2541 0%, #0b132b 100%);
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        z-index: 999999; transition: opacity 0.8s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.8s;
    }
    #splash-screen.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
    .splash-container { text-align: center; animation: zoomInSplash 0.8s ease-out; }
    .splash-title { font-family: 'Cinzel', serif; font-weight: 800; font-size: 22px; color: #fcf6ba !important; letter-spacing: 2px; margin-bottom: 5px; }
    .splash-subtitle { font-size: 12px; color: #94a3b8 !important; letter-spacing: 3px; text-transform: uppercase; font-weight: 600; }
    @keyframes zoomInSplash { from { opacity: 0; transform: scale(0.85); } to { opacity: 1; transform: scale(1); } }

    .app-header-logo {
        width: 100px !important; height: 100px !important;
        border-radius: 50% !important; object-fit: cover !important;
        border: 3px solid #b38728; padding: 3px; background: var(--card-paper);
        box-shadow: 0 8px 20px rgba(212, 175, 55, 0.25); margin: 0 auto 15px auto; display: block;
    }
"""

JS_THEME_SCRIPT = """
<script>
    (function() {
        const savedTheme = localStorage.getItem('theme_mode') || 'terang';
        document.documentElement.setAttribute('data-theme', savedTheme);
    })();

    document.addEventListener("DOMContentLoaded", function() {
        updateIcon();
        setupScrollTopBtn();
        window.addEventListener('scroll', function() {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            const progressBar = document.getElementById("reading-progress");
            if (progressBar) progressBar.style.width = scrolled + "%";
        });
    });

    window.addEventListener('load', function() {
        const splash = document.getElementById('splash-screen');
        if (splash) {
            setTimeout(function() { splash.classList.add('hidden'); }, 1200);
        }
    });

    function toggleModeInstan() {
        const currentTheme = document.documentElement.getAttribute('data-theme') === 'gelap' ? 'terang' : 'gelap';
        document.documentElement.setAttribute('data-theme', currentTheme);
        localStorage.setItem('theme_mode', currentTheme);
        updateIcon();
    }

    function updateIcon() {
        const icon = document.getElementById('icon-mode');
        if (icon) {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            icon.className = currentTheme === 'gelap' ? 'fa-solid fa-sun text-warning' : 'fa-solid fa-moon text-dark';
        }
    }

    function setupScrollTopBtn() {
        const btn = document.getElementById('btnScrollTop');
        if (!btn) return;
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) btn.classList.add('show');
            else btn.classList.remove('show');
        });
    }

    let deferredPrompt;
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
    });

    function manualInstallGuide() {
        if (deferredPrompt) deferredPrompt.prompt();
        else alert("Untuk menginstal aplikasi PWA di HP Anda:\\n\\n1. Ketuk titik tiga (⋮) di pojok kanan atas Chrome.\\n2. Pilih 'Tambahkan ke Layar Utama' / 'Instal Aplikasi'.");
    }
</script>
"""

# ==================================================
# TEMPLATE HTML KODE UTUH
# ==================================================
HTML_INDEX = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pustaka Karya & Catatan Dede Suhendra</title>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<div id="splash-screen">
    <div class="splash-container">
        <h1 class="splash-title">PUSTAKA KARYA</h1>
        <p class="splash-subtitle">DEDE SUHENDRA</p>
    </div>
</div>

<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-5" style="max-width: 900px;">
    <div class="text-center mb-4">
        <img src="/logo.png" onerror="this.src='/profile.jpg'" class="app-header-logo" alt="Logo">
        <span class="top-badge mb-2 d-inline-block"><i class="fa-solid fa-gem me-1"></i> Cloud Pustaka Supabase</span>
        <h1 class="header-title display-6">Pustaka Karya & Catatan</h1>
        <p class="text-muted small">Dokumentasi Pemikiran, Riset & Karya Tulis Dede Suhendra</p>
    </div>

    <!-- Search Box -->
    <form action="/cari" method="GET" class="search-box mb-4">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input type="text" name="q" class="form-control form-control-lg rounded-pill" placeholder="Cari bab, catatan, esai, atau jurnal..." required>
    </form>

    <!-- Navigation Bar -->
    <div class="d-flex flex-wrap gap-2 justify-content-center mb-4">
        <a href="/penulis" class="btn btn-custom-outline btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-user-pen me-1"></i> Profil Penulis</a>
        <a href="/catatan-penulis" class="btn btn-custom-outline btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-feather me-1"></i> Esai Penulis <span class="badge-count">{{ jumlah_esai }}</span></a>
        <a href="/jurnal" class="btn btn-custom-outline btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-book-bookmark me-1"></i> Koleksi Jurnal <span class="badge-count">{{ jumlah_jurnal }}</span></a>
        <a href="/baca-pdf" class="btn btn-custom-outline btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-file-pdf me-1"></i> PDF Reader</a>
        <a href="/favorit" class="btn btn-custom-outline btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-star me-1 text-warning"></i> Favorit</a>
        {% if is_admin %}
            <a href="/logout" class="btn btn-outline-danger btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-right-from-bracket me-1"></i> Logout Admin</a>
        {% else %}
            <a href="/login" class="btn btn-outline-warning btn-sm rounded-pill fw-bold px-3"><i class="fa-solid fa-lock me-1"></i> Login Admin</a>
        {% endif %}
    </div>

    <!-- Penanda Baca Aktif -->
    {% if penanda_list %}
    <div class="card-gold p-3 mb-4 rounded-4" style="border-left:4px solid #b38728 !important;">
        <h6 class="fw-bold text-warning mb-2 small"><i class="fa-solid fa-bookmark me-1"></i> Terakhir Dibaca:</h6>
        <div class="d-flex flex-wrap gap-2">
            {% for p in penanda_list %}
                <a href="/buku/{{ p.buku_id }}#bab-{{ p.catatan_id }}" class="btn btn-sm btn-outline-warning rounded-pill small">
                    📖 {{ p.buku.judul }} - Bab: {{ p.catatan.judul_bab }}
                </a>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <!-- Daftar Tema & Buku -->
    <div class="row g-4">
        {% for tema in tema_list %}
        <div class="col-12">
            <div class="card-gold p-4 rounded-4">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h3 class="h5 fw-bold text-warning mb-0" style="font-family:'Cinzel',serif;"><i class="fa-solid fa-folder-open me-2"></i>{{ tema.nama }}</h3>
                    <a href="/tema/{{ tema.id }}" class="btn btn-sm btn-custom-outline rounded-pill fw-bold px-3">Lihat Semua ({{ tema.buku_list|length }})</a>
                </div>
                <div class="row g-3">
                    {% for buku in tema.buku_list[:3] %}
                    <div class="col-md-4">
                        <div class="p-3 border rounded-3 h-100 d-flex flex-column justify-content-between" style="border-color:var(--border-color)!important;">
                            <div>
                                {% if buku.cover_url %}
                                <img src="{{ buku.cover_url }}" class="img-fluid rounded mb-2 style="max-height:120px; object-fit:cover; width:100%;">
                                {% endif %}
                                <h4 class="h6 fw-bold mb-1"><a href="/buku/{{ buku.id }}" class="text-decoration-none text-warning">{{ buku.judul }}</a></h4>
                                <p class="small text-muted mb-2">{{ buku.subjudul or '' }}</p>
                            </div>
                            <a href="/buku/{{ buku.id }}" class="btn btn-sm btn-outline-warning w-100 rounded-pill mt-2">Baca Buku &rarr;</a>
                        </div>
                    </div>
                    {% else %}
                    <p class="small text-muted mb-0">Belum ada buku dalam tema ini.</p>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>

<a href="#" id="btnScrollTop" class="btn-to-top" title="Ke Atas"><i class="fa-solid fa-arrow-up"></i></a>
</body>
</html>
"""

HTML_PENULIS = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Profil Penulis - Dede Suhendra</title>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-5" style="max-width:760px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Kembali ke Utama</a>
    
    <div class="card-gold p-4 mb-4 rounded-4" style="display:flex; gap:20px; align-items:center; flex-wrap:wrap;">
        <img src="/profile.jpg" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'" alt="Dede Suhendra" style="width:140px; height:140px; border-radius:50%; object-fit:cover; border:3px solid #b38728; margin:0 auto; display:block;">
        <div style="flex:1; min-width:250px;">
            <h2 class="h4 fw-bold text-warning mb-2" style="font-family:'Cinzel',serif;">👨‍💻 Profil Penulis</h2>
            <p class="small mb-2">Selamat datang di ruang pustaka pribadi karya dan catatan saya. Nama saya <strong>Dede Suhendra</strong>, lahir 8 Juli 2001, dari Subang.</p>
            <p class="small text-muted mb-0">Dokumentasi pemikiran, perjalanan belajar, riset harian, serta modul pembelajaran yang disusun terstruktur.</p>
        </div>
    </div>
    
    <div class="card-gold p-4 mb-4 rounded-4">
        <h4 class="h5 fw-bold text-warning mb-3">✍️ Perjuangan & Latar Belakang Penulisan</h4>
        <p class="small mb-2">Setiap tulisan lahir dari proses yang tidak instan. Di tengah padatnya aktivitas harian, setiap sisa waktu luang dimanfaatkan untuk tetap konsisten menulis dan mendokumentasikan ilmu.</p>
        <p class="small text-muted mb-0">Bagi saya, menulis bukan sekadar merangkai kata, melainkan bentuk pengikatan ilmu dan sarana merefleksikan pembelajaran hidup agar bermanfaat secara luas dan berkelanjutan.</p>
    </div>
    
    <div class="card-gold p-4 mb-4 rounded-4">
        <h4 class="h5 fw-bold text-warning mb-3">📜 Riwayat Pendidikan & Pengalaman</h4>
        <h6 class="fw-bold text-warning small mb-2">🎓 Pendidikan:</h6>
        <div style="border-left:2px solid var(--border-color); padding-left:15px; margin-bottom:15px;" class="small">
            <div class="mb-2"><strong>2013:</strong> SDN Sindang Laut II (Lulus SD)</div>
            <div class="mb-2"><strong>2013–2015:</strong> Ponpes Madinatul Musthofa</div>
            <div class="mb-2"><strong>2015–2016:</strong> Pondok Tahfidz Qur'an (Fokus Hafalan)</div>
            <div class="mb-2"><strong>2016–2019:</strong> Ponpes Madinatul Musthofa</div>
            <div class="mb-2"><strong>2019–2022:</strong> Pondok Modern Darussalam Gontor (KMI)</div>
            <div class="mb-2"><strong>2022–2023:</strong> Pengabdian Gontor & UNIDA Gontor</div>
            <div><strong>2023–2025:</strong> Pengajar Ponpes & STISQ AL-IHYA Subang</div>
        </div>
        <h6 class="fw-bold text-warning small mb-2">💼 Pengalaman Kerja & Khidmat:</h6>
        <div style="border-left:2px solid var(--border-color); padding-left:15px;" class="small">
            <div class="mb-2"><strong>2025:</strong> Gudang Shopee Tangerang (Logistik)</div>
            <div class="mb-2"><strong>2025:</strong> Karyawan Fotokopi Jakarta Pusat</div>
            <div class="mb-2"><strong>2025:</strong> Barista & Chef Bogor</div>
            <div><strong>Sekarang:</strong> Imam, Muadzin & Pengajar Al-Qur'an Tangerang</div>
        </div>
    </div>
    
    <div class="card-gold p-4 mb-4 rounded-4">
        <h4 class="h5 fw-bold text-warning mb-3">🎯 Visi & Misi Penulisan</h4>
        <p class="small mb-2"><strong>Visi:</strong> Menjadikan dokumentasi catatan pribadi sebagai sarana pengikat ilmu, pengembangan diri berkelanjutan, dan ladang manfaat terstruktur.</p>
        <p class="small fw-bold mb-1">Misi:</p>
        <ul class="small text-muted ps-3 mb-0">
            <li>Memanfaatkan setiap sisa waktu luang secara produktif untuk merangkai karya tulis dan modul bermanfaat.</li>
            <li>Memdokumentasikan pemahaman keagamaan, riset harian, dan keterampilan operasional secara rapi dan terbuka.</li>
            <li>Terus belajar dan memberikan dampak positif bagi santri, jamaah masjid, serta lingkungan sekitar.</li>
        </ul>
    </div>
    
    <div class="card-gold p-4 rounded-4">
        <h4 class="h5 fw-bold text-warning mb-3">🙏 Apresiasi & Rasa Syukur</h4>
        <p class="small text-muted mb-3">Rasa syukur dan terima kasih kepada orang-orang terkasih yang menjadi sumber kekuatan, doa, dan inspirasi:</p>
        <div class="row g-3">
            <div class="col-md-6"><div class="p-3 border rounded-3 h-100" style="border-color:var(--border-color)!important;"><strong class="text-warning">👨‍👦 Bapak Khairudin</strong><p class="small text-muted mb-0 mt-1">Doa, kerja keras, dan bimbingan tanpa henti.</p></div></div>
            <div class="col-md-6"><div class="p-3 border rounded-3 h-100" style="border-color:var(--border-color)!important;"><strong class="text-warning">💐 Ibu Sumini (Almarhumah)</strong><p class="small text-muted mb-0 mt-1">Semoga Allah mengampuni dan menempatkan di tempat terbaik.</p></div></div>
            <div class="col-md-6"><div class="p-3 border rounded-3 h-100" style="border-color:var(--border-color)!important;"><strong class="text-warning">👫 Siti Aisyah & Muhammad Naimul Ilmi</strong><p class="small text-muted mb-0 mt-1">Adik-adik tersayang, kebanggaan dan penyemangat.</p></div></div>
            <div class="col-md-6"><div class="p-3 border rounded-3 h-100" style="border-color:var(--border-color)!important;"><strong class="text-warning">👦 Muhammad Aji</strong><p class="small text-muted mb-0 mt-1">Kakak tercinta atas kebersamaan dan dukungan.</p></div></div>
            <div class="col-md-6"><div class="p-3 border rounded-3 h-100" style="border-color:var(--border-color)!important;"><strong class="text-warning">❤️ Sri Nur Safitri</strong><p class="small text-muted mb-0 mt-1">Perhatian, dorongan semangat, dan pendamping setia.</p></div></div>
            <div class="col-md-6"><div class="p-3 border rounded-3 h-100" style="border-color:var(--border-color)!important;"><strong class="text-warning">🤝 Sahabat & Kolega</strong><p class="small text-muted mb-0 mt-1">Dukungan dalam diskusi, perjuangan, dan kebersamaan.</p></div></div>
        </div>
    </div>
</div>
</body>
</html>
"""

HTML_LOGIN = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Login Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>""" + CSS_SHARED + """</style>
</head>
<body class="d-flex align-items-center justify-content-center min-vh-100">
<div class="card-gold p-4" style="max-width: 400px; width: 100%;">
    <h4 class="fw-bold text-center mb-3 text-warning">🔐 Authentikasi Admin</h4>
    {% if error %}
    <div class="alert alert-danger py-2 small">{{ error }}</div>
    {% endif %}
    <form action="/login" method="POST">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div class="mb-3">
            <label class="form-label small">Username</label>
            <input type="text" name="username" class="form-control" required>
        </div>
        <div class="mb-3">
            <label class="form-label small">Password</label>
            <input type="password" name="password" class="form-control" required>
        </div>
        <button type="submit" class="btn btn-warning text-dark fw-bold w-100">Login</button>
    </form>
</div>
</body>
</html>
"""

HTML_JURNAL = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Koleksi Jurnal & Artikel</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<div class="container py-5" style="max-width:850px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Kembali ke Beranda</a>
    <h2 class="h4 fw-bold text-warning mb-4"><i class="fa-solid fa-book-bookmark me-2"></i>Koleksi Jurnal & Ringkasan Referensi</h2>

    {% if is_admin %}
    <div class="card-gold p-4 mb-4 rounded-4">
        <h5 class="fw-bold text-warning mb-3">➕ Tambah Referensi Jurnal</h5>
        <form action="/tambah-jurnal" method="POST" enctype="multipart/form-data">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="mb-3">
                <input type="text" name="judul" class="form-control" placeholder="Judul Jurnal / Artikel" required>
            </div>
            <div class="row g-2 mb-3">
                <div class="col-md-6"><input type="text" name="penulis" class="form-control" placeholder="Penulis / Sumber"></div>
                <div class="col-md-6"><input type="text" name="kategori" class="form-control" placeholder="Kategori (misal: Agama, Sains)"></div>
            </div>
            <div class="mb-3">
                <textarea name="poin_penting" class="form-control" rows="3" placeholder="Poin penting & ringkasan isi..." required></textarea>
            </div>
            <div class="mb-3">
                <label class="form-label small text-muted">Upload File PDF (Opsional)</label>
                <input type="file" name="file_pdf" class="form-control" accept=".pdf">
            </div>
            <button type="submit" class="btn btn-warning text-dark fw-bold rounded-pill px-4">Simpan Jurnal</button>
        </form>
    </div>
    {% endif %}

    <div class="row g-3">
        {% for j in jurnal_list %}
        <div class="col-12">
            <div class="card-gold p-4 rounded-4">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h5 class="fw-bold text-warning mb-0">{{ j.judul }}</h5>
                    <span class="badge bg-warning text-dark">{{ j.kategori }}</span>
                </div>
                <p class="small text-muted mb-2">Penulis: {{ j.penulis or 'Tidak disebutkan' }}</p>
                <p class="small mb-3">{{ j.poin_penting }}</p>
                {% if j.file_pdf %}
                <a href="/file-pdf/{{ j.file_pdf }}" target="_blank" class="btn btn-sm btn-outline-warning rounded-pill"><i class="fa-solid fa-file-pdf me-1"></i> Buka File PDF</a>
                {% endif %}
            </div>
        </div>
        {% else %}
        <p class="text-muted">Belum ada jurnal yang ditambahkan.</p>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

HTML_BUKU_DETAIL = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>{{ buku.judul }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<div id="reading-progress"></div>
<div class="container py-5" style="max-width:850px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Beranda</a>
    
    <div class="card-gold p-4 mb-4 rounded-4">
        <h1 class="h3 fw-bold text-warning mb-2" style="font-family:'Cinzel',serif;">{{ buku.judul }}</h1>
        {% if buku.subjudul %}<p class="text-muted small mb-2">{{ buku.subjudul }}</p>{% endif %}
        {% if buku.kutipan %}<p class="fst-italic small border-start border-warning ps-3 my-2 text-warning">"{{ buku.kutipan }}"</p>{% endif %}
    </div>

    <!-- TOC Box -->
    <div class="toc-box mb-4">
        <h6 class="fw-bold text-warning mb-2"><i class="fa-solid fa-list-ol me-2"></i>Daftar Isi Buku</h6>
        <ul class="toc-list">
            {% for c in catatan_list %}
            <li><a href="#bab-{{ c.id }}"><i class="fa-solid fa-angle-right"></i> {{ c.judul_bab }}</a></li>
            {% endfor %}
        </ul>
    </div>

    {% if is_admin %}
    <div class="card-gold p-4 mb-4 rounded-4">
        <h5 class="fw-bold text-warning mb-3">➕ Tambah Catatan / Bab Baru</h5>
        <form action="/tambah-catatan" method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <input type="hidden" name="buku_id" value="{{ buku.id }}">
            <div class="row g-2 mb-3">
                <div class="col-md-4"><input type="text" name="bagian" class="form-control" placeholder="Bagian (misal: Bagian I)"></div>
                <div class="col-md-6"><input type="text" name="judul_bab" class="form-control" placeholder="Judul Bab" required></div>
                <div class="col-md-2"><input type="number" name="urutan" class="form-control" value="1" placeholder="Urutan"></div>
            </div>
            <div class="mb-3">
                <textarea name="isi" class="form-control markdown-body" rows="6" placeholder="Isi catatan (Mendukung Markdown)..." required></textarea>
            </div>
            <div class="mb-3">
                <input type="text" name="file_audio" class="form-control" placeholder="URL Google Drive Audio/Stream (Opsional)">
            </div>
            <button type="submit" class="btn btn-warning text-dark fw-bold rounded-pill px-4">Simpan Bab</button>
        </form>
    </div>
    {% endif %}

    <!-- Daftar Bab / Catatan -->
    {% for c in catatan_list %}
    <div class="card-gold p-4 mb-4 rounded-4 position-relative" id="bab-{{ c.id }}">
        <span class="note-card-badge">{{ c.bagian or 'BAB' }}</span>
        <h3 class="note-card-title">{{ c.judul_bab }}</h3>
        
        <div class="markdown-body mb-3">
            {{ c.isi|replace('\n', '<br>')|safe }}
        </div>

        {% if c.file_audio %}
        <div class="audio-player-box">
            <small class="fw-bold text-warning d-block mb-1"><i class="fa-solid fa-headphones me-1"></i> Audio Penjelas / Murattal</small>
            <iframe src="{{ c.file_audio }}" width="100%" height="60" frameborder="0"></iframe>
        </div>
        {% endif %}

        <div class="d-flex justify-content-between align-items-center border-top pt-3 mt-3" style="border-color:var(--border-color)!important;">
            <form action="/tandai-baca/{{ c.id }}" method="POST" class="d-inline">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button type="submit" class="btn btn-sm btn-outline-warning rounded-pill"><i class="fa-solid fa-bookmark me-1"></i> Tandai Terakhir Dibaca</button>
            </form>
            <small class="text-muted">Urutan: {{ c.urutan }}</small>
        </div>
    </div>
    {% else %}
    <p class="text-muted">Belum ada catatan pada buku ini.</p>
    {% endfor %}
</div>
</body>
</html>
"""

HTML_TEMA = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Tema: {{ tema.nama }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
</head>
<body>
<div class="container py-5" style="max-width:850px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Kembali ke Beranda</a>
    <h2 class="h4 fw-bold text-warning mb-4"><i class="fa-solid fa-folder me-2"></i>Koleksi Buku Tema: {{ tema.nama }}</h2>
    
    <div class="row g-3">
        {% for b in buku_list %}
        <div class="col-md-6">
            <div class="card-gold p-4 rounded-4 h-100">
                <h5 class="fw-bold text-warning mb-2"><a href="/buku/{{ b.id }}" class="text-decoration-none text-warning">{{ b.judul }}</a></h5>
                <p class="small text-muted mb-3">{{ b.subjudul or '' }}</p>
                <a href="/buku/{{ b.id }}" class="btn btn-sm btn-outline-warning rounded-pill">Buka Buku &rarr;</a>
            </div>
        </div>
        {% else %}
        <p class="text-muted">Belum ada buku untuk tema ini.</p>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

HTML_ESAI_PENULIS = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Esai & Refleksi Penulis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
</head>
<body>
<div class="container py-5" style="max-width:800px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Beranda</a>
    <h2 class="h4 fw-bold text-warning mb-4"><i class="fa-solid fa-feather me-2"></i>Esai & Refleksi Harian</h2>

    <div class="row g-3">
        {% for e in esai_list %}
        <div class="col-12">
            <div class="card-gold p-4 rounded-4">
                <span class="badge bg-warning text-dark mb-2">{{ e.kategori }}</span>
                <h4 class="h5 fw-bold text-warning mb-2">{{ e.judul }}</h4>
                <div class="markdown-body text-main mb-2">{{ e.isi|replace('\n', '<br>')|safe }}</div>
                <small class="text-muted">{{ e.dibuat_pada.strftime('%d %B %Y') }}</small>
            </div>
        </div>
        {% else %}
        <p class="text-muted">Belum ada esai yang dipublikasikan.</p>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

HTML_HASIL_CARI = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Hasil Pencarian</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>""" + CSS_SHARED + """</style>
</head>
<body>
<div class="container py-5" style="max-width:800px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Beranda</a>
    <h3 class="h5 fw-bold text-warning mb-4">🔍 Hasil Pencarian: "{{ query }}"</h3>

    <h6 class="fw-bold text-warning mt-4">📖 Bab & Catatan Buku:</h6>
    {% for c in hasil_catatan %}
    <div class="card-gold p-3 mb-2 rounded-3">
        <a href="/buku/{{ c.buku_id }}#bab-{{ c.id }}" class="fw-bold text-warning text-decoration-none">{{ c.judul_bab }}</a>
    </div>
    {% else %}
    <p class="small text-muted">Tidak ditemukan di bab buku.</p>
    {% endfor %}

    <h6 class="fw-bold text-warning mt-4">📚 Jurnal & Referensi:</h6>
    {% for j in hasil_jurnal %}
    <div class="card-gold p-3 mb-2 rounded-3">
        <span class="fw-bold text-warning">{{ j.judul }}</span>
    </div>
    {% else %}
    <p class="small text-muted">Tidak ditemukan di jurnal.</p>
    {% endfor %}
</div>
</body>
</html>
"""

HTML_PDF_VIEWER = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>PDF Viewer Cloud</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>""" + CSS_SHARED + """</style>
</head>
<body>
<div class="container py-5" style="max-width:900px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Beranda</a>
    <h2 class="h4 fw-bold text-warning mb-3">📄 Pembaca Dokumen PDF</h2>
    
    {% if url_pdf %}
    <iframe src="{{ url_pdf }}" width="100%" height="600" style="border:1px solid var(--border-color); border-radius:12px;"></iframe>
    {% else %}
    <div class="card-gold p-4 rounded-4 text-center">
        <p class="text-muted">Pilih dokumen PDF yang tersedia di daftar jurnal Anda.</p>
    </div>
    {% endif %}
</div>
</body>
</html>
"""

HTML_FAVORIT = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Catatan Favorit</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>""" + CSS_SHARED + """</style>
</head>
<body>
<div class="container py-5" style="max-width:800px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Beranda</a>
    <h2 class="h4 fw-bold text-warning mb-4">⭐ Catatan Favorit</h2>
    {% for c in catatan_favorit %}
    <div class="card-gold p-4 mb-3 rounded-4">
        <h5 class="fw-bold text-warning"><a href="/buku/{{ c.buku_id }}#bab-{{ c.id }}" class="text-decoration-none text-warning">{{ c.judul_bab }}</a></h5>
    </div>
    {% else %}
    <p class="text-muted">Belum ada catatan yang ditandai sebagai favorit.</p>
    {% endfor %}
</div>
</body>
</html>
"""

# ==================================================
# CONTROLLER & ROUTES APLIKASI
# ==================================================
@app.route('/')
def index():
    tema_list = Tema.query.order_by(Tema.id.asc()).all()
    jumlah_jurnal = Jurnal.query.count()
    jumlah_esai = EsaiPenulis.query.count()
    penanda_list = PenandaBaca.query.order_by(PenandaBaca.waktu_baca.desc()).all()
    is_admin = session.get('is_admin', False)
    return render_template_string(
        HTML_INDEX, 
        tema_list=tema_list, 
        jumlah_jurnal=jumlah_jurnal, 
        jumlah_esai=jumlah_esai, 
        penanda_list=penanda_list, 
        is_admin=is_admin
    )

@app.route('/penulis')
def profil_penulis():
    return render_template_string(HTML_PENULIS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        ip = request.remote_addr
        if not cek_rate_limit_login(ip):
            error = "Terlalu banyak percobaan login. Silakan tunggu 1 menit."
            return render_template_string(HTML_LOGIN, error=error)
            
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, password):
            session['is_admin'] = True
            catat_log("Login Admin", f"IP: {ip}")
            return redirect('/')
        else:
            error = "Username atau password salah."
    return render_template_string(HTML_LOGIN, error=error)

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')

@app.route('/jurnal')
def koleksi_jurnal():
    jurnal_list = Jurnal.query.order_by(Jurnal.tanggal_baca.desc()).all()
    is_admin = session.get('is_admin', False)
    return render_template_string(HTML_JURNAL, jurnal_list=jurnal_list, is_admin=is_admin)

@app.route('/tambah-jurnal', methods=['POST'])
def tambah_jurnal():
    if not session.get('is_admin'):
        return redirect('/')
    judul = request.form.get('judul')
    penulis = request.form.get('penulis')
    kategori = request.form.get('kategori') or "Umum"
    poin_penting = request.form.get('poin_penting')
    
    filename = None
    file = request.files.get('file_pdf')
    if file and file.filename.endswith('.pdf'):
        filename = f"{int(time.time())}_{file.filename}"
        file.save(os.path.join(UPLOAD_PDF_FOLDER, filename))

    jurnal_baru = Jurnal(
        judul=judul,
        penulis=penulis,
        kategori=kategori,
        poin_penting=poin_penting,
        file_pdf=filename
    )
    db.session.add(jurnal_baru)
    db.session.commit()
    catat_log("Tambah Jurnal", f"Judul: {judul}")
    return redirect('/jurnal')

@app.route('/buku/<int:buku_id>')
def detail_buku(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    catatan_list = Catatan.query.filter_by(buku_id=buku.id).order_by(Catatan.urutan.asc()).all()
    
    catatan_grouped = defaultdict(list)
    for c in catatan_list:
        bagian = c.bagian if c.bagian else "Utama"
        catatan_grouped[bagian].append(c)

    penanda_aktif = PenandaBaca.query.filter_by(buku_id=buku.id).first()
    is_admin = session.get('is_admin', False)
    
    return render_template_string(
        HTML_BUKU_DETAIL,
        buku=buku,
        catatan_list=catatan_list,
        catatan_grouped=catatan_grouped,
        penanda_aktif=penanda_aktif,
        is_admin=is_admin
    )

@app.route('/tema/<int:tema_id>')
def detail_tema(tema_id):
    tema = Tema.query.get_or_404(tema_id)
    buku_list = Buku.query.filter_by(tema_id=tema.id).all()
    semua_tema = Tema.query.all()
    is_admin = session.get('is_admin', False)
    return render_template_string(HTML_TEMA, tema=tema, buku_list=buku_list, semua_tema=semua_tema, is_admin=is_admin)

@app.route('/catatan-penulis')
def esai_penulis():
    esai_list = EsaiPenulis.query.order_by(EsaiPenulis.dibuat_pada.desc()).all()
    is_admin = session.get('is_admin', False)
    return render_template_string(HTML_ESAI_PENULIS, esai_list=esai_list, is_admin=is_admin)

@app.route('/tambah-catatan', methods=['POST'])
def tambah_catatan():
    if not session.get('is_admin'):
        return redirect('/')
    buku_id = request.form.get('buku_id')
    bagian = request.form.get('bagian')
    judul_bab = request.form.get('judul_bab')
    isi = request.form.get('isi')
    urutan = int(request.form.get('urutan', 1))
    file_audio = convert_gdrive_url(request.form.get('file_audio'))

    c = Catatan(buku_id=buku_id, bagian=bagian, judul_bab=judul_bab, isi=isi, urutan=urutan, file_audio=file_audio)
    db.session.add(c)
    db.session.commit()
    return redirect(f'/buku/{buku_id}')

@app.route('/cari')
def cari():
    q = request.args.get('q', '')
    hasil_catatan = Catatan.query.filter((Catatan.isi.ilike(f'%{q}%')) | (Catatan.judul_bab.ilike(f'%{q}%'))).all()
    hasil_jurnal = Jurnal.query.filter((Jurnal.poin_penting.ilike(f'%{q}%')) | (Jurnal.judul.ilike(f'%{q}%'))).all()
    hasil_esai = EsaiPenulis.query.filter((EsaiPenulis.isi.ilike(f'%{q}%')) | (EsaiPenulis.judul.ilike(f'%{q}%'))).all()
    return render_template_string(
        HTML_HASIL_CARI, 
        query=q, 
        hasil_catatan=hasil_catatan, 
        hasil_jurnal=hasil_jurnal, 
        hasil_esai=hasil_esai
    )

@app.route('/baca-pdf')
def viewer_pdf():
    nama_file = request.args.get('nama', 'Pilih file PDF di bawah')
    daftar_file = os.listdir(UPLOAD_PDF_FOLDER)
    url_pdf = None
    if nama_file != 'Pilih file PDF di bawah' and nama_file in daftar_file:
        url_pdf = f"/file-pdf/{nama_file}"
    is_admin = session.get('is_admin', False)
    return render_template_string(HTML_PDF_VIEWER, nama_file=nama_file, daftar_file=daftar_file, url_pdf=url_pdf, is_admin=is_admin)

@app.route('/file-pdf/<filename>')
def serve_pdf(filename):
    return send_from_directory(UPLOAD_PDF_FOLDER, filename)

@app.route('/favorit')
def favorit_page():
    catatan_favorit = Catatan.query.filter_by(favorit=True).all()
    return render_template_string(HTML_FAVORIT, catatan_favorit=catatan_favorit)

@app.route('/tandai-baca/<int:catatan_id>', methods=['POST'])
def tandai_baca(catatan_id):
    catatan = Catatan.query.get_or_404(catatan_id)
    PenandaBaca.query.filter_by(buku_id=catatan.buku_id).delete()
    penanda = PenandaBaca(buku_id=catatan.buku_id, catatan_id=catatan_id)
    db.session.add(penanda)
    db.session.commit()
    return redirect(f'/buku/{catatan.buku_id}#bab-{catatan_id}')

# ==================================================
# RUN APP SERVER
# ==================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
