import requests
import json
import time
import os

def post_to_facebook(video_path, caption, page_id, access_token):
    print("Initializing Facebook API Upload...")
    url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
    
    payload = {
        'description': caption,
        'access_token': access_token
    }
    
    with open(video_path, 'rb') as video_file:
        files = {
            'source': video_file
        }
        response = requests.post(url, data=payload, files=files)
        
    result = response.json()
    if 'id' in result:
        print(f"Facebook Upload Successful. Video ID: {result['id']}")
        return True
    else:
        print(f"Facebook Upload Failed: {result}")
        return False


def post_to_instagram(video_url, caption, ig_user_id, access_token):
    print("Initializing Instagram Reels Upload...")
    
    # Step 1: Create the media container
    create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    create_payload = {
        'media_type': 'REELS',
        'video_url': video_url,
        'caption': caption,
        'thumb_offset': '2000',  # Sets the cover image to the 2-second mark
        'access_token': access_token
    }
    
    create_req = requests.post(create_url, data=create_payload)
    create_res = create_req.json()
    
    if 'id' not in create_res:
        print(f"IG Container Creation Failed: {create_res}")
        return False
        
    container_id = create_res['id']
    print(f"Container created ({container_id}). Waiting for Meta to process video...")
    
    # Step 2: Poll status until processing is complete
    status_url = f"https://graph.facebook.com/v19.0/{container_id}?fields=status_code&access_token={access_token}"
    while True:
        status_req = requests.get(status_url)
        status_res = status_req.json()
        status_code = status_res.get('status_code')
        
        if status_code == 'FINISHED':
            break
        elif status_code == 'ERROR':
            print("Meta encountered an error processing the Instagram video.")
            return False
            
        time.sleep(10) # Wait 10 seconds before checking again
        
    # Step 3: Publish the container
    publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    publish_payload = {
        'creation_id': container_id,
        'access_token': access_token
    }
    
    publish_req = requests.post(publish_url, data=publish_payload)
    publish_res = publish_req.json()
    
    if 'id' in publish_res:
        print(f"Instagram Upload Successful. Post ID: {publish_res['id']}")
        return True
    return False


def post_to_linkedin(video_path, caption, person_id, access_token):
    print("Initializing LinkedIn Video Upload...")
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-Restli-Protocol-Version': '2.0.0',
        'Content-Type': 'application/json'
    }
    
    # Using 'member' instead of 'person' fixes the 403 Access Denied error
    author_urn = f"urn:li:member:{person_id}"
    
    # Step 1: Register the Upload
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
            "owner": author_urn,
            "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
        }
    }
    
    reg_req = requests.post(register_url, headers=headers, json=register_payload)
    reg_data = reg_req.json()
    
    if 'value' not in reg_data:
        print(f"LinkedIn Register Upload Failed: {reg_data}")
        return False

    upload_url = reg_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
    asset_urn = reg_data['value']['asset']
    
    # Step 2: Upload the binary file
    print("Uploading binary chunks to LinkedIn...")
    upload_headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/octet-stream'}
    with open(video_path, 'rb') as video_file:
        upload_req = requests.put(upload_url, headers=upload_headers, data=video_file)
        
    # Step 3: Create the UGC Post
    print("Creating LinkedIn Post...")
    post_url = "https://api.linkedin.com/v2/ugcPosts"
    post_payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": "VIDEO",
                "media": [{"status": "READY", "media": asset_urn}]
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }
    
    post_req = requests.post(post_url, headers=headers, json=post_payload)
    if post_req.status_code == 201:
        print("LinkedIn Upload Successful.")
        return True
    else:
        print(f"LinkedIn Post Creation Failed: {post_req.text}")
        return False


from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def post_to_youtube(video_path, title, caption, client_id, client_secret, refresh_token):
    print("Initializing YouTube Upload...")
    
    # Construct credentials object using your persistent refresh token
    creds_info = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    creds = Credentials.from_authorized_user_info(creds_info)
    
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": title,
            "description": caption,
            "categoryId": "22" # 22 = People & Blogs, change as needed
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    
    response = request.execute()
    
    if 'id' in response:
        print(f"YouTube Upload Successful. Video ID: {response['id']}")
        return True
    return False
