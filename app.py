import os
import json
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, session, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'karya-dede-suhendra-secret-key-2026-upgraded'

# ==================================================
# KONFIGURASI DATABASE
# ==================================================
db_path = os.path.join('/tmp', 'karya_buku.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 86400

db = SQLAlchemy(app)

ADMIN_USER = "dede"
ADMIN_PASS = "suhendra123"

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

class PengaturanPengguna(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mode_tema = db.Column(db.String(20), default='terang')
    ukuran_font = db.Column(db.String(20), default='normal')

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

# ==================================================
# TEMPLATE HTML KONTRASTIS & INSTAN SWITCH (PERBAIKAN CSS & JS)
# ==================================================

CSS_SHARED = """
    :root { 
        --bg-paper: #f7f4ef; 
        --card-paper: #ffffff; 
        --text-main: #1e293b; 
        --text-muted: #64748b;
        --gold-gradient: linear-gradient(135deg, #bf953f, #fcf6ba, #b38728, #fbf5b7);
        --border-color: rgba(212, 175, 55, 0.3);
        --btn-outline: #334155;
        --input-bg: #ffffff;
        --input-text: #1e293b;
    }
    [data-theme="gelap"] {
        --bg-paper: #0b132b; 
        --card-paper: #1c2541; 
        --text-main: #f8fafc; 
        --text-muted: #cbd5e1;
        --border-color: #334155;
        --btn-outline: #38bdf8;
        --input-bg: #1e293b;
        --input-text: #f8fafc;
    }
    body { 
        background-color: var(--bg-paper) !important; 
        font-family: 'Plus Jakarta Sans', sans-serif; 
        color: var(--text-main) !important; 
        transition: background-color 0.2s ease, color 0.2s ease;
    }
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: inherit;
    }
    .text-muted {
        color: var(--text-muted) !important;
    }
    .header-title { font-family: 'Cinzel', serif; font-weight: 700; }
    .top-badge { background: #fcf8ec; color: #b38728; border: 1px solid rgba(212,175,55,0.4); font-weight:700; padding:6px 16px; border-radius:30px; font-size:0.8rem; }
    .card-gold { background:var(--card-paper); border-radius:18px; border:1px solid var(--border-color); box-shadow:0 10px 25px rgba(0,0,0,0.03); transition:all 0.3s ease; position:relative; overflow:hidden; }
    .card-gold::before { content:''; position:absolute; top:0; left:0; width:100%; height:4px; background:var(--gold-gradient); }
    .card-gold:hover { transform:translateY(-4px); box-shadow:0 15px 30px rgba(212,175,55,0.18); }
    .card-penulis { background:var(--card-paper); border:2px solid rgba(212,175,55,0.5); }
    
    .btn-custom-outline { color: var(--text-main) !important; border-color: var(--border-color) !important; background: var(--card-paper); }
    .btn-custom-outline:hover { background: #b38728; color: #fff !important; }
    
    .search-box { position:relative; }
    .search-box input { padding-left:38px; background: var(--input-bg) !important; color: var(--input-text) !important; border-color: var(--border-color) !important; }
    .search-box i { position:absolute; left:12px; top:50%; transform:translateY(-50%); color:#888; }
    
    .badge-count { background:#b38728; color:white; border-radius:50%; width:22px; height:22px; display:inline-flex; align-items:center; justify-content:center; font-size:11px; margin-left:6px; }
    .btn-mode-toggle { position:fixed; top:15px; right:15px; z-index:100; border-radius:50%; width:44px; height:44px; display:flex; align-items:center; justify-content:center; background: var(--card-paper); border: 2px solid #b38728; color: #b38728; box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
    .filter-tag { cursor:pointer; transition:all 0.2s; background: var(--card-paper) !important; color: var(--text-main) !important; border-color: var(--border-color) !important; }
    .filter-tag:hover, .filter-tag.active { background:#b38728 !important; color:white !important; }
"""

JS_THEME_SCRIPT = """
<script>
    (function() {
        const savedTheme = localStorage.getItem('theme_mode') || 'terang';
        document.documentElement.setAttribute('data-theme', savedTheme);
    })();

    document.addEventListener("DOMContentLoaded", function() {
        updateIcon();
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

HTML_INDEX = f"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Perpustakaan Karya - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>{CSS_SHARED}</style>
    {JS_THEME_SCRIPT}
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-5" style="max-width:850px;">
    <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <a href="/penulis" class="btn btn-custom-outline rounded-pill btn-sm px-3 fw-bold"><i class="fa-solid fa-user-tie me-1"></i> Profil Penulis</a>
        <div class="d-flex gap-2 align-items-center">
            <a href="/statistik" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-chart-simple me-1 text-info"></i> Statistik</a>
            <a href="/tong-sampah" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-trash-can me-1 text-secondary"></i> Tong Sampah</a>
            {{% if is_admin %}}
                <a href="/backup" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-download me-1 text-primary"></i> Backup</a>
                <a href="/logout" class="btn btn-warning rounded-pill btn-sm fw-bold text-dark"><i class="fa-solid fa-right-from-bracket me-1"></i> Logout</a>
            {{% else %}}
                <a href="/login" class="btn btn-custom-outline rounded-pill btn-sm fw-bold"><i class="fa-solid fa-lock me-1"></i> Login</a>
            {{% endif %}}
        </div>
    </div>
    
    <div class="text-center mb-5">
        <span class="top-badge mb-2">OFFICIAL VAULT</span>
        <h1 class="header-title h2 mb-2">Catatan & Karya Buku</h1>
        <p class="text-muted small">Disusun & Dikelola oleh <strong>Dede Suhendra</strong></p>
    </div>

    <div class="card-gold p-3 mb-4 rounded-3">
        <div class="search-box mb-2">
            <i class="fa-solid fa-magnifying-glass"></i>
            <input type="text" id="cari-input" class="form-control form-control-sm" placeholder="Cari judul, kategori..." oninput="jalankanPencarian(this.value)">
        </div>
        <div class="d-flex flex-wrap gap-2 mt-2">
            <span class="badge border filter-tag active" data-filter="semua" onclick="filterKategori('semua')">Semua</span>
            {{% for t in tema_list %}}
            <span class="badge border filter-tag" data-filter="{{{{ t.nama }}}}" onclick="filterKategori('{{{{ t.nama }}}}')">{{{{ t.nama }}}}</span>
            {{% endfor %}}
        </div>
    </div>

    {{% if is_admin %}}
    <div class="card-gold p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-success mb-2"><i class="fa-solid fa-folder-plus me-1"></i> Tambah Tema Baru</h6>
        <form action="/tambah-tema" method="POST" class="row g-2">
            <div class="col-9"><input type="text" name="nama" class="form-control form-control-sm" placeholder="Misal: Psikologi..." required></div>
            <div class="col-3"><button type="submit" class="btn btn-success btn-sm w-100 fw-bold">Tambah</button></div>
        </form>
    </div>
    {{% endif %}}

    <h5 class="fw-bold mb-3" style="font-family:'Cinzel',serif;">Pilih Kategori Karya:</h5>
    <div class="row g-3" id="daftar-kategori">
        <div class="col-12 kategori-item" data-nama="Jurnal & Esai">
            <a href="/catatan-penulis" class="text-decoration-none">
                <div class="card-gold card-penulis p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <div class="bg-warning text-dark rounded-circle p-3 me-3"><i class="fa-solid fa-feather-pointed fs-4"></i></div>
                            <div>
                                <span class="badge bg-warning text-dark fw-bold mb-1">Ruang Refleksi</span>
                                <h4 class="h5 mb-1 fw-bold">✍️ Jurnal & Esai Bebas <span class="badge-count">{{{{ jumlah_esai }}}}</span></h4>
                                <p class="text-muted small mb-0">Kumpulan perenungan harian & ide acak.</p>
                            </div>
                        </div>
                        <i class="fa-solid fa-chevron-right text-warning fs-5"></i>
                    </div>
                </div>
            </a>
        </div>

        {{% for tema in tema_list %}}
        <div class="col-md-6 kategori-item" data-nama="{{{{ tema.nama }}}}">
            <div class="card-gold p-4">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <a href="/tema/{{{{ tema.id }}}}" class="text-decoration-none d-flex align-items-center flex-grow-1">
                        <i class="fa-solid fa-folder-open text-warning me-3 fs-4"></i>
                        <h4 class="h5 mb-0 fw-bold">{{{{ tema.nama }}}} <span class="badge-count">{{{{ tema.buku_list|length }}}}</span></h4>
                    </a>
                    {{% if is_admin %}}
                    <form action="/hapus-tema/{{{{ tema.id }}}}" method="POST" onsubmit="return confirm('Hapus beserta semua isinya?');">
                        <button type="submit" class="btn btn-link text-danger p-0 ms-2"><i class="fa-solid fa-trash"></i></button>
                    </form>
                    {{% endif %}}
                </div>
                <small class="text-muted ms-4">Dibuat: {{{{ tema.dibuat_pada.strftime('%d %b %Y') if tema.dibuat_pada else '-' }}}} &rarr;</small>
            </div>
        </div>
        {{% endfor %}}
    </div>
</div>

<script>
function jalankanPencarian(kata) {{
    document.querySelectorAll('.kategori-item').forEach(item => {{
        const nama = item.getAttribute('data-nama').toLowerCase();
        item.style.display = kata === '' || nama.includes(kata.toLowerCase()) ? '' : 'none';
    }});
}}
function filterKategori(nama) {{
    document.querySelectorAll('.filter-tag').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-filter="${{nama}}"]`).classList.add('active');
    document.querySelectorAll('.kategori-item').forEach(item => {{
        item.style.display = nama === 'semua' || item.getAttribute('data-nama') === nama ? '' : 'none';
    }});
}}
</script>
</body>
</html>
"""

HTML_ESAI_PENULIS = f"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jurnal & Esai - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>{CSS_SHARED}</style>
    {JS_THEME_SCRIPT}
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-4" style="max-width:760px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4"><i class="fa-solid fa-arrow-left me-1"></i> Kembali ke Utama</a>
    <div class="card-gold p-4 rounded-4 mb-4">
        <span class="badge bg-warning text-dark mb-2 fw-bold">RUANG REFLEKSI</span>
        <h2 class="h3 fw-bold text-warning mb-1">✍️ Jurnal & Esai Bebas Penulis</h2>
        <p class="text-muted small mb-0">Catatan ide acak, artikel ringkas, dan hikmah harian. Total: {{{{ esai_list|length }}}} karya.</p>
    </div>
    
    <div class="search-box mb-4">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input type="text" class="form-control" placeholder="Cari judul atau isi..." oninput="filterEsai(this.value)">
    </div>

    {{% if is_admin %}}
    <div class="card-gold p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-info mb-2"><i class="fa-solid fa-pen-nib me-1"></i> Tulis Esai Baru</h6>
        <form action="/tambah-esai" method="POST">
            <input type="text" name="judul" class="form-control form-control-sm mb-2" placeholder="Judul..." required>
            <input type="text" name="kategori" class="form-control form-control-sm mb-2" placeholder="Kategori: Refleksi, Ide, dll.">
            <textarea name="isi" class="form-control form-control-sm mb-2" rows="4" placeholder="Tulis catatan (Markdown didukung)..." required></textarea>
            <button type="submit" class="btn btn-info btn-sm w-100 fw-bold">Terbitkan Catatan</button>
        </form>
    </div>
    {{% endif %}}

    {{% for e in esai_list %}}
    <div class="card-gold p-4 mb-3 esai-item">
        {{% if is_admin %}}
        <form action="/hapus-esai/{{{{ e.id }}}}" method="POST" class="position-absolute top-0 end-0 p-3" onsubmit="return confirm('Hapus esai ini?');">
            <button type="submit" class="btn btn-link text-danger p-0"><i class="fa-solid fa-trash"></i></button>
        </form>
        {{% endif %}}
        <span class="badge bg-info text-dark mb-2">{{{{ e.kategori }}}}</span>
        <h4 class="text-warning fw-bold mb-3 esai-judul">{{{{ e.judul }}}}</h4>
        <div class="markdown-body" id="content-esai-{{{{ e.id }}}}"></div>
        <textarea id="raw-esai-{{{{ e.id }}}}" style="display:none;">{{{{ e.isi }}}}</textarea>
        <div class="text-muted small mt-3">Dibuat: {{{{ e.dibuat_pada.strftime('%d %b %Y %H:%M') if e.dibuat_pada else '-' }}}}</div>
    </div>
    {{% else %}}
    <div class="text-center py-5 card-gold rounded-4">
        <i class="fa-solid fa-feather fs-1 text-muted mb-2"></i>
        <p class="text-muted mb-0">Belum ada jurnal atau esai.</p>
    </div>
    {{% endfor %}}
</div>

<script>
document.addEventListener("DOMContentLoaded", function(){{
    marked.use({{ gfm: true, breaks: true }});
    {{% for e in esai_list %}}
        var rawText = document.getElementById('raw-esai-{{{{ e.id }}}}').value;
        document.getElementById('content-esai-{{{{ e.id }}}}').innerHTML = marked.parse(rawText);
    {{% endfor %}}

    filterEsai = function(kata) {{
        document.querySelectorAll('.esai-item').forEach(item => {{
            const judul = item.querySelector('.esai-judul').textContent.toLowerCase();
            item.style.display = kata === '' || judul.includes(kata.toLowerCase()) ? '' : 'none';
        }});
    }};
}});
</script>
</body>
</html>
"""

HTML_TEMA = f"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tema: {{{{ tema.nama }}}}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>{CSS_SHARED}</style>
    {JS_THEME_SCRIPT}
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-5" style="max-width:850px;">
    <a href="/" class="btn btn-custom-outline rounded-pill btn-sm px-4 mb-4 shadow-sm" style="font-weight:600;"><i class="fa-solid fa-arrow-left me-2"></i>Kembali ke Semua Tema</a>
    <div class="card-gold p-4 mb-4 rounded-4 border">
        <span class="badge bg-warning text-dark mb-2 fw-bold"><i class="fa-solid fa-folder-open me-1"></i> Kategori Karya</span>
        <h2 class="h3 fw-bold mb-1" style="font-family:'Cinzel',serif;">Tema: {{{{ tema.nama }}}}</h2>
        <small class="text-muted">Dibuat: {{{{ tema.dibuat_pada.strftime('%d %b %Y %H:%M') if tema.dibuat_pada else '-' }}}} &nbsp;|&nbsp; Jumlah Buku: {{{{ buku_list|length }}}}</small>
    </div>
    
    {{% if is_admin %}}
    <div class="card-gold p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-success mb-2"><i class="fa-solid fa-book-medical me-1"></i> Tambah Buku Baru</h6>
        <form action="/tambah-buku" method="POST" class="row g-2">
            <input type="hidden" name="tema_id" value="{{{{ tema.id }}}}">
            <div class="col-md-6"><input type="text" name="judul" class="form-control form-control-sm" placeholder="Judul Buku..." required></div>
            <div class="col-md-6"><input type="text" name="subjudul" class="form-control form-control-sm" placeholder="Subjudul (Opsional)"></div>
            <div class="col-12"><textarea name="kutipan" class="form-control form-control-sm" rows="2" placeholder="Kutipan Penulis..."></textarea></div>
            <div class="col-12"><button type="submit" class="btn btn-success btn-sm w-100 fw-bold">Simpan Buku</button></div>
        </form>
    </div>
    {{% endif %}}

    <h5 class="fw-bold mb-3" style="font-family:'Cinzel',serif;">Daftar Buku Tersimpan:</h5>
    <div class="row g-3">
        {{% for buku in buku_list %}}
        <div class="col-12">
            <div class="card-gold p-4">
                <div class="d-flex justify-content-between align-items-center">
                    <a href="/buku/{{{{ buku.id }}}}" class="text-decoration-none flex-grow-1">
                        <div class="d-flex align-items-center">
                            <i class="fa-solid fa-file-lines text-warning fs-4 me-3"></i>
                            <div>
                                <h4 class="h5 mb-1 fw-bold">{{{{ buku.judul.upper() }}}}</h4>
                                {{{% if buku.subjudul %}}}<p class="text-muted small mb-0">{{{{ buku.subjudul }}}}</p>{{{% endif %}}}
                            </div>
                        </div>
                    </a>
                    {{% if is_admin %}}
                    <form action="/hapus-buku/{{{{ buku.id }}}}/{{{{ tema.id }}}}" method="POST" onsubmit="return confirm('Hapus buku ini?');">
                        <button type="submit" class="btn btn-link text-danger p-0 ms-2"><i class="fa-solid fa-trash"></i></button>
                    </form>
                    {{% endif %}}
                </div>
            </div>
        </div>
        {{% else %}}
        <div class="text-center py-4 card-gold rounded-4">
            <p class="text-muted mb-0">Belum ada buku dalam tema ini.</p>
        </div>
        {{% endfor %}}
    </div>
</div>
</body>
</html>
"""

HTML_STATISTIK = f"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Statistik - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>{CSS_SHARED}
        .stat-card {{ text-align:center; }}
        .stat-number {{ font-size:42px; font-weight:800; color:#b38728; }}
    </style>
    {JS_THEME_SCRIPT}
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-4" style="max-width:600px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4"><i class="fa-solid fa-arrow-left me-1"></i> Kembali</a>
    <h3 class="mb-4 text-center fw-bold">📊 Statistik Perpustakaan</h3>
    <div class="row g-3">
        <div class="col-6"><div class="card-gold stat-card p-4"><i class="fa-solid fa-folder-tree fs-1 text-warning mb-2"></i><div class="stat-number">{{{{ total_tema }}}}</div><div class="text-muted">Kategori</div></div></div>
        <div class="col-6"><div class="card-gold stat-card p-4"><i class="fa-solid fa-book fs-1 text-primary mb-2"></i><div class="stat-number">{{{{ total_buku }}}}</div><div class="text-muted">Jumlah Buku</div></div></div>
        <div class="col-6"><div class="card-gold stat-card p-4"><i class="fa-solid fa-file-lines fs-1 text-info mb-2"></i><div class="stat-number">{{{{ total_catatan }}}}</div><div class="text-muted">Catatan / Bab</div></div></div>
        <div class="col-6"><div class="card-gold stat-card p-4"><i class="fa-solid fa-pen-nib fs-1 text-success mb-2"></i><div class="stat-number">{{{{ total_esai }}}}</div><div class="text-muted">Esai / Jurnal</div></div></div>
    </div>
    <div class="card-gold stat-card p-4 mt-4">
        <h6 class="fw-bold mb-3">📅 Ringkasan Aktivitas</h6>
        <p>Buku baru: <strong>{{{{ buku_bulan_ini }}}}</strong> &nbsp;|&nbsp; Esai baru: <strong>{{{{ esai_bulan_ini }}}}</strong></p>
        <p class="mb-0">Total kata diperkirakan: <strong>{{{{ total_kata }}}}</strong> kata</p>
    </div>
</div>
</body>
</html>
"""

HTML_TONG_SAMPAH = f"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tong Sampah - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>{CSS_SHARED}</style>
    {JS_THEME_SCRIPT}
</head>
<body>
<button class="btn btn-mode-toggle" onclick="toggleModeInstan()" title="Ganti Mode Tampilan">
    <i class="fa-solid fa-moon" id="icon-mode"></i>
</button>

<div class="container py-4" style="max-width:700px;">
    <a href="/" class="btn btn-custom-outline btn-sm mb-4"><i class="fa-solid fa-arrow-left me-1"></i> Kembali</a>
    <h4 class="mb-4 fw-bold">🗑️ Tong Sampah</h4>
    <p class="text-muted small mb-4">Item bisa dipulihkan atau dihapus permanen.</p>
    {{% if sampah_list %}}
        {{% for item in sampah_list %}}
        <div class="card-gold p-3 mb-2 d-flex justify-content-between align-items-center flex-row flex-wrap gap-2">
            <div>
                <span class="badge bg-secondary me-2">{{{{ item.tipe }}}}</span>
                <span>{{{{ item.data_json }}}}</span>
                <div class="text-muted small mt-1">Dihapus: {{{{ item.dihapus_pada.strftime('%d %b %Y %H:%M') }}}}</div>
            </div>
            <div class="d-flex gap-2">
                <a href="/pulihkan/{{{{ item.id }}}}" class="btn btn-sm btn-success"><i class="fa-solid fa-rotate-left"></i> Pulihkan</a>
                <a href="/hapus-permanen/{{{{ item.id }}}}" class="btn btn-sm btn-danger" onclick="return confirm('Hapus permanen?')"><i class="fa-solid fa-trash-xmark"></i></a>
            </div>
        </div>
        {{% endfor %}}
        <form action="/kosongkan-tong-sampah" method="POST" onsubmit="return confirm('Kosongkan semua?')">
            <button type="submit" class="btn btn-danger w-100 mt-3">🗑️ Kosongkan Tong Sampah</button>
        </form>
    {{% else %}}
        <div class="text-center py-5 card-gold rounded-4"><i class="fa-solid fa-trash-can-check fs-1 text-muted mb-2"></i><p class="text-muted">Tong sampah kosong.</p></div>
    {{% endif %}}
</div>
</body>
</html>
"""

HTML_PENULIS = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Profil Penulis - Dede Suhendra</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0b132b; --card: #1c2541; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8; --border: #334155; }
        * { box-sizing:border-box; margin:0; padding:0; font-family:'Plus Jakarta Sans',sans-serif; }
        body { background:var(--bg); color:var(--text); padding:20px; line-height:1.6; }
        .container { max-width:760px; margin:0 auto; }
        .btn-back { display:inline-block; color:var(--muted); text-decoration:none; font-size:13px; font-weight:600; margin-bottom:20px; }
        .btn-back:hover { color:var(--accent); }
        .card-box { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:24px; margin-bottom:24px; box-shadow:0 4px 15px rgba(0,0,0,0.2); }
        .card-title { font-size:18px; font-weight:800; color:var(--accent); margin-bottom:14px; display:flex; align-items:center; gap:8px; border-bottom:1px dashed var(--border); padding-bottom:10px; }
        .card-p { color:#cbd5e1; font-size:14px; margin-bottom:12px; }
        .timeline { position:relative; border-left:2px solid var(--border); padding-left:18px; margin-top:10px; margin-left:6px; }
        .timeline-item { position:relative; margin-bottom:16px; }
        .timeline-item::before { content:""; position:absolute; left:-24px; top:5px; width:10px; height:10px; border-radius:50%; background:var(--accent); }
        .timeline-year { font-size:12px; font-weight:800; color:var(--accent); }
        .timeline-title { font-size:14px; font-weight:700; color:var(--text); }
        .timeline-desc { font-size:13px; color:var(--muted); }
        .list-custom { list-style:none; padding-left:0; }
        .list-custom li { font-size:14px; color:#cbd5e1; margin-bottom:10px; padding-left:24px; position:relative; }
        .list-custom li::before { content:"🎯"; position:absolute; left:0; font-size:13px; }
        .appreciation-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin-top:10px; }
        .app-item { background:#0f172a; border:1px solid var(--border); border-radius:10px; padding:14px; font-size:13px; color:#cbd5e1; }
        .app-name { font-weight:700; color:var(--accent); margin-bottom:4px; display:flex; align-items:center; gap:6px; }
    </style>
</head>
<body>
<div class="container">
    <a href="/" class="btn-back">&larr; Kembali ke Utama</a>
    <div class="card-box" style="display:flex; gap:20px; align-items:center; flex-wrap:wrap;">
        <img src="/profile.jpg" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'" alt="Dede Suhendra" style="width:140px; height:140px; border-radius:50%; object-fit:cover; border:3px solid #38bdf8; margin:0 auto; display:block;">
        <div style="flex:1; min-width:250px;">
            <h2 class="card-title" style="border-bottom:none; padding-bottom:0; margin-bottom:8px;">👨‍💻 Profil Penulis</h2>
            <p class="card-p">Selamat datang di ruang pustaka pribadi karya dan catatan saya. Nama saya <strong>Dede Suhendra</strong>, lahir 8 Juli 2001, dari Subang.</p>
            <p class="card-p" style="margin-bottom:0;">Dokumentasi pemikiran, perjalanan belajar, riset harian, serta modul pembelajaran yang disusun terstruktur.</p>
        </div>
    </div>
    <div class="card-box">
        <h2 class="card-title">✍️ Perjuangan & Latar Belakang Penulisan</h2>
        <p class="card-p">Setiap tulisan lahir dari proses yang tidak instan. Di tengah padatnya aktivitas harian, setiap sisa waktu luang dimanfaatkan untuk tetap konsisten menulis dan mendokumentasikan ilmu.</p>
        <p class="card-p">Bagi saya, menulis bukan sekadar merangkai kata, melainkan bentuk pengikatan ilmu dan sarana merefleksikan pembelajaran hidup agar bermanfaat secara luas dan berkelanjutan.</p>
    </div>
    <div class="card-box">
        <h2 class="card-title">📜 Riwayat Pendidikan & Pengalaman</h2>
        <h4 style="color:var(--accent); font-size:14px; margin-top:10px; margin-bottom:10px;">🎓 Pendidikan:</h4>
        <div class="timeline">
            <div class="timeline-item"><div class="timeline-year">2013</div><div class="timeline-title">SDN Sindang Laut II</div><div class="timeline-desc">Lulus SD</div></div>
            <div class="timeline-item"><div class="timeline-year">2013–2015</div><div class="timeline-title">Ponpes Madinatul Musthofa</div><div class="timeline-desc">Pendidikan Pesantren</div></div>
            <div class="timeline-item"><div class="timeline-year">2015–2016</div><div class="timeline-title">Pondok Tahfidz Qur'an</div><div class="timeline-desc">Fokus Menghafal Al-Qur'an</div></div>
            <div class="timeline-item"><div class="timeline-year">2016–2019</div><div class="timeline-title">Ponpes Madinatul Musthofa</div><div class="timeline-desc">Studi Keagamaan</div></div>
            <div class="timeline-item"><div class="timeline-year">2019–2022</div><div class="timeline-title">Pondok Modern Darussalam Gontor</div><div class="timeline-desc">Pendidikan KMI Gontor</div></div>
            <div class="timeline-item"><div class="timeline-year">2022–2023</div><div class="timeline-title">Pengabdian Gontor & UNIDA Gontor</div><div class="timeline-desc">Mengabdi sambil kuliah</div></div>
            <div class="timeline-item"><div class="timeline-year">2023–2025</div><div class="timeline-title">Pengajar Ponpes & STISQ AL-IHYA Subang</div><div class="timeline-desc">Mengajar sambil kuliah IAT</div></div>
        </div>
        <h4 style="color:var(--accent); font-size:14px; margin-top:20px; margin-bottom:10px;">💼 Pengalaman Kerja & Khidmat:</h4>
        <div class="timeline">
            <div class="timeline-item"><div class="timeline-year">2025</div><div class="timeline-title">Gudang Shopee Tangerang</div><div class="timeline-desc">Operasional Logistik</div></div>
            <div class="timeline-item"><div class="timeline-year">2025</div><div class="timeline-title">Karyawan Fotokopi Jakarta Pusat</div><div class="timeline-desc">Operasional Toko</div></div>
            <div class="timeline-item"><div class="timeline-year">2025</div><div class="timeline-title">Barista & Chef Bogor</div><div class="timeline-desc">Minuman & Dapur</div></div>
            <div class="timeline-item"><div class="timeline-year">Sekarang</div><div class="timeline-title">Imam, Muadzin & Pengajar Al-Qur'an Tangerang</div><div class="timeline-desc">Kemakmuran Masjid & Pengajian Anak-anak</div></div>
        </div>
    </div>
    <div class="card-box">
        <h2 class="card-title">🎯 Visi & Misi Penulisan</h2>
        <p class="card-p"><strong>Visi:</strong> Menjadikan dokumentasi catatan pribadi sebagai sarana pengikat ilmu, pengembangan diri berkelanjutan, dan ladang manfaat terstruktur.</p>
        <p class="card-p"><strong>Misi:</strong></p>
        <ul class="list-custom">
            <li>Memanfaatkan setiap sisa waktu luang secara produktif untuk merangkai karya tulis dan modul bermanfaat.</li>
            <li>Mendokumentasikan pemahaman keagamaan, riset harian, dan keterampilan operasional secara rapi dan terbuka.</li>
            <li>Terus belajar dan memberikan dampak positif bagi santri, jamaah masjid, serta lingkungan sekitar.</li>
        </ul>
    </div>
    <div class="card-box">
        <h2 class="card-title">🙏 Apresiasi & Rasa Syukur</h2>
        <p class="card-p">Rasa syukur dan terima kasih kepada orang-orang terkasih yang menjadi sumber kekuatan, doa, dan inspirasi:</p>
        <div class="appreciation-grid">
            <div class="app-item"><div class="app-name">👨‍👦 Bapak Khairudin</div><div>Doa, kerja keras, dan bimbingan tanpa henti.</div></div>
            <div class="app-item"><div class="app-name">💐 Ibu Sumini (Almarhumah)</div><div>Semoga Allah mengampuni dan menempatkan di tempat terbaik.</div></div>
            <div class="app-item"><div class="app-name">👫 Siti Aisyah & Muhammad Naimul Ilmi</div><div>Adik-adik tersayang, kebanggaan dan penyemangat.</div></div>
            <div class="app-item"><div class="app-name">👦 Muhammad Aji</div><div>Kakak tercinta atas kebersamaan dan dukungan.</div></div>
            <div class="app-item"><div class="app-name">❤️ Sri Nur Safitri</div><div>Perhatian, dorongan semangat, dan pendamping setia.</div></div>
            <div class="app-item"><div class="app-name">🤝 Sahabat & Kolega</div><div>Semua yang telah mendukung dan mendoakan.</div></div>
        </div>
    </div>
</div>
</body>
</html>
"""

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login Admin - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .login-card { background: #1e293b; border: 1px solid #334155; padding: 30px; border-radius: 12px; width: 100%; max-width: 400px; }
    </style>
</head>
<body>
    <div class="login-card shadow-lg">
        <h3 class="text-info text-center fw-bold mb-1">🔑 Login Admin</h3>
        <p class="text-muted text-center small mb-4">Masuk untuk mengelola catatan karya</p>
        {% if error %}<div class="alert alert-danger py-2 small text-center">{{ error }}</div>{% endif %}
        <form action="/login" method="POST">
            <input type="text" name="username" class="form-control mb-3 bg-dark text-white border-secondary" placeholder="Username" required>
            <input type="password" name="password" class="form-control mb-3 bg-dark text-white border-secondary" placeholder="Password" required>
            <button type="submit" class="btn btn-info w-100 fw-bold">Masuk ke Sistem</button>
        </form>
        <div class="text-center mt-3">
            <a href="/" class="text-muted text-decoration-none small">&larr; Kembali ke Utama</a>
        </div>
    </div>
</body>
</html>
"""

# ==================================================
# ROUTING APLIKASI PYTHON FLASK
# ==================================================

@app.route('/')
def index():
    is_admin = session.get('is_admin')
    tema_list = Tema.query.order_by(Tema.id.asc()).all()
    jumlah_esai = EsaiPenulis.query.count()
    return render_template_string(HTML_INDEX, tema_list=tema_list, is_admin=is_admin, jumlah_esai=jumlah_esai)

@app.route('/penulis')
def tentang_penulis():
    return render_template_string(HTML_PENULIS)

@app.route('/catatan-penulis')
def catatan_penulis():
    is_admin = session.get('is_admin')
    esai_list = EsaiPenulis.query.order_by(EsaiPenulis.id.desc()).all()
    return render_template_string(HTML_ESAI_PENULIS, esai_list=esai_list, is_admin=is_admin)

@app.route('/tambah-esai', methods=['POST'])
def tambah_esai():
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    judul = request.form.get('judul')
    kategori = request.form.get('kategori', 'Refleksi Harian')
    isi = request.form.get('isi')
    if judul and isi:
        e = EsaiPenulis(judul=judul, kategori=kategori, isi=isi)
        db.session.add(e)
        db.session.commit()
    return redirect('/catatan-penulis')

@app.route('/hapus-esai/<int:esai_id>', methods=['POST'])
def hapus_esai(esai_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    e = EsaiPenulis.query.get(esai_id)
    if e:
        masukkan_sampah('esai', {'judul': e.judul, 'kategori': e.kategori, 'isi': e.isi})
        db.session.delete(e)
        db.session.commit()
    return redirect('/catatan-penulis')

@app.route('/tema/<int:tema_id>')
def detail_tema(tema_id):
    is_admin = session.get('is_admin')
    tema = Tema.query.get_or_404(tema_id)
    buku_list = Buku.query.filter_by(tema_id=tema_id).order_by(Buku.id.asc()).all()
    return render_template_string(HTML_TEMA, tema=tema, buku_list=buku_list, is_admin=is_admin)

@app.route('/tambah-tema', methods=['POST'])
def tambah_tema():
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    nama = request.form.get('nama')
    if nama:
        db.session.add(Tema(nama=nama))
        db.session.commit()
    return redirect('/')

@app.route('/hapus-tema/<int:tema_id>', methods=['POST'])
def hapus_tema(tema_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    tema = Tema.query.get(tema_id)
    if tema:
        masukkan_sampah('tema', {'nama': tema.nama})
        db.session.delete(tema)
        db.session.commit()
    return redirect('/')

@app.route('/tambah-buku', methods=['POST'])
def tambah_buku():
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    judul = request.form.get('judul')
    subjudul = request.form.get('subjudul', '')
    tema_id = request.form.get('tema_id')
    kutipan = request.form.get('kutipan', '')
    if judul and tema_id:
        buku_baru = Buku(judul=judul, subjudul=subjudul, tema_id=int(tema_id), kutipan=kutipan)
        db.session.add(buku_baru)
        db.session.commit()
    return redirect(f'/tema/{tema_id}')

@app.route('/hapus-buku/<int:buku_id>/<int:tema_id>', methods=['POST'])
def hapus_buku(buku_id, tema_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    buku = Buku.query.get(buku_id)
    if buku:
        masukkan_sampah('buku', {'judul': buku.judul, 'subjudul': buku.subjudul})
        db.session.delete(buku)
        db.session.commit()
    return redirect(f'/tema/{tema_id}')

@app.route('/statistik')
def statistik():
    total_tema = Tema.query.count()
    total_buku = Buku.query.count()
    total_catatan = Catatan.query.count()
    total_esai = EsaiPenulis.query.count()
    
    semua_catatan = Catatan.query.all()
    semua_esai = EsaiPenulis.query.all()
    total_kata = sum(len(c.isi.split()) for c in semua_catatan) + sum(len(e.isi.split()) for e in semua_esai)
    
    awal_bulan = datetime(datetime.utcnow().year, datetime.utcnow().month, 1)
    buku_bulan_ini = Buku.query.filter(Buku.dibuat_pada >= awal_bulan).count()
    esai_bulan_ini = EsaiPenulis.query.filter(EsaiPenulis.dibuat_pada >= awal_bulan).count()
    
    return render_template_string(HTML_STATISTIK, 
                                  total_tema=total_tema, total_buku=total_buku, 
                                  total_catatan=total_catatan, total_esai=total_esai,
                                  total_kata=total_kata, buku_bulan_ini=buku_bulan_ini, 
                                  esai_bulan_ini=esai_bulan_ini)

@app.route('/tong-sampah')
def tong_sampah():
    sampah_list = TongSampah.query.order_by(TongSampah.dihapus_pada.desc()).all()
    return render_template_string(HTML_TONG_SAMPAH, sampah_list=sampah_list)

@app.route('/pulihkan/<int:item_id>')
def pulihkan(item_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    item = TongSampah.query.get_or_404(item_id)
    data = json.loads(item.data_json)
    if item.tipe == 'tema':
        db.session.add(Tema(nama=data['nama']))
    elif item.tipe == 'buku':
        db.session.add(Buku(judul=data['judul'], subjudul=data.get('subjudul', ''), tema_id=1))
    elif item.tipe == 'esai':
        db.session.add(EsaiPenulis(judul=data['judul'], kategori=data.get('kategori', 'Refleksi'), isi=data['isi']))
    db.session.delete(item)
    db.session.commit()
    return redirect('/tong-sampah')

@app.route('/hapus-permanen/<int:item_id>')
def hapus_permanen(item_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    item = TongSampah.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect('/tong-sampah')

@app.route('/kosongkan-tong-sampah', methods=['POST'])
def kosongkan_tong_sampah():
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    TongSampah.query.delete()
    db.session.commit()
    return redirect('/tong-sampah')

@app.route('/login', methods=['GET', 'POST'])
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

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')

@app.route('/backup')
def backup_db():
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    data = {
        "tema": [{"id": t.id, "nama": t.nama} for t in Tema.query.all()],
        "buku": [{"id": b.id, "judul": b.judul, "subjudul": b.subjudul, "tema_id": b.tema_id, "kutipan": b.kutipan} for b in Buku.query.all()],
        "catatan": [{"id": c.id, "bagian": c.bagian, "judul_bab": c.judul_bab, "isi": c.isi, "buku_id": c.buku_id} for c in Catatan.query.all()],
        "esai": [{"id": e.id, "judul": e.judul, "kategori": e.kategori, "isi": e.isi} for e in EsaiPenulis.query.all()]
    }
    return Response(json.dumps(data, indent=2), mimetype='application/json', headers={'Content-Disposition': 'attachment;filename=backup_karya.json'})

app = app
