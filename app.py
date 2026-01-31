import streamlit as st
import pandas as pd
import cv2
import numpy as np
import os
from datetime import datetime
from fpdf import FPDF

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Gurukulam Manager", page_icon="🕉️", layout="wide")

# --- FILE PATHS ---
DB_FILE = "gurukulam_data.csv"
TRAINER_FILE = "trainer.yml"
ADMIN_PASSWORD = "Gurukulam@admin"

# --- INIT FACE RECOGNIZER ---
recognizer = cv2.face.LBPHFaceRecognizer_create()
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# --- HELPER FUNCTIONS ---
def load_data():
    """Loads student data and creates missing columns if needed."""
    columns = [
        "SystemID", "Name", "Role", "Gender", "Mobile", "Address", 
        "GuardianName", "Class", "BloodGroup", "OfficialID", 
        "Subject", "LastAttendance"
    ]
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=columns)
    
    df = pd.read_csv(DB_FILE)
    
    # Ensure all columns exist
    for col in columns:
        if col not in df.columns:
            df[col] = "N/A"
            
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def detect_face(image_buffer):
    file_bytes = np.asarray(bytearray(image_buffer.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray) # Improve contrast
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
    st.caption("Shri Hulas Bramh Baba Sanskrit Ved Gurukulam")
    st.markdown("---")
    
    st.markdown("### 🔐 Admin Login")
    input_pass = st.text_input("Enter Password", type="password", key="sidebar_pass")
    is_admin = input_pass == ADMIN_PASSWORD
    if is_admin: st.success("✅ Access Granted")

# --- MAIN APP ---
st.title("🕉️ Gurukulam Upasthiti System")

# ADDED TAB 4 for Database Management
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Registration (Admin)", 
    "📷 Face Attendance", 
    "📊 Analytics", 
    "🗑️ Manage Database"
])

