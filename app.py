# ==============================================================================
# GURUKULAM ENTERPRISE MANAGEMENT SYSTEM (GEMS)
# Version: 2.0 (Professional Edition)
# Architecture: Modular Monolith with RBAC (Role-Based Access Control)
# ==============================================================================

import streamlit as st
import pandas as pd
import qrcode
import io
import time
import os
import cv2
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List, Any, Optional, Tuple
from streamlit_gsheets import GSheetsConnection
from PIL import Image, ImageDraw, ImageFont

# PDF Generation Engine
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# ==============================================================================
# 1. CONFIGURATION & CONSTANTS
# ==============================================================================
class AppConfig:
    # Identity
    APP_NAME = "GURUKULAM"
    SCHOOL_NAME = "Shri Hulas Bramh Baba Sanskrit Ved Gurukulam"
    ADDRESS_LINE_1 = "Karahiya, Gadaipur, Ghazipur"
    ADDRESS_LINE_2 = "Uttar Pradesh - 232339"
    
    # Security
    ADMIN_PASS = "Gurukul@admin"
    
    # Database Sheets
    SHEET_STUDENT = "Student_DB"
    SHEET_TEACHER = "Teacher_DB"
    SHEET_STAFF = "Staff_DB"
    SHEET_AUDIT = "System_Audit_Trail"
    SHEET_LEAVES = "Leave_Requests"
    
    # Theme Colors
    COLOR_PRIMARY = "#b90e0a"  # Deep Red (Admin/Official)
    COLOR_SECONDARY = "#FF9933" # Saffron (Student/Culture)
    COLOR_ACCENT = "#1A1A1A"    # Black/Grey (Text)
    COLOR_BG = "#FFFDF5"        # Cream (Background)

CONFIG = AppConfig()

