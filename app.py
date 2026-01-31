import streamlit as st
import pandas as pd
import cv2
import numpy as np
import os
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Gurukulam Manager", page_icon="🕉️", layout="wide")

# --- FILE PATHS ---
DB_FILE = "gurukulam_data.csv"
TRAINER_FILE = "trainer.yml"

# --- INIT FACE RECOGNIZER ---
# We use LBPH (Local Binary Patterns Histograms) which is light and fast
recognizer = cv2.face.LBPHFaceRecognizer_create()
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# --- HELPER FUNCTIONS ---

def load_data():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=["ID", "Name", "Role", "LastAttendance"])
    return pd.read_csv(DB_FILE)

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def train_model(df):
    """Retrains the model using saved face data (simulated for this session)"""
    # In a real persistence scenario without storage, we have to rely on the .yml file
    # This function loads the existing trainer.yml if it exists
    if os.path.exists(TRAINER_FILE):
        recognizer.read(TRAINER_FILE)
        return True
    return False

def detect_face(image_buffer):
    """Detects face and returns the face region (ROI)"""
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
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🕉️")
    st.markdown("### Gurukulam Manager")
    st.markdown("---")
    admin_pass = st.text_input("Enter Admin Password", type="password")
    is_admin = admin_pass == "om"
    if is_admin: st.success("Admin Logged In")

# --- MAIN APP ---
st.title("🕉️ Gurukulam Upasthiti System")
tab1, tab2, tab3 = st.tabs(["📝 Registration", "📷 Face Attendance", "📊 Analytics"])

# --- TAB 1: REGISTRATION ---
with tab1:
    st.header("Register New Member")
    
    # 1. Role Selection (Determines which fields to show)
    role = st.selectbox("Select Role", ["Student", "Teacher", "Staff"])
    
    # 2. Dynamic Input Fields
    col1, col2 = st.columns(2)
    
    # --- COMMON FIELDS (Everyone has these) ---
    with col1:
        name = st.text_input("Full Name")
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        mobile = st.text_input("Mobile Number")
        
    with col2:
        # SYSTEM ID: Crucial for Face Recognition (Must be Number)
        system_id = st.number_input("System ID (Numeric Only)", min_value=1, step=1, help="Unique number for Face System")
        address = st.text_area("Address", height=100)

    st.markdown("---")
    
    # --- ROLE SPECIFIC FIELDS ---
    guardian_name = ""
    student_class = ""
    blood_group = ""
    official_id = "" # Roll No or Staff ID
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
    st.info("📷 Photo Setup (Required for Face ID)")

    # 3. CAMERA CONTROLS (Preserved from previous version)
    if 'reg_camera_active' not in st.session_state:
        st.session_state.reg_camera_active = False

    col_cam1, col_cam2 = st.columns(2)
    with col_cam1:
        # Start/Stop
        if st.button("🔴 Stop Camera" if st.session_state.reg_camera_active else "📷 Start Camera", key="reg_cam_toggle"):
            st.session_state.reg_camera_active = not st.session_state.reg_camera_active
            st.rerun()

    with col_cam2:
        # Switch Camera
        if st.session_state.reg_camera_active:
            if st.button("🔄 Switch Camera", key="reg_cam_switch"):
                st.session_state.reg_camera_active = False
                st.rerun()

    # 4. Camera Input
    img_file = None
    if st.session_state.reg_camera_active:
        img_file = st.camera_input("Take Photo", key="reg_camera", label_visibility="collapsed")

    st.markdown("---")

    # 5. SAVE LOGIC
    if st.button("💾 Save Registration", type="primary"):
        if name and system_id and img_file:
            try:
                face_roi, _ = detect_face(img_file)
                
                if face_roi is not None:
                    df = load_data()
                    
                    if system_id in df['SystemID'].values:
                        st.error(f"⚠️ System ID {system_id} is already taken! Please use a different one.")
                    else:
                        # Construct Data Row
                        new_data = {
                            "SystemID": system_id,
                            "Name": name,
                            "Role": role,
                            "Gender": gender,
                            "Mobile": mobile,
                            "Address": address,
                            "GuardianName": guardian_name if role == "Student" else "N/A",
                            "Class": student_class if role == "Student" else "N/A",
                            "BloodGroup": blood_group if role == "Student" else "N/A",
                            "OfficialID": official_id, # Stores Roll No or Staff ID
                            "Subject": subject if role == "Teacher" else "N/A",
                            "LastAttendance": "Never"
                        }
                        
                        # Save to CSV
                        new_entry = pd.DataFrame([new_data])
                        df = pd.concat([df, new_entry], ignore_index=True)
                        save_data(df)
                        
                        # Train Face Model
                        if os.path.exists(TRAINER_FILE):
                            recognizer.read(TRAINER_FILE)
                        recognizer.update([face_roi], np.array([system_id]))
                        recognizer.write(TRAINER_FILE)
                        
                        st.balloons()
                        st.success(f"✅ Registered {name} ({role})")
                        st.session_state.reg_camera_active = False
                        st.rerun()
                else:
                    st.error("⚠️ No face detected. Please ensure good lighting.")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("⚠️ Please fill in Name, System ID, and take a Photo.")
            
