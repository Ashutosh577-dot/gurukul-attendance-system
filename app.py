"""
Gurukulam Management System - Enterprise Edition
Version: FINAL FIXED (Indentation & Variable Scope Corrected)
Date: 2026-01-03
"""

import logging
import time 
import os
import io
import shutil
import qrcode
# --- STEP 1: Safe Audio Imports ---
try:
    import winsound
    import pyttsx3
    HAS_AUDIO = True
except (ImportError, ModuleNotFoundError):
    # This runs on the Cloud/Linux where sounds don't work
    HAS_AUDIO = False

# --- STEP 2: Update your Audio Class/Logic ---
# Anywhere you use winsound or pyttsx3, wrap it like this:
def play_welcome_voice(text):
    if HAS_AUDIO:
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except:
            pass
    else:
        # On the cloud, we just print the message instead of speaking it
        print(f"Audio suppressed on cloud: {text}")
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import calendar
import re
from PIL import Image
from datetime import datetime, timedelta

# External Component for Auto-Refresh logic
try:
    from streamlit_autorefresh import st_autorefresh 
except ImportError:
    st.error("Missing dependency: 'streamlit-autorefresh'. Please run: pip install streamlit-autorefresh")
    st.stop()

# ==========================================
# --- 1. SYSTEM CONFIGURATION ---
# ==========================================

logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)

class SystemConfig:
    # File System Paths
    STUDENT_DB_PATH = 'student_data.xlsx'
    TEACHER_DB_PATH = 'teacher_data.xlsx'
    STUDENT_LOG_PATH = 'attendance_log.xlsx'
    TEACHER_LOG_PATH = 'teacher_attendance.xlsx'
    SYSTEM_AUDIT_LOG_PATH = 'admin_audit_trail.txt'
    BACKUP_DIRECTORY = "Backups"
    
    # Security Credentials
    ADMINISTRATOR_PASSWORD = "gurukul@admin"
    
    # Visual Theme Settings
    THEME_PRIMARY_COLOR = "#FFD700"  # Vedic Gold
    THEME_SUCCESS = "#2ecc71"
    THEME_ERROR = "#e74c3c"
    THEME_TEXT_COLOR = "#FFFFFF"

# ==========================================
# --- 2. SESSION MANAGEMENT ---
# ==========================================

class SessionManager:
    @staticmethod
    def initialize_session():
        if "authenticated" not in st.session_state:
            st.session_state["authenticated"] = False
        if "v4_anim_done" not in st.session_state:
            st.session_state["v4_anim_done"] = False
        if "last_backup_timestamp" not in st.session_state:
            st.session_state["last_backup_timestamp"] = 0
        if "qr_buffer" not in st.session_state:
            st.session_state["qr_buffer"] = None

# ==========================================
# --- 3. STYLE & THEME LOADER ---
# ==========================================

class StyleLoader:
    @staticmethod
    def apply_custom_css():
        css = f"""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Mukta:wght@300;500;800&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@700&display=swap');
            
            /* GLOBAL THEME */
            html, body, [class*="css"] {{ font-family: 'Mukta', sans-serif; }}
            .stApp {{ background: radial-gradient(circle at center, #1f1f1f 0%, #000000 100%); color: #ffffff; }}
            
            /* HEADERS */
            h1, h2, h3 {{ color: {SystemConfig.THEME_PRIMARY_COLOR} !important; font-weight: 800; text-shadow: 0px 0px 15px rgba(255, 215, 0, 0.4); }}
            
            /* INPUT FIELDS */
            .stTextInput > div > div > input {{ background-color: rgba(255, 255, 255, 0.05); color: {SystemConfig.THEME_PRIMARY_COLOR}; border: 1px solid #444; }}
            
            /* ANIMATION CONTAINER - FORCED CENTERING */
            .intro-screen {{ 
                position: fixed !important; 
                top: 0 !important; 
                left: 0 !important; 
                width: 100vw !important; 
                height: 100vh !important; 
                background-color: #000000 !important; 
                display: flex !important; 
                flex-direction: column !important; 
                justify-content: center !important; 
                align-items: center !important;     
                z-index: 999999 !important; 
            }}
            
            .intro-logo {{ font-size: 80px; margin-bottom: 20px; animation: pulse 2s infinite; }}
            
            /* --- CURSOR BLINK ANIMATION --- */
            @keyframes blink-caret {{
                from, to {{ border-color: transparent; }}
                50% {{ border-color: #FFD700; }}
            }}

            .typewriter-line {{ 
                font-family: 'Courier Prime', monospace; 
                font-size: 26px; 
                color: #FFD700; 
                border-right: 3px solid #FFD700; /* The Cursor */
                white-space: nowrap; 
                overflow: hidden; 
                margin: 10px 0; 
                text-align: center;
                animation: blink-caret 0.75s step-end infinite; /* Makes it blink */
            }}
            
            @keyframes pulse {{ 0% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.1); opacity: 0.8; }} 100% {{ transform: scale(1); opacity: 1; }} }}
            </style>
        """
        st.markdown(css, unsafe_allow_html=True)

