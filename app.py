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
    
    # 1. Open the form
    with st.form("reg_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name")
        role = c1.selectbox("Role", ["Student", "Teacher", "Staff"])
        user_id = c2.number_input("ID Number", min_value=1, step=1)
        
        st.info("Take a photo to register face.")
        img_file = st.camera_input("Register Face")
        
        # 2. THIS BUTTON MUST BE INDENTED INSIDE 'with st.form'
        submit = st.form_submit_button("Save Member")

    # 3. This logic is OUTSIDE the form (Indentation moves back)
    if submit:
        if img_file and name:
            # ... your saving logic here ...
            st.success("Processing...")
        else:
            st.warning("Please enter name and take photo.")
            
# --- TAB 2: ATTENDANCE ---
with tab2:
    st.header("Mark Attendance")
    cam = st.camera_input("Scan Face", key="attendance")
    
    if cam:
        if os.path.exists(TRAINER_FILE):
            recognizer.read(TRAINER_FILE)
            face_roi, _ = detect_face(cam)
            
            if face_roi is not None:
                # Predict
                id_predicted, confidence = recognizer.predict(face_roi)
                
                # Confidence: Lower is better in OpenCV LBPH (0 = perfect match)
                # Usually < 60 is a good match
                if confidence < 70:
                    df = load_data()
                    user = df[df['ID'] == id_predicted]
                    if not user.empty:
                        name = user.iloc[0]['Name']
                        role = user.iloc[0]['Role']
                        st.balloons()
                        st.success(f"Attendance Marked: {name} ({role})")
                        st.info(f"Confidence Score: {round(100 - confidence)}%")
                    else:
                        st.warning(f"Face recognized as ID {id_predicted}, but ID not found in CSV.")
                else:
                    st.error("Face not recognized. Please register.")
            else:
                st.error("No face found in frame.")
        else:
            st.error("System has no registered faces yet.")

# --- TAB 3: ANALYTICS ---
with tab3:
    if is_admin:
        st.header("Database")
        df = load_data()
        st.dataframe(df)
    else:
        st.warning("Admin Access Required")
