from flask import Blueprint, request, redirect, render_template_string, session, Response, send_from_directory
import json
from datetime import datetime

system_bp = Blueprint('system', __name__)

from __main__ import db, Tema, Buku, Catatan, EsaiPenulis, TongSampah, HTML_INDEX, HTML_PDF_VIEWER, HTML_STATISTIK, HTML_TONG_SAMPAH, HTML_PENULIS

@system_bp.route('/')
def index():
    is_admin = session.get('is_admin')
    tema_list = Tema.query.order_by(Tema.id.asc()).all()
    jumlah_esai = EsaiPenulis.query.count()
    return render_template_string(HTML_INDEX, tema_list=tema_list, is_admin=is_admin, jumlah_esai=jumlah_esai)

@system_bp.route('/baca-pdf')
def baca_pdf():
    url_pdf = request.args.get('url', 'https://raw.githubusercontent.com/mozilla/pdf.js/ba2edeae/web/compressed.tracemonkey-pldi-09.pdf')
    judul_pdf = request.args.get('judul', 'Demo Naskah E-Book Digital')
    return render_template_string(HTML_PDF_VIEWER, url_pdf=url_pdf, judul_pdf=judul_pdf)

@system_bp.route('/penulis')
def tentang_penulis():
    return render_template_string(HTML_PENULIS)

@system_bp.route('/profile.jpg')
def serve_profile():
    return send_from_directory('.', 'profile.jpg')

@system_bp.route('/statistik')
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
    return render_template_string(HTML_STATISTIK, total_tema=total_tema, total_buku=total_buku, total_catatan=total_catatan, total_esai=total_esai, total_kata=total_kata, buku_bulan_ini=buku_bulan_ini, esai_bulan_ini=esai_bulan_ini)

@system_bp.route('/tong-sampah')
def tong_sampah():
    sampah_list = TongSampah.query.order_by(TongSampah.dihapus_pada.desc()).all()
    return render_template_string(HTML_TONG_SAMPAH, sampah_list=sampah_list)

@system_bp.route('/pulihkan/<int:item_id>')
def pulihkan(item_id):
    if not session.get('is_admin'): return "Akses Ditolak", 403
    item = TongSampah.query.get_or_404(item_id)
    data = json.loads(item.data_json)
    if item.tipe == 'tema': db.session.add(Tema(nama=data['nama']))
    elif item.tipe == 'buku': db.session.add(Buku(judul=data['judul'], subjudul=data.get('subjudul', ''), tema_id=1))
    elif item.tipe == 'esai': db.session.add(EsaiPenulis(judul=data['judul'], kategori=data.get('kategori', 'Refleksi'), isi=data['isi']))
    db.session.delete(item)
    db.session.commit()
    return redirect('/tong-sampah')

@system_bp.route('/hapus-permanen/<int:item_id>')
def hapus_permanen(item_id):
    if not session.get('is_admin'): return "Akses Ditolak", 403
    db.session.delete(TongSampah.query.get_or_404(item_id))
    db.session.commit()
    return redirect('/tong-sampah')

@system_bp.route('/kosongkan-tong-sampah', methods=['POST'])
def kosongkan_tong_sampah():
    if not session.get('is_admin'): return "Akses Ditolak", 403
    TongSampah.query.delete()
    db.session.commit()
    return redirect('/tong-sampah')

@system_bp.route('/backup')
def backup_db():
    if not session.get('is_admin'): return "Akses Ditolak", 403
    data = {
        "tema": [{"id": t.id, "nama": t.nama} for t in Tema.query.all()],
        "buku": [{"id": b.id, "judul": b.judul, "subjudul": b.subjudul, "tema_id": b.tema_id, "kutipan": b.kutipan} for b in Buku.query.all()],
        "catatan": [{"id": c.id, "bagian": c.bagian, "judul_bab": c.judul_bab, "isi": c.isi, "buku_id": c.buku_id} for c in Catatan.query.all()],
        "esai": [{"id": e.id, "judul": e.judul, "kategori": e.kategori, "isi": e.isi} for e in EsaiPenulis.query.all()]
    }
    return Response(json.dumps(data, indent=2), mimetype='application/json', headers={'Content-Disposition': 'attachment;filename=backup_karya.json'})

@system_bp.route('/restore', methods=['POST'])
def restore_db():
    if not session.get('is_admin'): return "Akses Ditolak", 403
    file = request.files.get('file_json')
    if file:
        data = json.load(file)
        for t in data.get('tema', []):
            if not Tema.query.get(t['id']): db.session.add(Tema(id=t['id'], nama=t['nama']))
        for b in data.get('buku', []):
            if not Buku.query.get(b['id']): db.session.add(Buku(id=b['id'], judul=b['judul'], subjudul=b.get('subjudul'), tema_id=b['tema_id'], kutipan=b.get('kutipan')))
        for c in data.get('catatan', []):
            if not Catatan.query.get(c['id']): db.session.add(Catatan(id=c['id'], bagian=c.get('bagian'), judul_bab=c['judul_bab'], isi=c['isi'], buku_id=c['buku_id']))
        for e in data.get('esai', []):
            if not EsaiPenulis.query.get(e['id']): db.session.add(EsaiPenulis(id=e['id'], judul=e['judul'], kategori=e.get('kategori', 'Refleksi'), isi=e['isi']))
        db.session.commit()
    return redirect('/')
