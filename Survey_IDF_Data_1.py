# ✅ Survey_IDF_Data_1.py
import streamlit as st
import pandas as pd
from datetime import datetime
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
GOOGLE_SHEET_ID = '1UGrGEtWy5coI7nduIY8J8Vjh9S0Ahej7ekDG_4nl-SQ'
DRIVE_FOLDER_ID = '1l6N7Gfd8T1V8t3hR2OuLn5CDtBuzjsKu'
CREDENTIALS_FILE = 'credentials.json'

# --- GOOGLE AUTH ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

gauth = GoogleAuth()
gauth.DEFAULT_SETTINGS['client_config_file'] = CREDENTIALS_FILE
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# --- Load CSV ---
df = pd.read_csv("IDF_ACCT_ID.csv")

st.title("Supervisor Field Survey – IDF Cases")
st.caption("Please fill this form after on-site verification of IDF accounts.")

acct_id_input = st.text_input("**ENTER ACCT_ID**", max_chars=10)
if acct_id_input and not acct_id_input.isdigit():
    st.error("❌ ACCT_ID should be numeric only.")

if acct_id_input:
    match = df[df["ACCT_ID"].astype(str) == acct_id_input.strip()]
    if not match.empty:
        st.success("✅ ACCT_ID matched. Details below:")
        fields = {
            "ZONE": match.iloc[0]["ZONE"],
            "CIRCLE": match.iloc[0]["CIRCLE"],
            "DIVISION": match.iloc[0]["DIVISION"],
            "SUB-DIVISION": match.iloc[0]["SUB-DIVISION"]
        }

        cols = st.columns(len(fields))
        for col, (label, value) in zip(cols, fields.items()):
            col.markdown(f"<b>{label}:</b><br>{value}", unsafe_allow_html=True)

        st.markdown("---")

        remark_options = {
            "OK": ["METER SERIAL NUMBER", "METER IMAGE", "READING", "DEMAND"],
            "DEFECTIVE METER": ["METER SERIAL NUMBER", "METER IMAGE"],
            "NO METER AT SITE": ["PREMISES IMAGE"],
            "PDC": ["METER IMAGE", "PREMISES IMAGE", "DOCUMENT RELATED TO PDC"]
        }

        selected_remark = st.selectbox("Select REMARK", [""] + list(remark_options.keys()))

        if selected_remark:
            mobile_no = st.text_input("Enter Consumer Mobile Number (10 digits)", max_chars=10)
            input_data = {}
            uploaded_images = {}

            for field in remark_options[selected_remark]:
                if "IMAGE" in field or "DOCUMENT" in field:
                    uploaded = st.file_uploader(f"Upload {field}", type=["jpg", "jpeg", "png"], key=field)
                    if uploaded:
                        uploaded_images[field] = uploaded
                else:
                    value = st.text_input(field)
                    input_data[field.replace(" ", "_").upper()] = value

            if st.button("✅ Submit"):
                uploaded_links = {}
                for field, file_data in uploaded_images.items():
                    filename = f"{acct_id_input}_{field.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                    file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': DRIVE_FOLDER_ID}]})
                    file_drive.SetContentString(file_data.read().decode("ISO-8859-1"))
                    file_drive.Upload()
                    uploaded_links[field] = file_drive['alternateLink']

                row = [
                    acct_id_input,
                    selected_remark,
                    fields["ZONE"],
                    fields["CIRCLE"],
                    fields["DIVISION"],
                    fields["SUB-DIVISION"],
                    mobile_no,
                    "",
                    input_data.get("METER_SERIAL_NUMBER", ""),
                    input_data.get("READING", ""),
                    input_data.get("DEMAND", ""),
                    uploaded_links.get("METER IMAGE", ""),
                    uploaded_links.get("PREMISES IMAGE", ""),
                    uploaded_links.get("DOCUMENT RELATED TO PDC", "")
                ]
                sheet.append_row(row)
                st.success("🎉 Data saved successfully to Google Sheet & Drive!")
    else:
        st.error("❌ ACCT_ID not found. Please try again.")
