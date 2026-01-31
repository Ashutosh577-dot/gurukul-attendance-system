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
ADMIN_PASSWORD = "Gurukulam@admin"  # Password set here

# --- INIT FACE RECOGNIZER ---
recognizer = cv2.face.LBPHFaceRecognizer_create()
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# --- HELPER FUNCTIONS ---
def load_data():
    columns = [
        "SystemID", "Name", "Role", "Gender", "Mobile", "Address", 
        "GuardianName", "Class", "BloodGroup", "OfficialID", 
        "Subject", "LastAttendance"
    ]
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(DB_FILE)
    for col in columns:
        if col not in df.columns:
            df[col] = "" 
    return df

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def detect_face(image_buffer):
    file_bytes = np.asarray(bytearray(image_buffer.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5)
    if len(faces) > 0:
        (x, y, w, h) = faces[0]
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
    
    if is_admin: 
        st.success("✅ Access Granted")
    elif input_pass:
        st.error("❌ Invalid Password")

# --- MAIN APP ---
st.title("🕉️ Gurukulam Upasthiti System")
tab1, tab2, tab3 = st.tabs(["📝 Registration (Admin)", "📷 Face Attendance", "📊 Analytics"])

# ==========================================
# TAB 1: REGISTRATION (LOCKED 🔒)
# ==========================================
with tab1:
    if is_admin:
        st.header("Register New Member")
        
        # 1. Role Selection
        role = st.selectbox("Select Role", ["Student", "Teacher", "Staff"])
        
        # 2. Dynamic Input Fields
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name")
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            mobile = st.text_input("Mobile Number")
        with col2:
            system_id = st.number_input("System ID (Numeric Only)", min_value=1, step=1, help="Unique number for Face System")
            address = st.text_area("Address", height=100)

        st.markdown("---")
        
        # Role Specific Fields
        guardian_name = ""
        student_class = ""
        blood_group = ""
        official_id = "" 
        subject = ""
        
        if role == "Student":
            st.subheader("🎓 Student Details")
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                official_id = st.text_input("Roll Number")
                student_class = st.text_input("Class / Standard")
            with c_s2:
                guardian_name = st.text_input("Guardian / Father's Name")
                blood_group = st.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"])
                
        elif role == "Teacher":
            st.subheader("👨‍🏫 Teacher Details")
            c_t1, c_t2 = st.columns(2)
            with c_t1:
                official_id = st.text_input("Teacher ID (Official)")
            with c_t2:
                subject = st.text_input("Subject / Designation")
                
        elif role == "Staff":
            st.subheader("🛠️ Staff Details")
            official_id = st.text_input("Staff ID")

        st.markdown("---")
        st.info("📷 Photo Setup")

        # Camera Controls
        if 'reg_camera_active' not in st.session_state:
            st.session_state.reg_camera_active = False

        col_cam1, col_cam2 = st.columns(2)
        with col_cam1:
            if st.button("🔴 Stop Camera" if st.session_state.reg_camera_active else "📷 Start Camera", key="reg_cam_toggle"):
                st.session_state.reg_camera_active = not st.session_state.reg_camera_active
                st.rerun()
        with col_cam2:
            if st.session_state.reg_camera_active:
                if st.button("🔄 Switch Camera", key="reg_cam_switch"):
                    st.session_state.reg_camera_active = False
                    st.rerun()

        img_file = None
        if st.session_state.reg_camera_active:
            img_file = st.camera_input("Take Photo", key="reg_camera", label_visibility="collapsed")

        st.markdown("---")

        if st.button("💾 Save Registration", type="primary"):
            if name and system_id and img_file:
                try:
                    face_roi, _ = detect_face(img_file)
                    if face_roi is not None:
                        df = load_data()
                        if system_id in df['SystemID'].values:
                            st.error(f"⚠️ System ID {system_id} is already taken!")
                        else:
                            new_data = {
                                "SystemID": system_id, "Name": name, "Role": role, "Gender": gender,
                                "Mobile": mobile, "Address": address,
                                "GuardianName": guardian_name if role == "Student" else "N/A",
                                "Class": student_class if role == "Student" else "N/A",
                                "BloodGroup": blood_group if role == "Student" else "N/A",
                                "OfficialID": official_id,
                                "Subject": subject if role == "Teacher" else "N/A",
                                "LastAttendance": "Never"
                            }
                            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                            save_data(df)
                            if os.path.exists(TRAINER_FILE): recognizer.read(TRAINER_FILE)
                            recognizer.update([face_roi], np.array([system_id]))
                            recognizer.write(TRAINER_FILE)
                            st.balloons()
                            st.success(f"✅ Registered {name}")
                            st.session_state.reg_camera_active = False
                            st.rerun()
                    else:
                        st.error("⚠️ No face detected.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("⚠️ Fill Name, ID & Photo.")
    else:
        st.warning("🔒 This section is protected. Enter Admin Password in Sidebar.")

# ==========================================
# TAB 2: ATTENDANCE (OPEN)
# ==========================================
with tab2:
    st.header("Mark Attendance")
    if 'att_camera_active' not in st.session_state: st.session_state.att_camera_active = False

    col_att1, col_att2 = st.columns(2)
    with col_att1:
        if st.button("🔴 Stop Camera" if st.session_state.att_camera_active else "📷 Start Camera", key="att_cam_toggle"):
            st.session_state.att_camera_active = not st.session_state.att_camera_active
            st.rerun()
    with col_att2:
        if st.session_state.att_camera_active:
            if st.button("🔄 Switch Camera", key="att_cam_switch"):
                st.session_state.att_camera_active = False
                st.rerun()

    if st.session_state.att_camera_active:
        attendance_cam = st.camera_input("Scan Face", key="attendance_cam", label_visibility="collapsed")
        if attendance_cam:
            if os.path.exists(TRAINER_FILE):
                try:
                    recognizer.read(TRAINER_FILE)
                    face_roi, _ = detect_face(attendance_cam)
                    if face_roi is not None:
                        id_predicted, confidence = recognizer.predict(face_roi)
                        if confidence < 75:
                            df = load_data()
                            user = df[df['SystemID'] == id_predicted]
                            if not user.empty:
                                name_found = user.iloc[0]['Name']
                                role_found = user.iloc[0]['Role']
                                df.loc[df['SystemID'] == id_predicted, 'LastAttendance'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                save_data(df)
                                st.balloons()
                                st.success(f"✅ Marked: {name_found}")
                            else:
                                st.warning("ID found but no data.")
                        else:
                            st.error("❌ Face not matched.")
                    else:
                        st.warning("⚠️ No face detected.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("⚠️ Database empty.")

# ==========================================
# TAB 3: ANALYTICS (UNLOCKED + PDF REPORT)
# ==========================================
with tab3:
    st.header("Gurukulam Analytics (Public View)")
    
    df = load_data()
    
    if not df.empty:
        # 1. METRICS
        total = len(df)
        students = len(df[df['Role'] == 'Student'])
        teachers = len(df[df['Role'] == 'Teacher'])
        staff = len(df[df['Role'] == 'Staff'])
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", total)
        m2.metric("Students", students)
        m3.metric("Teachers", teachers)
        m4.metric("Staff", staff)
        
        st.markdown("### 📋 Database Records")
        st.dataframe(df)
        
    else:
        st.info("No data available yet.")
