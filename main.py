import os
import json
import requests
import gspread
import gdown
import subprocess
from datetime import datetime
from google.oauth2.service_account import Credentials

# Import your publisher functions from the separate file
from social_publishers import (
    post_to_facebook, 
    post_to_instagram, 
    post_to_linkedin, 
    post_to_youtube
)

# Configuration using your specific Google Sheet ID
SHEET_ID = "1lSBKYJ2mmzF7fkGHQ3NggaFmoJ4cBym4OjfRfAWh6xs" 
TAB_NAME = "Sheet1"

def authenticate_sheets():
    """Authenticates the Google Sheets Service Account."""
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

def download_large_video(drive_url, task_id):
    """Safely downloads large files from Drive bypassing the virus scan."""
    file_id = drive_url.split('/d/')[1].split('/')[0]
    direct_url = f"https://drive.google.com/uc?id={file_id}"
    
    filename = f"raw_task_{task_id}.mp4"
    print(f"Downloading massive video for Task ID: {task_id}...")
    
    # gdown automatically handles the large file warning
    gdown.download(direct_url, filename, quiet=False)
    return filename

def compress_video(input_path, output_path):
    """Uses GitHub's built-in FFmpeg to compress the video automatically."""
    print(f"Compressing {input_path} to reduce size...")
    command = [
        'ffmpeg', '-i', input_path,
        '-vcodec', 'libx264', '-crf', '28', # crf 28 highly compresses while keeping quality
        '-preset', 'fast',
        output_path
    ]
    # Run the compression command
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Compression complete!")
    return output_path

def get_public_url_for_instagram(filepath):
    """Uploads to a temporary free server to give Instagram a direct download link."""
    print("Generating public URL for Meta...")
    with open(filepath, 'rb') as f:
        # Catbox.moe is a free, no-auth temporary file host
        res = requests.post('https://catbox.moe/user/api.php', data={'reqtype': 'fileupload'}, files={'fileToUpload': f})
    
    public_url = res.text
    print(f"Public URL generated: {public_url}")
    return public_url

def process_pending_posts():
    """Reads the sheet, processes videos, and uploads them."""
    FB_TOKEN = os.environ.get("FB_ACCESS_TOKEN")
    FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
    IG_USER_ID = os.environ.get("IG_USER_ID")
    LI_TOKEN = os.environ.get("LI_ACCESS_TOKEN")
    LI_PERSON_ID = os.environ.get("LI_PERSON_ID")
    YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
    YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
    YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

    client = authenticate_sheets()
    sheet = client.open_by_key(SHEET_ID).worksheet(TAB_NAME)
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
            
            # 1. Download safely
            raw_video_path = download_large_video(row["drive_file_url"], task_id)
            
            # 2. Compress automatically
            compressed_video_path = f"compressed_task_{task_id}.mp4"
            compress_video(raw_video_path, compressed_video_path)
            
            # 3. Upload to platforms using the COMPRESSED video
            if "FB" in platforms:
                post_to_facebook(compressed_video_path, caption, FB_PAGE_ID, FB_TOKEN)
                
            if "IG" in platforms:
                # Meta needs a public URL, not a local file. Generate one from the compressed file!
                ig_public_url = get_public_url_for_instagram(compressed_video_path)
                post_to_instagram(ig_public_url, caption, IG_USER_ID, FB_TOKEN)
                
            if "LI" in platforms:
                post_to_linkedin(compressed_video_path, caption, LI_PERSON_ID, LI_TOKEN)
                
            if "YT" in platforms or "GB" in platforms:
                post_to_youtube(compressed_video_path, linkedin_title, caption, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN)
                
            # 4. Update Sheet
            sheet.update_cell(row_num, 9, "Done")
            print(f"Task {task_id} successfully marked as Done.")
            
            # 5. Clean up temporary files
            if os.path.exists(raw_video_path): os.remove(raw_video_path)
            if os.path.exists(compressed_video_path): os.remove(compressed_video_path)

if __name__ == "__main__":
    process_pending_posts()
