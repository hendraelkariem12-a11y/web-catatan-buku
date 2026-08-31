import os
import re
import json
import logging
import time
from collections import defaultdict
from io import BytesIO
from html import escape
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, session, Response, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

# ReportLab, Docx, & Ebooklib untuk Fitur Cetak / Ekspor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from docx import Document
from ebooklib import epub

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'karya-dede-suhendra-secret-key-2026-upgraded')

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

# ==================================================
# KONFIGURASI LOGGING SISTEM & FOLDER UPLOAD
# ==================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

UPLOAD_PDF_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploaded_pdfs')
os.makedirs(UPLOAD_PDF_FOLDER, exist_ok=True)

# ==================================================
# KONFIGURASI DATABASE
# ==================================================
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'karya_buku.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 86400

db = SQLAlchemy(app)

ADMIN_USER = os.environ.get('ADMIN_USER', 'dede')
ADMIN_PASS_HASH = generate_password_hash(os.environ.get('ADMIN_PASS', 'suhendra123'))

# ==================================================
# MODEL DATABASE
# ==================================================
class Tema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    buku_list = db.relationship('Buku', backref='tema', lazy=True, cascade="all, delete-orphan")

class Buku(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    subjudul = db.Column(db.String(250), nullable=True)
    kutipan = db.Column(db.Text, nullable=True)
    tema_id = db.Column(db.Integer, db.ForeignKey('tema.id'), nullable=False)
    status = db.Column(db.String(20), default='selesai')
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    catatan_list = db.relationship('Catatan', backref='buku', lazy=True, cascade="all, delete-orphan")

class Catatan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bagian = db.Column(db.String(100), nullable=True)
    judul_bab = db.Column(db.String(200), nullable=False)
    isi = db.Column(db.Text, nullable=False)
    urutan = db.Column(db.Integer, default=1)
    buku_id = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    favorit = db.Column(db.Boolean, default=False)
    tag = db.Column(db.String(200), nullable=True)

class EsaiPenulis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    kategori = db.Column(db.String(100), default="Refleksi Harian")
    isi = db.Column(db.Text, nullable=False)
    tanggal = db.Column(db.String(50), nullable=True)
    dibuat_pada = db.Column(db.DateTime, default=datetime.utcnow)
    diupdate_pada = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    favorit = db.Column(db.Boolean, default=False)

class TongSampah(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipe = db.Column(db.String(20), nullable=False)
    data_json = db.Column(db.Text, nullable=False)
    dihapus_pada = db.Column(db.DateTime, default=datetime.utcnow)

class LogAktivitas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aksi = db.Column(db.String(200), nullable=False)
    keterangan = db.Column(db.Text, nullable=True)
    waktu = db.Column(db.DateTime, default=datetime.utcnow)

class PenandaBaca(db.Model):
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

@app.route('/profile.jpg')
def serve_profile():
    return send_from_directory('.', 'profile.jpg')

def masukkan_sampah(tipe, data_dict):
    item = TongSampah(tipe=tipe, data_json=json.dumps(data_dict, ensure_ascii=False))
    db.session.add(item)
    db.session.commit()

def catat_log(aksi, keterangan=""):
    log_baru = LogAktivitas(aksi=aksi, keterangan=keterangan)
    db.session.add(log_baru)
    db.session.commit()

# ==================================================
# CSS & JAVASCRIPT SHARED
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
    .toc-box { background: rgba(179, 135, 40, 0.05); border: 1px dashed var(--border-color); border-radius: 12px; padding: 20px; margin-bottom: 25px; }
    .toc-section-title { font-size: 13px; font-weight: 800; text-transform: uppercase; color: #b38728; letter-spacing: 0.5px; margin-top: 14px; margin-bottom: 6px; border-bottom: 1px solid rgba(179, 135, 40, 0.2); padding-bottom: 3px; }
    .toc-section-title:first-child { margin-top: 0; }
    .toc-list { list-style-type: none; padding-left: 0; margin-bottom: 10px; }
    .toc-list li { margin-bottom: 5px; font-size: 13.5px; padding-left: 12px; }
    .toc-list a { color: var(--text-main); text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
    .toc-list a:hover { color: #b38728; text-decoration: underline; }
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
            if (progressBar) {
                progressBar.style.width = scrolled + "%";
            }
        });
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
            if (window.pageYOffset > 300) {
                btn.classList.add('show');
            } else {
                btn.classList.remove('show');
            }
        });
    }
