import os
import json
import requests
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

# Import your publisher functions from the separate file
from social_publishers import (
    post_to_facebook, 
    post_to_instagram, 
    post_to_linkedin, 
    post_to_youtube
)

# Configuration
SHEET_NAME = "Social Media Publisher" # Update to your exact Sheet name
TAB_NAME = "Sheet1"

def authenticate_sheets():
    """Authenticates the Google Sheets Service Account."""
    creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

def download_video(drive_url, task_id):
    """Downloads the video from Google Drive to the temporary GitHub server."""
    file_id = drive_url.split('/d/')[1].split('/')[0]
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    filename = f"video_task_{task_id}.mp4"
    print(f"Downloading video for Task ID: {task_id}...")
    
    response = requests.get(direct_url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return filename

def process_pending_posts():
    """Reads the sheet, posts the videos, and updates statuses."""
    # Retrieve API Secrets from GitHub Environment
    FB_TOKEN = os.environ.get("FB_ACCESS_TOKEN")
    FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
    IG_USER_ID = os.environ.get("IG_USER_ID")
    LI_TOKEN = os.environ.get("LI_ACCESS_TOKEN")
    LI_ORG_ID = os.environ.get("LI_ORG_ID")
    
    YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
    YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
    YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

    client = authenticate_sheets()
    sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
    records = sheet.get_all_records()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    for idx, row in enumerate(records):
        row_num = idx + 2 # Google Sheet rows are 1-indexed; skip header row
        
        status = str(row.get("Status", "")).strip().lower()
        schedule_date = str(row.get("Schedule Date", "")).strip()
        
        # Only process if scheduled for today AND not already marked "Done"
        if status != "done" and schedule_date == today:
            task_id = row.get("task_id")
            platforms = str(row.get("target_platforms", "")).split(",")
            caption = row.get("caption", "")
            linkedin_title = row.get("linkedin_title", "")
            
            print(f"--- Executing Task {task_id} ---")
            
            # Step 1: Download the media file locally
            video_path = download_video(row["drive_file_url"], task_id)
            
            # Step 2: Upload to requested platforms
            if "FB" in platforms:
                post_to_facebook(video_path, caption, FB_PAGE_ID, FB_TOKEN)
                
            if "IG" in platforms:
                # Instagram downloads directly from the Google Drive URL
                post_to_instagram(row["drive_file_url"], caption, IG_USER_ID, FB_TOKEN)
                
            if "LI" in platforms:
                post_to_linkedin(video_path, caption, LI_ORG_ID, LI_TOKEN)
                
            if "YT" in platforms or "GB" in platforms:
                post_to_youtube(video_path, linkedin_title, caption, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN)
                
            # Step 3: Write "Done" back to the Google Sheet (Column 9 / I)
            sheet.update_cell(row_num, 9, "Done")
            print(f"Task {task_id} successfully marked as Done.")
            
            # Step 4: Delete the local video file
            os.remove(video_path)

if __name__ == "__main__":
    process_pending_posts()