import streamlit as st
import pandas as pd
from datetime import datetime
import io
import time
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# --- CONFIG ---
GOOGLE_SHEET_ID = '1UGrGEtWy5coI7nduIY8J8Vjh9S0Ahej7ekDG_4nl-SQ'
DRIVE_FOLDER_ID = '1l6N7Gfd8T1V8t3hR2OuLn5CDtBuzjsKu'
INPUT_CSV = 'IDF_ACCT_ID.csv'

# --- Auth from st.secrets ---
try:
    creds_dict = st.secrets["google_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
except Exception as auth_error:
    st.error(f"Authentication failed: {auth_error}")
    st.stop()

# --- Setup Clients ---
try:
    sheet_client = gspread.authorize(creds)
    sheet = sheet_client.open_by_key(GOOGLE_SHEET_ID).sheet1
    drive_service = build("drive", "v3", credentials=creds)
except Exception as client_error:
    st.error(f"Client setup failed: {client_error}")
    st.stop()

# --- Load Master CSV ---
try:
    df = pd.read_csv(INPUT_CSV)
    df["ACCT_ID"] = df["ACCT_ID"].astype(str).str.strip()
except Exception as csv_error:
    st.error(f"Failed to load CSV file: {csv_error}")
    st.stop()

# --- UI Starts ---
st.title("Supervisor Field Survey – IDF Cases")
st.caption("Please fill this form after on-site verification of IDF accounts.")

acct_id = st.text_input("*ENTER ACCT_ID*", max_chars=10).strip()

if acct_id:
    if not acct_id.isdigit():
        st.error("❌ ACCT_ID should be numeric only.")
    else:
        match = df[df["ACCT_ID"] == acct_id]
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
                            try:
                                # Verify image
                                Image.open(uploaded)
                                # Prepare upload
                                file_ext = uploaded.name.split('.')[-1].lower()
                                filename = f"{acct_id}{field.replace(' ', '')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_ext}"
                                
                                # Upload to Drive
                                media = MediaIoBaseUpload(
                                    io.BytesIO(uploaded.getvalue()),
                                    mimetype=f"image/{file_ext}" if file_ext in ['jpg', 'jpeg', 'png'] else 'application/octet-stream'
                                )
                                
                                file_metadata = {
                                    'name': filename,
                                    'parents': [DRIVE_FOLDER_ID]
                                }
                                
                                file = drive_service.files().create(
                                    media_body=media,
                                    body=file_metadata,
                                    fields='webViewLink,id'
                                ).execute()
                                
                                image_links[field] = file.get("webViewLink")
                                st.success(f"Uploaded {field} successfully!")
                                
                            except HttpError as http_err:
                                st.error(f"Google Drive API error: {http_err}")
                            except Exception as upload_err:
                                st.error(f"Upload failed: {upload_err}")
                    else:
                        val = st.text_input(field)
                        if val:
                            input_data[field.replace(" ", "_").upper()] = val.strip()

                if st.button("✅ Submit"):
                    errors = []
                    if not mobile_no or not mobile_no.isdigit() or len(mobile_no) != 10:
                        errors.append("Valid 10-digit mobile number is required.")
                    
                    for field in remark_options[selected_remark]:
                        if "IMAGE" not in field and "DOCUMENT" not in field:
                            key = field.replace(" ", "_").upper()
                            if not input_data.get(key):
                                errors.append(f"{field} is required.")
                        else:
                            if field not in image_links:
                                errors.append(f"{field} is required.")

                    if errors:
                        for e in errors:
                            st.error("❌ " + e)
                    else:
                        # Prepare data row
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
                            image_links.get("DOCUMENT RELATED TO PDC", ""),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ]

                        # Debug output
                        st.write("Data to be saved:", row)
                        
                        # Attempt to save to Google Sheets
                        try:
                            # First verify we can access the sheet
                            sheet.append_row(["Test connection"], value_input_option="RAW")
                            sheet.delete_rows(2)  # Remove test row
                            
                            # Now insert real data
                            sheet.append_row(row, value_input_option="USER_ENTERED")
                            
                            st.success("🎉 Data saved to Google Sheet successfully!")
                            st.balloons()
                            time.sleep(2)
                            st.experimental_rerun()  # Clear the form
                            
                        except HttpError as http_err:
                            st.error(f"Google Sheets API error: {http_err}")
                            st.error(f"Details: {http_err.content.decode()}")
                        except gspread.exceptions.APIError as gs_err:
                            st.error(f"Gspread error: {gs_err}")
                        except Exception as save_error:
                            st.error(f"Failed to save data: {save_error}")
