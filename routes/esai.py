from flask import Blueprint, request, redirect, render_template_string, session, send_file, Response
from io import BytesIO
import re
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# 1. Definisikan Blueprint Esai
esai_bp = Blueprint('esai', __name__)

# Kita import db dan model dari file utama nanti (atau buat extensions.py, tapi untuk simpelnya kita import dari app)
from __main__ import db, EsaiPenulis, TongSampah, CSS_SHARED, JS_THEME_SCRIPT, masukkan_sampah

HTML_ESAI_PENULIS = """
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
    <style>""" + CSS_SHARED + """</style>
    """ + JS_THEME_SCRIPT + """
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
        <p class="text-muted small mb-0">Catatan ide acak, artikel ringkas, dan hikmah harian. Total: {{ esai_list|length }} karya.</p>
    </div>
    
    <div class="search-box mb-4">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input type="text" class="form-control" placeholder="Cari judul atau isi..." oninput="filterEsai(this.value)">
    </div>

    {% if is_admin %}
    <div class="card-gold p-3 mb-4 rounded-3">
        <h6 class="fw-bold text-info mb-2"><i class="fa-solid fa-pen-nib me-1"></i> Tulis Esai Baru</h6>
        <form action="/catatan-penulis/tambah" method="POST">
            <input type="text" name="judul" class="form-control form-control-sm mb-2" placeholder="Judul..." required>
            <input type="text" name="kategori" class="form-control form-control-sm mb-2" placeholder="Kategori: Refleksi, Ide, dll.">
            <textarea name="isi" class="form-control form-control-sm mb-2" rows="4" placeholder="Tulis catatan (Markdown didukung)..." required></textarea>
            <button type="submit" class="btn btn-info btn-sm w-100 fw-bold">Terbitkan Catatan</button>
        </form>
    </div>
    {% endif %}

    {% for e in esai_list %}
    <div class="card-gold p-4 mb-3 esai-item">
        {% if is_admin %}
        <form action="/catatan-penulis/hapus/{{ e.id }}" method="POST" class="position-absolute top-0 end-0 p-3" onsubmit="return confirm('Hapus esai ini?');">
            <button type="submit" class="btn btn-link text-danger p-0"><i class="fa-solid fa-trash"></i></button>
        </form>
        {% endif %}
        <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="badge bg-info text-dark">{{ e.kategori }}</span>
            <a href="/catatan-penulis/cetak-pdf/{{ e.id }}" class="btn btn-outline-warning btn-sm rounded-pill fw-bold"><i class="fa-solid fa-file-pdf me-1"></i> Cetak PDF</a>
        </div>
        <h4 class="text-warning fw-bold mb-3 esai-judul">{{ e.judul }}</h4>
        <div class="markdown-body" id="content-esai-{{ e.id }}"></div>
        <textarea id="raw-esai-{{ e.id }}" style="display:none;">{{ e.isi }}</textarea>
        <div class="text-muted small mt-3">Dibuat: {{ e.dibuat_pada.strftime('%d %b %Y %H:%M') if e.dibuat_pada else '-' }}</div>
    </div>
    {% else %}
    <div class="text-center py-5 card-gold rounded-4">
        <i class="fa-solid fa-feather fs-1 text-muted mb-2"></i>
        <p class="text-muted mb-0">Belum ada jurnal atau esai.</p>
    </div>
    {% endfor %}
</div>

<script>
document.addEventListener("DOMContentLoaded", function(){
    marked.use({ gfm: true, breaks: true });
    {% for e in esai_list %}
        var rawText = document.getElementById('raw-esai-{{ e.id }}').value;
        document.getElementById('content-esai-{{ e.id }}').innerHTML = marked.parse(rawText);
    {% endfor %}

    filterEsai = function(kata) {
        document.querySelectorAll('.esai-item').forEach(item => {
            const judul = item.querySelector('.esai-judul').textContent.toLowerCase();
            item.style.display = kata === '' || judul.includes(kata.toLowerCase()) ? '' : 'none';
        });
    };
});
</script>
</body>
</html>
"""

# 2. Gunakan @esai_bp.route untuk semua rute esai
@esai_bp.route('/catatan-penulis')
def catatan_penulis():
    is_admin = session.get('is_admin')
    esai_list = EsaiPenulis.query.order_by(EsaiPenulis.id.desc()).all()
    return render_template_string(HTML_ESAI_PENULIS, esai_list=esai_list, is_admin=is_admin)

@app.route('/catatan-penulis/cetak-pdf/<int:esai_id>') # atau pakai esai_bp.route
@esai_bp.route('/catatan-penulis/cetak-pdf/<int:esai_id>')
def cetak_esai_pdf(esai_id):
    try:
        esai = EsaiPenulis.query.get_or_404(esai_id)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor='#b38728', spaceAfter=10)
        meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor='#64748b', spaceAfter=15)
        body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=15, textColor='#1e293b')
        
        story = [
            Paragraph(f"<b>{escape(esai.judul)}</b>", title_style),
            Paragraph(f"Kategori: {escape(esai.kategori)} | Penulis: Dede Suhendra", meta_style),
            Spacer(1, 10),
            Paragraph(escape(esai.isi).replace('\n', '<br/>'), body_style)
        ]
        doc.build(story)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"esai_{esai.id}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error: {str(e)}", 500

@esai_bp.route('/catatan-penulis/tambah', methods=['POST'])
def tambah_esai():
    if not session.get('is_admin'): return "Akses Ditolak", 403
    judul, kategori, isi = request.form.get('judul'), request.form.get('kategori', 'Refleksi Harian'), request.form.get('isi')
    if judul and isi:
        db.session.add(EsaiPenulis(judul=judul, kategori=kategori, isi=isi))
        db.session.commit()
    return redirect('/catatan-penulis')

@esai_bp.route('/catatan-penulis/hapus/<int:esai_id>', methods=['POST'])
def hapus_esai(esai_id):
    if not session.get('is_admin'): return "Akses Ditolak", 403
    e = EsaiPenulis.query.get(esai_id)
    if e:
        masukkan_sampah('esai', {'judul': e.judul, 'kategori': e.kategori, 'isi': e.isi})
        db.session.delete(e)
        db.session.commit()
    return redirect('/catatan-penulis')
