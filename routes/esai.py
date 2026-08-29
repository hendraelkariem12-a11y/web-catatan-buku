from flask import Blueprint, render_template_string

# 1. Buat Blueprint khusus Esai
esai_bp = Blueprint('esai', __name__)

# 2. Gunakan @esai_bp.route
@esai_bp.route('/esai')
def daftar_esai():
    return """
    <h3>✍️ Ruang Esai & Catatan Penulis</h3>
    <ul>
        <li>Refleksi Harian - Keberanian Berkhidmat</li>
        <li>Manajemen Waktu Bagi Penulis</li>
    </ul>
    <a href="/">Kembali ke Utama</a>
    """
