import streamlit as st
import pandas as pd
from datetime import datetime
import io
from PIL import Image

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- Load Secrets ---
GOOGLE_SHEET_ID = st.secrets["GOOGLE_SHEET_ID"]
DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
creds_dict = st.secrets["google_service_account"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- Auth Google ---
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_key(GOOGLE_SHEET_ID).sheet1
drive_service = build("drive", "v3", credentials=creds)

# --- Load Master ACCT_IDs ---
df = pd.read_csv("IDF_ACCT_ID.csv")

# --- Streamlit UI ---
st.title("Supervisor Field Survey – IDF Cases")

acct_id_input = st.text_input("ENTER ACCT_ID", max_chars=10)
if acct_id_input and not acct_id_input.isdigit():
    st.error("❌ ACCT_ID should be numeric.")

if acct_id_input:
    match = df[df["ACCT_ID"].astype(str) == acct_id_input.strip()]
    if not match.empty:
        st.success("✅ ACCT_ID matched. Details below:")
        info = match.iloc[0]
        fields = {
            "ZONE": info["ZONE"],
            "CIRCLE": info["CIRCLE"],
            "DIVISION": info["DIVISION"],
            "SUB-DIVISION": info["SUB-DIVISION"]
        }

        cols = st.columns(len(fields))
        for col, (k, v) in zip(cols, fields.items()):
            col.markdown(f"**{k}**: {v}")

        st.markdown("---")

        remark_options = {
            "OK": ["METER SERIAL NUMBER", "METER IMAGE", "READING", "DEMAND"],
            "DEFECTIVE METER": ["METER SERIAL NUMBER", "METER IMAGE"],
            "NO METER AT SITE": ["PREMISES IMAGE"],
            "PDC": ["METER IMAGE", "PREMISES IMAGE", "DOCUMENT RELATED TO PDC"]
        }

        selected_remark = st.selectbox("Select REMARK", [""] + list(remark_options.keys()))

        if selected_remark:
            mobile_no = st.text_input("Consumer Mobile Number (10 digits)", max_chars=10)
            input_data = {}
            uploaded_links = {}

            for field in remark_options[selected_remark]:
                if "IMAGE" in field or "DOCUMENT" in field:
                    uploaded = st.file_uploader(f"Upload {field}", type=["png", "jpg", "jpeg"], key=field)
                    if uploaded:
                        filename = f"{acct_id_input}_{field.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        media = MediaIoBaseUpload(uploaded, mimetype='image/png')
                        uploaded_file = drive_service.files().create(
                            media_body=media,
                            body={
                                'name': filename,
                                'parents': [DRIVE_FOLDER_ID],
                                'mimeType': 'image/png'
                            },
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
                    "",  # REQUIRED_REMARK
                    input_data.get("METER_SERIAL_NUMBER", ""),
                    input_data.get("READING", ""),
                    input_data.get("DEMAND", ""),
                    uploaded_links.get("METER IMAGE", ""),
                    uploaded_links.get("PREMISES IMAGE", ""),
                    uploaded_links.get("DOCUMENT RELATED TO PDC", "")
                ]
                sheet.append_row(row)
                st.success("🎉 Data saved to Google Sheet & Drive!")
    else:
        st.error("❌ ACCT_ID not found.")
