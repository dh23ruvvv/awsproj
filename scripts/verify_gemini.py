"""
Verification script for Gemini API access using google-genai SDK.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def verify() -> int:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your-gemini-api-key-here":
        print("GEMINI_API_KEY is not configured.")
        return 1

    try:
        from google import genai
        client = genai.Client(api_key=key)
        model_name = "gemini-3.5-flash-lite"
        res = client.models.generate_content(
            model=model_name,
            contents="Say hello from FlowPilot verification test",
        )
        print(f"Gemini live API access verified using {model_name}.")
        return 0
    except Exception as exc:
        print(f"Gemini live API access verification failed: {exc}")
        return 1

if __name__ == "__main__":
    sys.exit(verify())
