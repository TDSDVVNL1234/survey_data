import streamlit as st
import pandas as pd
from datetime import datetime
import io
from PIL import Image

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- CONFIG ---
GOOGLE_SHEET_ID = '1UGrGEtWy5coI7nduIY8J8Vjh9S0Ahej7ekDG_4nl-SQ'
DRIVE_FOLDER_ID = '1l6N7Gfd8T1V8t3hR2OuLn5CDtBuzjsKu'
INPUT_CSV = 'IDF_ACCT_ID.csv'

# --- Auth from st.secrets ---
creds_dict = st.secrets["google_service_account"]
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])

# --- Setup Clients ---
sheet_client = gspread.authorize(creds)
sheet = sheet_client.open_by_key(GOOGLE_SHEET_ID).sheet1
drive_service = build("drive", "v3", credentials=creds)

# --- Load Master CSV ---
df = pd.read_csv(INPUT_CSV)

# --- UI Starts ---
st.title("Supervisor Field Survey – IDF Cases")
st.caption("Please fill this form after on-site verification of IDF accounts.")

acct_id = st.text_input("*ENTER ACCT_ID*", max_chars=10)

if acct_id and not acct_id.isdigit():
    st.error("❌ ACCT_ID should be numeric only.")

if acct_id:
    match = df[df["ACCT_ID"].astype(str) == acct_id.strip()]
    if match.empty:
        st.error("❌ ACCT_ID not found.")
    else:
        st.success("✅ ACCT_ID matched!")
        fields = {
            "ZONE": match.iloc[0]["ZONE"],
            "CIRCLE": match.iloc[0]["CIRCLE"],
            "DIVISION": match.iloc[0]["DIVISION"],
            "SUB-DIVISION": match.iloc[0]["SUB-DIVISION"]
        }

        cols = st.columns(len(fields))
        for col, (label, value) in zip(cols, fields.items()):
            col.markdown(f"*{label}*: {value}")

        st.markdown("---")

        remark_options = {
            "OK": ["METER SERIAL NUMBER", "METER IMAGE", "READING", "DEMAND"],
            "DEFECTIVE METER": ["METER SERIAL NUMBER", "METER IMAGE"],
            "NO METER AT SITE": ["PREMISES IMAGE"],
            "PDC": ["METER IMAGE", "PREMISES IMAGE", "DOCUMENT RELATED TO PDC"]
        }

        selected_remark = st.selectbox("Select REMARK", [""] + list(remark_options.keys()))

        if selected_remark:
            mobile_no = st.text_input("Enter Consumer Mobile Number", max_chars=10)
            input_data = {}
            image_links = {}

            for field in remark_options[selected_remark]:
                if "IMAGE" in field or "DOCUMENT" in field:
                    uploaded = st.file_uploader(f"Upload {field}", type=["png", "jpg", "jpeg"], key=field)
                    if uploaded:
                        filename = f"{acct_id}{field.replace(' ', '')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                        media = MediaIoBaseUpload(uploaded, mimetype='image/png')
                        try:
                            file = drive_service.files().create(
                                media_body=media,
                                body={'name': filename, 'parents': [DRIVE_FOLDER_ID]},
                                fields='webViewLink'
                            ).execute()
                            image_links[field] = file.get("webViewLink")
                        except Exception as e:
                            st.error(f"⚠️ Failed to upload {field}: {e}")
                else:
                    val = st.text_input(field)
                    input_data[field.replace(" ", "_").upper()] = val

            if st.button("✅ Submit"):
                # --- Validation ---
                errors = []
                if not mobile_no:
                    errors.append("Mobile number is required.")
                for field in remark_options[selected_remark]:
                    if "IMAGE" not in field and "DOCUMENT" not in field:
                        key = field.replace(" ", "_").upper()
                        if not input_data.get(key):
                            errors.append(f"{field} is required.")

                if errors:
                    for e in errors:
                        st.error("❌ " + e)
                else:
                    row = [
                        acct_id,
                        selected_remark,
                        fields["ZONE"],
                        fields["CIRCLE"],
                        fields["DIVISION"],
                        fields["SUB-DIVISION"],
                        mobile_no,
                        "",  # Optional Remarks
                        input_data.get("METER_SERIAL_NUMBER", ""),
                        input_data.get("READING", ""),
                        input_data.get("DEMAND", ""),
                        image_links.get("METER IMAGE", ""),
                        image_links.get("PREMISES IMAGE", ""),
                        image_links.get("DOCUMENT RELATED TO PDC", "")
                    ]

                    # Optional debug output
                    st.write("✅ Row to be saved:", row)

                    try:
                        sheet.append_row(row)
                        st.success("🎉 Data saved to Google Sheet & images uploaded to Drive!")
                    except Exception as e:
                        st.error(f"❌ Failed to save to Google Sheet: {e}")
