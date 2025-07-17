# dropbox_utils.py
import streamlit as st
import dropbox
from dropbox.exceptions import AuthError, ApiError
from io import BytesIO
import pandas as pd

def get_dropbox_client():
    """Initializes and returns the Dropbox client."""
    try:
        dbx_token = st.secrets["dropbox_api_token"]
        if not dbx_token:
            st.error("Dropbox API token not found in Streamlit secrets.")
            return None
        dbx = dropbox.Dropbox(dbx_token)
        # Test the connection
        dbx.users_get_current_account()
        return dbx
    except AuthError:
        st.error("Authentication Error: Invalid Dropbox API token.")
        return None
    except Exception as e:
        st.error(f"Failed to connect to Dropbox: {e}")
        return None

def upload_file(dbx, file_content, dropbox_path):
    """Uploads a file to a specific path in Dropbox."""
    try:
        dbx.files_upload(file_content, dropbox_path, mode=dropbox.files.WriteMode('overwrite'))
        return True
    except ApiError as e:
        st.error(f"Dropbox API error during upload: {e}")
        return False

def download_file(dbx, dropbox_path):
    """Downloads a file from a specific path in Dropbox."""
    try:
        _, res = dbx.files_download(path=dropbox_path)
        return res.content
    except ApiError as e:
        st.error(f"Dropbox API error during download: {e}")
        return None

def read_from_spreadsheet(dbx, dropbox_path):
    """Reads an entire sheet from an Excel file in Dropbox into a pandas DataFrame."""
    file_content = download_file(dbx, dropbox_path)
    if file_content:
        try:
            return pd.read_excel(BytesIO(file_content))
        except Exception as e:
            st.error(f"Error reading Excel file from Dropbox: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def update_spreadsheet_from_df(dbx, df_to_write, dropbox_path):
    """Updates a sheet in an Excel file in Dropbox with data from a pandas DataFrame."""
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_to_write.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()
        return upload_file(dbx, processed_data, dropbox_path)
    except Exception as e:
        st.error(f"Error writing to Excel file for Dropbox upload: {e}")
        return False

def create_folder(dbx, folder_path):
    """Creates a folder in Dropbox if it doesn't already exist."""
    try:
        dbx.files_create_folder_v2(folder_path)
    except ApiError as e:
        if e.error.is_path() and e.error.get_path().is_conflict():
            # Folder already exists
            pass
        else:
            st.error(f"Dropbox API error during folder creation: {e}")

def list_files(dbx, folder_path):
    """Lists all files in a specific folder in Dropbox."""
    try:
        res = dbx.files_list_folder(folder_path)
        return [entry.name for entry in res.entries]
    except ApiError as e:
        st.error(f"Dropbox API error while listing files: {e}")
        return []
