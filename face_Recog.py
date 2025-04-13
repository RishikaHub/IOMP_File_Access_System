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
        
        # Email configuration
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.email_password = email_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
        # Initialize face encodings
        self.load_known_faces()
        logger.info(f"Initialized with {len(self.known_face_names)} known faces: {', '.join(self.known_face_names)}")

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

    def send_file_access_notification(self, image_path, user_email, recognized_name):
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
            
            The attached image shows the person who attempted to access files.
            If this wasn't you, please contact system administrator immediately.
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

            logger.info(f"Access notification email sent to {user_email}")
            
        except Exception as e:
            logger.error(f"Error sending access notification email: {str(e)}")

    def load_known_faces(self):
        """Load and encode all known faces from the dataset directory"""
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

    def verify_face(self, image_data):
        """Verify a face against known faces"""
        try:
            # Convert image to RGB format
            if isinstance(image_data, np.ndarray):
                rgb_image = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image_data

            # Find faces in the image
            face_locations = face_recognition.face_locations(rgb_image)
            if not face_locations:
                logger.warning("No face detected in the image")
                return None, "No face detected"

            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            if not face_encodings:
                logger.warning("Could not encode face from the image")
                return None, "Could not encode face"

            # Compare with known faces
            matches = face_recognition.compare_faces(
                self.known_face_encodings,
                face_encodings[0],
                tolerance=0.6
            )

            if True in matches:
                name = self.known_face_names[matches.index(True)]
                logger.info(f"Face verified as {name}")
                return name, None
            else:
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
                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(
                        self.known_face_encodings, 
                        face_encoding,
                        tolerance=0.6
                    )
                    name = "Unknown"

                    if True in matches:
                        first_match_index = matches.index(True)
                        name = self.known_face_names[first_match_index]
                    
                    face_names.append(name)

                current_time = time.time()
                if "Unknown" in face_names and (current_time - last_save_time) >= 30:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    image_path = f"unknown_face_{timestamp}.jpg"
                    cv2.imwrite(image_path, frame)
                    self.send_unknown_face_email(image_path)
                    last_save_time = current_time

            process_this_frame = not process_this_frame

            # Draw the results
            for (top, right, bottom, left), name in zip(face_locations, face_names):
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
                cv2.putText(frame, name, (left + 6, bottom - 6), 
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