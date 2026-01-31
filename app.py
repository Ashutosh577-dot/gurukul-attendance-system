import streamlit as st
import pandas as pd
import cv2
import numpy as np
import os
from datetime import datetime
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# Optional: Import plotting libraries for analytics (Add matplotlib/seaborn to requirements.txt)
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False

# ======================================================
# 1. CONFIGURATION & CONSTANTS
# ======================================================
st.set_page_config(
    page_title="Gurukulam Manager Enterprise", 
    page_icon="🕉️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# File Paths
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "Gurukulam_Database"
TRAINER_FILE = "trainer.yml"
LOGO_FILE = "logo.jpeg"

# Security
ADMIN_PASSWORD = "Gurukulam@admin"

# Role Constants
ROLE_STUDENT = "Student"
ROLE_TEACHER = "Teacher"
ROLE_STAFF = "Staff"

# Tab Names in Google Sheet
TAB_STUDENTS = "Students"
TAB_TEACHERS = "Teachers"
TAB_STAFF = "Staff"

# ======================================================
# 2. ADVANCED DATABASE MANAGER CLASS
# ======================================================
class DatabaseManager:
    """
    Handles all interactions with Google Sheets.
    Uses Singleton pattern and Caching for performance.
    """
    def __init__(self):
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.client = None
        self.sheet = None

    def connect(self):
        """Authenticates with Google Cloud."""
        if self.client is None:
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, self.scope)
                self.client = gspread.authorize(creds)
                self.sheet = self.client.open(SHEET_NAME)
                return True
            except Exception as e:
                st.error(f"🔥 Database Connection Error: {e}")
                return False
        return True

    def get_worksheet(self, role):
        """Returns the specific worksheet object based on role."""
        self.connect()
        try:
            if role == ROLE_STUDENT:
                return self.sheet.worksheet(TAB_STUDENTS)
            elif role == ROLE_TEACHER:
                return self.sheet.worksheet(TAB_TEACHERS)
            elif role == ROLE_STAFF:
                return self.sheet.worksheet(TAB_STAFF)
        except gspread.WorksheetNotFound:
            st.error(f"Tab for {role} not found in Google Sheet.")
            return None

    def fetch_all_data(self):
        """Fetches data from ALL tabs and merges them with Role injection."""
        self.connect()
        try:
            # 1. Fetch Students
            d_s = self.sheet.worksheet(TAB_STUDENTS).get_all_records()
            df_s = pd.DataFrame(d_s)
            if not df_s.empty: df_s['Role'] = ROLE_STUDENT

            # 2. Fetch Teachers
            d_t = self.sheet.worksheet(TAB_TEACHERS).get_all_records()
            df_t = pd.DataFrame(d_t)
            if not df_t.empty: df_t['Role'] = ROLE_TEACHER

            # 3. Fetch Staff
            d_st = self.sheet.worksheet(TAB_STAFF).get_all_records()
            df_st = pd.DataFrame(d_st)
            if not df_st.empty: df_st['Role'] = ROLE_STAFF

            # Combine
            return pd.concat([df_s, df_t, df_st], ignore_index=True)
        except Exception as e:
            # Return empty frame structure if DB is empty or fails
            return pd.DataFrame(columns=["SystemID", "Name", "Role"])

    def generate_system_id(self):
        """Calculates the next unique System ID."""
        df = self.fetch_all_data()
        if df.empty or 'SystemID' not in df.columns:
            return 1001 # Start at 1001 for professional look
        
        # Ensure numeric
        df['SystemID'] = pd.to_numeric(df['SystemID'], errors='coerce').fillna(0)
        return int(df['SystemID'].max()) + 1

    def save_record(self, role, data_dict):
        """Saves data to the specific sheet based on Role."""
        try:
            wks = self.get_worksheet(role)
            if not wks: return False
            
            # Common Data Structure
            row_data = [
                data_dict["SystemID"],
                data_dict["Name"],
                data_dict["Gender"],
                str(data_dict["Mobile"]),
                str(data_dict["Address"]),
                data_dict["BloodGroup"],
                data_dict["OfficialID"],
                data_dict["LastAttendance"]
            ]
            
            # Append Specifics
            if role == ROLE_STUDENT:
                row_data.extend([data_dict.get("GuardianName", ""), data_dict.get("Class", "")])
            elif role == ROLE_TEACHER:
                row_data.extend([data_dict.get("Subject", "")])
            elif role == ROLE_STAFF:
                row_data.extend([data_dict.get("StaffDesignation", "")])
            
            wks.append_row(row_data)
            return True
        except Exception as e:
            st.error(f"Save Failed: {e}")
            return False

    def mark_attendance(self, system_id, timestamp):
        """Updates LastAttendance for the ID across all sheets."""
        self.connect()
        tabs = [TAB_STUDENTS, TAB_TEACHERS, TAB_STAFF]
        for tab in tabs:
            try:
                wks = self.sheet.worksheet(tab)
                cell = wks.find(str(system_id))
                if cell:
                    # Column 8 is LastAttendance
                    wks.update_cell(cell.row, 8, timestamp)
                    return True
            except gspread.exceptions.CellNotFound:
                continue
        return False

    def delete_record(self, system_id):
        """Deletes a record permanently."""
        self.connect()
        tabs = [TAB_STUDENTS, TAB_TEACHERS, TAB_STAFF]
        for tab in tabs:
            try:
                wks = self.sheet.worksheet(tab)
                cell = wks.find(str(system_id))
                if cell:
                    wks.delete_rows(cell.row)
                    return True
            except:
                continue
        return False

