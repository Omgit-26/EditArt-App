import os

class Config:
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'Incybic2025-26'
    INTERNAL_API_TOKEN = "coding_rangers_2.0"
    
   
    PROCESSOR_URL = "http://localhost:5001/process"
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
   
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    