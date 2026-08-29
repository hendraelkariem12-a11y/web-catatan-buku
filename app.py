import os
import json
from flask import Flask, request, redirect, render_template_string, session, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'karya-dede-suhendra-secret-key'

# --------------------------------------------------
# KONFIGURASI DATABASE SQLALCHEMY (VERCEL PERMANENT)
# --------------------------------------------------
db_path = os.path.join('/tmp', 'karya_buku.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ADMIN_USER = "dede"
ADMIN_PASS = "suhendra123"

# --------------------------------------------------
# MODEL DATABASE (SQLAlchemy ORM)
# --------------------------------------------------
class Tema(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    buku_list = db.relationship('Buku', backref='tema', lazy=True, cascade="all, delete-orphan")

class Buku(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    subjudul = db.Column(db.String(250), nullable=True)
    kutipan = db.Column(db.Text, nullable=True)
    tema_id = db.Column(db.Integer, db.ForeignKey('tema.id'), nullable=False)
    catatan_list = db.relationship('Catatan', backref='buku', lazy=True, cascade="all, delete-orphan")

class Catatan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bagian = db.Column(db.String(100), nullable=True)
    judul_bab = db.Column(db.String(200), nullable=False)
    isi = db.Column(db.Text, nullable=False)
    buku_id = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)

with app.app_context():
    db.create_all()
    if Tema.query.count() == 0:
        db.session.add_all([
            Tema(nama='Filsafat'),
            Tema(nama='Keuangan'),
            Tema(nama='Komunikasi')
        ])
        db.session.commit()

# Route khusus membaca profile.jpg dari folder utama
@app.route('/profile.jpg')
def serve_profile():
    return send_from_directory('.', 'profile.jpg')

# --------------------------------------------------
# TEMPLATE HTML
# --------------------------------------------------

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
    <style>
        :root { --bg-paper: #f7f4ef; --card-paper: #ffffff; --text-main: #2c2a29; --gold-gradient: linear-gradient(135deg, #bf953f, #fcf6ba, #b38728, #fbf5b7); }
        body { background-color: var(--bg-paper) !important; font-family: 'Plus Jakarta Sans', sans-serif; color: var(--text-main); }
        .header-title { font-family: 'Cinzel', serif; font-weight: 700; color: #1e293b; }
        .top-badge { background: #fcf8ec; color: #b38728; border: 1px solid rgba(212, 175, 55, 0.4); font-weight: 700; padding: 6px 16px; border-radius: 30px; font-size: 0.8rem; letter-spacing: 1px; display: inline-block; }
        .card-gold { background: var(--card-paper); border-radius: 18px; border: 1px solid rgba(212, 175, 55, 0.3); box-shadow: 0 10px 25px rgba(0,0,0,0.03); transition: all 0.3s ease; position: relative; overflow: hidden; }
        .card-gold::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 4px; background: var(--gold-gradient); }
        .card-gold:hover { transform: translateY(-4px); box-shadow: 0 15px 30px rgba(212, 175, 55, 0.18); }
        .card-penulis { background: linear-gradient(135deg, #ffffff 0%, #fcf8ec 100%); border: 2px solid rgba(212, 175, 55, 0.5); }
        .title-gold { font-family: 'Cinzel', serif; font-weight: 700; color: #1e293b; }
    </style>
</head>
<body>
<div class="container py-5" style="max-width: 850px;">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <a href="/penulis" class="btn btn-outline-dark rounded-pill btn-sm px-3 fw-bold"><i class="fa-solid fa-feather-pointed me-1"></i> Profil Penulis</a>
        <div>
            {% if is_admin %}
                <a href="/backup" class="btn btn-outline-primary rounded-pill btn-sm me-2"><i class="fa-solid fa-download me-1"></i> Backup</a>
                <a href="/logout" class="btn btn-warning rounded-pill btn-sm fw-bold text-dark"><i class="fa-solid fa-right-from-bracket me-1"></i> Logout Admin</a>
            {% else %}
                <a href="/login" class="btn btn-outline-dark rounded-pill btn-sm fw-bold"><i class="fa-solid fa-lock me-1"></i> Login Admin</a>
            {% endif %}
        </div>
    </div>
    
    <div class="text-center mb-5">
        <span class="top-badge mb-2">OFFICIAL VAULT</span>
        <h1 class="header-title h2 mb-2">Catatan & Karya Buku</h1>
        <p class="text-muted small">Disusun & Dikelola oleh <strong>Dede Suhendra</strong></p>
    </div>

    {% if is_admin %}
    <div class="card border-0 shadow-sm p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-success mb-2"><i class="fa-solid fa-folder-plus me-1"></i> Tambah Tema / Kategori Baru</h6>
        <form action="/tambah-tema" method="POST" class="row g-2">
            <div class="col-9">
                <input type="text" name="nama" class="form-control form-control-sm" placeholder="Misal: Psikologi, Filsafat..." required>
            </div>
            <div class="col-3">
                <button type="submit" class="btn btn-success btn-sm w-100 fw-bold">Tambah</button>
            </div>
        </form>
    </div>
    {% endif %}

    <h5 class="fw-bold mb-3" style="font-family: 'Cinzel', serif; color: #1e293b;">Pilih Tema / Kategori Karya:</h5>
    <div class="row g-3">
        <div class="col-12">
            <a href="/penulis" class="text-decoration-none">
                <div class="card-gold card-penulis p-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <div class="bg-warning text-dark rounded-circle p-3 me-3"><i class="fa-solid fa-feather-pointed fs-4"></i></div>
                            <div>
                                <span class="badge bg-warning text-dark fw-bold mb-1">Karya Spesial</span>
                                <h4 class="title-gold h5 mb-1">✍️ Catatan Penulis</h4>
                                <p class="text-muted small mb-0">Rangkuman pemikiran mendalam & jurnal esensial penulis.</p>
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
                        <h4 class="title-gold h5 mb-0">{{ tema.nama }}</h4>
                    </a>
                    {% if is_admin %}
                    <form action="/hapus-tema/{{ tema.id }}" method="POST" onsubmit="return confirm('Hapus tema beserta seluruh buku di dalamnya?');">
                        <button type="submit" class="btn btn-link text-danger p-0 ms-2"><i class="fa-solid fa-trash"></i></button>
                    </form>
                    {% endif %}
                </div>
                <small class="text-muted ms-4">Lihat Koleksi Buku &rarr;</small>
            </div>
        </div>
        {% endfor %}
    </div>
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
    <title>Catatan Penulis - Dede Suhendra</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0b132b; --card: #1c2541; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8; --border: #334155; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 20px; line-height: 1.6; }
        .container { max-width: 760px; margin: 0 auto; }
        .btn-back { display: inline-block; color: var(--muted); text-decoration: none; font-size: 13px; font-weight: 600; margin-bottom: 20px; }
        .btn-back:hover { color: var(--accent); }
        .card-box { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .card-title { font-size: 18px; font-weight: 800; color: var(--accent); margin-bottom: 14px; display: flex; align-items: center; gap: 8px; border-bottom: 1px dashed var(--border); padding-bottom: 10px; }
        .card-p { color: #cbd5e1; font-size: 14px; margin-bottom: 12px; }

        .timeline { position: relative; border-left: 2px solid var(--border); padding-left: 18px; margin-top: 10px; margin-left: 6px; }
        .timeline-item { position: relative; margin-bottom: 16px; }
        .timeline-item::before { content: ""; position: absolute; left: -24px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: var(--accent); }
        .timeline-year { font-size: 12px; font-weight: 800; color: var(--accent); }
        .timeline-title { font-size: 14px; font-weight: 700; color: var(--text); }
        .timeline-desc { font-size: 13px; color: var(--muted); }

        .list-custom { list-style: none; padding-left: 0; }
        .list-custom li { font-size: 14px; color: #cbd5e1; margin-bottom: 10px; padding-left: 24px; position: relative; }
        .list-custom li::before { content: "🎯"; position: absolute; left: 0; font-size: 13px; }

        .appreciation-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin-top: 10px; }
        .app-item { background: #0f172a; border: 1px solid var(--border); border-radius: 10px; padding: 14px; font-size: 13px; color: #cbd5e1; }
        .app-name { font-weight: 700; color: var(--accent); margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
    </style>
</head>
<body>

<div class="container">
    <a href="/" class="btn-back">&larr; Kembali ke Utama</a>

    <!-- 1. PROFIL PENULIS -->
    <div class="card-box" style="display: flex; gap: 20px; align-items: center; flex-wrap: wrap;">
        <img src="/profile.jpg" onerror="this.src='https://cdn-icons-png.flaticon.com/512/3135/3135715.png'" alt="Dede Suhendra" style="width: 140px; height: 140px; border-radius: 50%; object-fit: cover; border: 3px solid #38bdf8; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2); margin: 0 auto; display: block;">

        <div style="flex: 1; min-width: 250px;">
            <h2 class="card-title" style="border-bottom: none; padding-bottom: 0; margin-bottom: 8px;">👨‍💻 Profil Penulis</h2>
            <p class="card-p">Selamat datang di ruang pustaka pribadi karya dan catatan saya. Perkenalkan, nama saya <strong>Dede Suhendra</strong>, lahir pada tanggal <strong>8 Juli 2001</strong> dan berasal dari <strong>Subang</strong>.</p>
            <p class="card-p" style="margin-bottom: 0;">Halaman ini dihadirkan sebagai wadah dokumentasi pemikiran, perjalanan belajar, riset harian, serta modul pembelajaran yang disusun secara terstruktur.</p>
        </div>
    </div>

    <!-- 2. PERJUANGAN & LATAR BELAKANG PENULISAN -->
    <div class="card-box">
        <h2 class="card-title">✍️ Perjuangan & Latar Belakang Penulisan</h2>
        <p class="card-p">Setiap tulisan dan modul yang ada di dalam ruang ini lahir dari proses yang tidak instan. Di tengah padatnya aktivitas harian dan dinamika perjuangan hidup, saya memanfaatkan setiap sisa-sisa waktu luang yang ada untuk tetap konsisten menulis dan mendokumentasikan ilmu.</p>
        <p class="card-p">Bagi saya, menulis bukan sekadar merangkai kata, melainkan bentuk pengikatan ilmu dan sarana untuk merefleksikan setiap tahap pembelajaran hidup agar bermanfaat secara luas dan berkelanjutan.</p>
    </div>

    <!-- 3. RIWAYAT PENDIDIKAN & PENGALAMAN -->
    <div class="card-box">
        <h2 class="card-title">📜 Riwayat Pendidikan & Pengalaman Perjalanan</h2>

        <h4 style="color: var(--accent); font-size: 14px; margin-top: 10px; margin-bottom: 10px;">🎓 Riwayat Pendidikan:</h4>
        <div class="timeline">
            <div class="timeline-item">
                <div class="timeline-year">2013</div>
                <div class="timeline-title">SDN Sindang Laut II</div>
                <div class="timeline-desc">Lulus Pendidikan Sekolah Dasar</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2013 – 2015</div>
                <div class="timeline-title">Pondok Pesantren Madinatul Musthofa</div>
                <div class="timeline-desc">Menempuh Pendidikan Pesantren Tahap Awal</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2015 – 2016</div>
                <div class="timeline-title">Pondok Tahfidz Qur'an</div>
                <div class="timeline-desc">Fokus Menghafal Al-Qur'an</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2016 – 2019</div>
                <div class="timeline-title">Pondok Pesantren Madinatul Musthofa</div>
                <div class="timeline-desc">Melanjutkan Studi Keagamaan & Pesantren</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2019 – 2022</div>
                <div class="timeline-title">Pondok Modern Darussalam Gontor</div>
                <div class="timeline-desc">Menempuh Pendidikan di KMI Gontor</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2022 – 2023</div>
                <div class="timeline-title">Pengabdian Gontor Kampus 2 & UNIDA Gontor</div>
                <div class="timeline-desc">Mengabdi di PMDG Kampus 2 sambil menempuh kuliah Jurusan Studi Agama-Agama UNIDA Gontor</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2023 – 2025</div>
                <div class="timeline-title">Pengajar Ponpes Madinatul Musthofa & STISQ AL-IHYA Subang</div>
                <div class="timeline-desc">Mengajar di Ponpes Madinatun Mustofa sambil menempuh kuliah Jurusan Ilmu Al-Qur'an dan Tafsir (IAT) di STIESKU Subang</div>
            </div>
        </div>

        <h4 style="color: var(--accent); font-size: 14px; margin-top: 20px; margin-bottom: 10px;">💼 Pengalaman Kerja & Khidmat:</h4>
        <div class="timeline">
            <div class="timeline-item">
                <div class="timeline-year">2025</div>
                <div class="timeline-title">Gudang Shopee (Tangerang)</div>
                <div class="timeline-desc">Pengalaman Kerja Operasional Logistik</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2025</div>
                <div class="timeline-title">Karyawan Fotokopi (Jakarta Pusat)</div>
                <div class="timeline-desc">Menjaga & Mengelola Operasional Toko Fotokopi</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">2025</div>
                <div class="timeline-title">Barista & Chef / Tukang Masak (Bogor)</div>
                <div class="timeline-desc">Menggabungkan Peran Sebagai Barista Minuman & Penanggung Jawab Dapur Makanan</div>
            </div>
            <div class="timeline-item">
                <div class="timeline-year">Sekarang</div>
                <div class="timeline-title">Imam dan Muadzin & Pengajar Al-Qur'an (Tangerang)</div>
                <div class="timeline-desc">Mengurus Kemakmuran Masjid dan Mengajar Pengajian Al-Qur'an Anak-anak</div>
            </div>
        </div>
    </div>

    <!-- 4. VISI & MISI -->
    <div class="card-box">
        <h2 class="card-title">🎯 Visi & Misi Penulisan</h2>
        <p class="card-p"><strong>Visi:</strong> Menjadikan dokumentasi catatan pribadi sebagai sarana pengikat ilmu, pengembangan diri yang berkelanjutan, dan ladang manfaat yang terstruktur.</p>
        <div style="margin-top: 10px;">
            <p class="card-p"><strong>Misi:</strong></p>
            <ul class="list-custom">
                <li>Memanfaatkan setiap sisa waktu luang secara produktif untuk merangkai karya tulis dan modul bermanfaat.</li>
                <li>Mendokumentasikan pemahaman keagamaan, riset harian, dan keterampilan operasional secara rapi dan terbuka.</li>
                <li>Terus belajar dan memberikan dampak positif bagi santri, jamaah masjid, serta lingkungan sekitar.</li>
            </ul>
        </div>
    </div>

    <!-- 5. APRESIASI & UCAPAN TERIMA KASIH -->
    <div class="card-box">
        <h2 class="card-title">🙏 Apresiasi & Penghargaan Serta Rasa Syukur</h2>
        <p class="card-p">Rasa syukur dan terima kasih yang mendalam saya persembahkan kepada orang-orang terkasih yang selalu menjadi sumber kekuatan, doa, dan inspirasi dalam hidup saya:</p>

        <div class="appreciation-grid">
            <div class="app-item">
                <div class="app-name">👨‍👦 Bapak Khairudin</div>
                <div>Selaku ayah tercinta yang senantiasa memberikan doa, kerja keras, dan bimbingan tanpa henti.</div>
            </div>
            <div class="app-item">
                <div class="app-name">💐 Ibu Sumini (Almarhumah)</div>
                <div>Almarhumah ibu tercinta. Semoga Allah ﷻ mengampuni dosa-dosanya, mengangkat derajatnya, dan menempatkan beliau di tempat terbaik di sisi-Nya.</div>
            </div>
            <div class="app-item">
                <div class="app-name">👫 Siti Aisyah & Muhammad Naimul Ilmi</div>
                <div>Adik-adik tersayang yang selalu menjadi kebanggaan dan penyemangat dalam melangkah.</div>
            </div>
            <div class="app-item">
                <div class="app-name">👦 Muhammad Aji</div>
                <div>Kakak tercinta atas kebersamaan, support, dan persaudaraan yang luar biasa.</div>
            </div>
            <div class="app-item">
                <div class="app-name">❤️ Sri Nur Safitri</div>
                <div>Kekasih tercinta yang selalu memberikan perhatian, dorongan semangat, dan menemani setiap proses perjalanan.</div>
            </div>
            <div class="app-item">
                <div class="app-name">🤝 Sahabat & Kolega</div>
                <div>Seluruh teman-teman, guru-guru, rekan seperjuangan, dan kolega yang tidak bisa disebutkan satu per satu atas segala doa dan dukungannya.</div>
            </div>
        </div>
    </div>

</div>

</body>
</html>
"""

HTML_TEMA = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tema: {{ tema.nama }} - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --bg-paper: #f7f4ef; --card-paper: #ffffff; --text-main: #2c2a29; --gold-gradient: linear-gradient(135deg, #bf953f, #fcf6ba, #b38728, #fbf5b7); }
        body { background-color: var(--bg-paper) !important; font-family: 'Plus Jakarta Sans', sans-serif; color: var(--text-main); }
        .card-buku-gold { background: var(--card-paper); border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.3); box-shadow: 0 10px 25px rgba(0,0,0,0.03); transition: all 0.3s ease; position: relative; overflow: hidden; }
        .card-buku-gold::before { content: ''; position: absolute; top: 0; left: 0; width: 5px; height: 100%; background: var(--gold-gradient); }
        .title-buku { font-family: 'Cinzel', serif; font-weight: 700; color: #1e293b; }
    </style>
</head>
<body>
<div class="container py-5" style="max-width: 850px;">
    <a href="/" class="btn btn-outline-dark rounded-pill btn-sm px-4 mb-4 shadow-sm" style="font-weight: 600;">
        <i class="fa-solid fa-arrow-left me-2"></i>Kembali ke Semua Tema
    </a>

    <div class="bg-white rounded-4 p-4 mb-4 shadow-sm border" style="border-color: rgba(212, 175, 55, 0.3) !important;">
        <span class="badge bg-warning text-dark mb-2 fw-bold"><i class="fa-solid fa-folder-open me-1"></i> Kategori Karya</span>
        <h2 class="h3 fw-bold mb-1" style="font-family: 'Cinzel', serif; color: #1e293b;">Tema: {{ tema.nama }}</h2>
    </div>

    {% if is_admin %}
    <div class="card border-0 shadow-sm p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-success mb-2"><i class="fa-solid fa-book-medical me-1"></i> Tambah Buku Baru ke Tema Ini</h6>
        <form action="/tambah-buku" method="POST" class="row g-2">
            <input type="hidden" name="tema_id" value="{{ tema.id }}">
            <div class="col-md-6">
                <input type="text" name="judul" class="form-control form-control-sm" placeholder="Judul Buku..." required>
            </div>
            <div class="col-md-6">
                <input type="text" name="subjudul" class="form-control form-control-sm" placeholder="Subjudul (Opsional)...">
            </div>
            <div class="col-12">
                <textarea name="kutipan" class="form-control form-control-sm" rows="2" placeholder="Kutipan Penulis..."></textarea>
            </div>
            <div class="col-12">
                <button type="submit" class="btn btn-success btn-sm w-100 fw-bold">Tambah Buku</button>
            </div>
        </form>
    </div>
    {% endif %}

    <h5 class="fw-bold mb-3" style="font-family: 'Cinzel', serif; color: #1e293b;">Daftar Buku Tersimpan:</h5>
    <div class="row g-3">
        {% for buku in buku_list %}
        <div class="col-12">
            <div class="card-buku-gold p-4">
                <div class="d-flex justify-content-between align-items-center">
                    <a href="/buku/{{ buku.id }}" class="text-decoration-none flex-grow-1">
                        <div class="d-flex align-items-center">
                            <i class="fa-solid fa-file-lines text-warning fs-4 me-3"></i>
                            <div>
                                <h4 class="title-buku h5 mb-1">{{ buku.judul.upper() }}</h4>
                                {% if buku.subjudul %}<p class="text-muted small mb-0">{{ buku.subjudul }}</p>{% endif %}
                            </div>
                        </div>
                    </a>
                    {% if is_admin %}
                    <form action="/hapus-buku/{{ buku.id }}/{{ tema.id }}" method="POST" onsubmit="return confirm('Hapus buku ini?');">
                        <button type="submit" class="btn btn-link text-danger p-0 ms-2"><i class="fa-solid fa-trash"></i></button>
                    </form>
                    {% endif %}
                </div>
            </div>
        </div>
        {% else %}
        <div class="text-center py-4 bg-white rounded-4 shadow-sm">
            <p class="text-muted mb-0">Belum ada buku dalam tema ini.</p>
        </div>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

HTML_DETAIL_BUKU = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ buku.judul.upper() }} - Dede Suhendra</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Merriweather:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --bg-color: #0b0f19; --card-bg: #131c31; --accent: #38bdf8; --text-main: #f1f5f9; --text-muted: #94a3b8; --border-card: #334155; }
        body { background-color: var(--bg-color); color: var(--text-main); font-family: 'Plus Jakarta Sans', sans-serif; padding: 25px 15px; }
        .container { max-width: 760px; margin: 0 auto; }
        .book-cover-card { background: linear-gradient(135deg, var(--card-bg) 0%, #172554 100%); border: 1px solid var(--border-card); border-radius: 20px; padding: 40px 25px; text-align: center; margin-bottom: 25px; }
        .book-main-title { font-size: 28px; font-weight: 800; color: var(--accent); letter-spacing: 1px; }
        .author-quote-box { background: var(--card-bg); border-left: 4px solid var(--accent); padding: 18px 22px; font-style: italic; margin-bottom: 25px; border-radius: 0 12px 12px 0; }
        .note-card { background: var(--card-bg); border: 1px solid var(--border-card); border-radius: 16px; padding: 25px; margin-bottom: 25px; position: relative; }
        .markdown-body { line-height: 1.8; color: var(--text-main); }
    </style>
</head>
<body>
<div class="container">
    <a href="/tema/{{ buku.tema_id }}" class="btn btn-outline-light btn-sm mb-4"><i class="fa-solid fa-arrow-left me-1"></i> Kembali ke Tema</a>
    
    <div class="book-cover-card">
        <div class="book-main-title">📖 {{ buku.judul.upper() }}</div>
        {% if buku.subjudul %}<div class="text-muted mt-2 italic">{{ buku.subjudul }}</div>{% endif %}
        <div class="mt-3 text-uppercase small text-muted border-top pt-2 d-inline-block">Karya: Dede Suhendra</div>
    </div>

    {% if buku.kutipan %}
    <div class="author-quote-box">"{{ buku.kutipan }}"</div>
    {% endif %}

    {% if is_admin %}
    <div class="card bg-dark text-white border-secondary p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-info mb-2"><i class="fa-solid fa-pen-to-square me-1"></i> Tambah Bab / Catatan Baru</h6>
        <form action="/buku/{{ buku.id }}/tambah-catatan" method="POST">
            <input type="text" name="bagian" class="form-control form-control-sm mb-2 bg-secondary text-white border-0" placeholder="Bagian (Misal: Bagian 1: Fondasi)...">
            <input type="text" name="judul_bab" class="form-control form-control-sm mb-2 bg-secondary text-white border-0" placeholder="Judul Bab (Misal: Bab 1 - Pengantar)..." required>
            <textarea name="isi" class="form-control form-control-sm mb-2 bg-secondary text-white border-0" rows="4" placeholder="Tulis isi bab (Mendukung Markdown)..." required></textarea>
            <button type="submit" class="btn btn-info btn-sm w-100 fw-bold">Simpan ke Buku</button>
        </form>
    </div>
    {% endif %}

    {% for c in catatan_list %}
    <div class="note-card">
        {% if is_admin %}
        <form action="/hapus-catatan/{{ c.id }}/{{ buku.id }}" method="POST" class="position-absolute top-0 end-0 p-3" onsubmit="return confirm('Hapus bab ini?');">
            <button type="submit" class="btn btn-link text-danger p-0"><i class="fa-solid fa-trash"></i></button>
        </form>
        {% endif %}

        {% if c.bagian %}<span class="badge bg-info text-dark mb-2">{{ c.bagian }}</span>{% endif %}
        <h4 class="text-info fw-bold mb-3">{{ c.judul_bab }}</h4>
        <div class="markdown-body" id="content-{{ c.id }}"></div>
        <textarea id="raw-{{ c.id }}" style="display:none;">{{ c.isi }}</textarea>
    </div>
    {% else %}
    <p class="text-center text-muted py-4">Belum ada bab atau catatan tersimpan di buku ini.</p>
    {% endfor %}
</div>

<script>
    document.addEventListener("DOMContentLoaded", function() {
        marked.use({ gfm: true, breaks: true });
        {% for c in catatan_list %}
            var rawText = document.getElementById('raw-{{ c.id }}').value;
            document.getElementById('content-{{ c.id }}').innerHTML = marked.parse(rawText);
        {% endfor %}
    });
</script>
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

# --------------------------------------------------
# ROUTING APLIKASI
# --------------------------------------------------

@app.route('/')
def index():
    is_admin = session.get('is_admin')
    tema_list = Tema.query.order_by(Tema.id.asc()).all()
    return render_template_string(HTML_INDEX, tema_list=tema_list, is_admin=is_admin)

@app.route('/penulis')
def tentang_penulis():
    return render_template_string(HTML_PENULIS)

@app.route('/tema/<int:tema_id>')
def detail_tema(tema_id):
    is_admin = session.get('is_admin')
    tema = Tema.query.get_or_404(tema_id)
    buku_list = Buku.query.filter_by(tema_id=tema_id).order_by(Buku.id.asc()).all()
    return render_template_string(HTML_TEMA, tema=tema, buku_list=buku_list, is_admin=is_admin)

@app.route('/buku/<int:buku_id>')
def detail_buku(buku_id):
    is_admin = session.get('is_admin')
    buku = Buku.query.get_or_404(buku_id)
    catatan_list = Catatan.query.filter_by(buku_id=buku_id).order_by(Catatan.id.asc()).all()
    return render_template_string(HTML_DETAIL_BUKU, buku=buku, catatan_list=catatan_list, is_admin=is_admin)

# --------------------------------------------------
# API AKSI ADMIN (SQLAlchemy)
# --------------------------------------------------

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
        db.session.delete(buku)
        db.session.commit()
    return redirect(f'/tema/{tema_id}')

@app.route('/buku/<int:buku_id>/tambah-catatan', methods=['POST'])
def tambah_catatan(buku_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    bagian = request.form.get('bagian', '').strip()
    judul_bab = request.form.get('judul_bab')
    isi = request.form.get('isi')
    if judul_bab and isi:
        c_baru = Catatan(bagian=bagian, judul_bab=judul_bab, isi=isi, buku_id=buku_id)
        db.session.add(c_baru)
        db.session.commit()
    return redirect(f'/buku/{buku_id}')

@app.route('/hapus-catatan/<int:catatan_id>/<int:buku_id>', methods=['POST'])
def hapus_catatan(catatan_id, buku_id):
    if not session.get('is_admin'):
        return "Akses Ditolak", 403
    c = Catatan.query.get(catatan_id)
    if c:
        db.session.delete(c)
        db.session.commit()
    return redirect(f'/buku/{buku_id}')

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
        "catatan": [{"id": c.id, "bagian": c.bagian, "judul_bab": c.judul_bab, "isi": c.isi, "buku_id": c.buku_id} for c in Catatan.query.all()]
    }
    return Response(json.dumps(data, indent=2), mimetype='application/json', headers={'Content-Disposition': 'attachment;filename=backup_karya.json'})

app = app