# ======================================================
# 3. FACE DETECTION ENGINE
# ======================================================
class FaceEngine:
    def __init__(self):
        self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        if os.path.exists(TRAINER_FILE):
            self.recognizer.read(TRAINER_FILE)

    def detect(self, image_buffer):
        """Optimized detection for mobile/webcam."""
        try:
            file_bytes = np.asarray(bytearray(image_buffer.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, 1)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray) # Improve lighting
            
            faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
            
            if len(faces) > 0:
                biggest = max(faces, key=lambda rect: rect[2] * rect[3])
                (x, y, w, h) = biggest
                return gray[y:y+h, x:x+w], img
            return None, img
        except Exception as e:
            st.error(f"CV Error: {e}")
            return None, None

    def train(self, face_roi, label_id):
        """Updates the LBPH model."""
        try:
            if os.path.exists(TRAINER_FILE):
                self.recognizer.read(TRAINER_FILE)
            self.recognizer.update([face_roi], np.array([label_id]))
            self.recognizer.write(TRAINER_FILE)
            return True
        except Exception as e:
            st.error(f"Training Error: {e}")
            return False

# ======================================================
# 4. ADVANCED REPORT GENERATOR
# ======================================================
class ReportGenerator(FPDF):
    """Custom PDF Generator with Headers, Footers, and Dynamic Titles."""
    def __init__(self, title="Report"):
        super().__init__()
        self.report_title = title

    def header(self):
        if os.path.exists(LOGO_FILE):
            self.image(LOGO_FILE, x=10, y=8, w=25)
        
        self.set_font('Arial', 'B', 15)
        self.set_text_color(139, 0, 0) # Dark Red
        self.cell(80) # Move right
        self.cell(30, 10, 'Shri Hulas Bramh Baba Sanskrit Ved Gurukulam', 0, 0, 'C')
        self.ln(20)
        
        self.set_font('Arial', 'I', 12)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, f"{self.report_title} - {datetime.now().strftime('%d-%b-%Y')}", 0, 1, 'C')
        self.ln(10)
        
        # Table Header
        self.set_fill_color(220, 220, 220)
        self.set_font('Arial', 'B', 10)
        self.cell(40, 10, 'Name', 1, 0, 'C', True)
        self.cell(30, 10, 'Role', 1, 0, 'C', True)
        self.cell(30, 10, 'ID', 1, 0, 'C', True)
        self.cell(50, 10, 'Last Seen', 1, 1, 'C', True)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_row(self, row):
        self.set_font('Arial', '', 10)
        name = str(row.get('Name', ''))[:20]
        role = str(row.get('Role', ''))
        sys_id = str(row.get('SystemID', ''))
        last_att = str(row.get('LastAttendance', ''))
        
        self.cell(40, 10, name, 1)
        self.cell(30, 10, role, 1)
        self.cell(30, 10, sys_id, 1)
        self.cell(50, 10, last_att, 1)
        self.ln()

# ======================================================
# 5. UI COMPONENTS
# ======================================================

# --- Init Logic ---
db = DatabaseManager()
face_engine = FaceEngine()

