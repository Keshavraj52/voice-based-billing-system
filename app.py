import streamlit as st
import speech_recognition as sr
import pyttsx3
import re
import pandas as pd
from datetime import datetime
import threading
import time
import io
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import qrcode
from PIL import Image

# -------------------------------
# 1) CONFIG: Products, names, units
# -------------------------------

# Canonical product catalog with base price & unit
# unit ∈ {"kg", "liter", "unit"}
PRODUCTS = {
    'sugar':        {'price': 40,  'unit': 'kg'},
    'rice':         {'price': 60,  'unit': 'kg'},
    'wheat flour':  {'price': 33,  'unit': 'kg'},
    'wheat':        {'price': 33,  'unit': 'kg'},
    'flour':        {'price': 33,  'unit': 'kg'},
    'oil':          {'price': 120, 'unit': 'liter'},
    'cooking oil':  {'price': 120, 'unit': 'liter'},
    'dal':          {'price': 80,  'unit': 'kg'},
    'lentils':      {'price': 80,  'unit': 'kg'},
    'milk':         {'price': 25,  'unit': 'liter'},
    'bread':        {'price': 30,  'unit': 'unit'},
    'onion':        {'price': 20,  'unit': 'kg'},
    'potato':       {'price': 15,  'unit': 'kg'},
    'tomato':       {'price': 25,  'unit': 'kg'},
    'salt':         {'price': 18,  'unit': 'kg'},
    'tea':          {'price': 200, 'unit': 'kg'},
    'coffee':       {'price': 300, 'unit': 'kg'},
    'ghee':         {'price': 450, 'unit': 'kg'},
    'butter':       {'price': 350, 'unit': 'kg'},
    'cheese':       {'price': 400, 'unit': 'kg'},
}

# Hindi display names for each canonical product
HI_NAMES = {
    'sugar': 'चीनी',
    'rice': 'चावल',
    'wheat flour': 'आटा',
    'wheat': 'गेहूं',
    'flour': 'आटा',
    'oil': 'तेल',
    'cooking oil': 'खाद्य तेल',
    'dal': 'दाल',
    'lentils': 'दाल',
    'milk': 'दूध',
    'bread': 'ब्रेड',
    'onion': 'प्याज़',
    'potato': 'आलू',
    'tomato': 'टमाटर',
    'salt': 'नमक',
    'tea': 'चाय',
    'coffee': 'कॉफ़ी',
    'ghee': 'घी',
    'butter': 'मक्खन',
    'cheese': 'पनीर',
}

# Aliases: English + Hindi → canonical key
ALIASES = {
    # sugar
    'sugar': 'sugar', 'चीनी': 'sugar', 'शक्कर': 'sugar',
    # rice
    'rice': 'rice', 'चावल': 'rice',
    # wheat / flour
    'wheat': 'wheat', 'गेहूं': 'wheat',
    'flour': 'flour', 'aata': 'wheat flour', 'atta': 'wheat flour', 'आटा': 'wheat flour', 'गेहूं का आटा': 'wheat flour', 'wheat flour': 'wheat flour',
    # oil
    'oil': 'oil', 'cooking oil': 'cooking oil', 'तेल': 'oil', 'खाद्य तेल': 'cooking oil',
    # dal
    'dal': 'dal', 'lentils': 'lentils', 'दाल': 'dal', 'मसूर': 'dal', 'तूर': 'dal', 'मूंग': 'dal', 'चना दाल': 'dal',
    # milk
    'milk': 'milk', 'दूध': 'milk',
    # bread
    'bread': 'bread', 'ब्रेड': 'bread',
    # veggies
    'onion': 'onion', 'प्याज': 'onion', 'प्याज़': 'onion',
    'potato': 'potato', 'आलू': 'potato',
    'tomato': 'tomato', 'टमाटर': 'tomato',
    # others
    'salt': 'salt', 'नमक': 'salt',
    'tea': 'tea', 'चाय': 'tea',
    'coffee': 'coffee', 'कॉफी': 'coffee', 'कॉफ़ी': 'coffee',
    'ghee': 'ghee', 'घी': 'ghee',
    'butter': 'butter', 'मक्खन': 'butter',
    'cheese': 'cheese', 'पनीर': 'cheese',
}

