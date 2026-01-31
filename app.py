import streamlit as st
import pandas as pd
import cv2
import numpy as np
import os
from datetime import datetime
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Gurukulam Manager", page_icon="🕉️", layout="wide")

# --- CONFIGURATION ---
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "Gurukulam_Database"
TRAINER_FILE = "trainer.yml"
ADMIN_PASSWORD = "Gurukulam@admin"

# --- INIT FACE RECOGNIZER ---
recognizer = cv2.face.LBPHFaceRecognizer_create()
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# --- GOOGLE SHEETS CONNECTION ---
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    return gspread.authorize(creds)

# --- DATABASE FUNCTIONS ---

def get_all_data():
    """Fetches data and smart-injects the Role based on the sheet name."""
    try:
        client = get_client()
        sh = client.open(SHEET_NAME)
        
        # 1. Fetch Students
        data_s = sh.worksheet("Students").get_all_records()
        df_s = pd.DataFrame(data_s)
        if not df_s.empty: 
            df_s['Role'] = 'Student' # Inject Role back for Analytics

        # 2. Fetch Teachers
        data_t = sh.worksheet("Teachers").get_all_records()
        df_t = pd.DataFrame(data_t)
        if not df_t.empty: 
            df_t['Role'] = 'Teacher' # Inject Role back

        # 3. Fetch Staff
        data_st = sh.worksheet("Staff").get_all_records()
        df_st = pd.DataFrame(data_st)
        if not df_st.empty: 
            df_st['Role'] = 'Staff' # Inject Role back
        
        # Combine all
        df_combined = pd.concat([df_s, df_t, df_st], ignore_index=True)
        return df_combined
    except Exception as e:
        return pd.DataFrame(columns=["SystemID", "Name", "Role"])

def get_next_system_id():
    """Calculates the next unique ID."""
    df = get_all_data()
    if df.empty or 'SystemID' not in df.columns:
        return 1
    
    df['SystemID'] = pd.to_numeric(df['SystemID'], errors='coerce').fillna(0)
    if df.empty:
        return 1
    return int(df['SystemID'].max()) + 1

def save_to_sheet(data_dict, role_category):
    """Saves data WITHOUT the redundant Role column."""
    try:
        client = get_client()
        sh = client.open(SHEET_NAME)
        
        # 1. Prepare Common Data (Removed 'Role' from this list)
        common_data = [
            data_dict["SystemID"],
            data_dict["Name"],
            data_dict["Gender"],
            str(data_dict["Mobile"]),
            str(data_dict["Address"]),
            data_dict["BloodGroup"],
            data_dict["OfficialID"],
            data_dict["LastAttendance"]
        ]
        
        # 2. Append Specific Data based on Role
        if "Student" in role_category:
            wks = sh.worksheet("Students")
            # Append Guardian and Class
            row = common_data + [data_dict["GuardianName"], data_dict["Class"]]
            
        elif "Teacher" in role_category:
            wks = sh.worksheet("Teachers")
            # Append Subject Only
            row = common_data + [data_dict["Subject"]]
            
        else:
            wks = sh.worksheet("Staff")
            # Append Designation Only
            row = common_data + [data_dict["StaffDesignation"]]
            
        wks.append_row(row)
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False

def update_attendance_in_sheets(system_id, time_str):
    """Updates LastAttendance column (Column 8 / 'H')."""
    try:
        client = get_client()
        sh = client.open(SHEET_NAME)
        sheets = ["Students", "Teachers", "Staff"]
        
        for sheet_name in sheets:
            wks = sh.worksheet(sheet_name)
            try:
                cell = wks.find(str(system_id))
                if cell:
                    # 'LastAttendance' is now Column 8 because Role was removed
                    wks.update_cell(cell.row, 8, time_str)
                    return True
            except gspread.exceptions.CellNotFound:
                continue
        return False
    except Exception as e:
        st.error(f"Attendance Update Error: {e}")
        return False

def delete_from_sheets(system_id):
    try:
        client = get_client()
        sh = client.open(SHEET_NAME)
        sheets = ["Students", "Teachers", "Staff"]
        
        for sheet_name in sheets:
            wks = sh.worksheet(sheet_name)
            try:
                cell = wks.find(str(system_id))
                if cell:
                    wks.delete_rows(cell.row)
                    return True
            except gspread.exceptions.CellNotFound:
                continue
        return False
    except Exception as e:
        st.error(f"Delete Error: {e}")
        return False

