"""
Test Gemini connection. Run from backend: python manage.py test_gemini
Shows exactly why Gemini might be failing (package, API key, model, blocked response).
"""
from django.core.management.base import BaseCommand

from analytics.gemini_client import get_gemini_client, ask_gemini, get_last_gemini_error


class Command(BaseCommand):
    help = "Test Gemini API: package installed, API key, model, and a simple call."

    def handle(self, *args, **options):
        self.stdout.write("Testing Gemini setup...\n")

        # 1) Import
        try:
            import google.generativeai as genai
            self.stdout.write(self.style.SUCCESS("1. google-generativeai is installed."))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"1. Package NOT installed: {e}"))
            self.stdout.write("   Run: pip install google-generativeai")
            return

        # 2) Client (API key + model)
        try:
            model = get_gemini_client()
            self.stdout.write(self.style.SUCCESS("2. GEMINI_API_KEY is set and client created."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"2. Client failed: {e}"))
            self.stdout.write("   Check .env in propel-insights-backend: GEMINI_API_KEY=... and optionally GEMINI_MODEL=gemini-1.5-flash")
            return

        # 3) Simple call
        self.stdout.write("3. Sending a test prompt to Gemini...")
        out = ask_gemini("Reply with exactly: OK", "You reply with one word only.")
        if out:
            self.stdout.write(self.style.SUCCESS(f"   Response: {out[:200]}"))
            self.stdout.write(self.style.SUCCESS("Gemini is working."))
        else:
            err = get_last_gemini_error()
            self.stdout.write(self.style.ERROR(f"   Gemini failed: {err}"))
            self.stdout.write("   Fix the issue above (model name, API key, quota, or blocked response).")
