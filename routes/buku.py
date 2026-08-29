from flask import Blueprint, request, redirect, render_template_string, session

buku_bp = Blueprint('buku', __name__)

from __main__ import db, Tema, Buku, Catatan, HTML_TEMA, masukkan_sampah

@buku_bp.route('/tema/<int:tema_id>')
def detail_tema(tema_id):
    is_admin = session.get('is_admin')
    tema = Tema.query.get_or_404(tema_id)
    buku_list = Buku.query.filter_by(tema_id=tema_id).order_by(Buku.id.asc()).all()
    return render_template_string(HTML_TEMA, tema=tema, buku_list=buku_list, is_admin=is_admin)

@buku_bp.route('/tambah-tema', methods=['POST'])
def tambah_tema():
    if not session.get('is_admin'): return "Akses Ditolak", 403
    nama = request.form.get('nama')
    if nama:
        db.session.add(Tema(nama=nama))
        db.session.commit()
    return redirect('/')

@buku_bp.route('/hapus-tema/<int:tema_id>', methods=['POST'])
def hapus_tema(tema_id):
    if not session.get('is_admin'): return "Akses Ditolak", 403
    tema = Tema.query.get(tema_id)
    if tema:
        masukkan_sampah('tema', {'nama': tema.nama})
        db.session.delete(tema)
        db.session.commit()
    return redirect('/')

@buku_bp.route('/tambah-buku', methods=['POST'])
def tambah_buku():
    if not session.get('is_admin'): return "Akses Ditolak", 403
    judul = request.form.get('judul')
    subjudul = request.form.get('subjudul', '')
    tema_id = request.form.get('tema_id')
    kutipan = request.form.get('kutipan', '')
    if judul and tema_id:
        buku_baru = Buku(judul=judul, subjudul=subjudul, tema_id=int(tema_id), kutipan=kutipan)
        db.session.add(buku_baru)
        db.session.commit()
    return redirect(f'/tema/{tema_id}')

@buku_bp.route('/hapus-buku/<int:buku_id>/<int:tema_id>', methods=['POST'])
def hapus_buku(buku_id, tema_id):
    if not session.get('is_admin'): return "Akses Ditolak", 403
    buku = Buku.query.get(buku_id)
    if buku:
        masukkan_sampah('buku', {'judul': buku.judul, 'subjudul': buku.subjudul})
        db.session.delete(buku)
        db.session.commit()
    return redirect(f'/tema/{tema_id}')
