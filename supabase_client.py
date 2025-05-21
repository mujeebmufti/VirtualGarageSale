# supabase_client.py
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()  # Optional if not already called in main file

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY environment variable")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
