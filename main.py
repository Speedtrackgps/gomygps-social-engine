import os
import json
import requests
import gspread
import gdown
import subprocess
import mimetypes
import time
from datetime import datetime
from google.oauth2.service_account import Credentials

# Import your publisher functions
from social_publishers import (
    post_to_facebook, 
    post_to_instagram, 
    post_to_linkedin, 
    post_to_youtube,
    post_to_pinterest,
    post_to_google_business # <-- NEW
)

SHEET_ID = "1lSBKYJ2mmzF7fkGHQ3NggaFmoJ4cBym4OjfRfAWh6xs" 
TAB_NAME = "Sheet1"

def authenticate_sheets():
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

def download_file_and_detect_type(drive_url, task_id):
    file_id = drive_url.split('/d/')[1].split('/')[0]
    print(f"Downloading file for Task ID: {task_id}...")
    original_filename = gdown.download(id=file_id, output=None, quiet=False)
    
    if not original_filename:
        print("Failed to download file from Google Drive.")
        return None, None
        
    mime_type, _ = mimetypes.guess_type(original_filename)
    media_type = 'image' if mime_type and mime_type.startswith('image') else 'video'
    
    ext = os.path.splitext(original_filename)[1]
    safe_filename = f"raw_task_{task_id}{ext}"
    os.rename(original_filename, safe_filename)
    
    print(f"Detected media type: {media_type.upper()} ({ext})")
    return safe_filename, media_type

def compress_video(input_path, output_path):
    print(f"Optimizing and compressing video for Meta compliance...")
    command = [
        'ffmpeg', '-i', input_path,
        '-vcodec', 'libx264', 
        '-crf', '35',               # Higher CRF = much smaller file size
        '-vf', 'scale=-2:720',      # Downscale long videos to 720p to drastically reduce size
        '-maxrate', '800k',         # Restrict maximum bitrate
        '-bufsize', '1600k',        # Buffer size for bitrate control
        '-preset', 'fast',
        '-acodec', 'aac', 
        '-b:a', '128k',             # Lower audio bitrate to save space
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Optimization complete!")
    return output_path
    
def get_public_url_for_instagram(filepath):
    print("Uploading to direct file host (Uguu) for Meta/GBP consumption...")
    with open(filepath, 'rb') as f:
        res = requests.post('https://uguu.se/upload', files={'files[]': f})
    try:
        data = res.json()
        public_url = data['files'][0]['url']
        print(f"Public URL generated: {public_url}")
        return public_url
    except Exception as e:
        print(f"Upload failed: {res.text}")
        return None

def process_pending_posts():
    FB_TOKEN = os.environ.get("FB_ACCESS_TOKEN")
    FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
    IG_USER_ID = os.environ.get("IG_USER_ID")
    LI_TOKEN = os.environ.get("LI_ACCESS_TOKEN")
    YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
    YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
    YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")
    PIN_TOKEN = os.environ.get("PIN_ACCESS_TOKEN")
    PIN_BOARD = os.environ.get("PIN_BOARD_ID")
    
    # GBP VARIABLES
    GBP_TOKEN = os.environ.get("GBP_ACCESS_TOKEN")
    GBP_LOCATIONS = os.environ.get("GBP_LOCATION_IDS")

    client = authenticate_sheets()
    
    max_retries = 5
    sheet = None
    for attempt in range(max_retries):
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet(TAB_NAME)
            break
        except Exception as e:
            if "503" in str(e):
                if attempt < max_retries - 1:
                    print(f"Google API 503 Error. Retrying in 5 seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(5) 
                else:
                    raise e 
            else:
                raise e 

    records = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")
    
    for idx, row in enumerate(records):
        row_num = idx + 2 
        status = str(row.get("Status", "")).strip().lower()
        schedule_date = str(row.get("Schedule Date", "")).strip()
        
        if status != "done" and schedule_date == today:
            task_id = row.get("task_id")
            platforms = str(row.get("target_platforms", "")).split(",")
            caption = row.get("caption", "")
            linkedin_title = row.get("linkedin_title", "")
            
            print(f"\n--- Executing Task {task_id} ---")
            
            raw_file_path, media_type = download_file_and_detect_type(row["drive_file_url"], task_id)
            if not raw_file_path:
                continue
            
            if media_type == 'video':
                final_media_path = f"compressed_task_{task_id}.mp4"
                compress_video(raw_file_path, final_media_path)
            else:
                final_media_path = raw_file_path 
            
            # Generate public URL if needed by IG or GBP
            public_url = None
            if "IG" in platforms or ("GBP" in platforms and media_type == 'image'):
                public_url = get_public_url_for_instagram(final_media_path)

            if "FB" in platforms:
                post_to_facebook(final_media_path, caption, FB_PAGE_ID, FB_TOKEN, media_type)
                
            if "IG" in platforms:
                if public_url:
                    post_to_instagram(public_url, caption, IG_USER_ID, FB_TOKEN, media_type)
                else:
                    print("Skipping Instagram: Failed to generate public URL (file likely too large).")
                
            if "LI" in platforms:
                post_to_linkedin(final_media_path, caption, LI_TOKEN, media_type)
                
            if "YT" in platforms:
                post_to_youtube(final_media_path, linkedin_title, caption, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, media_type)
                
            if "PIN" in platforms:
                try:
                    post_to_pinterest(final_media_path, caption, PIN_BOARD, PIN_TOKEN, media_type)
                except Exception as e:
                    print(f"Pinterest execution generated an error: {e}")
                    
            if "GBP" in platforms:
                if media_type == 'image' and public_url:
                    post_to_google_business(public_url, GBP_TOKEN, GBP_LOCATIONS)
                elif media_type == 'video':
                    print("Skipping GBP: Video uploads are not supported for GBP in this script.")
                else:
                    print("GBP Upload Failed: Could not generate public URL.")
                
            sheet.update_cell(row_num, 9, "Done")
            print(f"Task {task_id} successfully marked as Done.")
            
            if os.path.exists(raw_file_path): os.remove(raw_file_path)
            if media_type == 'video' and os.path.exists(final_media_path): os.remove(final_media_path)

if __name__ == "__main__":
    process_pending_posts()