# ==========================================
# --- 4. AUDIO & FEEDBACK ENGINE ---
# ==========================================

class AudioFeedback:
    @staticmethod
    def play_system_sound(sound_type="success"):
        try:
            if sound_type == "success": winsound.Beep(1000, 150)
            elif sound_type == "error": winsound.Beep(400, 400)
            elif sound_type == "alert": winsound.Beep(1500, 100)
        except Exception:
            pass

# ==========================================
# --- 5. AUDIT & LOGGING ---
# ==========================================

class AuditTrail:
    @staticmethod
    def log_event(event_type, user="Admin", description=""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [USER:{user}] [EVENT:{event_type}] - {description}\n"
        try:
            with open(SystemConfig.SYSTEM_AUDIT_LOG_PATH, "a", encoding="utf-8") as log_file:
                log_file.write(log_entry)
        except IOError as e:
            pass

# ==========================================
# --- 6. DATA VALIDATION ---
# ==========================================

class DataValidator:
    @staticmethod
    def validate_mobile(mobile_number):
        if not mobile_number: return False, "Mobile number is required."
        clean_num = mobile_number.replace("-", "").replace(" ", "").replace("+91", "")
        if not clean_num.isdigit(): return False, "Mobile number must contain digits only."
        if len(clean_num) != 10: return False, "Mobile number must be exactly 10 digits."
        return True, ""

    @staticmethod
    def validate_name(name_text):
        if not name_text or len(name_text.strip()) < 3: return False, "Name is too short."
        if any(char.isdigit() for char in name_text): return False, "Name should not contain numbers."
        return True, ""

# ==========================================
# --- 7. DATABASE & FILE INTERFACE ---
# ==========================================

class DatabaseInterface:
    @staticmethod
    def check_system_integrity():
        if not os.path.exists(SystemConfig.BACKUP_DIRECTORY):
            try:
                os.makedirs(SystemConfig.BACKUP_DIRECTORY)
            except OSError: pass

        # Create basic Excel files if missing
        required_files = {
            SystemConfig.STUDENT_DB_PATH: ["Name", "Roll No", "Mobile", "Class", "Daily Rate", "Registration Date", "Status", "Guardian Name", "Blood Group"],
            SystemConfig.TEACHER_DB_PATH: ["Name", "ID No", "Mobile", "Class", "Daily Rate", "Joining Date", "Status", "Specialization", "Shift"],
            SystemConfig.STUDENT_LOG_PATH: ["Name", "ID", "Timestamp", "Status", "Date", "Verification Method"],
            SystemConfig.TEACHER_LOG_PATH: ["Name", "ID", "Timestamp", "Status", "Date", "Verification Method"],
        }
        
        for file_path, headers in required_files.items():
            if not os.path.exists(file_path):
                try:
                    df = pd.DataFrame(columns=headers)
                    df.to_excel(file_path, index=False)
                except Exception: pass

    @staticmethod
    def create_safe_backup(file_path, backup_tag):
        if os.path.exists(file_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path).replace(".xlsx", "")
            dest_path = f"{SystemConfig.BACKUP_DIRECTORY}/{backup_tag}_{filename}_{timestamp}.xlsx"
            try:
                shutil.copy(file_path, dest_path)
                return True
            except Exception: return False
        return False

    @staticmethod
    def register_new_member(role, data_packet):
        target_file = SystemConfig.STUDENT_DB_PATH if role == "Student" else SystemConfig.TEACHER_DB_PATH
        try:
            if os.path.exists(target_file):
                df = pd.read_excel(target_file)
            else:
                df = pd.DataFrame()
            
            id_column = "Roll No" if role == "Student" else "ID No"
            new_id = data_packet.get(id_column)
            
            if not df.empty and id_column in df.columns:
                existing_ids = df[id_column].astype(str).tolist()
                if str(new_id) in existing_ids:
                    return False, f"Duplicate Entry: {role} with ID {new_id} already exists."
            
            data_packet["Registration Date"] = datetime.now().strftime("%Y-%m-%d")
            data_packet["Status"] = "Active"
            
            new_entry = pd.DataFrame([data_packet])
            df = pd.concat([df, new_entry], ignore_index=True)
            df.to_excel(target_file, index=False)
            
            AuditTrail.log_event("REGISTER_SUCCESS", description=f"Added {role}: {data_packet['Name']}")
            return True, "Registration completed successfully."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_live_feed_excel(file_path):
        if os.path.exists(file_path):
            try:
                df = pd.read_excel(file_path)
                return df.tail(50).iloc[::-1]
            except:
                return pd.DataFrame()
        return pd.DataFrame()

# ==========================================
# --- 8. VISUALIZATION & ANALYTICS ---
# ==========================================

class VisualizationEngine:
    @staticmethod
    def plot_attendance_donut(present_count, absent_count, title_text):
        labels = ['Present', 'Absent']
        values = [present_count, absent_count]
        colors = [SystemConfig.THEME_SUCCESS, SystemConfig.THEME_ERROR]

        fig = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=.65,
            marker=dict(colors=colors, line=dict(color='#000000', width=3)),
            textinfo='percent+label', textfont_size=14
        )])

        fig.update_layout(
            title_text=title_text, title_x=0.5, title_font_color=SystemConfig.THEME_TEXT_COLOR,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'), showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
            margin=dict(t=50, b=20, l=20, r=20), height=350
        )
        return fig

    @staticmethod
    def plot_school_operations(days_open, days_closed, month_name):
        labels = ['Days Operated', 'Days Closed/Holiday']
        values = [days_open, days_closed]
        colors = ["#3498db", "#95a5a6"] 

        fig = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=.5,
            marker=dict(colors=colors, line=dict(color='#ffffff', width=2)),
            textinfo='value+label'
        )])

        fig.update_layout(
            title_text=f"Operations: {month_name}", 
            title_x=0.5, title_font_color="#FFFFFF",
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'), showlegend=False,
            margin=dict(t=40, b=10, l=10, r=10), height=250
        )
        return fig

