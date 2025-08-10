# dropbox_utils.py
import streamlit as st
import dropbox
import time
from datetime import datetime
from dropbox.exceptions import AuthError, ApiError
from io import BytesIO
import pandas as pd
# Import the new config variable
# Import config variables, including LOG_FILE_PATH
from config import (
    DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN, LOG_FILE_PATH
)

def log_activity(dbx, username, role):
    """
    Appends a new login activity record to the log file in Dropbox.
    This function reads the existing file, adds a row, and re-uploads it.
    """
    if not dbx:
        st.warning("Dropbox client is not available. Skipping activity logging.")
        return False

    log_columns = ['Timestamp', 'Username', 'Role']
    
    # Read existing log data from the path specified in config
    df_logs = read_from_spreadsheet(dbx, LOG_FILE_PATH)

    # If the file is empty or has wrong columns, create a new DataFrame in memory
    if df_logs.empty or list(df_logs.columns) != log_columns:
        df_logs = pd.DataFrame(columns=log_columns)

    # Append the new log entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_log_entry = pd.DataFrame([{'Timestamp': timestamp, 'Username': username, 'Role': role}])
    df_logs = pd.concat([df_logs, new_log_entry], ignore_index=True)

    # Upload the updated DataFrame back to Dropbox
    if update_spreadsheet_from_df(dbx, df_logs, LOG_FILE_PATH):
        return True
    else:
        st.error("Failed to update the log file in Dropbox.")
        return False
def get_dropbox_client():
    """Initializes and returns the Dropbox client using a refresh token."""
    try:
        # Check if the secrets have been loaded into the config variables
        if not all([DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN]):
            st.error("Dropbox credentials are not found in Streamlit secrets.")
            return None

        # Initialize the client with the app key, secret, and refresh token
        # The SDK will handle refreshing the access token automatically
        dbx = dropbox.Dropbox(
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
        )
        # Test the connection by getting the current user's account info
        dbx.users_get_current_account()
        return dbx
        
    except AuthError as e:
        st.error(f"Authentication Error: Please check your Dropbox credentials. Details: {e}")
        return None
    except Exception as e:
        st.error(f"Failed to connect to Dropbox: {e}")
        return None
        
def get_shareable_link(dbx, dropbox_path):
    """Gets a shareable link for a file, creating one if it doesn't exist."""
    try:
        links = dbx.sharing_list_shared_links(path=dropbox_path, direct_only=True).links
        if links:
            return links[0].url
        else:
            settings = dropbox.sharing.SharedLinkSettings(requested_visibility=dropbox.sharing.RequestedVisibility.public)
            link = dbx.sharing_create_shared_link_with_settings(dropbox_path, settings=settings)
            return link.url
    except ApiError as e:
        # If a link already exists but is not direct_only, this will fail. We can try getting any link.
        try:
            links = dbx.sharing_list_shared_links(path=dropbox_path).links
            if links:
                return links[0].url
        except ApiError:
            pass # Fall through to error if all attempts fail
        print(f"Dropbox API error getting shareable link for {dropbox_path}: {e}")
        return None # Return None if a link can't be fetched or created
        