# ==========================================
# TAB 1: REGISTRATION (NEW DESIGN)
# ==========================================
with tab1:
    if is_admin:
        st.header("Register New Member")
        
        # 1. SELECT ROLE (Radio Buttons instead of Dropdown)
        st.markdown("### Step 1: Select Category")
        role_selection = st.radio("Choose Role to Register:", 
                                ["Student 🎓", "Teacher 👨‍🏫", "Staff 🛠️"], 
                                horizontal=True)
        
        # Clean up the role string (Remove emoji)
        role = role_selection.split()[0] 

        st.markdown("---")
        st.markdown(f"### Step 2: Enter {role} Details")

        # 2. COMMON FIELDS (Asked for EVERYONE now)
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name")
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            blood_group = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-", "Unknown"])
        with col2:
            mobile = st.text_input("Mobile Number")
            address = st.text_area("Address (City/Village)", height=100)

        # 3. SPECIFIC FIELDS (Based on Role)
        official_id = "N/A"
        student_class = "N/A"
        guardian_name = "N/A"
        subject = "N/A"

        if role == "Student":
            st.info("🎓 Student Specific Details")
            c_s1, c_s2 = st.columns(2)
            official_id = c_s1.text_input("Roll Number")
            student_class = c_s1.text_input("Class / Standard")
            guardian_name = c_s2.text_input("Guardian / Father's Name")
            
        elif role == "Teacher":
            st.info("👨‍🏫 Teacher Specific Details")
            c_t1, c_t2 = st.columns(2)
            official_id = c_t1.text_input("Teacher ID")
            subject = c_t2.text_input("Subject / Designation")
            
        elif role == "Staff":
            st.info("🛠️ Staff Specific Details")
            official_id = st.text_input("Staff ID")

        st.markdown("---")
        st.markdown("### Step 3: Face Setup")

        # 4. CAMERA (Start/Stop Only - No Switch)
        if 'reg_cam_on' not in st.session_state: st.session_state.reg_cam_on = False

        if st.button("🔴 Stop Camera" if st.session_state.reg_cam_on else "📷 Start Camera", key="reg_toggle"):
            st.session_state.reg_cam_on = not st.session_state.reg_cam_on
            st.rerun()

        img_file = None
        if st.session_state.reg_cam_on:
            img_file = st.camera_input("Capture Face", label_visibility="collapsed")

        # 5. SAVE BUTTON
        st.markdown("---")
        if st.button(f"💾 Register {role}", type="primary", use_container_width=True):
            if name and img_file:
                try:
                    face_roi, _ = detect_face(img_file)
                    if face_roi is not None:
                        df = load_data()
                        
                        # Auto-Generate System ID
                        if df.empty or 'SystemID' not in df.columns or df['SystemID'].isnull().all():
                            new_sys_id = 1
                        else:
                            # Safely get max ID
                            df['SystemID'] = pd.to_numeric(df['SystemID'], errors='coerce').fillna(0)
                            new_sys_id = int(df['SystemID'].max()) + 1
                        
                        # DATA SAVING LOGIC (Ensuring all fields are saved)
                        new_data = {
                            "SystemID": new_sys_id,
                            "Name": name,
                            "Role": role,
                            "Gender": gender,
                            "Mobile": str(mobile), # Force string
                            "Address": str(address), # Force string
                            "GuardianName": guardian_name,
                            "Class": student_class,
                            "BloodGroup": blood_group,
                            "OfficialID": official_id,
                            "Subject": subject,
                            "LastAttendance": "Never"
                        }
                        
                        # Add to DataFrame
                        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                        save_data(df)
                        
                        # Train Face
                        if os.path.exists(TRAINER_FILE): recognizer.read(TRAINER_FILE)
                        recognizer.update([face_roi], np.array([new_sys_id]))
                        recognizer.write(TRAINER_FILE)
                        
                        st.balloons()
                        st.success(f"✅ Registered: {name} (ID: {new_sys_id})")
                        st.session_state.reg_cam_on = False
                        st.rerun()
                    else:
                        st.error("⚠️ No face detected. Try again.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("⚠️ Please fill Name and Take Photo.")
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
                            df = load_data()
                            # Find user
                            user = df[df['SystemID'] == id_predicted]
                            if not user.empty:
                                name_found = user.iloc[0]['Name']
                                role_found = user.iloc[0]['Role']
                                # Mark Time
                                df.loc[df['SystemID'] == id_predicted, 'LastAttendance'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                save_data(df)
                                st.success(f"✅ Marked: {name_found}")
                                st.balloons()
                            else:
                                st.warning("ID found in Face DB but missing in CSV.")
                        else:
                            st.error("❌ Face not matched.")
                    else:
                        st.warning("⚠️ No face detected.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("⚠️ Database empty.")

# ==========================================
# TAB 3: ANALYTICS (PDF & VIEW)
# ==========================================
with tab3:
    st.header("Gurukulam Analytics")
    df = load_data()
    if not df.empty:
        # Metrics
        st.metric("Total Members", len(df))
        st.dataframe(df) # Shows all columns now including Mobile/Address
        
        # PDF Generator
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
                    # Table Header
                    self.cell(40, 10, 'Name', 1)
                    self.cell(30, 10, 'Role', 1)
                    self.cell(30, 10, 'Mobile', 1) # Added Mobile to PDF
                    self.cell(50, 10, 'Last Attendance', 1)
                    self.ln()
            
            pdf = PDF()
            pdf.add_page()
            pdf.set_font('Arial', '', 10)
            for _, row in dataframe.iterrows():
                pdf.cell(40, 10, str(row['Name'])[:20], 1)
                pdf.cell(30, 10, str(row['Role']), 1)
                pdf.cell(30, 10, str(row['Mobile']), 1)
                pdf.cell(50, 10, str(row['LastAttendance']), 1)
                pdf.ln()
            return pdf.output(dest='S').encode('latin-1')

        if st.button("📄 Generate PDF Report"):
            try:
                pdf_bytes = create_pdf(df)
                st.download_button("Download PDF", data=pdf_bytes, file_name="Gurukulam_Report.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"PDF Error: {e}")
    else:
        st.info("No data found.")

# ==========================================
# TAB 4: DATABASE MANAGER (EDIT/DELETE)
# ==========================================
with tab4:
    if is_admin:
        st.header("🗑️ Manage Database")
        st.warning("⚠️ Warning: Deleting a member is permanent.")
        
        df = load_data()
        if not df.empty:
            st.subheader("Current Records")
            # Show a simplified table for selection
            st.dataframe(df[['SystemID', 'Name', 'Role', 'Mobile', 'BloodGroup']])
            
            # DELETE SECTION
            st.markdown("---")
            st.subheader("Delete Member")
            
            # Select ID to delete
            id_list = df['SystemID'].tolist()
            id_to_delete = st.selectbox("Select System ID to Delete", id_list)
            
            if st.button("❌ Delete Selected Member"):
                # Filter out the selected ID
                new_df = df[df['SystemID'] != id_to_delete]
                save_data(new_df)
                
                # Note: We cannot easily remove just one face from the LBPH model 
                # without retraining from all images. For a simple CSV app, 
                # we just delete the record so their ID won't match a name anymore.
                st.success(f"Member with ID {id_to_delete} has been deleted.")
                st.rerun()
        else:
            st.info("Database is empty.")
    else:
        st.warning("🔒 Admin Access Required")
