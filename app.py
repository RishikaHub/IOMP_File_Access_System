# app.py
from flask import Flask, send_from_directory, jsonify, request, session
from flask_cors import CORS
from face_Recog import FaceRecognitionSystem
import threading
import cv2
import os
import base64
import numpy as np
from io import BytesIO
from PIL import Image
import face_recognition
from datetime import datetime
import jwt
import requests
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('./templates/.env')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secure-jwt-secret-key-change-this-in-production')

app = Flask(__name__, static_folder='templates/public')
app.secret_key = JWT_SECRET_KEY  # Use same key for session and JWT

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:8080", "http://localhost:5050"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Initialize face recognition system
face_system = FaceRecognitionSystem(
    dataset_path="dataset_family/",
    sender_email="gaddamlokesh20@gmail.com",
    recipient_email="rishikabussa31@gmail.com",
    email_password="fewb zzgt kufv bpep"
)

recognition_thread = None
is_recognition_running = False

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    # Mock user database - In production, use a real database
    users = {
        "test@example.com": "password123",
        "gaddamlokesh20@gmail.com": "password123"
    }
    
    if email in users and users[email] == password:
        session['user'] = email
        session['user_email'] = email
        token = jwt.encode({"email": email}, JWT_SECRET_KEY, algorithm="HS256")
        return jsonify({"status": "success", "message": "Login successful", "token": token})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/api/verify-face', methods=['POST'])
def verify_face():
    # Get JWT token from header
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        logger.warning("No authorization header provided")
        return jsonify({"status": "error", "message": "Not authenticated"}), 401
    
    try:
        # Verify token using the same secret key as Node.js
        token = auth_header.split(' ')[1]
        user_data = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        user_email = user_data.get('email')
        
        if not user_email:
            logger.warning("No email found in token")
            return jsonify({"status": "error", "message": "Invalid token"}), 401
        
        # Get the base64 image from the request
        try:
            image_data = request.json.get('image').split(',')[1]
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            logger.error(f"Error processing image data: {str(e)}")
            # Send email notification for invalid image data
            face_system.send_file_access_notification(
                None,
                user_email,
                "Unknown",
                message="Failed verification attempt - Invalid image data"
            )
            return jsonify({"status": "error", "message": "Error processing image. Please try again."}), 400
        
        # Save the captured image temporarily
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_image_path = f"face_capture_{timestamp}.jpg"
        
        try:
            with open(temp_image_path, "wb") as f:
                f.write(image_bytes)
            
            # Convert image to numpy array for face recognition
            image_np = cv2.imread(temp_image_path)
            if image_np is None:
                # Send email notification for failed image reading
                face_system.send_file_access_notification(
                    temp_image_path,
                    user_email,
                    "Unknown",
                    message="Failed verification attempt - Could not process image"
                )
                return jsonify({"status": "error", "message": "Error processing image. Please try again."}), 400
            
            # Use the new verify_face method
            name, error = face_system.verify_face(image_np)
            
            if error:
                logger.warning(f"Face verification failed: {error}")
                # Send email notification for failed verification
                face_system.send_file_access_notification(
                    temp_image_path,
                    user_email,
                    "Unknown",
                    message=f"Failed verification attempt - {error}"
                )
                
                # Different messages for different error cases
                if "Access denied" in error:  # For spoof detection
                    return jsonify({"status": "error", "message": error}), 400
                elif error == "No face detected":
                    return jsonify({"status": "error", "message": "No face detected. Please ensure your face is visible in the camera."}), 400
                else:
                    return jsonify({"status": "error", "message": "You don't have access to system. Mail has been sent to your email."}), 400
            
            # Send email notification about successful verification
            face_system.send_file_access_notification(
                temp_image_path,
                user_email,
                name,
                message="Successful verification"
            )
            
            return jsonify({
                "status": "success",
                "message": "Face verified",
                "name": name
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except Exception as e:
                    logger.error(f"Error removing temporary file: {str(e)}")
                
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return jsonify({"status": "error", "message": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
        return jsonify({"status": "error", "message": "Invalid token"}), 401
    except Exception as e:
        logger.error(f"Unexpected error in verify_face: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred"
        }), 500

@app.route('/')
def index():
    return send_from_directory('templates/public', 'index.html')

@app.route('/start_recognition')
def start_recognition():
    global recognition_thread, is_recognition_running
    
    # Check if email password is configured
    if not face_system.email_password:
        return jsonify({
            "status": "error", 
            "message": "Email password not configured in face recognition system."
        })
    
    # If recognition is already running, stop it first
    if is_recognition_running:
        face_system.stop_recognition()
        if recognition_thread:
            recognition_thread.join(timeout=1)
        cv2.destroyAllWindows()
    
    # Start new recognition thread
    is_recognition_running = True
    recognition_thread = threading.Thread(target=face_system.run_recognition)
    recognition_thread.daemon = True
    recognition_thread.start()
    return jsonify({"status": "success", "message": "Face recognition started"})

@app.route('/stop_recognition')
def stop_recognition():
    global is_recognition_running
    if is_recognition_running:
        face_system.stop_recognition()
        is_recognition_running = False
        cv2.destroyAllWindows()
        return jsonify({"status": "success", "message": "Face recognition stopped"})
    return jsonify({"status": "warning", "message": "Face recognition is not running"})

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('templates/public', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)