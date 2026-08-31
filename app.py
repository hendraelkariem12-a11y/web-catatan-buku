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

# ReportLab, Docx, & Ebooklib untuk Ekspor Dokumen
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
# LOGGING SISTEM & FOLDER UPLOAD
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
        db.session.add_all([Tema(nama='Filsafat'), Tema(nama='Keuangan'), Tema(nama='Komunikasi')])
        db.session.commit()

def masukkan_sampah(tipe, data_dict):
    item = TongSampah(tipe=tipe, data_json=json.dumps(data_dict, ensure_ascii=False))
    db.session.add(item)
    db.session.commit()

def catat_log(aksi, keterangan=""):
    log_baru = LogAktivitas(aksi=aksi, keterangan=keterangan)
    db.session.add(log_baru)
    db.session.commit()

# ==================================================
# TEMPLATE STYLES (CSS & JS)
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
    .btn-mode-toggle { position:fixed; top:15px; right:15px; z-index:100; border-radius:50%; width:44px; height:44px; display:flex; align-items:center; justify-content:center; background: var(--card-paper) !important; border: 2px solid #b38728 !important; color: #b38728 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
    
    #reading-progress {
        position: fixed; top: 0; left: 0; height: 4px;
        background: linear-gradient(90deg, #bf953f, #fcf6ba, #b38728);
        width: 0%; z-index: 9999; transition: width 0.1s ease-out;
    }
    .note-card-badge { display: block; width: fit-content; background: rgba(56, 189, 248, 0.15); color: #38bdf8 !important; font-size: 11px; font-weight: 700; padding: 5px 12px; border-radius: 6px; text-transform: uppercase; margin-bottom: 8px; }
    .note-card-title { color: #b38728 !important; font-size: 20px; font-weight: 800; margin-top: 4px; margin-bottom: 12px; padding-right: 170px; }
    .toc-box { background: rgba(179, 135, 40, 0.05); border: 1px dashed var(--border-color); border-radius: 12px; padding: 20px; margin-bottom: 25px; }
"""

JS_THEME_SCRIPT = """
<script>
    (function() {
        const savedTheme = localStorage.getItem('theme_mode') || 'terang';
        document.documentElement.setAttribute('data-theme', savedTheme);
    })();

    document.addEventListener("DOMContentLoaded", function() {
        updateIcon();
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
</script>
"""

# ==================================================
# HTML TEMPLATES
# ==================================================
HTML_INDEX = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Perpustakaan Karya - Dede Suhendra</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-5" style="max-width:850px;"><div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2"><a href="/penulis" class="btn btn-custom-outline rounded-pill btn-sm px-3 fw-bold"><i class="fa-solid fa-user-tie me-1"></i> Profil Penulis</a><div class="d-flex gap-2 align-items-center flex-wrap"><a href="/favorit" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-star me-1 text-warning"></i> Favorit</a><a href="/baca-pdf" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-book-open me-1 text-danger"></i> PDF Reader</a><a href="/statistik" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-chart-simple me-1 text-info"></i> Statistik</a><a href="/tong-sampah" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-trash-can me-1 text-secondary"></i> Sampah</a>{% if is_admin %}<a href="/logout" class="btn btn-warning rounded-pill btn-sm fw-bold text-dark">Logout</a>{% else %}<a href="/login" class="btn btn-custom-outline rounded-pill btn-sm fw-bold">Login</a>{% endif %}</div></div><div class="text-center mb-5"><span class="top-badge mb-2">OFFICIAL VAULT</span><h1 class="header-title h2 mb-2">Catatan & Karya Buku</h1><p class="text-muted small">Disusun oleh <strong>Dede Suhendra</strong></p></div><div class="row g-3">{% for tema in tema_list %}<div class="col-md-6"><div class="card-gold p-4"><a href="/tema/{{ tema.id }}" class="text-decoration-none"><h4 class="h5 mb-0 fw-bold">{{ tema.nama }}</h4></a></div></div>{% endfor %}</div></div></body></html>"""

HTML_BUKU_DETAIL = """<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{{ buku.judul }}</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>""" + CSS_SHARED + """</style>""" + JS_THEME_SCRIPT + """</head><body><div id="reading-progress"></div><button class="btn btn-mode-toggle" onclick="toggleModeInstan()"><i class="fa-solid fa-moon" id="icon-mode"></i></button><div class="container py-5" style="max-width:850px;"><div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2"><a href="/tema/{{ buku.tema_id }}" class="btn btn-custom-outline rounded-pill btn-sm px-4 fw-bold">&larr; Kembali</a><div class="d-flex gap-2 align-items-center flex-wrap"><a href="/export-buku/{{ buku.id }}" class="btn btn-outline-warning btn-sm rounded-pill fw-bold">TXT</a><a href="/export-buku-docx/{{ buku.id }}" class="btn btn-outline-info btn-sm rounded-pill fw-bold">DOCX</a><a href="/export-buku-epub/{{ buku.id }}" class="btn btn-outline-success btn-sm rounded-pill fw-bold">EPUB</a><a href="/export-buku-pdf/{{ buku.id }}" class="btn btn-warning text-dark btn-sm rounded-pill fw-bold">PDF Buku</a></div></div><div class="card-gold p-4 mb-4 rounded-4"><h2 class="h3 fw-bold mb-1">{{ buku.judul.upper() }}</h2>{% if buku.subjudul %}<p class="text-muted mb-2">{{ buku.subjudul }}</p>{% endif %}</div>{% for cat in catatan_list %}<div class="card-gold p-4 mb-3" id="bab-{{ cat.id }}"><h4 class="note-card-title">{{ cat.judul_bab }}</h4><div class="markdown-body text-main" id="content-catatan-{{ cat.id }}"></div><textarea id="raw-catatan-{{ cat.id }}" style="display:none;">{{ cat.isi }}</textarea></div>{% endfor %}</div><script>document.addEventListener("DOMContentLoaded", function(){marked.use({ gfm: true, breaks: true });{% for cat in catatan_list %}document.getElementById('content-catatan-{{ cat.id }}').innerHTML = marked.parse(document.getElementById('raw-catatan-{{ cat.id }}').value);{% endfor %});</script></body></html>"""

# ==================================================
# ROUTES APLIKASI
# ==================================================
@app.route('/')
def index():
    return render_template_string(HTML_INDEX, tema_list=Tema.query.all(), is_admin=session.get('is_admin'))

@app.route('/buku/<int:buku_id>')
def detail_buku(buku_id):
    buku = Buku.query.get_or_404(buku_id)
    catatan_list = Catatan.query.filter_by(buku_id=buku_id).order_by(Catatan.id.asc()).all()
    return render_template_string(HTML_BUKU_DETAIL, buku=buku, catatan_list=catatan_list, is_admin=session.get('is_admin'))

# --- ROUTE EKSPOR (TXT, PDF, DOCX, EPUB) ---
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

# --- ROUTE LOGIN & LAINNYA ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not cek_rate_limit_login(request.remote_addr):
            return "Terlalu banyak percobaan login. Coba lagi 1 menit kemudian.", 429
        if request.form.get('username') == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, request.form.get('password')):
            session['is_admin'] = True
            return redirect('/')
        return "Salah Password!"
    return '<form method="POST"><input type="hidden" name="csrf_token" value="' + csrf.generate_csrf() + '"><input type="text" name="username"><input type="password" name="password"><button type="submit">Login</button></form>'

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