</script>
"""

# ==================================================
# TEMPLATE HTML
# ==================================================
HTML_INDEX = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Perpustakaan Karya - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<a href="#" class="btn-to-top" id="btnScrollTop" title="Kembali ke Atas"><i class="fa-solid fa-arrow-up"></i></a>

<div class="container py-5" style="max-width:850px;">
    <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <a href="/penulis" class="btn btn-custom-outline rounded-pill btn-sm px-3 fw-bold"><i class="fa-solid fa-user-tie me-1"></i> Profil Penulis</a>
        <div class="d-flex gap-2 align-items-center flex-wrap">
            <a href="/favorit" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-star me-1 text-warning"></i> Favorit</a>
            <a href="/baca-pdf" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-book-open me-1 text-danger"></i> PDF Reader</a>
            <a href="/statistik" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-chart-simple me-1 text-info"></i> Statistik</a>
            <a href="/tong-sampah" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-trash-can me-1 text-secondary"></i> Sampah</a>
            {% if is_admin %}
                <a href="/riwayat-log" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-list-check me-1 text-warning"></i> Log</a>
                <a href="/backup" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-download me-1 text-primary"></i> Backup</a>
                <button type="button" class="btn btn-custom-outline rounded-pill btn-sm fw-bold text-success" data-bs-toggle="modal" data-bs-target="#restoreModal"><i class="fa-solid fa-upload me-1"></i> Restore</button>
                <a href="/logout" class="btn btn-warning rounded-pill btn-sm fw-bold text-dark"><i class="fa-solid fa-right-from-bracket me-1"></i> Logout</a>
            {% else %}
                <a href="/login" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-lock me-1"></i> Login</a>
            {% endif %}
        </div>
    </div>

    {% if penanda_list %}
    <div class="card-gold p-3 mb-4 rounded-4 border-warning">
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
            <div class="d-flex align-items-center">
                <div class="bg-warning text-dark rounded-circle p-2 me-3"><i class="fa-solid fa-bookmark fs-5"></i></div>
                <div>
                    <span class="badge bg-warning text-dark fw-bold mb-1">LANJUTKAN MEMBACA</span>
                    <h6 class="mb-0 fw-bold">Posisi Terakhir: {{ penanda_list[0].catatan.judul_bab }}</h6>
                    <small class="text-muted">Buku: <strong>{{ penanda_list[0].buku.judul }}</strong></small>
                </div>
            </div>
            <a href="/buku/{{ penanda_list[0].buku_id }}" class="btn btn-warning btn-sm text-dark rounded-pill fw-bold px-3">
                <i class="fa-solid fa-play me-1"></i> Lanjut Baca
            </a>
        </div>
    </div>
    {% endif %}

    <div class="text-center mb-5">
        <span class="top-badge mb-2">OFFICIAL VAULT</span>
        <h1 class="header-title h2 mb-2">Catatan & Karya Buku</h1>
        <p class="text-muted small">Disusun & Dikelola oleh <strong>Dede Suhendra</strong></p>
    </div>

    <div class="card-gold p-3 mb-4 rounded-3">
        <form action="/cari" method="GET" class="search-box mb-0">
            <i class="fa-solid fa-magnifying-glass"></i>
            <input type="text" name="q" class="form-control form-control-sm" placeholder="Cari kata kunci dalam isi bab/naskah (Tekan Enter)...">
        </form>
    </div>

    {% if is_admin %}
    <div class="card-gold p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-success mb-2"><i class="fa-solid fa-folder-plus me-1"></i> Tambah Tema Baru</h6>
        <form action="/tambah-tema" method="POST" class="row g-2">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="col-9"><input type="text" name="nama" class="form-control form-control-sm" placeholder="Misal: Psikologi..." required></div>
            <div class="col-3"><button type="submit" class="btn btn-success btn-sm w-100 fw-bold">Tambah</button></div>
        </form>
    </div>
    {% endif %}

    <h5 class="fw-bold mb-3" style="font-family:'Cinzel',serif;">Pilih Kategori Karya:</h5>
    <div class="row g-3" id="daftar-kategori">
        <div class="col-12">
            <a href="/catatan-penulis" class="text-decoration-none">
                <div class="card-gold p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <div class="bg-warning text-dark rounded-circle p-3 me-3"><i class="fa-solid fa-feather-pointed fs-4"></i></div>
                            <div>
                                <span class="badge bg-warning text-dark fw-bold mb-1">Ruang Refleksi</span>
                                <h4 class="h5 mb-1 fw-bold">✍️ Jurnal & Esai Bebas <span class="badge-count">{{ jumlah_esai }}</span></h4>
                                <p class="text-muted small mb-0">Kumpulan perenungan harian & ide acak.</p>
                            </div>
                        </div>
                        <i class="fa-solid fa-chevron-right text-warning fs-5"></i>
                    </div>
                </div>
            </a>
        </div>

        {% for tema in tema_list %}
        <div class="col-md-6">
            <div class="card-gold p-4">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <a href="/tema/{{ tema.id }}" class="text-decoration-none d-flex align-items-center flex-grow-1">
                        <i class="fa-solid fa-folder-open text-warning me-3 fs-4"></i>
                        <h4 class="h5 mb-0 fw-bold">{{ tema.nama }} <span class="badge-count">{{ tema.buku_list|length }}</span></h4>
                    </a>
                    {% if is_admin %}
                    <form action="/hapus-tema/{{ tema.id }}" method="POST" class="mb-0" onsubmit="return confirm('Hapus beserta semua isinya?');">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                        <button type="submit" class="btn btn-link text-danger p-0 ms-2"><i class="fa-solid fa-trash"></i></button>
                    </form>
                    {% endif %}
                </div>
                <small class="text-muted ms-4">Dibuat: {{ tema.dibuat_pada.strftime('%d %b %Y') if tema.dibuat_pada else '-' }} &rarr;</small>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HTML_HASIL_CARI = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Hasil Pencarian: {{ query }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button>
<div class="container py-5" style="max-width:800px;">
    <a href="/" class="btn btn-custom-outline rounded-pill btn-sm mb-4 fw-bold">&larr; Kembali</a>
    
    <div class="card-gold p-4 mb-4 rounded-4">
        <h4 class="fw-bold mb-2">🔍 Hasil Pencarian: "<span class="text-warning">{{ query }}</span>"</h4>
        <p class="text-muted small mb-0">Ditemukan {{ hasil_catatan|length }} bab buku dan {{ hasil_esai|length }} esai.</p>
    </div>

    <h5 class="fw-bold text-warning mb-3">Bab Buku</h5>
    {% for c in hasil_catatan %}
    <div class="card-gold p-3 mb-3">
        <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="badge bg-secondary">{{ c.bagian or 'Bab' }}</span>
            <a href="/buku/{{ c.buku_id }}#bab-{{ c.id }}" class="btn btn-warning btn-sm text-dark fw-bold rounded-pill">Buka Bab &rarr;</a>
        </div>
        <h5 class="fw-bold mb-1">{{ c.judul_bab }}</h5>
        <p class="small text-muted mb-0">{{ c.isi[:180] }}...</p>
    </div>
    {% else %}
    <p class="text-muted small mb-4">Tidak ada bab yang cocok.</p>
    {% endfor %}

    <h5 class="fw-bold text-warning mb-3">Jurnal & Esai</h5>
    {% for e in hasil_esai %}
    <div class="card-gold p-3 mb-3">
        <span class="badge bg-info text-dark mb-1">{{ e.kategori }}</span>
        <h5 class="fw-bold mb-1">{{ e.judul }}</h5>
        <p class="small text-muted mb-0">{{ e.isi[:180] }}...</p>
    </div>
    {% else %}
    <p class="text-muted small">Tidak ada esai yang cocok.</p>
    {% endfor %}
</div>
</body>
</html>
"""