# def upload_file(dbx, file_content, dropbox_path):
#     """Uploads a file to a specific path in Dropbox."""
#     try:
#         dbx.files_upload(file_content, dropbox_path, mode=dropbox.files.WriteMode('overwrite'))
#         st.write("Uploading the sheet to db")
#         return True
#     except ApiError as e:
#         st.error(f"Dropbox API error during upload: {e}")
#         return False
def upload_file(dbx, file_content, dropbox_path):
    """Try different methods to keep same filename"""
    import time
    
    file_size_mb = len(file_content) / (1024 * 1024)
    st.write(f"📊 Uploading {file_size_mb:.2f}MB...")
    
    start_time = time.time()
    
    # Method 1: Try update mode (updates existing file)
    try:
        st.write("🔄 Trying update mode...")
        dbx.files_upload(
            file_content, 
            dropbox_path,
            mode=dropbox.files.WriteMode.update(rev="latest")
        )
        
        upload_time = time.time() - start_time
        st.success(f"✅ Update mode worked in {upload_time:.1f}s")
        return True
        
    except Exception as e:
        st.write(f"⚠️ Update mode failed: {e}")
    
    # Method 2: Fallback to temp-then-move
    st.write("🔄 Using temp-then-move method...")
    
    temp_path = dropbox_path.replace('.xlsx', f'_temp_{int(time.time())}.xlsx')
    
    try:
        # Upload to temp
        dbx.files_upload(file_content, temp_path)
        
        # Replace original
        try:
            dbx.files_delete_v2(dropbox_path)
        except:
            pass
            
        dbx.files_move_v2(temp_path, dropbox_path)
        
        upload_time = time.time() - start_time
        st.success(f"✅ Uploaded in {upload_time:.1f}s")
        st.success(f"📁 Filename: {dropbox_path.split('/')[-1]} (unchanged)")
        
        return True
        
    except Exception as e:
        upload_time = time.time() - start_time
        st.error(f"❌ Upload failed: {e}")
        
        # Cleanup
        try:
            dbx.files_delete_v2(temp_path)
        except:
            pass
            
        return False
def download_file(dbx, dropbox_path):
    """Downloads a file from a specific path in Dropbox."""
    try:
        _, res = dbx.files_download(path=dropbox_path)
        return res.content
    except ApiError as e:
        if isinstance(e.error, dropbox.files.DownloadError) and e.error.is_path() and e.error.get_path().is_not_found():
            return None
        st.error(f"Dropbox API error during download: {e}")
        return None

