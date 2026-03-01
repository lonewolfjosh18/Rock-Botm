from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import re
import instaloader
import tempfile
import uuid
import requests
import io

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all routes

def extract_shortcode(url):
    """
    Extract the shortcode from an Instagram Reel URL
    """
    # Pattern matches Instagram reel URLs
    pattern = r"(?:instagram\.com)/(?:reel|reels|p)/([^/?&#]+)"
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    return None

def get_reel_info(shortcode):
    """
    Use instaloader to fetch reel information and video URL
    """
    # Initialize instaloader
    loader = instaloader.Instaloader()
    
    try:
        # Get post by shortcode
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        
        # Check if it's a video
        if not post.is_video:
            return {
                "success": False,
                "error": "This post is not a video/reel"
            }
        
        # Extract relevant information
        reel_data = {
            "success": True,
            "video_url": post.video_url,
            "caption": post.caption if post.caption else "",
            "owner_username": post.owner_username,
            "thumbnail_url": post.url,
            "likes": post.likes,
            "comments": post.comments,
            "timestamp": post.date_utc.isoformat() if post.date_utc else None,
            "shortcode": shortcode  # Add shortcode for reference
        }
        
        return reel_data
        
    except instaloader.exceptions.ProfileNotExistsException:
        return {"success": False, "error": "Profile does not exist"}
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        return {"success": False, "error": "This is a private account"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def download_reel_video(shortcode):
    """
    Download the actual video file and return the file path
    """
    loader = instaloader.Instaloader()
    
    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        
        if not post.is_video:
            return None, "Not a video"
        
        # Create a temporary directory for this download
        temp_dir = tempfile.mkdtemp()
        
        # Download the post
        loader.download_post(post, target=temp_dir)
        
        # Find the downloaded video file
        for file in os.listdir(temp_dir):
            if file.endswith('.mp4'):
                video_path = os.path.join(temp_dir, file)
                return video_path, None
        
        return None, "Video file not found after download"
        
    except Exception as e:
        return None, str(e)

@app.route('/')
def home():
    """Serve the main index.html page"""
    return send_from_directory('.', 'index.html')

@app.route('/download')
def video_download_page():
    """Serve the video download page"""
    return send_from_directory('.', 'video-download.html')

@app.route('/api/info', methods=['GET'])
def get_reel_info_endpoint():
    """
    API endpoint to get reel information without downloading
    """
    url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    # Extract shortcode from URL
    shortcode = extract_shortcode(url)
    if not shortcode:
        return jsonify({"error": "Invalid Instagram URL"}), 400
    
    # Get reel information
    result = get_reel_info(shortcode)
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify({"error": result["error"]}), 404

@app.route('/api/download', methods=['GET'])
def download_reel_endpoint():
    """
    API endpoint to download the actual video file
    """
    url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    # Extract shortcode from URL
    shortcode = extract_shortcode(url)
    if not shortcode:
        return jsonify({"error": "Invalid Instagram URL"}), 400
    
    # Download the video
    video_path, error = download_reel_video(shortcode)
    
    if video_path:
        # Send the file and then clean up (in a real app, you'd want async cleanup)
        return send_file(
            video_path,
            as_attachment=True,
            download_name=f"instagram_reel_{shortcode}.mp4",
            mimetype="video/mp4"
        )
    else:
        return jsonify({"error": error}), 404

@app.route('/api/thumbnail', methods=['GET'])
def proxy_thumbnail():
    """
    Proxy endpoint to serve Instagram thumbnails
    """
    thumbnail_url = request.args.get('url')
    
    if not thumbnail_url:
        return jsonify({"error": "Missing thumbnail URL"}), 400
    
    try:
        # Forward the request to Instagram with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com'
        }
        
        response = requests.get(thumbnail_url, headers=headers, stream=True)
        
        if response.status_code == 200:
            # Forward the image with proper content type
            return send_file(
                io.BytesIO(response.content),
                mimetype=response.headers.get('content-type', 'image/jpeg'),
                as_attachment=False,
                download_name='thumbnail.jpg'
            )
        else:
            return jsonify({"error": "Failed to fetch thumbnail"}), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/info-post', methods=['POST'])
def get_reel_info_post():
    """
    Alternative POST endpoint for better URL handling
    """
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({"error": "Missing url in request body"}), 400
    
    url = data['url']
    shortcode = extract_shortcode(url)
    
    if not shortcode:
        return jsonify({"error": "Invalid Instagram URL"}), 400
    
    result = get_reel_info(shortcode)
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify({"error": result["error"]}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

# For Vercel (this is required)
app = app