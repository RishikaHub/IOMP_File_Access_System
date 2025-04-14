import cv2
import face_recognition
import os
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import logging
import numpy as np
import pickle
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceRecognitionSystem:
    def __init__(self, dataset_path="dataset_family/", 
                 sender_email=None,
                 recipient_email=None,
                 email_password=None):
        self.known_face_encodings = []
        self.known_face_names = []
        self.dataset_path = dataset_path
        self.is_running = False
        self.cache_file = "face_encodings_cache.pkl"
        self.cache_metadata_file = "face_encodings_metadata.pkl"
        
        # Email configuration
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.email_password = email_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
        # Face recognition settings
        self.known_face_tolerance = 0.6  # Keep lenient face matching

        # Very lenient screen detection threshold
        self.screen_pattern_threshold = 200  # Extremely high threshold to only catch obvious screens
        
        # Initialize face encodings
        self.load_known_faces()
        logger.info(f"Initialized with {len(self.known_face_names)} known faces: {', '.join(self.known_face_names)}")

    def get_file_hash(self, filepath):
        """Calculate MD5 hash of file for change detection"""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            buf = f.read(65536)  # Read in 64kb chunks
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def load_cache(self):
        """Load cached face encodings if available"""
        if os.path.exists(self.cache_file) and os.path.exists(self.cache_metadata_file):
            try:
                with open(self.cache_metadata_file, 'rb') as f:
                    cached_metadata = pickle.load(f)
                
                # Check if any files have changed
                current_metadata = {}
                for filename in os.listdir(self.dataset_path):
                    if filename.endswith((".jpg", ".jpeg", ".png")):
                        filepath = os.path.join(self.dataset_path, filename)
                        current_metadata[filename] = self.get_file_hash(filepath)
                
                # If metadata matches, load cached encodings
                if current_metadata == cached_metadata:
                    with open(self.cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                        self.known_face_encodings = cache_data['encodings']
                        self.known_face_names = cache_data['names']
                        logger.info("Successfully loaded face encodings from cache")
                        return True
            except Exception as e:
                logger.warning(f"Error loading cache: {str(e)}")
        
        return False

    def save_cache(self):
        """Save face encodings to cache"""
        try:
            # Save encodings
            cache_data = {
                'encodings': self.known_face_encodings,
                'names': self.known_face_names
            }
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # Save metadata
            metadata = {}
            for filename in os.listdir(self.dataset_path):
                if filename.endswith((".jpg", ".jpeg", ".png")):
                    filepath = os.path.join(self.dataset_path, filename)
                    metadata[filename] = self.get_file_hash(filepath)
            
            with open(self.cache_metadata_file, 'wb') as f:
                pickle.dump(metadata, f)
            
            logger.info("Successfully saved face encodings to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")

    def load_known_faces(self):
        """Load and encode all known faces from the dataset directory"""
        # Try to load from cache first
        if self.load_cache():
            return

        self.known_face_encodings = []
        self.known_face_names = []
        
        if not os.path.exists(self.dataset_path):
            logger.error(f"Dataset path {self.dataset_path} does not exist")
            raise FileNotFoundError(f"Dataset path {self.dataset_path} does not exist")
        
        for filename in os.listdir(self.dataset_path):
            if filename.endswith((".jpg", ".jpeg", ".png")):
                name = os.path.splitext(filename)[0]
                image_path = os.path.join(self.dataset_path, filename)
                
                try:
                    logger.info(f"Processing {filename}")
                    image = face_recognition.load_image_file(image_path)
                    face_encodings = face_recognition.face_encodings(image)
                    
                    if len(face_encodings) > 0:
                        self.known_face_encodings.append(face_encodings[0])
                        self.known_face_names.append(name)
                        logger.info(f"Successfully encoded face for {name}")
                    else:
                        logger.warning(f"No face found in {filename}")
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")

        if not self.known_face_encodings:
            logger.error("No faces could be encoded from the dataset")
            raise ValueError("No faces could be encoded from the dataset")
        
        # Save to cache for future use
        self.save_cache()

    def send_unknown_face_email(self, image_path):
        """Send email with unknown face image as attachment"""
        if not all([self.sender_email, self.email_password, self.recipient_email]):
            logger.warning("Email configuration is incomplete. Skipping email notification.")
            return

        try:
            # Create the email message
            msg = MIMEMultipart()
            msg['Subject'] = 'Unknown Face Detected - Security Alert'
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email

            # Add text body
            text_body = f"""
            Security Alert: Unknown face detected at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            
            Please review the attached image for more information.
            """
            msg.attach(MIMEText(text_body, 'plain'))

            # Add the image attachment
            with open(image_path, 'rb') as f:
                img_data = f.read()
            image = MIMEImage(img_data, name=os.path.basename(image_path))
            msg.attach(image)

            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.email_password)
                server.send_message(msg)
                server.quit() 

            logger.info("Alert email sent successfully")
            
            # Clean up the temporary image file
            os.remove(image_path)
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")

    def send_file_access_notification(self, image_path, user_email, recognized_name, message=None):
        """Send email notification when files are accessed"""
        try:
            # Create the email message
            msg = MIMEMultipart()
            msg['Subject'] = 'File Access Notification - Security Alert'
            msg['From'] = self.sender_email
            msg['To'] = user_email

            # Add text body
            text_body = f"""
            Security Notification: File Access Event

            Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            User Email: {user_email}
            Recognized Person: {recognized_name}
            {f'Message: {message}' if message else ''}
            
            {'The attached image shows the person who attempted to access files.' if image_path else ''}
            If this wasn't you, please contact system administrator immediately.
            """
            msg.attach(MIMEText(text_body, 'plain'))

            # Add the image attachment if available
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    img_data = f.read()
                image = MIMEImage(img_data, name=os.path.basename(image_path))
                msg.attach(image)

            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.email_password)
                server.send_message(msg)
                server.quit() 

            logger.info(f"Access notification email sent to {user_email}")
            
        except Exception as e:
            logger.error(f"Error sending access notification email: {str(e)}")

    def check_for_screen(self, image):
        """
        Enhanced screen detection using FFT analysis
        Returns: (is_screen, confidence)
        """
        try:
            # Convert to grayscale properly
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Calculate FFT
            freqs = np.fft.fft2(blurred)
            freq_magnitudes = np.abs(freqs)
            
            # Calculate peak ratios at different frequency bands
            peak_ratio = np.max(freq_magnitudes) / np.mean(freq_magnitudes)
            
            # Screen patterns typically show very high peak ratios
            # Calculate confidence based on observed peak ratios
            # Screens typically show ratios > 300
            base_confidence = min(peak_ratio / 3, 100)  # Scale to percentage
            
            # Enhance confidence calculation with additional features
            
            # 1. Check for regular grid patterns
            freq_threshold = np.percentile(freq_magnitudes, 99)
            high_freq_points = np.sum(freq_magnitudes > freq_threshold)
            grid_confidence = min(high_freq_points / 100, 100)
            
            # 2. Check for periodic patterns
            dy, dx = np.gradient(gray)
            gradient_magnitude = np.sqrt(dx**2 + dy**2)
            gradient_std = np.std(gradient_magnitude)
            periodic_confidence = min(gradient_std / 2, 100)
            
            # Combine confidences with weights
            final_confidence = (0.5 * base_confidence + 
                              0.3 * grid_confidence + 
                              0.2 * periodic_confidence)
            
            # For clear screens, boost confidence to 100%
            if peak_ratio > 300 and grid_confidence > 80:
                final_confidence = 100.0
            
            logger.info(f"Screen detection details:")
            logger.info(f"- Peak ratio: {peak_ratio:.2f}")
            logger.info(f"- Base confidence: {base_confidence:.2f}%")
            logger.info(f"- Grid confidence: {grid_confidence:.2f}%")
            logger.info(f"- Periodic confidence: {periodic_confidence:.2f}%")
            logger.info(f"- Final confidence: {final_confidence:.2f}%")
            
            # Consider it a screen if final confidence is high enough
            if final_confidence > 90:
                return True, final_confidence
            return False, final_confidence
            
        except Exception as e:
            logger.error(f"Error in screen detection: {str(e)}")
            return False, 0

    def verify_face(self, image_data):
        """Verify a face against known faces with minimal screen detection"""
        try:
            # Convert image to RGB format
            if isinstance(image_data, np.ndarray):
                rgb_image = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image_data

            # Quick check for obvious screens with high confidence
            is_screen, screen_confidence = self.check_for_screen(image_data)
            logger.info(f"Screen confidence: {screen_confidence:.2f}%")
            
            # Use strict floating point comparison for 60% threshold
            if float(screen_confidence) >= 60.0 or abs(float(screen_confidence) - 60.0) < 0.0001:
                logger.warning(f"Screen detected with {screen_confidence:.2f}% confidence - Access Denied")
                return None, f"Access denied - Screen display detected ({screen_confidence:.1f}% confidence)"

            # Get face locations
            face_locations = face_recognition.face_locations(rgb_image)
            if not face_locations:
                logger.warning("No face detected in the image")
                return None, "No face detected"

            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            if not face_encodings:
                logger.warning("Could not encode face from the image")
                return None, "Could not encode face"

            # Compare with known faces - keep the lenient matching
            matches = face_recognition.compare_faces(
                self.known_face_encodings,
                face_encodings[0],
                tolerance=self.known_face_tolerance
            )

            # Calculate face confidence for all known faces
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encodings[0])
            face_confidences = [(1 - dist) * 100 for dist in face_distances]
            
            if True in matches:
                best_match_index = matches.index(True)
                name = self.known_face_names[best_match_index]
                confidence = face_confidences[best_match_index]
                logger.info(f"Face recognition - Name: {name}, Confidence: {confidence:.2f}%")
                logger.info(f"All face confidences: {', '.join([f'{name}: {conf:.2f}%' for name, conf in zip(self.known_face_names, face_confidences)])}")
                return name, None
            else:
                # Log best confidence even for non-matches
                if face_confidences:
                    best_confidence = max(face_confidences)
                    logger.info(f"Best non-matching face confidence: {best_confidence:.2f}%")
                logger.warning("Face not recognized")
                return None, "Face not recognized"

        except Exception as e:
            logger.error(f"Error during face verification: {str(e)}")
            return None, str(e)

    def run_recognition(self):
        """Run the face recognition system"""
        if self.is_running:
            cv2.destroyAllWindows()
            
        self.is_running = True
        video_capture = cv2.VideoCapture(0)
        
        if not video_capture.isOpened():
            logger.error("Error: Could not open video capture device")
            return

        cv2.namedWindow('Face Recognition', cv2.WINDOW_NORMAL)
        cv2.setWindowProperty('Face Recognition', cv2.WND_PROP_TOPMOST, 1)
        
        process_this_frame = True
        last_save_time = 0
        
        while self.is_running:
            ret, frame = video_capture.read()
            if not ret:
                logger.error("Error reading frame from video capture")
                break

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            if process_this_frame:
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                face_names = []
                face_confidences = []
                
                # Only check for screen if we detect a face
                is_screen = False
                if face_encodings:
                    is_screen, screen_conf = self.check_for_screen(frame)
                    # Use strict floating point comparison for 60% threshold
                    if float(screen_conf) >= 60.0 or abs(float(screen_conf) - 60.0) < 0.0001:
                        face_names = ["Screen Detected"] * len(face_encodings)
                        face_confidences = [screen_conf] * len(face_encodings)
                        continue

                # Regular face recognition
                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(
                        self.known_face_encodings, 
                        face_encoding,
                        tolerance=self.known_face_tolerance
                    )
                    name = "Unknown"
                    confidence = 100  # Show high confidence for known faces

                    if True in matches:
                        best_match_index = matches.index(True)
                        name = self.known_face_names[best_match_index]
                    
                    face_names.append(name)
                    face_confidences.append(confidence)

                # Save unknown faces for email notification
                current_time = time.time()
                if "Unknown" in face_names and (current_time - last_save_time) >= 30:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    image_path = f"unknown_face_{timestamp}.jpg"
                    cv2.imwrite(image_path, frame)
                    self.send_unknown_face_email(image_path)
                    last_save_time = current_time

            process_this_frame = not process_this_frame

            # Draw the results
            for (top, right, bottom, left), name, confidence in zip(face_locations, face_names, face_confidences):
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)  # Green for known, red for unknown
                display_text = f"{name} ({confidence:.1f}%)"
                
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                cv2.putText(frame, display_text, (left + 6, bottom - 6), 
                           cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow('Face Recognition', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        video_capture.release()
        cv2.destroyAllWindows()
        self.is_running = False
    
    def stop_recognition(self):
        """Stop the face recognition system"""
        self.is_running = False
        cv2.destroyAllWindows()