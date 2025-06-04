from openai import OpenAI
from dotenv import load_dotenv
import os

def get_openai_client():
    """Get OpenAI client with fresh environment variables"""
    # Reload environment variables to catch any updates
    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    return OpenAI(api_key=api_key)

# Initialize once for backward compatibility, but use get_openai_client() for fresh keys
load_dotenv()
openai_client = get_openai_client()
