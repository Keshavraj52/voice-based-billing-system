import streamlit as st
import speech_recognition as sr
import pyttsx3
import re
import pandas as pd
from datetime import datetime
import threading
import time
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import base64

# Initialize speech recognition and text-to-speech
recognizer = sr.Recognizer()
tts_engine = pyttsx3.init()

# Predefined product prices (in Rs/kg or Rs/unit)
PRODUCT_PRICES = {
    'sugar': 40,
    'rice': 60,
    'wheat flour': 33,
    'wheat': 33,
    'flour': 33,
    'oil': 120,
    'cooking oil': 120,
    'dal': 80,
    'lentils': 80,
    'milk': 25,
    'bread': 30,
    'onion': 20,
    'potato': 15,
    'tomato': 25,
    'salt': 18,
    'tea': 200,
    'coffee': 300,
    'ghee': 450,
    'butter': 350,
    'cheese': 400
}

def speak_text(text):
    """Convert text to speech"""
    try:
        tts_engine.say(text)
        tts_engine.runAndWait()
    except:
        pass

def listen_for_voice():
    """Listen for voice input and return recognized text"""
    try:
        with sr.Microphone() as source:
            st.info("🎤 Listening... Please speak your order")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
        
        text = recognizer.recognize_google(audio)
        return text.lower()
    except sr.UnknownValueError:
        return "Could not understand the audio"
    except sr.RequestError as e:
        return f"Error with speech recognition service: {e}"
    except sr.WaitTimeoutError:
        return "No speech detected within timeout"
    except Exception as e:
        return f"Error: {e}"
    
def parse_voice_command(command):
    """Parse voice command to extract product and quantity"""
    command = command.lower()
    items = []

    # Split command by 'and' or comma
    segments = re.split(r'\band\b|,', command)

    # Common patterns for voice commands
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:kg|kilogram|kilograms?|liters?|l|grams?|g)?\s*(?:of\s+)?([a-zA-Z\s]+)',
        r'([a-zA-Z\s]+)\s*(\d+(?:\.\d+)?)(?:\s*(?:kg|kilogram|kilograms?|liters?|l|grams?|g))?'
    ]

    for segment in segments:
        segment = segment.strip()
        for pattern in patterns:
            matches = re.findall(pattern, segment)
            for match in matches:
                try:
                    if re.match(r'^\d', match[0]):
                        quantity = float(match[0])
                        product = match[1].strip()
                    else:
                        product = match[0].strip()
                        quantity = float(match[1])

                    # Normalize product
                    matched_product = None
                    for prod in PRODUCT_PRICES.keys():
                        if prod in product or product in prod:
                            matched_product = prod
                            break

                    if matched_product:
                        items.append({
                            'product': matched_product,
                            'quantity': quantity,
                            'price_per_unit': PRODUCT_PRICES[matched_product],
                            'total_price': quantity * PRODUCT_PRICES[matched_product]
                        })
                except ValueError:
                    continue

    return items

