import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import io

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread

# --- Constants ---
GOOGLE_SHEET_ID = '1UGrGEtWy5coI7nduIY8J8Vjh9S0Ahej7ekDG_4nl-SQ'
DRIVE_FOLDER_ID = '1l6N7Gfd8T1V8t3hR2OuLn5CDtBuzjsKu'

# --- Google Auth from Secrets ---
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
)

gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_key(GOOGLE_SHEET_ID).sheet1
drive_service = build("drive", "v3", credentials=creds)

# --- Load ACCT_ID File ---
df = pd.read_csv("IDF_ACCT_ID.csv")

st.title("Supervisor Field Survey – IDF Cases")
acct_id_input = st.text_input("ENTER ACCT_ID")

if acct_id_input and acct_id_input.isdigit():
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
            st.write(f"{k}: {v}")

        remarks = {
            "OK": ["METER SERIAL NUMBER", "METER IMAGE", "READING", "DEMAND"],
            "DEFECTIVE METER": ["METER SERIAL NUMBER", "METER IMAGE"],
            "NO METER AT SITE": ["PREMISES IMAGE"],
            "PDC": ["METER IMAGE", "PREMISES IMAGE", "DOCUMENT RELATED TO PDC"]
        }

        selected = st.selectbox("Select REMARK", [""] + list(remarks.keys()))
        if selected:
            mobile_no = st.text_input("Mobile Number")
            input_data = {}
            image_links = {}

            for field in remarks[selected]:
                if "IMAGE" in field or "DOCUMENT" in field:
                    img = st.file_uploader(f"Upload {field}", type=["png", "jpg", "jpeg"], key=field)
                    if img:
                        filename = f"{acct_id_input}_{field}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        media = MediaIoBaseUpload(img, mimetype="image/png")
                        uploaded = drive_service.files().create(
                            media_body=media,
                            body={'name': filename, 'parents': [DRIVE_FOLDER_ID]},
                            fields='id, webViewLink'
                        ).execute()
                        image_links[field] = uploaded.get("webViewLink")
                else:
                    input_data[field] = st.text_input(field)

            if st.button("✅ Submit"):
                row = [
                    acct_id_input,
                    selected,
                    fields["ZONE"],
                    fields["CIRCLE"],
                    fields["DIVISION"],
                    fields["SUB-DIVISION"],
                    mobile_no,
                    "",  # Required Remark Placeholder
                    input_data.get("METER SERIAL NUMBER", ""),
                    input_data.get("READING", ""),
                    input_data.get("DEMAND", ""),
                    image_links.get("METER IMAGE", ""),
                    image_links.get("PREMISES IMAGE", ""),
                    image_links.get("DOCUMENT RELATED TO PDC", "")
                ]
                sheet.append_row(row)
                st.success("✅ Submitted to Google Sheet and Drive.")
    else:
        st.error("❌ ACCT_ID not found.")
