"""Minimal Sarvam AI check: one chat completion call."""
import os
import sys

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    raise SystemExit("SARVAM_API_KEY is not set. Paste your key into .env.")

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Say hello in Hindi and English in one short line."}],
)

sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252, which can't print Indic scripts
print(response.choices[0].message.content)