def read_from_spreadsheet(dbx, dropbox_path):
    """Reads an Excel file in Dropbox into a pandas DataFrame."""
    file_content = download_file(dbx, dropbox_path)
    #st.write("File downloaded")
    if file_content:
        try:
            return pd.read_excel(BytesIO(file_content))
        except Exception as e:
            st.error(f"Error reading Excel file from Dropbox: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# def update_spreadsheet_from_df(dbx, df_to_write, dropbox_path):
#     """Updates an Excel file in Dropbox with data from a pandas DataFrame."""
#     try:
#         output = BytesIO()
#         with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
#             df_to_write.to_excel(writer, index=False, sheet_name='Sheet1')
#             st.write("File updated. Now uploading")
#         processed_data = output.getvalue()
#         return upload_file(dbx, processed_data, dropbox_path)
#     except Exception as e:
#         st.error(f"Error writing to Excel file for Dropbox upload: {e}")
#         return False
def update_spreadsheet_from_df(dbx, df_to_write, dropbox_path):
    """Faster Excel creation and upload"""
    import time
    
    start_time = time.time()
    row_count = len(df_to_write)
    
    try:
        output = BytesIO()
        
        # Use openpyxl for small files (much faster than xlsxwriter)
        if row_count < 1000:
            st.write(f"📊 Creating Excel with {row_count} rows using openpyxl...")
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_to_write.to_excel(writer, index=False, sheet_name='Sheet1')
        else:
            st.write(f"📊 Creating Excel with {row_count} rows using xlsxwriter...")
            # xlsxwriter with optimization for larger files
            with pd.ExcelWriter(output, engine='xlsxwriter', options={
                'strings_to_numbers': False,
                'strings_to_formulas': False,
                'strings_to_urls': False
            }) as writer:
                df_to_write.to_excel(writer, index=False, sheet_name='Sheet1')
        
        processed_data = output.getvalue()
        excel_time = time.time() - start_time
        file_size_mb = len(processed_data) / (1024 * 1024)
        
        st.write(f"📁 Excel created in {excel_time:.1f}s, size: {file_size_mb:.2f}MB")
        
        return upload_file(dbx, processed_data, dropbox_path)
        
    except Exception as e:
        excel_time = time.time() - start_time
        st.error(f"Error creating Excel file after {excel_time:.1f}s: {e}")
        return False
def create_folder(dbx, folder_path):
    """Creates a folder in Dropbox if it doesn't already exist."""
    try:
        dbx.files_create_folder_v2(folder_path)
    except ApiError as e:
        if e.error.is_path() and e.error.get_path().is_conflict():
            pass # Folder already exists
        else:
            st.error(f"Dropbox API error during folder creation: {e}")

def list_files(dbx, folder_path):
    """Lists all files in a specific folder in Dropbox."""
    try:
        res = dbx.files_list_folder(folder_path)
        return [entry.name for entry in res.entries]
    except ApiError as e:
        st.error(f"Dropbox API error while listing files: {e}")
        return []# # dropbox_utils.py
def optimize_dataframe_for_excel(df):
    """Optimize DataFrame to reduce Excel file size and creation time"""
    
    df_optimized = df.copy()
    
    # Round float columns to 2 decimal places to reduce file size
    for col in df_optimized.select_dtypes(include=['float']).columns:
        df_optimized[col] = df_optimized[col].round(2)
    
    # Trim string columns
    for col in df_optimized.select_dtypes(include=['object']).columns:
        df_optimized[col] = df_optimized[col].astype(str).str.strip()
    
    return df_optimized

def diagnose_upload_performance(dbx, df_to_test, dropbox_path):
    """Diagnose what's causing slow uploads"""
    import time
    
    st.markdown("### 🔍 Upload Performance Diagnostics")
    
    # Step 1: DataFrame analysis
    row_count = len(df_to_test)
    col_count = len(df_to_test.columns)
    df_memory_mb = df_to_test.memory_usage(deep=True).sum() / (1024 * 1024)
    
    st.write(f"📊 **DataFrame Analysis:**")
    st.write(f"   • Rows: {row_count:,}")
    st.write(f"   • Columns: {col_count}")
    st.write(f"   • Memory usage: {df_memory_mb:.2f} MB")
    
    # Step 2: Test small subset first
    st.write(f"🔬 **Testing with 10 rows...**")
    test_df = df_to_test.head(10)
    test_path = dropbox_path.replace('.xlsx', '_test.xlsx')
    
    start_time = time.time()
    success = update_spreadsheet_from_df(dbx, test_df, test_path)
    test_time = time.time() - start_time
    
    if success:
        st.success(f"✅ 10 rows uploaded in {test_time:.1f}s")
        if test_time > 5:
            st.warning("⚠️ Even 10 rows are slow - likely network/API issue")
        else:
            st.info("✅ Small upload speed is normal")
    else:
        st.error("❌ 10-row test failed")
        return False
    
    # Step 3: Test connectivity
    st.write(f"🌐 **Testing Dropbox API response...**")
    try:
        api_start = time.time()
        dbx.users_get_current_account()
        api_time = time.time() - api_start
        
        if api_time > 2:
            st.warning(f"⚠️ Slow API response: {api_time:.2f}s")
        else:
            st.success(f"✅ Good API response: {api_time:.2f}s")
    except Exception as e:
        st.error(f"❌ API connectivity issue: {e}")
    
    return True

def create_monthly_file_structure(dbx):
    """Create monthly file structure and helper functions"""
    
    def get_monthly_file_path(mcm_period):
        """Convert 'July 2025' to '/MCM_Data/july_2025.xlsx'"""
        safe_period = mcm_period.lower().replace(" ", "_")
        return f"/MCM_Data/mcm_data_{safe_period}.xlsx"
    
    def read_monthly_data(dbx, mcm_period):
        """Read ONLY the specific month's data"""
        monthly_file_path = get_monthly_file_path(mcm_period)
        return read_from_spreadsheet(dbx, monthly_file_path)
    
    def save_monthly_data(dbx, df_month_data, mcm_period):
        """Save ONLY the specific month's data"""
        monthly_file_path = get_monthly_file_path(mcm_period)
        create_folder(dbx, "/MCM_Data")  # Ensure folder exists
        return update_spreadsheet_from_df(dbx, df_month_data, monthly_file_path)
    
    return get_monthly_file_path, read_monthly_data, save_monthly_data


