import streamlit as st
from st_gsheets_connection import GSheetsConnection
from streamlit_qr_scanner import streamlit_qr_scanner
import pandas as pd
import segno
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- 1. SETTINGS & BRANDING ---
st.set_page_config(page_title="Gurukulam Attendance System", page_icon="🕉️", layout="wide")
ADMIN_PASSWORD = "Gurukulam@admin"
GURUKULAM_NAME = "Sri Gurukulam Educational Trust"

# Initialize Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. TRADITIONAL GURUKULAM CSS ---
st.markdown("""
    <style>
        .stApp { background-color: #FFF8E1; color: #5D4037; }
        [data-testid="stSidebar"] { background-image: linear-gradient(#FF9933, #FF8000); border-right: 5px solid #FFD700; }
        [data-testid="stSidebar"] * { color: white !important; font-family: 'Georgia', serif; }
        h1, h2, h3 { color: #8B0000 !important; text-align: center; font-family: 'Times New Roman', serif; }
        div.stButton > button:first-child { 
            background-color: #FFD700; color: #8B0000; border: 2px solid #8B0000; 
            border-radius: 5px; font-weight: bold; width: 100%;
        }
        div.stButton > button:hover { background-color: #8B0000; color: #FFD700; }
        .stAlert { background-color: #FFECB3; border: 1px solid #FFBF00; color: #8B4513; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CORE LOGIC FUNCTIONS ---

def generate_complete_id_card(row_data):
    """Generates an ornate physical ID card for printing."""
    qr = segno.make(row_data['ID'], error='h')
    qr_buf = BytesIO()
    qr.save(qr_buf, kind='png', scale=6, border=0)
    qr_img = Image.open(qr_buf).convert("RGBA")

    try:
        bg_img = Image.open("qr_bg.png").convert("RGBA") # Ensure this is in your GitHub repo
        draw = ImageDraw.Draw(bg_img)
        # Text settings
        text_color = (139, 69, 19) 
        draw.text((50, 400), f"Name: {row_data['Name']}", fill=text_color)
        draw.text((50, 460), f"ID: {row_data['ID']}", fill=text_color)
        draw.text((50, 510), f"Class: {row_data.get('Department', 'N/A')}", fill=text_color)
        draw.text((50, 560), f"Blood: {row_data['Blood']}", fill=(178, 0, 0))
        draw.text((50, 610), f"Guardian: {row_data['Guardian']}", fill=text_color)

        # Paste QR
        bg_w, bg_h = bg_img.size
        offset = ((bg_w - qr_img.size[0]) // 2, bg_h - qr_img.size[1] - 50)
        bg_img.paste(qr_img, offset, qr_img)
        
        final_buf = BytesIO()
        bg_img.save(final_buf, format="PNG")
        return final_buf
    except:
        return qr_buf

# --- 4. NAVIGATION ---
st.sidebar.markdown("<h1 style='font-size: 40px;'>🕉️</h1>", unsafe_allow_html=True)
choice = st.sidebar.radio("Navigation", ["Student Attendance", "New Registration", "Teacher Dashboard", "Admin Archives"])

# --- 5. MODULES ---

# MODULE: STUDENT SELF-ATTENDANCE
if choice == "Student Attendance":
    st.markdown("<h1>🙏 Swagatam - Daily Attendance</h1>", unsafe_allow_html=True)
    st.info("Students: Please scan your ID card below.")
    
    scanned_id = streamlit_qr_scanner(key="gate_scan")
    if scanned_id:
        students_df = conn.read(worksheet="Students")
        student = students_df[students_df['ID'] == scanned_id]
        
        if not student.empty:
            s_name = student.iloc[0]['Name']
            st.success(f"Verified: {s_name}")
            
            # Log Attendance
            att_entry = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "ID": scanned_id,
                "Name": s_name,
                "Time": datetime.now().strftime("%H:%M:%S"),
                "Status": "Present"
            }])
            conn.append(data=att_entry, worksheet="Attendance")
            st.balloons()
        else:
            st.error("ID Not Recognized. Please see the Acharya.")

# MODULE: REGISTRATION
elif choice == "New Registration":
    st.header("📝 Register New Student/Staff")
    pwd = st.sidebar.text_input("Admin Password", type="password")
    if pwd == ADMIN_PASSWORD:
        with st.form("reg_form"):
            role = st.selectbox("Role", ["Student", "Teacher", "Staff"])
            name = st.text_input("Full Name")
            u_id = st.text_input("ID / Roll No")
            blood = st.selectbox("Blood Group", ["A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"])
            guardian = st.text_input("Guardian Name")
            dept = st.text_input("Department / Class")
            addr = st.text_area("Address")
            
            if st.form_submit_button("Register & Generate ID"):
                reg_data = pd.DataFrame([{
                    "Name": name, "ID": u_id, "Blood": blood, 
                    "Guardian": guardian, "Department": dept, "Address": addr
                }])
                conn.append(data=reg_data, worksheet=f"{role}s")
                st.success("Registration Successful!")
                
                # Show ID Card
                id_card = generate_complete_id_card(reg_data.iloc[0].to_dict())
                st.image(id_card)
                st.download_button("Download Print-Ready ID", id_card.getvalue(), f"{u_id}.png")

# MODULE: TEACHER DASHBOARD
elif choice == "Teacher Dashboard":
    st.header("📋 Daily Absence Report")
    pwd = st.sidebar.text_input("Admin Password", type="password")
    if pwd == ADMIN_PASSWORD:
        today = datetime.now().strftime("%Y-%m-%d")
        students = conn.read(worksheet="Students")
        attendance = conn.read(worksheet="Attendance")
        
        present_ids = attendance[attendance['Date'] == today]['ID'].tolist()
        absent_students = students[~students['ID'].isin(present_ids)]
        
        st.metric("Present Today", len(present_ids))
        if not absent_students.empty:
            st.warning("Absentees for Today:")
            st.table(absent_students[['ID', 'Name', 'Guardian']])
        else:
            st.success("All students are present!")

# MODULE: ADMIN
elif choice == "Admin Archives":
    st.header("⚙️ Data Management")
    pwd = st.sidebar.text_input("Admin Password", type="password")
    if pwd == ADMIN_PASSWORD:
        st.subheader("Historical Attendance")
        data = conn.read(worksheet="Attendance")
        st.dataframe(data)
        
        if st.button("Archive & Reset Yearly Logs"):
            archive_name = f"Archive_{datetime.now().year}"
            conn.create(data=data, worksheet=archive_name)
            conn.update(data=pd.DataFrame(columns=data.columns), worksheet="Attendance")
            st.success("Yearly logs archived successfully.")
            