# --- TAB 2: ATTENDANCE ---
with tab2:
    st.header("Mark Attendance")
    
    # 1. Initialize State
    if 'camera_active' not in st.session_state:
        st.session_state.camera_active = False

    # 2. Controls
    col_cam1, col_cam2 = st.columns(2)
    
    with col_cam1:
        # Main ON/OFF Switch
        if st.button("🔴 Stop Camera" if st.session_state.camera_active else "📷 Start Camera"):
            st.session_state.camera_active = not st.session_state.camera_active
            st.rerun()

    with col_cam2:
        # "Flip" Logic: We actually just clear the key to force a reset
        if st.session_state.camera_active:
            if st.button("🔄 Switch Camera"):
                # This clears the widget, forcing the browser to ask for camera permission again
                # enabling the user to select 'Back Camera' on their phone.
                st.session_state.camera_active = False
                st.rerun()

    # 3. Camera Logic
    if st.session_state.camera_active:
        st.write("Scan Face below:")
        
        # We add a unique key based on time to ensure it reloads cleanly if needed
        attendance_cam = st.camera_input("Attendance Scanner", label_visibility="collapsed")
        
        if attendance_cam:
            if os.path.exists(TRAINER_FILE):
                try:
                    recognizer.read(TRAINER_FILE)
                    face_roi, _ = detect_face(attendance_cam)
                    
                    if face_roi is not None:
                        id_predicted, confidence = recognizer.predict(face_roi)
                        
                        if confidence < 75:  # Slightly looser tolerance for mobile cameras
                            df = load_data()
                            user = df[df['ID'] == id_predicted]
                            if not user.empty:
                                name = user.iloc[0]['Name']
                                role = user.iloc[0]['Role']
                                st.success(f"✅ Present: {name} ({role})")
                                st.balloons()
                            else:
                                st.warning(f"ID {id_predicted} found but no name attached.")
                        else:
                            st.error("❌ Face not matched.")
                    else:
                        st.warning("⚠️ Face not clear.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("⚠️ Database empty.")
    else:
        st.info("Tap 'Start Camera' to begin.")

# --- TAB 3: ANALYTICS ---
with tab3:
    if is_admin:
        st.header("Database")
       def load_data():
    # Define all possible columns we might need
    columns = [
        "SystemID", "Name", "Role", "Gender", "Mobile", "Address", 
        "GuardianName", "Class", "BloodGroup", "OfficialID", 
        "Subject", "LastAttendance"
    ]
    
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=columns)
    
    df = pd.read_csv(DB_FILE)
    
    # Safety: If the CSV exists but has old columns, add the new missing ones
    for col in columns:
        if col not in df.columns:
            df[col] = "" # Fill missing columns with empty string
            
    return df
    else:
        st.warning("Admin Access Required")