HTML_BUKU_DETAIL = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ buku.judul }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
</head>
<body>
<div id="reading-progress"></div>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button>

<div class="container py-5" style="max-width:850px;">
    <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <a href="/tema/{{ buku.tema_id }}" class="btn btn-custom-outline rounded-pill btn-sm px-4 fw-bold">&larr; Kembali</a>
        <div class="d-flex gap-2 align-items-center flex-wrap">
            <a href="/export-buku/{{ buku.id }}" class="btn btn-outline-warning btn-sm rounded-pill fw-bold">TXT</a>
            <a href="/export-buku-docx/{{ buku.id }}" class="btn btn-outline-info btn-sm rounded-pill fw-bold">DOCX</a>
            <a href="/export-buku-epub/{{ buku.id }}" class="btn btn-outline-success btn-sm rounded-pill fw-bold">EPUB</a>
            <a href="/export-buku-pdf/{{ buku.id }}" class="btn btn-warning text-dark btn-sm rounded-pill fw-bold">PDF Buku</a>
        </div>
    </div>
    
    <div class="card-gold p-4 mb-4 rounded-4">
        <h2 class="h3 fw-bold mb-1">{{ buku.judul.upper() }}</h2>
        {% if buku.subjudul %}<p class="text-muted mb-2">{{ buku.subjudul }}</p>{% endif %}
    </div>

    {% for cat in catatan_list %}
    <div class="card-gold p-4 mb-3" id="bab-{{ cat.id }}">
        <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="note-card-badge">{{ cat.bagian or 'BAB' }}</span>
            <button type="button" class="btn btn-sm btn-info text-dark rounded-pill fw-bold px-2 py-1" onclick="playBabTTS({{ cat.id }}, '{{ cat.judul_bab | e }}')">
                <i class="fa-solid fa-headphones me-1"></i> Dengar Bab
            </button>
        </div>
        <h4 class="note-card-title">{{ cat.judul_bab }}</h4>
        <div class="markdown-body text-main tts-isi-bab-{{ cat.id }}" id="content-catatan-{{ cat.id }}"></div>
        <textarea id="raw-catatan-{{ cat.id }}" style="display:none;">{{ cat.isi }}</textarea>
    </div>
    {% endfor %}
