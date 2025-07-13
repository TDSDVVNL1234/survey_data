import streamlit as st
import pandas as pd
from datetime import datetime
import io
from PIL import Image

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json

# --- Config ---
GOOGLE_SHEET_ID = '1UGrGEtWy5coI7nduIY8J8Vjh9S0Ahej7ekDG_4nl-SQ'
DRIVE_FOLDER_ID = '1l6N7Gfd8T1V8t3hR2OuLn5CDtBuzjsKu'

# --- Auth from st.secrets ---
credentials_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)

# Google Drive API
drive_service = build('drive', 'v3', credentials=creds)

# Google Sheet API
gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_key(GOOGLE_SHEET_ID).sheet1

# Local CSV for ACCT_ID validation
df = pd.read_csv('IDF_ACCT_ID.csv')

# --- UI ---
st.title("Supervisor Field Survey – IDF Cases")

acct_id_input = st.text_input("Enter ACCT_ID", max_chars=10)
if acct_id_input and not acct_id_input.isdigit():
    st.error("❌ ACCT_ID should be numeric only.")

if acct_id_input:
    match = df[df["ACCT_ID"].astype(str) == acct_id_input.strip()]
    if not match.empty:
        st.success("✅ ACCT_ID matched.")
        fields = {
            "ZONE": match.iloc[0]["ZONE"],
            "CIRCLE": match.iloc[0]["CIRCLE"],
            "DIVISION": match.iloc[0]["DIVISION"],
            "SUB-DIVISION": match.iloc[0]["SUB-DIVISION"]
        }

        for k, v in fields.items():
            st.write(f"**{k}**: {v}")

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
            uploaded_links = {}

            for field in remark_options[selected_remark]:
                if "IMAGE" in field or "DOCUMENT" in field:
                    image = st.file_uploader(f"Upload {field}", type=["png", "jpg", "jpeg"], key=field)
                    if image:
                        filename = f"{acct_id_input}_{field.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        media = MediaIoBaseUpload(image, mimetype='image/png')
                        uploaded_file = drive_service.files().create(
                            media_body=media,
                            body={'name': filename, 'parents': [DRIVE_FOLDER_ID]},
                            fields='id, webViewLink'
                        ).execute()
                        uploaded_links[field] = uploaded_file.get("webViewLink")
                else:
                    value = st.text_input(field)
                    input_data[field.replace(" ", "_").upper()] = value

            if st.button("✅ Submit"):
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
                st.success("🎉 Data saved successfully!")
    else:
        st.error("❌ ACCT_ID not found.")
