import qrcode
import io
from PIL import Image

def generate_upi_qr(total_amount, upi_id="keshavrajpore52@okaxis", payee_name="My Shop"):
    """
    Generate UPI QR Code for PhonePe / GPay / Paytm payments.
    Works offline (just encodes UPI URL).
    """
    upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={total_amount:.2f}&cu=INR"
    print("Generated UPI URL:", upi_url)  # for debugging

    # Create QR
    qr = qrcode.make(upi_url)

    # Save to buffer
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer

if __name__ == "__main__":
    amount = 500.00  # test with ₹50
    qr_buffer = generate_upi_qr(amount, upi_id="keshavrajpore52@okaxis", payee_name="Test Shop")

    # Save QR image file for checking
    with open("upi_qr.png", "wb") as f:
        f.write(qr_buffer.getvalue())

    print("✅ QR code generated and saved as upi_qr.png")
    print("📲 Scan with PhonePe / GPay to test (amount should be ₹50).")