# Unit labels for UI/PDF/speech
UNIT_LABELS = {
    'kg':    {'hi': 'किग्रा', 'en': 'kg'},
    'liter': {'hi': 'लीटर',  'en': 'L'},
    'unit':  {'hi': 'पीस',    'en': 'pc'},
}

# Words mapping → canonical unit
UNIT_KEYWORDS = {
    # kilograms
    'kg': 'kg', 'kilogram': 'kg', 'kilograms': 'kg',
    'किलो': 'kg', 'किलोग्राम': 'kg',
    # grams
    'g': 'g', 'gram': 'g', 'grams': 'g', 'ग्राम': 'g',
    # liter
    'l': 'liter', 'liter': 'liter', 'liters': 'liter',
    'लीटर': 'liter',
    # milliliter
    'ml': 'ml', 'मिलीलीटर': 'ml',
    # pieces / units
    'piece': 'unit', 'pieces': 'unit', 'unit': 'unit',
    'पीस': 'unit', 'टुकड़े': 'unit', 'पैकेट': 'unit',
}

# -------------------------------
# 2) Speech: recognizer + TTS
# -------------------------------
recognizer = sr.Recognizer()
tts_engine = pyttsx3.init()

def setup_tts_hindi():
    """Try to select a Hindi TTS voice if available."""
    try:
        voices = tts_engine.getProperty('voices')
        # Candidates if name/id/language hints 'hi' or 'Hindi'
        candidates = []
        for v in voices:
            lang_tags = []
            try:
                lang_tags = v.languages or []
            except Exception:
                lang_tags = []
            # Normalize to str
            lang_tags = [lt.decode('utf-8', errors='ignore') if isinstance(lt, (bytes, bytearray)) else str(lt) for lt in lang_tags]

            if ('hi' in ''.join(lang_tags).lower()) or \
               ('hindi' in (v.name or '').lower()) or \
               ('hi' in (v.id or '').lower()):
                candidates.append(v)

        if candidates:
            tts_engine.setProperty('voice', candidates[0].id)
        # reasonable speaking rate for Hindi
        tts_engine.setProperty('rate', 170)
    except Exception:
        pass

setup_tts_hindi()

def speak_text(text):
    """Speak Hindi text (fallback safe)."""
    try:
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception:
        pass

# -------------------------------
# 3) Helpers: Hindi PDF font
# -------------------------------
def try_register_devanagari_font():
    """Register Noto Sans Devanagari if found; else fallback to default fonts."""
    font_candidates = [
        "NotoSansDevanagari-Regular.ttf",
        os.path.join("fonts", "NotoSansDevanagari-Regular.ttf"),
        os.path.join("assets", "NotoSansDevanagari-Regular.ttf"),
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("NotoSansDevanagari", path))
                return "NotoSansDevanagari"
            except Exception:
                pass
    return None

DEV_FONT_NAME = try_register_devanagari_font()

# -------------------------------
# 4) Voice in (Hindi)
# -------------------------------
def listen_for_voice_hi():
    """Listen and return Hindi text."""
    try:
        with sr.Microphone() as source:
            st.info("🎤 सुन रहे हैं... कृपया अपना ऑर्डर बोलें")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
        text = recognizer.recognize_google(audio, language="hi-IN")
        return text.strip()
    except sr.UnknownValueError:
        return "आवाज़ समझ में नहीं आई"
    except sr.RequestError as e:
        return f"स्पीच सर्विस में समस्या: {e}"
    except sr.WaitTimeoutError:
        return "समय सीमा में बोलना नहीं पाया गया"
    except Exception as e:
        return f"त्रुटि: {e}"

# -------------------------------
# 5) Parse Hindi command
# -------------------------------
DEVANAGARI = r"\u0900-\u097F"
ALPHA_ANY = rf"a-zA-Z{DEVANAGARI}"

# Two patterns:
#  (1) qty [unit] product
#  (2) product qty [unit]
PATTERNS = [
    rf"(\d+(?:\.\d+)?)\s*([{ALPHA_ANY}\.]*?)\s*(?:का|की|के)?\s*([{ALPHA_ANY}\s]+)",
    rf"([{ALPHA_ANY}\s]+?)\s*(\d+(?:\.\d+)?)\s*([{ALPHA_ANY}\.]*)",
]

def _normalize_unit(token: str):
    token = (token or "").strip().lower()
    # pick the longest matching keyword present in token
    for word, canon in UNIT_KEYWORDS.items():
        if word in token:
            return canon
    return None