def detect_face(image_buffer):
    file_bytes = np.asarray(bytearray(image_buffer.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
    if len(faces) > 0:
        biggest_face = max(faces, key=lambda rect: rect[2] * rect[3])
        (x, y, w, h) = biggest_face
        return gray[y:y+h, x:x+w], img
    return None, img

# --- STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #FFF8E1; }
    section[data-testid="stSidebar"] { background-color: #FF9933; color: white; }
    h1, h2, h3 { color: #8B0000; font-family: serif; }
    .stButton>button { background-color: #8B0000; color: white; border: 2px solid #5D4037; }
    div[data-testid="stCameraInput"] { border: 2px solid #8B0000; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🕉️")
    st.markdown("### Gurukulam Manager")
    st.caption("Database: Smart-Split Sheets ☁️")
    st.markdown("---")
    
    st.markdown("### 🔐 Admin Login")
    input_pass = st.text_input("Enter Password", type="password", key="sidebar_pass")
    is_admin = input_pass == ADMIN_PASSWORD
    if is_admin: st.success("✅ Access Granted")

# --- MAIN APP ---
st.title("🕉️ Gurukulam Upasthiti System")

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Registration (Admin)", 
    "📷 Face Attendance", 
    "📊 Analytics", 
    "🗑️ Manage Database"
])

# ==========================================
# TAB 1: REGISTRATION (CLEANER)
# ==========================================
with tab1:
    if is_admin:
        st.header("Register New Member")
        
        st.markdown("### Step 1: Select Category")
        role_selection = st.radio("Choose Role:", ["Student 🎓", "Teacher 👨‍🏫", "Staff 🛠️"], horizontal=True)
        role = role_selection.split()[0] 

        st.markdown("---")
        st.markdown(f"### Step 2: Enter Details")

        # 1. COMMON FIELDS
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("Full Name")
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        with c2:
            mobile = st.text_input("Mobile Number")
            address = st.text_area("Address", height=35)
        with c3:
            blood_group = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Unknown"])

        # 2. SPECIFIC FIELDS
        official_id_input = ""
        guardian_name = ""
        student_class = ""
        subject = ""
        staff_designation = ""

        if role == "Student":
            st.info("🎓 Student Details")
            cs1, cs2, cs3 = st.columns(3)
            official_id_input = cs1.text_input("Roll Number")
            student_class = cs2.text_input("Class")
            guardian_name = cs3.text_input("Guardian Name")
            
        elif role == "Teacher":
            st.info("👨‍🏫 Teacher Details")
            ct1, ct2 = st.columns(2)
            official_id_input = ct1.text_input("Teacher ID")
            subject = ct2.text_input("Subject")
            
        elif role == "Staff":
            st.info("🛠️ Staff Details")
            cst1, cst2 = st.columns(2)
            official_id_input = cst1.text_input("Staff ID")
            staff_designation = cst2.text_input("Staff Role / Designation")

        st.markdown("---")
        st.markdown("### Step 3: Face Setup")

        if 'reg_cam_on' not in st.session_state: st.session_state.reg_cam_on = False
        if st.button("🔴 Stop Camera" if st.session_state.reg_cam_on else "📷 Start Camera", key="reg_toggle"):
            st.session_state.reg_cam_on = not st.session_state.reg_cam_on
            st.rerun()

        img_file = None
        if st.session_state.reg_cam_on:
            img_file = st.camera_input("Capture Face", label_visibility="collapsed")

        st.markdown("---")
        if st.button(f"💾 Save {role} to Cloud", type="primary", use_container_width=True):
            if name and img_file:
                try:
                    face_roi, _ = detect_face(img_file)
                    if face_roi is not None:
                        new_sys_id = get_next_system_id()
                        
                        # Data Dictionary
                        new_data = {
                            "SystemID": new_sys_id,
                            "Name": name,
                            "Gender": gender,
                            "Mobile": str(mobile),
                            "Address": str(address),
                            "BloodGroup": blood_group,
                            "OfficialID": official_id_input,
                            "LastAttendance": "Never",
                        }
                        
                        # Add specific fields based on role
                        if role == "Student":
                            new_data["GuardianName"] = guardian_name
                            new_data["Class"] = student_class
                        elif role == "Teacher":
                            new_data["Subject"] = subject
                        elif role == "Staff":
                            new_data["StaffDesignation"] = staff_designation
                        
                        success = save_to_sheet(new_data, role)
                        
                        if success:
                            if os.path.exists(TRAINER_FILE): recognizer.read(TRAINER_FILE)
                            recognizer.update([face_roi], np.array([new_sys_id]))
                            recognizer.write(TRAINER_FILE)
                            st.balloons()
                            st.success(f"✅ Registered {name} (ID: {new_sys_id})")
                            st.session_state.reg_cam_on = False
                            st.rerun()
                    else:
                        st.error("⚠️ No face detected.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("⚠️ Fill Name & Photo.")
    else:
        st.warning("🔒 Admin Access Required")

# ==========================================
# TAB 2: ATTENDANCE
# ==========================================
with tab2:
    st.header("Mark Attendance")
    if 'att_cam_on' not in st.session_state: st.session_state.att_cam_on = False

    if st.button("🔴 Stop Camera" if st.session_state.att_cam_on else "📷 Start Camera", key="att_toggle"):
        st.session_state.att_cam_on = not st.session_state.att_cam_on
        st.rerun()

    if st.session_state.att_cam_on:
        attendance_cam = st.camera_input("Scan Face", key="att_cam", label_visibility="collapsed")
        if attendance_cam:
            if os.path.exists(TRAINER_FILE):
                try:
                    recognizer.read(TRAINER_FILE)
                    face_roi, _ = detect_face(attendance_cam)
                    if face_roi is not None:
                        id_predicted, confidence = recognizer.predict(face_roi)
                        if confidence < 75:
                            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            success = update_attendance_in_sheets(id_predicted, time_now)
                            if success:
                                st.success(f"✅ Attendance Marked! (ID: {id_predicted})")
                                st.balloons()
                            else:
                                st.error("ID recognized but not found in Google Sheet.")
                        else:
                            st.error("❌ Face not matched.")
                    else:
                        st.warning("⚠️ No face detected.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("⚠️ Database Empty.")

# ==========================================
# TAB 3: ANALYTICS
# ==========================================
with tab3:
    st.header("Gurukulam Analytics")
    if st.button("🔄 Refresh Data"): st.rerun()
        
    df = get_all_data()
    
    if not df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df))
        c2.metric("Students", len(df[df['Role'] == 'Student']))
        c3.metric("Teachers", len(df[df['Role'] == 'Teacher']))
        c4.metric("Staff", len(df[df['Role'] == 'Staff']))
        
        # Display data
        st.dataframe(df)
        
        def create_pdf(dataframe):
            class PDF(FPDF):
                def header(self):
                    if os.path.exists("logo.jpeg"):
                        self.image("logo.jpeg", x=90, y=10, w=30)
                        self.ln(35)
                    else:
                        self.ln(10)
                    self.set_fill_color(200, 0, 0)
                    self.set_text_color(255, 255, 255)
                    self.set_font('Arial', 'B', 14)
                    self.cell(0, 15, 'Shri Hulas Bramh Baba Sanskrit Ved Gurukulam', 0, 1, 'C', True)
                    self.ln(10)
                    self.set_text_color(0, 0, 0)
                    self.set_font('Arial', 'B', 10)
                    # Headers
                    self.cell(40, 10, 'Name', 1)
                    self.cell(20, 10, 'Role', 1)
                    self.cell(30, 10, 'Official ID', 1)
                    self.cell(40, 10, 'Last Attendance', 1)
                    self.ln()
            
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', '', 10)
            for _, row in dataframe.iterrows():
                # Safety check
                name = str(row.get('Name', ''))[:20]
                role = str(row.get('Role', ''))
                off_id = str(row.get('OfficialID', ''))
                last_att = str(row.get('LastAttendance', ''))
                
                pdf.cell(40, 10, name, 1)
                pdf.cell(20, 10, role, 1)
                pdf.cell(30, 10, off_id, 1)
                pdf.cell(40, 10, last_att, 1)
                pdf.ln()
            return pdf.output(dest='S').encode('latin-1')

        if st.button("📄 Generate PDF Report"):
            try:
                pdf_bytes = create_pdf(df)
                st.download_button("Download PDF", data=pdf_bytes, file_name="Gurukulam_Report.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"PDF Error: {e}")
    else:
        st.info("Cloud Database is empty.")

# ==========================================
# TAB 4: DATABASE MANAGER
# ==========================================
with tab4:
    if is_admin:
        st.header("🗑️ Manage Cloud Database")
        df = get_all_data()
        if not df.empty:
            st.dataframe(df[['SystemID', 'Name', 'Role', 'OfficialID']])
            id_to_delete = st.selectbox("Select System ID to Delete", df['SystemID'].tolist())
            
            if st.button("❌ Delete from Google Sheet"):
                success = delete_from_sheets(id_to_delete)
                if success:
                    st.success(f"Deleted ID {id_to_delete} from Cloud.")
                    st.rerun()
                else:
                    st.error("Failed to delete.")
        else:
            st.info("Nothing to delete.")
    else:
        st.warning("🔒 Admin Access Required")
