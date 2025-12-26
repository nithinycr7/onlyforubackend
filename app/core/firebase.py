"""
Firebase Admin SDK initialization and utilities
"""
import firebase_admin
from firebase_admin import credentials, auth
import os

_firebase_initialized = False

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global _firebase_initialized
    
    if _firebase_initialized:
        return
    
    try:
        # Check if already initialized
        firebase_admin.get_app()
        _firebase_initialized = True
    except ValueError:
        # Try to initialize from environment variables first (for production)
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        private_key = os.getenv('FIREBASE_PRIVATE_KEY')
        client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
        
        if project_id and private_key and client_email:
            # Initialize from environment variables
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key.replace('\\n', '\n'),  # Fix escaped newlines
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("✅ Firebase Admin SDK initialized from environment variables")
        else:
            # Fall back to service account file (for local development)
            cred_path = os.path.join(os.path.dirname(__file__), '../../firebase-service-account.json')
            
            if not os.path.exists(cred_path):
                print(f"⚠️  Firebase service account not found at {cred_path}")
                print("⚠️  Firebase environment variables not set")
                print("Phone authentication will not work until you add the service account JSON file or set environment variables.")
                return
            
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("✅ Firebase Admin SDK initialized from file")

def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID token and return user data
    
    Args:
        token: Firebase ID token from client
    
    Returns:
        dict with keys: uid, phone_number, email (if available)
    
    Raises:
        ValueError: If token is invalid
    """
    if not _firebase_initialized:
        raise ValueError("Firebase not initialized. Please add service account JSON file.")
    
    try:
        decoded_token = auth.verify_id_token(token)
        return {
            'uid': decoded_token['uid'],
            'phone': decoded_token.get('phone_number'),
            'email': decoded_token.get('email'),
        }
    except Exception as e:
        raise ValueError(f"Invalid Firebase token: {str(e)}")