</div>

<script>
document.addEventListener("DOMContentLoaded", function(){
    marked.use({ gfm: true, breaks: true });
    {% for cat in catatan_list %}
        document.getElementById('content-catatan-{{ cat.id }}').innerHTML = marked.parse(document.getElementById('raw-catatan-{{ cat.id }}').value);
    {% endfor %}
});

let synth = window.speechSynthesis;
function playBabTTS(id, judulBab) {
    if (!synth) return;
    if (synth.speaking) { synth.cancel(); return; }

    const contentEl = document.querySelector('.tts-isi-bab-' + id);
    if (!contentEl) return;

    let textToRead = "Judul bab: " + judulBab + ". " + contentEl.innerText;
    textToRead = textToRead.replace(/[«»“”"''*#_`~]/g, '');

    let utterance = new SpeechSynthesisUtterance(textToRead);
    utterance.lang = 'id-ID';
    synth.speak(utterance);
}
</script>
</body>
</html>
"""

HTML_FAVORIT = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Favorit</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-4" style="max-width:750px;"><a href="/" class="btn btn-custom-outline btn-sm mb-4">&larr; Kembali</a><h4 class="fw-bold mb-3 text-warning">Koleksi Favorit</h4>{% for c in catatan_favorit %}<div class="card-gold p-4 mb-3"><h5 class="fw-bold mb-2">{{ c.judul_bab }}</h5><p class="small text-muted mb-0">{{ c.isi[:140] }}...</p></div>{% endfor %}</div></body></html>"""
HTML_PDF_VIEWER = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>PDF Reader</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-4" style="max-width:920px;"><a href="/" class="btn btn-custom-outline btn-sm mb-3">&larr; Kembali</a><div class="card-gold p-3 mb-3"><h4 class="h5 fw-bold mb-0 text-warning">{{ nama_file }}</h4></div>{% if url_pdf %}<iframe src="https://mozilla.github.io/pdf.js/web/viewer.html?file={{ url_pdf }}" style="width:100%; height:75vh; border:none;"></iframe>{% endif %}</div></body></html>"""
HTML_ESAI_PENULIS = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Esai</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-4" style="max-width:760px;"><a href="/" class="btn btn-custom-outline btn-sm mb-4">&larr; Kembali</a>{% for e in esai_list %}<div class="card-gold p-4 mb-3"><h4 class="text-warning fw-bold mb-3">{{ e.judul }}</h4><div class="markdown-body" id="content-esai-{{ e.id }}"></div><textarea id="raw-esai-{{ e.id }}" style="display:none;">{{ e.isi }}</textarea></div>{% endfor %}</div><script>document.addEventListener("DOMContentLoaded", function(){marked.use({ gfm: true, breaks: true });{% for e in esai_list %}document.getElementById('content-esai-{{ e.id }}').innerHTML = marked.parse(document.getElementById('raw-esai-{{ e.id }}').value);{% endfor %});</script></body></html>"""
HTML_TEMA = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Tema: {{ tema.nama }}</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-5" style="max-width:850px;"><a href="/" class="btn btn-custom-outline rounded-pill btn-sm px-4 mb-4 fw-bold">&larr; Kembali</a><div class="card-gold p-4 mb-4 rounded-4"><h2 class="h3 fw-bold mb-1">Tema: {{ tema.nama }}</h2></div><div class="row g-3">{% for buku in buku_list %}<div class="col-12"><div class="card-gold p-4 d-flex justify-content-between align-items-center"><a href="/buku/{{ buku.id }}" class="text-decoration-none"><h4 class="h5 mb-1 fw-bold text-warning">{{ buku.judul.upper() }}</h4></a></div></div>{% endfor %}</div></div></body></html>"""
HTML_PENULIS = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Profil Penulis</title><link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-5" style="max-width:760px;"><a href="/" class="btn btn-custom-outline btn-sm mb-4 rounded-pill px-3 fw-bold">&larr; Kembali</a><div class="card-gold p-4 mb-4 rounded-4"><h2 class="h4 fw-bold text-warning mb-2">👨‍💻 Profil Penulis</h2><p class="small mb-2">Nama saya <strong>Dede Suhendra</strong>, lahir 8 Juli 2001, dari Subang.</p></div></div></body></html>"""
HTML_STATISTIK = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Statistik</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-4" style="max-width:600px;"><a href="/" class="btn btn-custom-outline btn-sm mb-4">&larr; Kembali</a><h3 class="mb-4 text-center fw-bold">📊 Statistik</h3><div class="row g-3"><div class="col-6"><div class="card-gold text-center p-4"><div>{{ total_buku }}</div><div class="text-muted">Buku</div></div></div><div class="col-6"><div class="card-gold text-center p-4"><div>{{ total_catatan }}</div><div class="text-muted">Bab</div></div></div></div></div></body></html>"""
HTML_TONG_SAMPAH = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Tong Sampah</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-4" style="max-width:700px;"><a href="/" class="btn btn-custom-outline btn-sm mb-4">&larr; Kembali</a><h4 class="mb-4 fw-bold">🗑️ Tong Sampah</h4>{% for item in sampah_list %}<div class="card-gold p-3 mb-2 d-flex justify-content-between align-items-center"><div><span class="badge bg-secondary me-2">{{ item.tipe }}</span><span>{{ item.data_json }}</span></div></div>{% endfor %}</div></body></html>"""
HTML_LOG = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Log</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-4" style="max-width:750px;"><a href="/" class="btn btn-custom-outline btn-sm mb-4">&larr; Kembali</a><h4 class="fw-bold mb-3 text-warning">Riwayat Log</h4>{% for l in logs %}<div class="card-gold p-3 mb-2"><span class="badge bg-warning text-dark fw-bold mb-1">{{ l.aksi }}</span><p class="mb-0 small">{{ l.keterangan }}</p></div>{% endfor %}</div></body></html>"""
HTML_LOGIN = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{background:#0f172a;color:#f8fafc;display:flex;justify-content:center;align-items:center;min-height:100vh;}.login-card{background:#1e293b;border:1px solid #334155;padding:30px;border-radius:12px;width:100%;max-width:400px;}</style></head><body><div class="login-card shadow-lg"><h3 class="text-info text-center fw-bold mb-3">🔑 Login Admin</h3>{% if error %}<div class="alert alert-danger py-2 small text-center">{{ error }}</div>{% endif %}<form action="/login" method="POST"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><input type="text" name="username" class="form-control mb-3 bg-dark text-white border-secondary" placeholder="Username" required><input type="password" name="password" class="form-control mb-3 bg-dark text-white border-secondary" placeholder="Password" required><button type="submit" class="btn btn-info w-100 fw-bold">Masuk</button></form><div class="text-center mt-3"><a href="/" class="text-muted text-decoration-none small">&larr; Kembali</a></div></div></body></html>"""

# ==================================================
# ROUTE HANDLERS
# ==================================================
@app.route('/')
def index():
    return render_template_string(HTML_INDEX, tema_list=Tema.query.all(), is_admin=session.get('is_admin'), jumlah_esai=EsaiPenulis.query.count(), penanda_list=PenandaBaca.query.order_by(PenandaBaca.waktu_baca.desc()).limit(1).all())

@app.route('/cari')
def cari_naskah():
    query = request.args.get('q', '').strip()
    hasil_catatan = []
    hasil_esai = []

    if query:
        hasil_catatan = Catatan.query.filter(
            (Catatan.judul_bab.ilike(f'%{query}%')) | 
            (Catatan.isi.ilike(f'%{query}%'))
        ).all()

        hasil_esai = EsaiPenulis.query.filter(
            (EsaiPenulis.judul.ilike(f'%{query}%')) | 
            (EsaiPenulis.isi.ilike(f'%{query}%'))
        ).all()

    return render_template_string(HTML_HASIL_CARI, query=query, hasil_catatan=hasil_catatan, hasil_esai=hasil_esai)

@app.route('/buku/<int:buku_id>')
def detail_buku(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    catatan_list = Catatan.query.filter_by(buku_id=buku_id).order_by(Catatan.urutan.asc(), Catatan.id.asc()).all()
    return render_template_string(HTML_BUKU_DETAIL, buku=buku, catatan_list=catatan_list, is_admin=session.get('is_admin'))

@app.route('/ubah-urutan-bab/<int:buku_id>', methods=['POST'])
def ubah_urutan_bab(buku_id):
    if not session.get('is_admin'): return "Akses Ditolak", 403
    urutan_data = request.form.getlist('catatan_id[]')
    for index, c_id in enumerate(urutan_data, start=1):
        catatan = Catatan.query.get(c_id)
        if catatan:
            catatan.urutan = index
    db.session.commit()
    catat_log("URUTAN BAB", f"Mengubah urutan bab buku ID: {buku_id}")
    return redirect(f'/buku/{buku_id}')

# --- ROUTE EKSPOR DOKUMEN (TXT, DOCX, EPUB, PDF) ---
@app.route('/export-buku/<int:buku_id>')
def export_buku(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    teks = f"JUDUL: {buku.judul}\n" + "\n".join([f"[{c.bagian}] {c.judul_bab}\n{c.isi}\n" for c in buku.catatan_list])
    return Response(teks, mimetype='text/plain', headers={'Content-Disposition': f'attachment;filename={buku.judul}.txt'})

@app.route('/export-buku-docx/<int:buku_id>')
def export_buku_docx(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    doc = Document()
    doc.add_heading(buku.judul.upper(), level=0)
    if buku.subjudul: doc.add_paragraph(buku.subjudul)
    doc.add_page_break()

    for c in buku.catatan_list:
        doc.add_heading(c.judul_bab, level=2)
        for p in c.isi.split('\n'):
            if p.strip(): doc.add_paragraph(p.strip())

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', buku.judul)
    return send_file(buffer, as_attachment=True, download_name=f"{filename}.docx", mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

@app.route('/export-buku-epub/<int:buku_id>')
def export_buku_epub(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    book = epub.EpubBook()
    book.set_identifier(f'buku-{buku.id}')
    book.set_title(buku.judul)
    book.set_language('id')
    book.add_author('Dede Suhendra')

    chapters = []
    for idx, c in enumerate(buku.catatan_list):
        ch = epub.EpubHtml(title=c.judul_bab, file_name=f'chap_{idx+1}.xhtml', lang='id')
        isi_html = f"<h2>{escape(c.judul_bab)}</h2>"
        for p in c.isi.split('\n'):
            if p.strip(): isi_html += f"<p>{escape(p.strip())}</p>"
        ch.content = isi_html
        book.add_item(ch)
        chapters.append(ch)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + chapters

    buffer = BytesIO()
    epub.write_epub(buffer, book, {})
    buffer.seek(0)
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', buku.judul)
    return send_file(buffer, as_attachment=True, download_name=f"{filename}.epub", mimetype='application/epub+zip')

@app.route('/export-buku-pdf/<int:buku_id>')
def export_buku_pdf(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    style_cover_title = ParagraphStyle('CoverTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=24, leading=30, alignment=TA_CENTER)
    style_bab_title = ParagraphStyle('BabTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=15, spaceBefore=10, spaceAfter=4)
    style_bab_body = ParagraphStyle('BabBody', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=10)

    story = [Spacer(1, 120), Paragraph(f"<b>{escape(buku.judul.upper())}</b>", style_cover_title), PageBreak()]
    for c in buku.catatan_list:
        story.append(Paragraph(f"<b>{escape(c.judul_bab)}</b>", style_bab_title))
        story.append(Paragraph(escape(c.isi).replace('\n', '<br/>'), style_bab_body))

    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{re.sub(r'[^a-zA-Z0-9_.-]', '_', buku.judul)}.pdf", mimetype='application/pdf')

# --- ROUTE TAMBAHAN LAINNYA ---
@app.route('/penulis')
def tentang_penulis(): return render_template_string(HTML_PENULIS)
@app.route('/catatan-penulis')
def catatan_penulis(): return render_template_string(HTML_ESAI_PENULIS, esai_list=EsaiPenulis.query.order_by(EsaiPenulis.id.desc()).all(), is_admin=session.get('is_admin'))
@app.route('/favorit')
def halaman_favorit(): return render_template_string(HTML_FAVORIT, catatan_favorit=Catatan.query.filter_by(favorit=True).all())
@app.route('/baca-pdf')
def baca_pdf():
    is_admin = session.get('is_admin')
    daftar_file = [f for f in os.listdir(UPLOAD_PDF_FOLDER) if f.endswith('.pdf')]
    nama_pilihan = request.args.get('nama') or (daftar_file[0] if daftar_file else None)
    url_pdf = f"/file-pdf/{nama_pilihan}" if nama_pilihan in daftar_file else None
    return render_template_string(HTML_PDF_VIEWER, url_pdf=url_pdf, nama_file=nama_pilihan or "Pilih file PDF", daftar_file=daftar_file, is_admin=is_admin)

@app.route('/statistik')
def statistik(): return render_template_string(HTML_STATISTIK, total_buku=Buku.query.count(), total_catatan=Catatan.query.count())
@app.route('/tong-sampah')
def tong_sampah(): return render_template_string(HTML_TONG_SAMPAH, sampah_list=TongSampah.query.all())
@app.route('/riwayat-log')
def riwayat_log():
    if not session.get('is_admin'): return redirect('/login')
    return render_template_string(HTML_LOG, logs=LogAktivitas.query.order_by(LogAktivitas.id.desc()).limit(50).all())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not cek_rate_limit_login(request.remote_addr):
            return render_template_string(HTML_LOGIN, error="Terlalu banyak percobaan login! Coba lagi 1 menit kemudian.")
        if request.form.get('username') == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, request.form.get('password')):
            session['is_admin'] = True
            return redirect('/')
        return render_template_string(HTML_LOGIN, error="Salah password atau username!")
    return render_template_string(HTML_LOGIN, error=None)

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
