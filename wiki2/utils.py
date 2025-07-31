# wiki2/utils.py
import qrcode
import base64
from io import BytesIO

def qr_img(request):
    current_url = request.build_absolute_uri()
    qr = qrcode.QRCode(box_size=5, border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(current_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return img_base64