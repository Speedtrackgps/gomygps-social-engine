import requests
import json
import time
import os
import base64

def post_to_facebook(file_path, caption, page_id, access_token, media_type):
    print(f"Initializing Facebook {media_type.capitalize()} Upload...")
    
    if media_type == 'image':
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        payload = {'message': caption, 'access_token': access_token}
        with open(file_path, 'rb') as f:
            response = requests.post(url, data=payload, files={'source': f})
    else:
        url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
        payload = {'description': caption, 'thumb_offset': '2000', 'access_token': access_token}
        with open(file_path, 'rb') as f:
            response = requests.post(url, data=payload, files={'source': f})
        
    result = response.json()
    if 'id' in result:
        print(f"Facebook Upload Successful. ID: {result['id']}")
        return True
    else:
        print(f"Facebook Upload Failed: {result}")
        return False


def post_to_instagram(file_url, caption, ig_user_id, access_token, media_type):
    print(f"Initializing Instagram {media_type.capitalize()} Upload...")
    
    # Step 1: Create the media container
    create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    
    if media_type == 'image':
        create_payload = {
            'image_url': file_url,
            'caption': caption,
            'access_token': access_token
        }
    else:
        create_payload = {
            'media_type': 'REELS',
            'video_url': file_url,
            'caption': caption,
            'thumb_offset': '2000',
            'access_token': access_token
        }
    
    create_req = requests.post(create_url, data=create_payload)
    create_res = create_req.json()
    
    if 'id' not in create_res:
        print(f"IG Container Creation Failed: {create_res}")
        return False
        
    container_id = create_res['id']
    print(f"Container created ({container_id}). Processing...")
    
    # Step 2: Poll status (Required for video, usually instant for images but safe to poll)
    status_url = f"https://graph.facebook.com/v19.0/{container_id}?fields=status_code&access_token={access_token}"
    while True:
        status_req = requests.get(status_url)
        status_res = status_req.json()
        status_code = status_res.get('status_code')
        
        if status_code == 'FINISHED' or status_code is None: # Images may not return a status code
            break
        elif status_code == 'ERROR':
            print("Meta encountered an error processing the Instagram media.")
            return False
            
        time.sleep(5)
        
    # Step 3: Publish the container
    publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    publish_payload = {'creation_id': container_id, 'access_token': access_token}
    
    publish_req = requests.post(publish_url, data=publish_payload)
    publish_res = publish_req.json()
    
    if 'id' in publish_res:
        print(f"Instagram Upload Successful. Post ID: {publish_res['id']}")
        return True
    return False


def post_to_linkedin(file_path, caption, access_token, media_type):
    print(f"Initializing LinkedIn {media_type.capitalize()} Upload...")
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-Restli-Protocol-Version': '2.0.0',
        'Content-Type': 'application/json'
    }
    
    # Fetch Member ID
    me_req = requests.get('https://api.linkedin.com/v2/userinfo', headers=headers)
    if me_req.status_code != 200:
        me_req = requests.get('https://api.linkedin.com/v2/me', headers=headers)
        
    if me_req.status_code == 200:
        data = me_req.json()
        person_id = data.get('sub') or data.get('id')
        author_urn = f"urn:li:person:{person_id}"
    else:
        print(f"Failed to fetch ID. Error: {me_req.text}")
        return False

    # Route parameters based on media type
    recipe = "urn:li:digitalmediaRecipe:feedshare-image" if media_type == 'image' else "urn:li:digitalmediaRecipe:feedshare-video"
    share_category = "IMAGE" if media_type == 'image' else "VIDEO"

    # Step 1: Register the Upload
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    register_payload = {
        "registerUploadRequest": {
            "recipes": [recipe],
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
    print("Uploading binary data to LinkedIn...")
    upload_headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/octet-stream'}
    with open(file_path, 'rb') as file_data:
        requests.put(upload_url, headers=upload_headers, data=file_data)
        
    # Step 3: Create the UGC Post
    print("Creating LinkedIn Post...")
    post_url = "https://api.linkedin.com/v2/ugcPosts"
    post_payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": share_category,
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

def post_to_youtube(file_path, title, caption, client_id, client_secret, refresh_token, media_type):
    if media_type == 'image':
        print("Skipping YouTube: Standard API does not support direct image posting.")
        return True

    print("Initializing YouTube Video Upload...")
    creds_info = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    creds = Credentials.from_authorized_user_info(creds_info)
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {"title": title, "description": caption, "categoryId": "22"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    
    if 'id' in response:
        print(f"YouTube Upload Successful. Video ID: {response['id']}")
        return True
    return False

def post_to_pinterest(file_path, caption, board_id, access_token, media_type):
    print(f"Initializing Pinterest {media_type.capitalize()} Upload...")
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    if media_type == 'image':
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        pin_payload = {
            "board_id": board_id,
            "title": caption[:100],
            "description": caption[:800],
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/jpeg", 
                "data": encoded_string
            }
        }
        pin_req = requests.post("https://api.pinterest.com/v5/pins", headers=headers, json=pin_payload)
        
        if pin_req.status_code == 201:
            print("Pinterest Image Upload Successful.")
            return True
        return False

    else:
        print("Registering video with Pinterest...")
        reg_payload = {"media_type": "video"}
        reg_req = requests.post("https://api.pinterest.com/v5/media", headers=headers, json=reg_payload)
        reg_data = reg_req.json()
        
        if 'media_id' not in reg_data:
            print(f"Pinterest Registration Failed: {reg_data}")
            return False
            
        media_id = reg_data['media_id']
        upload_url = reg_data['upload_url']
        upload_params = reg_data['upload_parameters']
        
        print(f"Uploading video binary to Pinterest server...")
        with open(file_path, 'rb') as video_file:
            files = {'file': video_file}
            upload_req = requests.post(upload_url, data=upload_params, files=files)
            
        print("Waiting for Pinterest to process the video...")
        while True:
            status_req = requests.get(f"https://api.pinterest.com/v5/media/{media_id}", headers=headers)
            status = status_req.json().get('status')
            if status == 'succeeded':
                break
            elif status == 'failed':
                return False
            time.sleep(5)
            
        pin_payload = {
            "board_id": board_id,
            "title": caption[:100],
            "description": caption[:800],
            "media_source": {"source_type": "video_id", "media_id": media_id}
        }
        pin_req = requests.post("https://api.pinterest.com/v5/pins", headers=headers, json=pin_payload)
        
        if pin_req.status_code == 201:
            print("Pinterest Video Upload Successful.")
            return True
        return False