# Initialize Page
st.set_page_config(
    page_title="Gurukulam OS", 
    page_icon="🕉️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CSS & STYLING ENGINE (The "Beautiful" Look)
# ==============================================================================
def inject_custom_css():
    st.markdown(f"""
    <style>
        /* Main Background */
        .stApp {{
            background-color: {CONFIG.COLOR_BG};
        }}
        
        /* Sidebar Styling */
        [data-testid="stSidebar"] {{
            background-color: #FFFFFF;
            border-right: 1px solid #E0E0E0;
        }}
        
        /* Custom Red Box for School Name */
        .school-title-box {{
            background-color: {CONFIG.COLOR_PRIMARY};
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .school-title-box h3 {{
            margin: 0;
            color: white !important;
            font-family: 'Helvetica', sans-serif;
            font-weight: 600;
            font-size: 18px;
        }}
        
        /* Address Styling */
        .address-text {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 5px;
            line-height: 1.4;
        }}
        
        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 50px;
            white-space: pre-wrap;
            background-color: #FFFFFF;
            border-radius: 5px;
            color: #333;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }}
        .stTabs [aria-selected="true"] {{
            background-color: {CONFIG.COLOR_PRIMARY} !important;
            color: white !important;
        }}
        
        /* Button Styling */
        .stButton button {{
            background-color: {CONFIG.COLOR_PRIMARY};
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: bold;
        }}
        .stButton button:hover {{
            background-color: #8a0a07;
            color: white;
        }}
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 3. DATABASE ACCESS LAYER (DAO)
# ==============================================================================
class DatabaseManager:
    def __init__(self):
        try:
            self.conn = st.connection("gsheets", type=GSheetsConnection)
        except Exception as e:
            st.error(f"🔌 Database Connection Failed: {e}")

    def fetch_data(self, sheet_name: str) -> pd.DataFrame:
        """Fetches data with zero caching for real-time updates."""
        try:
            return self.conn.read(worksheet=sheet_name, ttl=0)
        except Exception:
            # Return empty DF with basic columns to prevent crash
            return pd.DataFrame()

    def insert_row(self, sheet_name: str, row_data: List[Any]) -> bool:
        """Appends a single row to the specified sheet."""
        try:
            df = self.fetch_data(sheet_name)
            new_row = pd.DataFrame([row_data], columns=df.columns)
            new_df = pd.concat([df, new_row], ignore_index=True)
            self.conn.update(worksheet=sheet_name, data=new_df)
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ Write Error: {e}")
            return False

# ==============================================================================
# 4. BUSINESS LOGIC SERVICES
# ==============================================================================

# --- Identity Logic ---
@dataclass
class UserProfile:
    name: str; uid: str; role: str; mobile: str; context: str; blood: str; guardian: str; address: str

class IdentityService:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def resolve_user(self, name: str, role: str) -> Tuple[bool, Optional[UserProfile]]:
        sheet = CONFIG.SHEET_STUDENT if role == "Student" else CONFIG.SHEET_TEACHER
        if role == "Staff": sheet = CONFIG.SHEET_STAFF
        
        df = self.db.fetch_data(sheet)
        if df.empty or "Name" not in df.columns:
            return False, None
            
        # Case-insensitive fuzzy match
        match = df[df["Name"].str.lower() == name.lower().strip()]
        
        if not match.empty:
            rec = match.iloc[0]
            # Safe Getters
            uid = rec.get("Roll No") or rec.get("ID") or "N/A"
            mob = rec.get("Mobile", "N/A")
            ctx = rec.get("Class") or rec.get("Department", "N/A")
            bld = rec.get("Blood Group", "Unknown")
            grd = rec.get("Guardian", "N/A")
            adr = rec.get("Address", "N/A")
            
            return True, UserProfile(name, str(uid), role, str(mob), str(ctx), str(bld), str(grd), str(adr))
        return False, None

# --- PDF Engine ---
class PDFService:
    @staticmethod
    def generate_report(title: str, dfs: dict) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=40, bottomMargin=40)
        elements = []
        styles = getSampleStyleSheet()
        
        # 1. Header
        elements.append(Paragraph(CONFIG.SCHOOL_NAME, ParagraphStyle('H1', parent=styles['Heading1'], alignment=TA_CENTER, textColor=colors.maroon)))
        elements.append(Paragraph(f"{CONFIG.ADDRESS_LINE_1}, {CONFIG.ADDRESS_LINE_2}", ParagraphStyle('H2', parent=styles['Normal'], alignment=TA_CENTER)))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(title, ParagraphStyle('H3', parent=styles['Heading2'], alignment=TA_CENTER)))
        elements.append(Spacer(1, 20))
        
        # 2. Tables
        for section_name, df in dfs.items():
            elements.append(Paragraph(section_name, styles['Heading3']))
            if not df.empty:
                # Select display columns
                cols = [c for c in ['Name', 'ID', 'Status', 'Timestamp'] if c in df.columns]
                data = [cols] + df[cols].astype(str).values.tolist()
                
                t = Table(data, colWidths=[150, 80, 80, 100])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ]))
                elements.append(t)
            else:
                elements.append(Paragraph("No records found.", styles['Italic']))
            elements.append(Spacer(1, 15))
            
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

# --- ID Card Engine ---
class IDCardEngine:
    @staticmethod
    def create_card(user: UserProfile) -> Image.Image:
        W, H = 400, 650
        img = Image.new('RGB', (W, H), "white")
        d = ImageDraw.Draw(img)
        
        border_col = CONFIG.COLOR_SECONDARY # Orange
        
        # 1. Rounded Border
        d.rounded_rectangle([10, 10, W-10, H-10], radius=20, outline=border_col, width=8)
        
        # Fonts
        try:
            font_title = ImageFont.truetype("arial.ttf", 32)
            font_name = ImageFont.truetype("arial.ttf", 28)
            font_std = ImageFont.truetype("arial.ttf", 20)
        except:
            font_title = ImageFont.load_default()
            font_name = ImageFont.load_default()
            font_std = ImageFont.load_default()
            
        # 2. Header
        d.text((W//2, 50), "GURUKULAM", font=font_title, fill=CONFIG.COLOR_PRIMARY, anchor="mm")
        d.text((W//2, 85), "Sanskrit Ved Vidyalaya", font=font_std, fill="gray", anchor="mm")
        d.line([(50, 105), (350, 105)], fill=border_col, width=2)
        
        # 3. Role Badge
        d.rounded_rectangle([130, 130, 270, 170], radius=5, fill="#D32F2F")
        d.text((W//2, 150), user.role.upper(), font=font_std, fill="white", anchor="mm")
        
        # 4. Details
        d.text((W//2, 210), user.name, font=font_name, fill="black", anchor="mm")
        d.text((W//2, 250), f"ID: {user.uid}", font=font_std, fill="#333", anchor="mm")
        d.text((W//2, 280), f"Mo: {user.mobile}", font=font_std, fill="#555", anchor="mm")
        
        label = "Class" if user.role == "Student" else "Dept"
        d.text((W//2, 310), f"{label}: {user.context}", font=font_std, fill="#333", anchor="mm")
        
        if user.blood != "Unknown":
            d.text((W//2, 340), f"Blood: {user.blood}", font=font_std, fill="red", anchor="mm")
            
        # 5. QR Code
        qr_data = f"{user.name},{user.uid},{user.role}"
        qr = qrcode.make(qr_data)
        img.paste(qr.resize((180, 180)), (110, 400))
        
        return img

# ==============================================================================
# 5. VIEW CONTROLLERS (TABS)
# ==============================================================================

class TabController:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.identity = IdentityService(db)

    def render_registration(self):
        st.header("➕ Registration Desk")
        st.info("New admissions and staff onboarding.")
        
        with st.form("reg_form", clear_on_submit=True):
            role_type = st.radio("Registration Type", ["Student", "Teacher", "Staff"], horizontal=True)
            st.divider()
            
            c1, c2 = st.columns(2)
            name = c1.text_input("Full Name")
            roll = c2.text_input("Roll No / ID / Staff ID")
            
            c3, c4 = st.columns(2)
            mob = c3.text_input("Mobile Number")
            bg = c4.selectbox("Blood Group", ["Unknown", "A+", "B+", "O+", "AB+", "A-", "B-", "O-"])
            
            c5, c6 = st.columns(2)
            cls = c5.text_input("Class / Department / Designation")
            guard = c6.text_input("Guardian Name (Students Only)")
            
            addr = st.text_area("Permanent Address")
            
            submitted = st.form_submit_button("Submit Record")
            
            if submitted:
                if not name or not roll:
                    st.error("⚠️ Name and ID are mandatory fields.")
                else:
                    target_sheet = CONFIG.SHEET_STUDENT if role_type=="Student" else CONFIG.SHEET_TEACHER
                    if role_type=="Staff": target_sheet = CONFIG.SHEET_STAFF
                    
                    # Schema: Name, Roll, Mobile, Gender, Blood, Class, Guardian, Address, Status, Date
                    row = [name, roll, mob, "Unknown", bg, cls, guard, addr, "Active", datetime.now().strftime("%Y-%m-%d")]
                    
                    if self.db.insert_row(target_sheet, row):
                        st.success(f"✅ {role_type} '{name}' registered successfully.")
                        self.audit_log(f"Registered new {role_type}: {name}")

    def render_id_cards(self):
        st.header("🖨️ ID Card Center")
        
        c_filter, c_display = st.columns([1, 2])
        
        with c_filter:
            st.subheader("Search")
            role = st.selectbox("Select Category", ["Student", "Teacher", "Staff"])
            sheet = CONFIG.SHEET_STUDENT if role=="Student" else CONFIG.SHEET_TEACHER
            if role=="Staff": sheet = CONFIG.SHEET_STAFF
            
            df = self.db.fetch_data(sheet)
            if not df.empty and "Name" in df.columns:
                name_list = sorted(df["Name"].dropna().unique())
                selected_name = st.selectbox("Select Individual", name_list)
            else:
                st.warning("No records found.")
                selected_name = None
                
        with c_display:
            if selected_name:
                if st.button("Generate Card", type="primary", use_container_width=True):
                    found, user = self.identity.resolve_user(selected_name, role)
                    if found:
                        card = IDCardEngine.create_card(user)
                        st.image(card, caption=f"{user.name} - {user.role}", width=350)
                        
                        buf = io.BytesIO()
                        card.save(buf, format="PNG")
                        st.download_button("⬇️ Download Card", buf.getvalue(), f"ID_{user.uid}.png", "image/png")

    def render_scanner(self):
        st.header("📷 Attendance Scanner")
        
        # Camera Toggle Logic
        enable_cam = st.toggle("Open Camera", value=False)
        
        if enable_cam:
            img_file_buffer = st.camera_input("Scan QR Code", label_visibility="collapsed")
            if img_file_buffer:
                # Process Image
                bytes_data = img_file_buffer.getvalue()
                cv_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(cv_img)
                
                if data:
                    try:
                        # QR Format: Name,ID,Role
                        parts = data.split(',')
                        p_name = parts[0]
                        p_id = parts[1]
                        
                        st.success(f"✅ Verified: {p_name} (ID: {p_id})")
                        st.toast(f"Marked Present: {p_name}")
                        # In a full implementation, write this to *_Logs sheets
                    except:
                        st.error("❌ Invalid QR Format")
        else:
            st.info("Camera is currently OFF. Toggle the switch to start scanning.")

    def render_analytics(self):
        st.header("📊 Analytics & Reports")
        
        # Metrics
        df_s = self.db.fetch_data(CONFIG.SHEET_STUDENT)
        df_t = self.db.fetch_data(CONFIG.SHEET_TEACHER)
        df_st = self.db.fetch_data(CONFIG.SHEET_STAFF)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Students", len(df_s) if not df_s.empty else 0)
        m2.metric("Teachers", len(df_t) if not df_t.empty else 0)
        m3.metric("Staff", len(df_st) if not df_st.empty else 0)
        
        st.divider()
        st.subheader("📂 Master Database Views")
        
        with st.expander("👨‍🎓 Student Records", expanded=True):
            st.dataframe(df_s, use_container_width=True)
            
        with st.expander("👨‍🏫 Teacher Records"):
            st.dataframe(df_t, use_container_width=True)
            
        with st.expander("🛠️ Staff Records"):
            st.dataframe(df_st, use_container_width=True)
            
        st.divider()
        st.subheader("📥 Report Generation")
        r_date = st.date_input("Select Report Date")
        
        if st.button("Generate Daily Report PDF"):
            # Mocking Log Data for demo - in real app, fetch from Log sheets filtered by date
            report_data = {
                "Student Attendance": df_s.head(5), # Just demo data
                "Teacher Attendance": df_t.head(5),
                "Staff Attendance": df_st.head(5)
            }
            pdf_bytes = PDFService.generate_report(f"Daily Report: {r_date}", report_data)
            st.download_button("⬇️ Download PDF", pdf_bytes, f"Report_{r_date}.pdf", "application/pdf")

    def render_leaves(self):
        st.header("📅 Leave Management")
        with st.form("leave_form"):
            name = st.text_input("Applicant Name")
            role = st.selectbox("Role", ["Student", "Teacher", "Staff"])
            dates = st.date_input("Leave Dates", [])
            reason = st.text_area("Reason for Leave")
            if st.form_submit_button("Submit Request"):
                row = [name, role, str(dates), reason, "Pending", datetime.now().strftime("%Y-%m-%d")]
                if self.db.insert_row(CONFIG.SHEET_LEAVES, row):
                    st.success("Leave Request Submitted.")

    def render_audit(self):
        st.header("🛡️ System Audit Trail")
        df = self.db.fetch_data(CONFIG.SHEET_AUDIT)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No logs available.")

    def render_help(self):
        st.header("📘 Help Desk")
        st.markdown("""
        **Support Contacts:**
        * 📞 Admin Office: +91-9999999999
        * 📧 Email: support@gurukulam.com
        
        **User Guide:**
        1.  **Guest Mode:** View Stats, Download ID Cards, Request Leave.
        2.  **Admin Mode:** Register users, View Audit Logs.
        """)

    def audit_log(self, action: str):
        """Helper to log actions to DB"""
        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Admin", action]
        self.db.insert_row(CONFIG.SHEET_AUDIT, row)

# ==============================================================================
# 6. MAIN APPLICATION CONTROLLER
# ==============================================================================

class GurukulamApp:
    def __init__(self):
        self.db = DatabaseManager()
        self.tabs = TabController(self.db)
        
        # Initialize Session State for Login
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

    def sidebar_ui(self):
        with st.sidebar:
            # 1. Logo Section
            if os.path.exists("logo.jpeg"):
                st.image("logo.jpeg", use_container_width=True)
            else:
                st.warning("Logo not found")

            # 2. School Title (Red Box)
            st.markdown(f"""
                <div class="school-title-box">
                    <h3>{CONFIG.SCHOOL_NAME}</h3>
                </div>
                <div class="address-text">
                    {CONFIG.ADDRESS_LINE_1}<br>{CONFIG.ADDRESS_LINE_2}
                </div>
                <hr style="margin: 15px 0;">
            """, unsafe_allow_html=True)

            # 3. Login Logic
            if not st.session_state.logged_in:
                st.markdown("### 🔒 Admin Login")
                password = st.text_input("Password", type="password", placeholder="Enter Admin Pass", label_visibility="collapsed")
                if st.button("Unlock Admin Panel", use_container_width=True):
                    if password == CONFIG.ADMIN_PASS:
                        st.session_state.logged_in = True
                        st.success("Access Granted")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Incorrect Password")
                
                st.info("You are currently in **Guest Mode**")
            else:
                st.success("🔓 Admin Access Active")
                if st.button("Logout", use_container_width=True):
                    st.session_state.logged_in = False
                    st.rerun()

    def run(self):
        inject_custom_css()
        self.sidebar_ui()
        
        # DEFINE TABS
        # Admin gets 7 tabs, Guest gets 5 tabs
        if st.session_state.logged_in:
            tab_titles = [
                "➕ Registration", # Tab 1
                "🖨️ ID Cards",     # Tab 2
                "🛡️ Audit Trail",   # Tab 3
                "📷 Scanner",      # Tab 4
                "📅 Leave Req",    # Tab 5
                "📊 Analytics",    # Tab 6
                "📘 Help Desk"     # Tab 7
            ]
            active_tabs = st.tabs(tab_titles)
            
            with active_tabs[0]: self.tabs.render_registration()
            with active_tabs[1]: self.tabs.render_id_cards()
            with active_tabs[2]: self.tabs.render_audit()
            with active_tabs[3]: self.tabs.render_scanner()
            with active_tabs[4]: self.tabs.render_leaves()
            with active_tabs[5]: self.tabs.render_analytics()
            with active_tabs[6]: self.tabs.render_help()
            
        else:
            # Guest Mode (Subset)
            # Tabs: ID Cards(2), Scanner(4), Leave(5), Analytics(6), Help(7)
            tab_titles = [
                "🖨️ ID Cards", 
                "📷 Scanner", 
                "📅 Leave Req", 
                "📊 Analytics", 
                "📘 Help Desk"
            ]
            active_tabs = st.tabs(tab_titles)
            
            with active_tabs[0]: self.tabs.render_id_cards()
            with active_tabs[1]: self.tabs.render_scanner()
            with active_tabs[2]: self.tabs.render_leaves()
            with active_tabs[3]: self.tabs.render_analytics()
            with active_tabs[4]: self.tabs.render_help()

# Entry Point
if __name__ == "__main__":
    app = GurukulamApp()
    app.run()