# ==========================================
# --- 9. BACKGROUND AUTOMATION ---
# ==========================================

class AutomationDaemon:
    @staticmethod
    def run_silent_backup_routine():
        BACKUP_INTERVAL_SECONDS = 86400 # 24 Hours
        current_time = time.time()
        last_run = st.session_state.get("last_backup_timestamp", 0)
        
        if (current_time - last_run) > 60:
            flag_file = os.path.join(SystemConfig.BACKUP_DIRECTORY, "last_backup.flag")
            should_backup = True
            
            if os.path.exists(flag_file):
                file_mod_time = os.path.getmtime(flag_file)
                if (current_time - file_mod_time) < BACKUP_INTERVAL_SECONDS:
                    should_backup = False
            
            if should_backup:
                s1 = DatabaseInterface.create_safe_backup(SystemConfig.STUDENT_LOG_PATH, "AUTO_STUD")
                s2 = DatabaseInterface.create_safe_backup(SystemConfig.TEACHER_LOG_PATH, "AUTO_TEACH")
                with open(flag_file, 'w') as f: f.write(str(current_time))
                st.session_state["last_backup_timestamp"] = current_time

# ==========================================
# --- 10. UI COMPONENT MANAGERS ---
# ==========================================

class CinematicIntro:
    @staticmethod
    def run():
        if st.session_state.get("v4_anim_done", False):
            return 

        intro_holder = st.empty()
        
        sequence = [
           "श्री हुलास ब्रम्ह बाबा संस्कृत वेद गुरूकुलम में आपका स्वागत है।",
            "Initializing Gurukulam OS...", 
            "Loading Biometric Databases...", 
            "Establishing Secure Link...", 
            "Access Granted.", 
            "सुस्वागतम ! अमित प्रताप उपाध्याय जी..."
        ]

        for line in sequence:
            current_text = ""
            for char in line:
                current_text += char
                intro_holder.markdown(
                    f"""
                    <div class="intro-screen">
                        <div class="intro-logo">🏛️</div>
                        <div class="typewriter-line">{current_text}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                time.sleep(0.06) 
            
            time.sleep(1.2) 

        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.say("System Ready. Welcome Admin.")
            engine.runAndWait()
        except: pass
        
        intro_holder.empty()
        st.session_state["v4_anim_done"] = True

class AuthScreen:
    @staticmethod
    def show():
        if not st.session_state["authenticated"]:
            c_mid = st.columns([1, 2, 1])[1]
            with c_mid:
                st.markdown("## 🔐 Secure Administration Portal")
                with st.form("login_form"):
                    password_input = st.text_input("Enter Password", type="password", key="login_pass")
                    login_submitted = st.form_submit_button("Authenticate Access")
                    
                    if login_submitted:
                        if password_input == SystemConfig.ADMINISTRATOR_PASSWORD:
                            st.session_state["authenticated"] = True
                            AudioFeedback.play_system_sound("success")
                            st.rerun()
                        else:
                            st.error("ACCESS DENIED")
                            AudioFeedback.play_system_sound("error")
            st.stop()

# ==========================================
# --- 11. MAIN APP LOGIC ---
# ==========================================

def main_application():
    st.set_page_config(page_title="श्री हुलास ब्रम्ह बाबा संस्कृत वेद गुरूकुलम", page_icon="🏛️", layout="wide", initial_sidebar_state="collapsed")
    
    SessionManager.initialize_session()
    StyleLoader.apply_custom_css()
    DatabaseInterface.check_system_integrity()
    st_autorefresh(interval=30000, key="global_refresh")
    AutomationDaemon.run_silent_backup_routine()
    
    CinematicIntro.run()
    AuthScreen.show()
    
    col_h1, col_h2 = st.columns([6, 1])
    with col_h1:
        st.markdown("# 🏛️ श्री हुलास ब्रम्ह बाबा संस्कृत वेद गुरूकुलम")
        st.caption(f"Status: ONLINE (Excel-Core) | Date: {datetime.now().strftime('%A, %d %B %Y')}")
    with col_h2:
        if st.button("🔒 LOGOUT", type="secondary"):
            st.session_state["authenticated"] = False
            st.rerun()
            
    st.markdown("---")

    tabs = st.tabs(["➕ Registration", "🖨️ ID Card Gen", "📡 Live Monitor", "📈 Analytics", "🗓️ Cumulative Logs"])
    
    # =========================================
    # TAB 1: REGISTRATION (INTEGRATED SPECIFIC LOGIC)
    # =========================================
    with tabs[0]:
        st.subheader("📝 New Member Registration Portal")
        
        reg_tab_s, reg_tab_t = st.tabs(["👨‍🎓 Register Student", "👨‍🏫 Register Teacher"])
        
        # --- SUB-TAB: STUDENT (YOUR SPECIFIC CODE) ---
        with reg_tab_s:
            with st.form("reg_student_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    s_name = st.text_input("Student Name *", placeholder="e.g. Ram Upadhyay")
                    s_mob = st.text_input("Mobile Number *", placeholder="10-digit Mobile Number")
                    s_guardian = st.text_input("Guardian Name *", placeholder="Father/Mother Name")
                with c2:
                    s_id = st.text_input("Roll Number *", placeholder="Unique Roll No")
                    s_class = st.text_input("Class / Standard *", placeholder="e.g. Prathama")
                
                if st.form_submit_button("✅ SAVE STUDENT"):
                    if not s_name or not s_id:
                        st.error("Name, Roll Number, Class and Mobile Number are required.")
                    else:
                        packet = {"Name": s_name, "Mobile": s_mob, "Roll No": s_id, "Class": s_class, "Guardian Name": s_guardian}
                        success, msg = DatabaseInterface.register_new_member("Student", packet)
                        if success: st.success(msg); AudioFeedback.play_system_sound("success")
                        else: st.error(msg); AudioFeedback.play_system_sound("error")

        # --- SUB-TAB: TEACHER ---
        with reg_tab_t:
            with st.form("reg_teacher_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    t_name = st.text_input("Teacher Name *", placeholder="e.g. Acharya Ji")
                    t_mob = st.text_input("Mobile *", placeholder="10-digit")
                    t_spec = st.text_input("Specialization", placeholder="e.g. Veda")
                with c2:
                    t_id = st.text_input("Teacher ID *", placeholder="Unique Staff ID")
                    t_dept = st.text_input("Department *", placeholder="e.g. Vyakaran")
                    t_rate = st.number_input("Daily Rate (₹)", min_value=0, step=100)
                
                if st.form_submit_button("✅ SAVE TEACHER"):
                    if not t_name or not t_id:
                        st.error("Name and ID are required.")
                    else:
                        packet = {"Name": t_name, "Mobile": t_mob, "ID No": t_id, "Class": t_dept, "Specialization": t_spec, "Daily Rate": t_rate}
                        success, msg = DatabaseInterface.register_new_member("Teacher", packet)
                        if success: st.success(msg); AudioFeedback.play_system_sound("success")
                        else: st.error(msg); AudioFeedback.play_system_sound("error")

    # =========================================
    # TAB 2: QR GENERATOR (FIXED INDENTATION & LOGIC)
    # =========================================
    with tabs[1]:
        st.subheader("🖨️ Identity Card QR Generation")
        qr_c1, qr_c2 = st.columns([1, 2])
        with qr_c1:
            # 1. Selection & File Reading (Outside Form to allow instant updates)
            q_role = st.selectbox("Select Category", ["Student", "Teacher"], key="qr_role_sel")
            target_db = SystemConfig.STUDENT_DB_PATH if q_role == "Student" else SystemConfig.TEACHER_DB_PATH
            
            # Initialize variables to prevent "not defined" errors
            name_list = ["Select..."]
            df_qr = pd.DataFrame()

            if os.path.exists(target_db):
                try:
                    df_qr = pd.read_excel(target_db)
                    
                    # Fix Column Names
                    if 'Name' not in df_qr.columns:
                        for col in df_qr.columns:
                            if "name" in str(col).lower():
                                df_qr.rename(columns={col: 'Name'}, inplace=True)
                                break
                    
                    # Prepare list
                    if not df_qr.empty and 'Name' in df_qr.columns:
                        df_qr['Name'] = df_qr['Name'].astype(str).str.strip()
                        name_list = ["Select..."] + df_qr['Name'].tolist()
                except Exception as e:
                    st.error(f"Error reading file: {e}")

            # 2. Form for Generation (Enter Key Support)
            with st.form("qr_gen_form"):
                q_name = st.selectbox("Search Name", name_list)
                
                generate_clicked = st.form_submit_button("⚡ GENERATE CODE")

                if generate_clicked:
                    if q_name != "Select..." and not df_qr.empty:
                        try:
                            user_row = df_qr[df_qr['Name'] == q_name].iloc[0]
                            detail_info = user_row.get('Class', user_row.get('Detail', 'N/A'))
                            
                            payload = f"{q_name},{detail_info}"
                            qr = qrcode.QRCode(box_size=10, border=4)
                            qr.add_data(payload)
                            qr.make(fit=True)
                            img = qr.make_image(fill_color="black", back_color="white")
                            buf = io.BytesIO()
                            img.save(buf)
                            st.session_state["qr_buffer"] = buf.getvalue()
                            st.session_state["qr_user"] = q_name
                        except Exception as e:
                            st.error(f"Generation Error: {e}")
                    else:
                        st.warning("Please select a valid member.")

        with qr_c2:
            if st.session_state["qr_buffer"]:
                st.markdown(f"#### Preview: {st.session_state.get('qr_user', '')}")
                st.image(st.session_state["qr_buffer"], width=250)
                st.download_button("📥 Download PNG", st.session_state["qr_buffer"], file_name="qr_code.png", mime="image/png")

    # =========================================
    # TAB 3: LIVE MONITOR (NO SQLITE)
    # =========================================
    with tabs[2]:
        st.subheader("📡 Real-Time Surveillance Feed (Excel Stream)")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown("### 👨‍🎓 Student Log")
            df_live_s = DatabaseInterface.get_live_feed_excel(SystemConfig.STUDENT_LOG_PATH)
            if not df_live_s.empty: 
                st.dataframe(df_live_s, height=400, use_container_width=True)
            else: st.info("Waiting for scans... (Check attendance_log.xlsx)")
        with m_col2:
            st.markdown("### 👨‍🏫 Teacher Log")
            df_live_t = DatabaseInterface.get_live_feed_excel(SystemConfig.TEACHER_LOG_PATH)
            if not df_live_t.empty: 
                st.dataframe(df_live_t, height=400, use_container_width=True)
            else: st.info("Waiting for scans... (Check teacher_attendance.xlsx)")

    # =========================================
    # TAB 4: ANALYTICS (CRASH PROOF)
    # =========================================
    with tabs[3]:
        st.subheader("📈 Performance Analytics")
        ana_t1, ana_t2 = st.tabs(["Student Insights", "Teacher Insights"])
        
        def render_analytics(role_label, db_path, log_path, id_key):
            if os.path.exists(db_path) and os.path.exists(log_path):
                try:
                    df_master = pd.read_excel(db_path)
                    df_logs = pd.read_excel(log_path)
                except Exception as e:
                    st.error(f"Error reading {role_label} files: {e}")
                    return

                # --- 1. SMART COLUMN FIXING ---
                if 'Name' not in df_master.columns:
                    col_found = False
                    for col in df_master.columns:
                        if "name" in str(col).lower():
                            df_master.rename(columns={col: 'Name'}, inplace=True)
                            col_found = True
                            break
                    if not col_found:
                        st.error(f"⚠️ Data Error: '{os.path.basename(db_path)}' is missing a 'Name' column.")
                        return 

                if not df_logs.empty and 'Name' not in df_logs.columns:
                    for col in df_logs.columns:
                        if "name" in str(col).lower():
                            df_logs.rename(columns={col: 'Name'}, inplace=True)
                            break
                
                # --- 2. AUTO-CLEAN NAMES ---
                df_master['Name'] = df_master['Name'].astype(str).str.strip()
                if not df_logs.empty and 'Name' in df_logs.columns:
                    df_logs['Name'] = df_logs['Name'].astype(str).str.strip()

                # --- 3. STRICT MERGE & CALCULATION ---
                total_reg = len(df_master)
                today_str = datetime.now().strftime('%Y-%m-%d')
                
                valid_names = df_master['Name'].unique().tolist()
                
                if not df_logs.empty and 'Date' in df_logs.columns:
                    df_logs['Date'] = df_logs['Date'].astype(str)
                    present_today = len(df_logs[
                        (df_logs['Date'] == today_str) & 
                        (df_logs['Name'].isin(valid_names))
                    ]['Name'].unique())
                else:
                    present_today = 0
                
                absent_today = max(0, total_reg - present_today)
                
                # UI Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric(f"Total {role_label}s", total_reg)
                m2.metric("Present Today", present_today)
                m3.metric("Absent Today", absent_today, delta_color="inverse")
                
                st.markdown("---")
                
                # Visuals
                c1, c2 = st.columns([1, 2])
                with c1:
                    fig = VisualizationEngine.plot_attendance_donut(present_today, absent_today, f"{role_label} Attendance")
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.markdown(f"#### {role_label} Attendance Leaderboard")
                    if not df_logs.empty:
                        counts = df_logs.groupby('Name').size().reset_index(name='Total Days')
                        merged = pd.merge(df_master, counts, on='Name', how='left').fillna(0)
                        
                        actual_id_col = id_key
                        if id_key not in merged.columns:
                            possible = [c for c in merged.columns if "Roll" in c or "ID" in c]
                            actual_id_col = possible[0] if possible else "ID"
                            if actual_id_col == "ID" and "ID" not in merged.columns: merged["ID"] = "N/A"

                        actual_class_col = "Class" if "Class" in merged.columns else "Detail" if "Detail" in merged.columns else None
                        
                        show_cols = ['Name', actual_id_col, 'Total Days']
                        if actual_class_col: show_cols.insert(2, actual_class_col)
                        
                        merged['Total Days'] = merged['Total Days'].astype(int)
                        merged = merged.sort_values(by='Total Days', ascending=True)
                        
                        st.dataframe(merged[show_cols], use_container_width=True, height=300)
            else:
                st.error(f"Excel files for {role_label} not found.")

        with ana_t1: render_analytics("Student", SystemConfig.STUDENT_DB_PATH, SystemConfig.STUDENT_LOG_PATH, "Roll No")
        with ana_t2: render_analytics("Teacher", SystemConfig.TEACHER_DB_PATH, SystemConfig.TEACHER_LOG_PATH, "ID No")

    # =========================================
    # TAB 5: SCHOOL OPERATIONS (EXCEL ONLY)
    # =========================================
    with tabs[4]:
        st.subheader("🗓️ Cumulative School Operations")
        log_files = [SystemConfig.STUDENT_LOG_PATH, SystemConfig.TEACHER_LOG_PATH]
        operational_dates = set()
        
        for file in log_files:
            if os.path.exists(file):
                try:
                    df_temp = pd.read_excel(file)
                    if 'Date' in df_temp.columns:
                        dates = df_temp['Date'].dropna().astype(str).unique().tolist()
                        operational_dates.update(dates)
                except: continue

        if operational_dates:
            valid_dt = []
            for d in operational_dates:
                try:
                    if re.match(r'\d{4}-\d{2}-\d{2}', d):
                        valid_dt.append(datetime.strptime(d, '%Y-%m-%d'))
                except: continue
            
            curr_year = datetime.now().year
            curr_month = datetime.now().month
            year_days = len([d for d in valid_dt if d.year == curr_year])
            month_days = len([d for d in valid_dt if d.year == curr_year and d.month == curr_month])
            
            _, total_month_days = calendar.monthrange(curr_year, curr_month)
            closed_days = total_month_days - month_days
            month_name = calendar.month_name[curr_month]
            
            c1, c2 = st.columns(2)
            c1.metric(f"Operational Days ({curr_year})", year_days)
            c2.metric(f"Days Open this Month", month_days)
            
            st.markdown("---")
            if hasattr(VisualizationEngine, 'plot_school_operations'):
                fig_ops = VisualizationEngine.plot_school_operations(month_days, closed_days, month_name)
                st.plotly_chart(fig_ops, use_container_width=True)
        else:
            st.info("No attendance recorded yet.")

if __name__ == "__main__":

    main_application()