def generate_bill_pdf(bill_items, total_amount):
    """Generate PDF bill"""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 750, "GROCERY BILL")
    p.drawString(50, 730, f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Headers
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, 700, "Item")
    p.drawString(200, 700, "Quantity")
    p.drawString(300, 700, "Price/Unit")
    p.drawString(400, 700, "Total")
    
    # Line under headers
    p.line(50, 695, 500, 695)
    
    # Bill items
    y_position = 675
    p.setFont("Helvetica", 10)
    
    for item in bill_items:
        p.drawString(50, y_position, item['product'].title())
        p.drawString(200, y_position, f"{item['quantity']} kg")
        p.drawString(300, y_position, f"₹{item['price_per_unit']}")
        p.drawString(400, y_position, f"₹{item['total_price']:.2f}")
        y_position -= 20
    
    # Total
    p.line(50, y_position, 500, y_position)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(300, y_position - 20, f"Total Amount: ₹{total_amount:.2f}")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def main():
    st.set_page_config(page_title="Voice Bill Calculator", page_icon="🛒", layout="wide")
    
    st.title("🛒 Voice-Based Bill Calculator")
    st.markdown("---")
    
    # Initialize session state
    if 'bill_items' not in st.session_state:
        st.session_state.bill_items = []
    if 'listening' not in st.session_state:
        st.session_state.listening = False
    
    # Sidebar with product prices
    st.sidebar.header("📋 Product Prices")
    st.sidebar.markdown("**Available Products:**")
    
    price_df = pd.DataFrame(list(PRODUCT_PRICES.items()), columns=['Product', 'Price (₹/kg)'])
    st.sidebar.dataframe(price_df, use_container_width=True)
    
    # Main interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("🎤 Voice Commands")
        
        # Voice input button
        if st.button("🎙️ Start Voice Input", use_container_width=True):
            with st.spinner("Listening for your order..."):
                voice_text = listen_for_voice()
                
                if voice_text and "error" not in voice_text.lower() and "could not" not in voice_text.lower():
                    st.success(f"🎯 Recognized: {voice_text}")
                    
                    # Parse the voice command
                    items = parse_voice_command(voice_text)
                    
                    if items:
                        st.session_state.bill_items += items
                        st.success(f"✅ Added {len(items)} item(s) to bill")
                        
                        # Provide voice feedback
                        speak_text(f"Added {len(items)} items to your bill")
                    else:
                        st.warning("⚠️ No valid products found in your command")
                        speak_text("Sorry, I couldn't find any valid products in your command")
                else:
                    st.error(f"❌ {voice_text}")
        
        # Manual input option
        st.markdown("---")
        st.subheader("✍️ Manual Input")
        
        with st.form("manual_input"):
            manual_product = st.selectbox("Select Product", list(PRODUCT_PRICES.keys()))
            manual_quantity = st.number_input("Quantity (kg)", min_value=0.1, step=0.1)
            
            if st.form_submit_button("Add to Bill"):
                if manual_quantity > 0:
                    item = {
                        'product': manual_product,
                        'quantity': manual_quantity,
                        'price_per_unit': PRODUCT_PRICES[manual_product],
                        'total_price': manual_quantity * PRODUCT_PRICES[manual_product]
                    }
                    st.session_state.bill_items.append(item)
                    st.success(f"✅ Added {manual_quantity} kg of {manual_product}")
    
    with col2:
        st.header("🧾 Current Bill")
        
        if st.session_state.bill_items:
            # Create bill dataframe
            bill_df = pd.DataFrame(st.session_state.bill_items)
            bill_df['Product'] = bill_df['product'].str.title()
            bill_df['Quantity (kg)'] = bill_df['quantity']
            bill_df['Price/Unit (₹)'] = bill_df['price_per_unit']
            bill_df['Total (₹)'] = bill_df['total_price'].round(2)
            
            display_df = bill_df[['Product', 'Quantity (kg)', 'Price/Unit (₹)', 'Total (₹)']]
            st.dataframe(display_df, use_container_width=True)
            
            # Total amount
            total_amount = sum(item['total_price'] for item in st.session_state.bill_items)
            st.markdown(f"### 💰 **Total Amount: ₹{total_amount:.2f}**")
            
            # Action buttons
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("🗑️ Clear Bill", use_container_width=True):
                    st.session_state.bill_items = []
                    st.rerun()
            
            with col_btn2:
                if st.button("📄 Generate PDF", use_container_width=True):
                    pdf_buffer = generate_bill_pdf(st.session_state.bill_items, total_amount)
                    
                    st.download_button(
                        label="📥 Download Bill PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"bill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            
            with col_btn3:
                if st.button("🔊 Read Bill", use_container_width=True):
                    bill_text = "Your bill contains: "
                    for item in st.session_state.bill_items:
                        bill_text += f"{item['quantity']} kg of {item['product']} for {item['total_price']} rupees, "
                    bill_text += f"Total amount is {total_amount} rupees"
                    
                    threading.Thread(target=speak_text, args=(bill_text,)).start()
                    st.info("🔊 Reading bill aloud...")
        
        else:
            st.info("🛒 Your bill is empty. Add items using voice commands or manual input.")
    
    # Instructions
    st.markdown("---")
    st.markdown("### 📝 Voice Command Examples:")
    st.markdown("""
    - "2 kg sugar"
    - "1.5 kg rice"
    - "3 kg wheat flour"
    - "500 grams dal" (will be converted to 0.5 kg)
    - "2 liters milk"
    """)
    
    st.markdown("### 🎯 Tips:")
    st.markdown("""
    - Speak clearly and at a moderate pace
    - Include quantity and product name
    - Use 'kg' or 'kilogram' for better recognition
    - Make sure your microphone is working
    """)

if __name__ == "__main__":
    main()