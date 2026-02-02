import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_qr_scanner import streamlit_qr_scanner
import pandas as pd
import segno
import plotly.express as px
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

# --- 1. SETTINGS & BRANDING ---
st.set_page_config(
    page_title="Gurukulam Attendance System",
    page_icon="🕉️",
    layout="wide"
)

APP_NAME = "Gurukulam Attendance System"
ADMIN_PASSWORD = "Gurukulam@admin"

# Initialize Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. CORE UTILITIES ---

def log_audit(action, details):
    """Logs administrative and system actions."""
    try:
        audit_entry = pd.DataFrame([{
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": action,
            "Details": details
        }])
        conn.append(data=audit_entry, worksheet="Audit")
    except Exception as e:
        st.error(f"Audit failure: {e}")

def create_pdf_archive(df):
    """Generates an official PDF with watermarks."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    
    # Watermark
    p.saveState()
    p.setFont("Helvetica-Bold", 60)
    p.setStrokeColorRGB(0.9, 0.9, 0.9)
    p.setFillColorRGB(0.9, 0.9, 0.9)
    p.translate(w/2, h/2)
    p.rotate(45)
    p.drawCentredString(0, 0, "GURUKULAM OFFICIAL")
    p.restoreState()
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(w/2, h - 50, APP_NAME)
    p.setFont("Helvetica", 10)
    p.drawCentredString(w/2, h - 70, f"Generated on: {datetime.now().strftime('%Y-%m-%d')}")
    
    p.showPage()
    p.save()
    return buffer.getvalue()

# --- 3. NAVIGATION ---
st.sidebar.title(f"🕉️ {APP_NAME}")
menu = ["Gate Entry (QR)", "Register User", "Leave Management", "Admin & Archives"]
choice = st.sidebar.radio("Navigate", menu)

# --- 4. MODULES ---

# MODULE 1: GATE ENTRY
if choice == "Gate Entry (QR)":
    st.header("📸 QR Attendance Scanner")
    qr_code = streamlit_qr_scanner(key='gate_scanner')
    
    if qr_code:
        st.success(f"ID Detected: {qr_code}")
        if st.button("Confirm Entry"):
            entry = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "ID": qr_code,
                "Time": datetime.now().strftime("%H:%M:%S"),
                "Status": "Present"
            }])
            conn.append(data=entry, worksheet="Attendance")
            st.balloons()
            st.toast("Attendance Logged Successfully")

# MODULE 2: REGISTRATION
elif choice == "Register User":
    st.header("📝 User Registration")
    pwd = st.text_input("Admin Password", type="password")
    
    if pwd == ADMIN_PASSWORD:
        with st.form("reg_form"):
            col1, col2 = st.columns(2)
            role = col1.selectbox("Role", ["Student", "Teacher", "Staff"])
            name = col1.text_input("Name")
            u_id = col2.text_input("ID / Roll No")
            mob = col2.text_input("Mobile No")
            
            blood = col1.selectbox("Blood Group", ["A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"])
            addr = st.text_area("Address")
            
            # Role Specific logic
            guardian = st.text_input("Guardian Name") if role == "Student" else ""
            spec = st.text_input("Specialization") if role == "Teacher" else ""
            job = st.text_input("Job Title") if role == "Staff" else ""
            
            if st.form_submit_button("Register"):
                reg_df = pd.DataFrame([{
                    "Name": name, "ID": u_id, "Mobile": mob, "Blood": blood, 
                    "Address": addr, "Guardian": guardian, "Specialization": spec, "Job": job
                }])
                conn.append(data=reg_df, worksheet=f"{role}s")
                
                # Show QR for the new user
                qr = segno.make(u_id)
                buf = BytesIO()
                qr.save(buf, kind='png', scale=10)
                st.image(buf, caption=f"ID QR for {name}")
                st.download_button("Download QR", buf.getvalue(), f"{u_id}.png")
                log_audit("Register", f"Added {role}: {u_id}")

# MODULE 3: LEAVE
elif choice == "Leave Management":
    st.header("📅 Leave Requests")
    with st.form("leave_req"):
        l_id = st.text_input("Your ID")
        reason = st.text_area("Reason")
        if st.form_submit_button("Submit"):
            l_df = pd.DataFrame([{"ID": l_id, "Reason": reason, "Status": "Pending"}])
            conn.append(data=l_df, worksheet="Leave_Requests")
            st.success("Submitted.")

# MODULE 4: ADMIN
elif choice == "Admin & Archives":
    st.header("📊 Administration")
    pwd = st.text_input("Password", type="password")
    if pwd == ADMIN_PASSWORD:
        att_data = conn.read(worksheet="Attendance")
        st.dataframe(att_data)
        
        # Archiving
        if st.button("Yearly Archive & Clear Logs"):
            archive_sheet = f"Archive_{datetime.now().year}"
            conn.create(data=att_data, worksheet=archive_sheet)
            # Clear logic - update with empty df
            conn.update(data=pd.DataFrame(columns=att_data.columns), worksheet="Attendance")
            st.success("Archived to Google Sheets.")
            log_audit("Archive", "Full System Archive Run")
            
        # PDF Report
        pdf_bytes = create_pdf_archive(att_data)
        st.download_button("Download PDF Report", pdf_bytes, "Report.pdf")