def _to_canonical_product(name: str):
    name = (name or "").strip().lower()
    # exact alias hit
    if name in ALIASES:
        return ALIASES[name]
    # partial contains
    for alias, canon in ALIASES.items():
        if alias in name or name in alias:
            return canon
    return None

def _convert_quantity(qty, src_unit, default_unit):
    """
    Convert qty into the product's base unit.
    src_unit ∈ {'kg','g','liter','ml','unit', None}
    default_unit ∈ {'kg','liter','unit'}
    """
    if src_unit is None:
        # use product's base unit directly
        return float(qty), default_unit

    # grams/ml → base
    if src_unit == 'g':
        return float(qty) / 1000.0, 'kg'
    if src_unit == 'ml':
        return float(qty) / 1000.0, 'liter'

    if src_unit in {'kg', 'liter', 'unit'}:
        return float(qty), src_unit

    # fallback
    return float(qty), default_unit

def parse_voice_command_hi(command):
    """Parse Hindi/English mixed voice commands → list of items."""
    cmd = (command or "").lower()
    items = []

    # split by "और" or "and" or comma
    segments = re.split(r"\b(?:और|and)\b|,", cmd)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        matched = False
        for pat in PATTERNS:
            matches = re.findall(pat, seg)
            for m in matches:
                try:
                    # Disambiguate (pattern 1 or 2)
                    if len(m) == 3:
                        # pattern 1: qty, unit_hint, product
                        # pattern 2: product, qty, unit_hint
                        if re.match(r"^\d", str(m[0])):
                            qty = float(m[0])
                            unit_hint = _normalize_unit(m[1])
                            product_name = m[2].strip()
                        else:
                            product_name = m[0].strip()
                            qty = float(m[1])
                            unit_hint = _normalize_unit(m[2])

                        canon = _to_canonical_product(product_name)
                        if not canon or canon not in PRODUCTS:
                            continue

                        default_unit = PRODUCTS[canon]['unit']
                        qty_conv, final_unit = _convert_quantity(qty, unit_hint, default_unit)

                        price = PRODUCTS[canon]['price']
                        total = qty_conv * price if final_unit == default_unit or default_unit == 'unit' else qty_conv * price
                        # If mismatch like saying पीस for rice, still compute by price (assume base)

                        items.append({
                            'product': canon,
                            'display_hi': HI_NAMES.get(canon, canon),
                            'quantity': qty_conv,
                            'unit': default_unit if final_unit is None else final_unit,
                            'price_per_unit': price,
                            'total_price': round(qty_conv * price, 2),
                        })
                        matched = True
                except Exception:
                    continue
        # no pattern match → ignore that segment
    return items