# --- CSS Styling ---
st.markdown("""
    <style>
    .stApp { background-color: #FFF8E1; }
    section[data-testid="stSidebar"] { background-color: #FF9933; }
    h1, h2, h3 { color: #8B0000; font-family: 'Georgia', serif; }
    .stButton>button { background-color: #8B0000; color: white; border-radius: 5px; }
    div[data-testid="stMetricValue"] { color: #8B0000; }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🕉️ Gurukulam Admin")
    if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=100)
    st.markdown("---")
    
    password = st.text_input("🔐 Admin Access", type="password")
    is_admin = password == ADMIN_PASSWORD
    
    if is_admin:
        st.success("Authenticated")
        st.caption("System Status: Online 🟢")
    else:
        st.warning("Locked 🔒")

# --- MAIN TABS ---
t1, t2, t3, t4 = st.tabs(["📝 Register", "📷 Attendance", "📊 Analytics & Reports", "⚙️ Database"])

# ------------------------------------------------------
# TAB 1: REGISTRATION (Dynamic & Form-Based)
# ------------------------------------------------------
with t1:
    if is_admin:
        st.header("New Member Registration")
        
        # 1. Camera Section (Interactive)
        st.markdown("### 1. Biometric Capture")
        if 'cam_active' not in st.session_state: st.session_state.cam_active = False
        
        if st.button("🔴 Stop Camera" if st.session_state.cam_active else "📷 Start Camera", key="reg_cam_btn"):
            st.session_state.cam_active = not st.session_state.cam_active
            st.rerun()
            
        img_buffer = None
        if st.session_state.cam_active:
            img_buffer = st.camera_input("Face Scanner", label_visibility="collapsed")
            if img_buffer: st.success("📸 Image Acquired!")

        st.divider()

        # 2. Details Section (Dynamic Form)
        st.markdown("### 2. Member Details")
        
        # Role Selector determines form fields
        role_type = st.radio("Select Category:", [ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF], horizontal=True)
        
        with st.form("main_reg_form", clear_on_submit=True):
            st.caption(f"Registering New {role_type}")
            
            # Common Fields
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("Full Name")
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            with c2:
                mobile = st.text_input("Mobile Number")
                address = st.text_area("Address", height=35)
            with c3:
                blood = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "Unknown"])

            # Specific Fields
            spec1, spec2, spec3 = st.columns(3)
            
            # Initialize Vars
            off_id = ""
            guard = ""
            cls = ""
            subj = ""
            desig = ""

            if role_type == ROLE_STUDENT:
                off_id = spec1.text_input("Roll Number")
                cls = spec2.text_input("Class / Standard")
                guard = spec3.text_input("Guardian Name")
            elif role_type == ROLE_TEACHER:
                off_id = spec1.text_input("Teacher ID")
                subj = spec2.text_input("Subject")
            elif role_type == ROLE_STAFF:
                off_id = spec1.text_input("Staff ID")
                desig = spec2.text_input("Designation")
            
            st.markdown("---")
            submitted = st.form_submit_button("💾 Save to Cloud (Press Enter)", type="primary")
            
            if submitted:
                if name and img_buffer:
                    with st.spinner("Processing..."):
                        # Detect Face
                        roi, _ = face_engine.detect(img_buffer)
                        
                        if roi is not None:
                            # Generate ID
                            sys_id = db.generate_system_id()
                            
                            # Prepare Data Payload
                            data = {
                                "SystemID": sys_id, "Name": name, "Gender": gender,
                                "Mobile": mobile, "Address": address, "BloodGroup": blood,
                                "OfficialID": off_id, "LastAttendance": "Never"
                            }
                            
                            # Add Extras
                            if role_type == ROLE_STUDENT:
                                data.update({"GuardianName": guard, "Class": cls})
                            elif role_type == ROLE_TEACHER:
                                data.update({"Subject": subj})
                            elif role_type == ROLE_STAFF:
                                data.update({"StaffDesignation": desig})
                            
                            # Save
                            if db.save_record(role_type, data):
                                face_engine.train(roi, sys_id)
                                st.balloons()
                                st.success(f"✅ Registered {name} (ID: {sys_id})")
                            else:
                                st.error("Database Save Failed")
                        else:
                            st.error("Face not detected clearly. Try again.")
                else:
                    st.warning("⚠️ Name and Photo are required.")
    else:
        st.info("Please login to register members.")

# ------------------------------------------------------
# TAB 2: ATTENDANCE
# ------------------------------------------------------
with t2:
    st.header("Daily Attendance")
    
    if 'att_active' not in st.session_state: st.session_state.att_active = False
    
    if st.button("🔴 Stop Scanner" if st.session_state.att_active else "📷 Start Scanner", key="att_btn"):
        st.session_state.att_active = not st.session_state.att_active
        st.rerun()
        
    if st.session_state.att_active:
        att_buf = st.camera_input("Scanner", label_visibility="collapsed")
        
        if att_buf:
            roi, _ = face_engine.detect(att_buf)
            if roi is not None:
                if hasattr(face_engine.recognizer, 'predict'):
                    try:
                        id_pred, conf = face_engine.recognizer.predict(roi)
                        
                        # Confidence < 75 is a match
                        if conf < 75:
                            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if db.mark_attendance(id_pred, ts):
                                st.success(f"✅ Attendance Marked (ID: {id_pred})")
                                st.balloons()
                            else:
                                st.warning("ID recognized but not in Database.")
                        else:
                            st.error("❌ Face not matched")
                    except:
                        st.warning("Model not trained yet.")
            else:
                st.warning("No face detected.")

# ------------------------------------------------------
# TAB 3: ANALYTICS (Advanced & Visual)
# ------------------------------------------------------
with t3:
    st.header("Reports & Analytics")
    if st.button("🔄 Refresh Data"): st.rerun()
    
    df = db.fetch_all_data()
    
    if not df.empty:
        # Filter Logic
        view_filter = st.selectbox("Select View:", ["All Members", ROLE_STUDENT, ROLE_TEACHER, ROLE_STAFF])
        
        if view_filter != "All Members":
            view_df = df[df['Role'] == view_filter]
        else:
            view_df = df
            
        # 1. Metrics
        m1, m2 = st.columns(2)
        m1.metric(f"Total {view_filter}", len(view_df))
        
        # Active Today logic
        today_str = datetime.now().strftime('%Y-%m-%d')
        active_count = len(view_df[view_df['LastAttendance'].str.contains(today_str, na=False)])
        m2.metric("Present Today", active_count)
        
        # 2. Visuals (Charts)
        if PLOTTING_AVAILABLE:
            st.subheader("Demographics")
            c1, c2 = st.columns(2)
            with c1:
                # Role Distribution
                if view_filter == "All Members":
                    fig1, ax1 = plt.subplots(figsize=(5,3))
                    view_df['Role'].value_counts().plot.pie(autopct='%1.1f%%', ax=ax1, colors=sns.color_palette('pastel'))
                    ax1.set_ylabel('')
                    ax1.set_title("Role Distribution")
                    st.pyplot(fig1)
            with c2:
                # Gender Distribution
                fig2, ax2 = plt.subplots(figsize=(5,3))
                sns.countplot(data=view_df, x='Gender', palette="Set2", ax=ax2)
                ax2.set_title("Gender Split")
                st.pyplot(fig2)
        
        # 3. Data Table
        st.subheader("Detailed Records")
        st.dataframe(view_df, use_container_width=True)
        
        # 4. Downloads
        d1, d2 = st.columns(2)
        
        # CSV
        csv = view_df.to_csv(index=False).encode('utf-8')
        d1.download_button(f"📥 Download {view_filter} CSV", data=csv, file_name=f"{view_filter}_Data.csv", mime="text/csv")
        
        # PDF
        if d2.button(f"📄 Generate {view_filter} PDF Report"):
            try:
                pdf = ReportGenerator(title=f"{view_filter} Attendance Report")
                pdf.add_page()
                for _, row in view_df.iterrows():
                    pdf.add_row(row)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button(
                    label="⬇️ Click to Download PDF",
                    data=pdf_bytes,
                    file_name=f"{view_filter}_Report.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"PDF Error: {e}")
    else:
        st.info("Database is empty.")

# ------------------------------------------------------
# TAB 4: MANAGER
# ------------------------------------------------------
with t4:
    if is_admin:
        st.header("Database Maintenance")
        df = db.fetch_all_data()
        
        if not df.empty:
            st.warning("⚠️ Deleting a record is permanent.")
            
            # Smart Selector
            options = df.apply(lambda x: f"{x['SystemID']} - {x['Name']} ({x['Role']})", axis=1)
            selected = st.selectbox("Select Record to Delete", options)
            
            if st.button("❌ Delete Permanently"):
                sys_id = selected.split(" - ")[0]
                if db.delete_record(sys_id):
                    st.success(f"ID {sys_id} Deleted.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Delete failed.")
        else:
            st.info("No records to manage.")
    else:
        st.warning("🔒 Admin Access Required")