# -------------------------------
# 6) PDF in Hindi
# -------------------------------
def generate_bill_pdf_hindi(bill_items, total_amount):
    """Generate PDF bill in Hindi; uses Devanagari font if available."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    if DEV_FONT_NAME:
        header_font = DEV_FONT_NAME
        text_font = DEV_FONT_NAME
    else:
        # fallback (English only glyphs)
        header_font = "Helvetica-Bold"
        text_font = "Helvetica"

    # Title
    p.setFont(header_font, 16)
    title = "किराना बिल" if DEV_FONT_NAME else "GROCERY BILL"
    p.drawString(50, 750, title)
    p.setFont(text_font, 11)
    p.drawString(50, 730, f"तारीख: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Headers
    p.setFont(header_font, 12)
    p.drawString(50, 700, "वस्तु" if DEV_FONT_NAME else "Item")
    p.drawString(200, 700, "मात्रा" if DEV_FONT_NAME else "Quantity")
    p.drawString(300, 700, "दाम/इकाई" if DEV_FONT_NAME else "Price/Unit")
    p.drawString(400, 700, "कुल" if DEV_FONT_NAME else "Total")
    p.line(50, 695, 500, 695)

    # Rows
    y = 675
    p.setFont(text_font, 10)
    for it in bill_items:
        unit_hi = UNIT_LABELS[it['unit']]['hi'] if DEV_FONT_NAME else UNIT_LABELS[it['unit']]['en']
        name = it.get('display_hi') if DEV_FONT_NAME else it['product'].title()
        p.drawString(50, y, str(name))
        p.drawString(200, y, f"{it['quantity']} {unit_hi}")
        p.drawString(300, y, f"₹{it['price_per_unit']}")
        p.drawString(400, y, f"₹{it['total_price']:.2f}")
        y -= 20

    # Total
    p.line(50, y, 500, y)
    p.setFont(header_font, 12)
    total_label = "कुल राशि" if DEV_FONT_NAME else "Total Amount"
    p.drawString(300, y - 20, f"{total_label}: ₹{total_amount:.2f}")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer
def generate_upi_qr(total_amount, upi_id="keshavrajpore52@okaxis", payee_name="keshavrajpore"):
    """
    Generate UPI QR Code for PhonePe / GPay / Paytm payments.
    """
    upi_url = f"upi://pay?pa={upi_id}&pn={payee_name}&am={total_amount:.2f}&cu=INR"
    qr = qrcode.make(upi_url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# -------------------------------
# 7) Streamlit App (Hindi UI)
# -------------------------------
def main():
    st.set_page_config(page_title="हिंदी वॉइस बिल कैलकुलेटर", page_icon="🛒", layout="wide")

    st.title("🛒 हिंदी वॉइस-आधारित बिल कैलकुलेटर")
    st.markdown("---")

    # Session state
    if 'bill_items' not in st.session_state:
        st.session_state.bill_items = []
    if 'payment_done' not in st.session_state:
        st.session_state.payment_done = False

    # Sidebar: product price list
    st.sidebar.header("📋 उपलब्ध वस्तुएँ और कीमत")
    sidebar_df = pd.DataFrame([
        {
            'वस्तु': HI_NAMES.get(k, k),
            'इकाई': UNIT_LABELS[v['unit']]['hi'],
            'कीमत (₹/इकाई)': v['price'],
        }
        for k, v in PRODUCTS.items()
    ])
    st.sidebar.dataframe(sidebar_df, use_container_width=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("🎤 आवाज़ से ऑर्डर")

        if st.button("🎙️ आवाज़ सुनना शुरू करें", use_container_width=True):
            with st.spinner("सुन रहे हैं..."):
                voice_text = listen_for_voice_hi()
                if voice_text and not voice_text.startswith("त्रुटि") and "समस्या" not in voice_text and "नहीं" not in voice_text[:10]:
                    st.success(f"🎯 समझा गया: {voice_text}")
                    items = parse_voice_command_hi(voice_text)

                    if items:
                        st.session_state.bill_items += items
                        st.success(f"✅ {len(items)} आइटम जोड़े गए")
                        threading.Thread(target=speak_text, args=(f"{len(items)} वस्तुएँ जोड़ दी गई हैं।",)).start()
                    else:
                        st.warning("⚠️ आपके आदेश से कोई मान्य वस्तु नहीं मिली")
                        threading.Thread(target=speak_text, args=("क्षमा करें, आपके आदेश में मान्य वस्तु नहीं मिली।",)).start()
                else:
                    st.error(f"❌ {voice_text}")

        st.markdown("---")
        st.subheader("✍️ मैनुअल इनपुट")

        # Manual add form
        with st.form("manual_input_hi"):
            # show Hindi display options but store canonical key
            product_options = {HI_NAMES.get(k, k): k for k in PRODUCTS.keys()}
            chosen_hi = st.selectbox("वस्तु चुनें", list(product_options.keys()))
            chosen_key = product_options[chosen_hi]

            default_unit = PRODUCTS[chosen_key]['unit']
            unit_choice = st.selectbox("इकाई", [UNIT_LABELS[u]['hi'] for u in ['kg','liter','unit']], index=['kg','liter','unit'].index(default_unit))
            # reverse map to canonical unit
            unit_rev = {UNIT_LABELS[u]['hi']: u for u in UNIT_LABELS}
            unit_canon = unit_rev[unit_choice]

            qty = st.number_input("मात्रा", min_value=0.1, step=0.1, value=1.0)

            if st.form_submit_button("बिल में जोड़ें"):
                price = PRODUCTS[chosen_key]['price']

                # Convert qty to product base if needed
                if unit_canon == 'g':
                    qty_base, final_unit = qty / 1000.0, 'kg'
                elif unit_canon == 'ml':
                    qty_base, final_unit = qty / 1000.0, 'liter'
                else:
                    qty_base, final_unit = qty, unit_canon

                # Align to product base unit for pricing
                qty_for_price = qty_base
                total = round(qty_for_price * price, 2)

                item = {
                    'product': chosen_key,
                    'display_hi': HI_NAMES.get(chosen_key, chosen_key),
                    'quantity': qty_for_price,
                    'unit': PRODUCTS[chosen_key]['unit'],  # store base unit
                    'price_per_unit': price,
                    'total_price': total
                }
                st.session_state.bill_items.append(item)
                st.success(f"✅ {qty} {unit_choice} {chosen_hi} जोड़ा गया")

    with col2:
        st.header("🧾 वर्तमान बिल")

        if st.session_state.bill_items:
            bill_df = pd.DataFrame(st.session_state.bill_items)
            # display in Hindi
            bill_df['वस्तु'] = bill_df['display_hi']
            bill_df['मात्रा'] = bill_df['quantity'].map(lambda x: f"{x}")
            bill_df['इकाई'] = bill_df['unit'].map(lambda u: UNIT_LABELS[u]['hi'])
            bill_df['दाम/इकाई (₹)'] = bill_df['price_per_unit']
            bill_df['कुल (₹)'] = bill_df['total_price'].round(2)

            display_df = bill_df[['वस्तु', 'मात्रा', 'इकाई', 'दाम/इकाई (₹)', 'कुल (₹)']]
            st.dataframe(display_df, use_container_width=True)

            total_amount = sum(item['total_price'] for item in st.session_state.bill_items)
            st.markdown(f"### 💰 **कुल राशि: ₹{total_amount:.2f}**")

            col_btn1, col_btn2, col_btn3 = st.columns(3)

            with col_btn1:
                if st.button("🗑️ बिल साफ़ करें", use_container_width=True):
                    st.session_state.bill_items = []
                    st.session_state.payment_done = False
                    st.rerun()

            with col_btn2:
                if not st.session_state.payment_done:
                    if st.button("💳 भुगतान QR दिखाएँ", use_container_width=True):
                        qr_buffer = generate_upi_qr(total_amount, upi_id="keshavrajpore52@okaxis", payee_name="keshavraj pore")
                        st.image(qr_buffer, caption="📲 स्कैन करें और भुगतान करें", use_container_width=False)
                        st.info("कृपया ग्राहक से भुगतान की पुष्टि करें।")
                        if st.button("✅ भुगतान स्वीकार करें", use_container_width=True):
                            st.session_state.payment_done = True
                            st.success("💰 भुगतान सफल, अब बिल बना सकते हैं।")
                            st.rerun()
                else:
                    if st.button("📄 अंतिम बिल बनाएं (PDF)", use_container_width=True):
                        pdf_buffer = generate_bill_pdf_hindi(st.session_state.bill_items, total_amount)
                        st.download_button(
                            label="📥 बिल पीडीएफ डाउनलोड करें",
                            data=pdf_buffer.getvalue(),
                            file_name=f"bill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )

            with col_btn3:
                if st.button("🔊 बिल सुनाएँ", use_container_width=True):
                    parts = []
                    for it in st.session_state.bill_items:
                        unit_hi = UNIT_LABELS[it['unit']]['hi']
                        parts.append(f"{it['quantity']} {unit_hi} {it.get('display_hi', it['product'])} के लिए {int(it['total_price'])} रुपये")
                    bill_text = "आपके बिल में है: " + " , ".join(parts) + f". कुल राशि {int(total_amount)} रुपये।"
                    threading.Thread(target=speak_text, args=(bill_text,)).start()
                    st.info("🔊 बिल पढ़ा जा रहा है...")

        else:
            st.info("🛒 आपका बिल खाली है। आवाज़ से या मैनुअल तरीके से वस्तुएँ जोड़ें।")

    st.markdown("---")
    st.markdown("### 📝 आवाज़ कमांड के उदाहरण:")
    st.markdown("""
    - "2 किलो चीनी"
    - "1.5 किलो चावल"
    - "500 ग्राम दाल" (अपने आप 0.5 किग्रा में बदलेगा)
    - "2 लीटर दूध"
    - "1 किलो प्याज़ और 2 किलो आलू"
    """)

    st.markdown("### 🎯 सुझाव:")
    st.markdown("""
    - धीरे और साफ़ बोलें
    - मात्रा के साथ वस्तु का नाम बोलें (किलो/ग्राम/लीटर/पीस)
    - माइक सही काम कर रहा हो यह सुनिश्चित करें
    """)

if __name__ == "__main__":
    main()
