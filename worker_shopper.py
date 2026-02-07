import os
import time
import datetime
import sys
import traceback  # FIX #1: Added missing import
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart  # FIX #1: Added missing import
from email.mime.image import MIMEImage  # FIX #1: Added missing import
from supabase import create_client

# --- Configuration ---
load_dotenv()

# IPAT Credentials (Rakuten Bank)
IPAT_INET_ID = os.getenv("IPAT_INET_ID")
IPAT_SUBSCRIBER_ID = os.getenv("IPAT_SUBSCRIBER_ID")
IPAT_PARS_NUM = os.getenv("IPAT_PARS_NUM")
IPAT_PIN = os.getenv("IPAT_PIN")

# Safety Caps
DAILY_BUDGET_CAP = int(os.getenv("DAILY_CAP", "10000"))
SEMI_AUTO_MODE = os.getenv("SEMI_AUTO_MODE", "False").lower() == "true"  # FIX #7: Default to False for cloud

# Mail Config
MAIL_SENDER = os.getenv("MAIL_SENDER")
MAIL_APP_PASS = os.getenv("MAIL_APP_PASS")
MAIL_RECEIVER = os.getenv("MAIL_RECEIVER")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# FIX #10: Dashboard URL from environment
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://horse-racing-dashboard.streamlit.app/")

class Shopper:
    def __init__(self, supabase_client=None):
        # Allow passing client to reuse connection
        if supabase_client:
            self.supabase = supabase_client
        else:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            
        self.driver = None
        self.total_spent = 0
        self.alert_history = {}  # Key: Error Signature, Value: Last Sent Timestamp
        
        # Mail config
        self.mail_user = MAIL_SENDER
        self.mail_pass = MAIL_APP_PASS
        self.mail_to = MAIL_RECEIVER
        
        print(f"[SHOPPER] Initialized instance.")
        
    def check_env(self):
        """Verify environment variables are set"""
        if not all([IPAT_INET_ID, IPAT_SUBSCRIBER_ID, IPAT_PARS_NUM, IPAT_PIN]):
            print("[ERROR] Missing IPAT Credentials in .env (or Secrets)")
            return False
        return True

    def start_browser(self):
        """FIX #2: Properly cleanup old driver before creating new one"""
        # Close existing driver to prevent memory leak
        if self.driver:
            try:
                self.driver.quit()
                print("[SHOPPER] Closed existing browser.")
            except Exception as e:
                print(f"[WARN] Error closing old driver: {e}")
        
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Required for cloud
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")  # Memory optimization
        options.add_argument("--disable-gpu")
        options.add_argument("--single-process") # FIX: Prevent thread exhaustion (Errno 11)
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=options
            )
            print("[SHOPPER] Browser started.")
        except Exception as e:
            print(f"[ERROR] Failed to start browser: {e}")
            raise
        
    def login_ipat(self):
        """Login to IPAT with improved error handling (FIX #4)"""
        print("[SHOPPER] Logging in to IPAT...")
        
        try:
            self.driver.get("https://www.ipat.jra.go.jp/")
            wait = WebDriverWait(self.driver, 10)
            
            # Step 1: INET-ID
            try:
                wait.until(EC.presence_of_element_located((By.NAME, "inetid")))
                self.driver.find_element(By.NAME, "inetid").send_keys(IPAT_INET_ID)
                self.driver.find_element(By.CSS_SELECTOR, "a[onclick*='DoLogin']").click()
            except Exception as e:
                print(f"[ERROR] Login Step 1 Failed: {e}")
                self.send_error_alert(e, context="IPAT Login Step 1")
                return False

            # Step 2: Subscriber, P-ARS, PIN
            try:
                wait.until(EC.presence_of_element_located((By.NAME, "i")))
                self.driver.find_element(By.NAME, "i").send_keys(IPAT_SUBSCRIBER_ID)
                self.driver.find_element(By.NAME, "p").send_keys(IPAT_PARS_NUM)
                self.driver.find_element(By.NAME, "f").send_keys(IPAT_PIN)
                self.driver.find_element(By.CSS_SELECTOR, "a[onclick*='DoLogin']").click()
                print("[SHOPPER] Login Success.")
                return True
            except Exception as e:
                print(f"[ERROR] Login Step 2 Failed: {e}")
                self.send_error_alert(e, context="IPAT Login Step 2")
                return False
                
        except Exception as e:
            print(f"[ERROR] Login process failed: {e}")
            self.send_error_alert(e, context="IPAT Login General")
            return False

    def _cleanup_alert_history(self):
        """FIX #5: Clean up old alert history entries to prevent memory leak"""
        now = datetime.datetime.now()
        cutoff = now - datetime.timedelta(days=7)
        old_count = len(self.alert_history)
        
        self.alert_history = {
            sig: ts for sig, ts in self.alert_history.items()
            if ts > cutoff
        }
        
        cleaned = old_count - len(self.alert_history)
        if cleaned > 0:
            print(f"[ALERT] Cleaned {cleaned} old alert entries.")

    def send_error_alert(self, exception_obj, context="General"):
        """Sends diagnostic email with Traceback and Screenshot"""
        try:  # FIX #6: Wrap entire function to prevent alert failure from crashing caller
            now = datetime.datetime.now()
            error_sig = f"{context}:{type(exception_obj).__name__}"
            
            # Rate Limiting (1 Hour)
            last_sent = self.alert_history.get(error_sig)
            if last_sent:
                if (now - last_sent).total_seconds() < 3600:
                    print(f"[ALERT] Suppressed redundant alert: {error_sig}")
                    return

            print(f"[ALERT] Sending Error Report for: {error_sig}")
            
            # Build Message
            subject = f"🚨 JRA System Alert: {type(exception_obj).__name__}"
            tb_str = "".join(traceback.format_tb(exception_obj.__traceback__))
            
            body = f"""
System Alert Report
===================
Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
Context: {context}
Error: {str(exception_obj)}

Traceback:
{tb_str}

Recovery Advice:
- Check JRA Maintenance Hours (weekday evenings, late nights)
- Verify .env credentials if Login failed
- Check selector changes if ElementNotFound
- Review system_logs table in Supabase for more details
"""
            
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = self.mail_user
            msg['To'] = self.mail_to
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach Screenshot (if driver active)
            if self.driver:
                try:
                    screenshot = self.driver.get_screenshot_as_png()
                    image = MIMEImage(screenshot, name="error_state.png")
                    msg.attach(image)
                    print("[ALERT] Screenshot attached.")
                except Exception as e:
                    print(f"[ALERT] Could not attach screenshot: {e}")

            # Send
            if not all([self.mail_user, self.mail_pass, self.mail_to]):
                print("[ALERT] Mail credentials missing. Cannot send alert.")
                return
                
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.mail_user, self.mail_pass)
            server.send_message(msg)
            server.quit()
            
            print("[ALERT] Sent successfully.")
            self.alert_history[error_sig] = now
            
            # FIX #5: Cleanup old entries
            self._cleanup_alert_history()
            
        except Exception as alert_error:
            # FIX #6: Don't let alert failures crash the system
            print(f"[ALERT] Failed to send error alert: {alert_error}")

    def send_mail(self, subject, body):
        """Send simple text email"""
        if not all([self.mail_user, self.mail_pass, self.mail_to]):
            print("[MAIL] Credentials missing. Skipping email.")
            return

        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.mail_user
            msg['To'] = self.mail_to

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.mail_user, self.mail_pass)
            server.send_message(msg)
            server.quit()
            print("[MAIL] Sent successfully.")
        except Exception as e:
            print(f"[MAIL] Failed: {e}")

    def check_and_buy(self, daily_limit_override=None):
        """Main purchase logic with improved error handling"""
        try:
            # Safety Cap Check
            limit = daily_limit_override if daily_limit_override is not None else DAILY_BUDGET_CAP
            
            if self.total_spent >= limit:
                print(f"[SAFETY] Daily Cap Reached (¥{self.total_spent:,} / ¥{limit:,}). Stopping.")
                return False

            # Fetch Approved Bets
            res = self.supabase.table("bet_queue").select("*").eq("status", "approved").execute()
            bets = res.data if hasattr(res, 'data') else []
            
            if not bets:
                return True  # Continue polling

            # Start browser if needed
            if not self.driver:
                self.start_browser()
                if not self.login_ipat():
                    return True  # Retry login later

            purchased_items = []

            for bet in bets:
                print(f"\n[BUY ALERT] Race: {bet['race_id']} Horse: {bet['horse_num']} Amount: ¥{bet['amount']}")
                
                # Spending Check
                if self.total_spent + int(bet['amount']) > limit:
                    print("[SAFETY] Bet exceeds cap. Skipping.")
                    continue

                # FIX #7: Only ask for input if running locally with TTY
                if SEMI_AUTO_MODE and sys.stdin.isatty():
                    text = input(f"Permission to buy ¥{bet['amount']}? (y/n): ")
                    if text.lower() != 'y':
                        print("Skipped by operator.")
                        continue
                
                print("Buying... (Development Mode: Not clicking final button yet)")
                # TODO: Actual purchase logic
                # self.driver.find_element(...).click()
                
                # Post-Purchase Update
                self.total_spent += int(bet['amount'])
                self.supabase.table("bet_queue").update({"status": "purchased"}).eq("id", bet['id']).execute()
                print(f"[DONE] Purchased. Total Spent: ¥{self.total_spent:,}")
                purchased_items.append(bet)
                
            # Send Summary Mail
            if purchased_items:
                count = len(purchased_items)
                total = sum(b['amount'] for b in purchased_items)
                
                subject = f"🏇 [ACTION] {count} Bets Placed (¥{total:,})"
                
                body_lines = [
                    "JRA Betting Action Report",
                    "=========================",
                    f"Total Invested: ¥{total:,}",
                    f"Current Cycle Spend: ¥{self.total_spent:,} / ¥{limit:,}",
                    "",
                    "Details:",
                ]
                for b in purchased_items:
                    body_lines.append(f"- Race {b['race_id']}: #{b['horse_num']} ({b['bet_type']}) ¥{b['amount']}")
                    if 'details' in b:
                        body_lines.append(f"  Info: {b['details']}")
                
                body_lines.append("")
                body_lines.append(f"Dashboard: {DASHBOARD_URL}")
                body_lines.append("Status: PURCHASED (Order Sent)")
                
                self.send_mail(subject, "\n".join(body_lines))

            return True
            
        except Exception as e:
            print(f"[ERROR] check_and_buy failed: {e}")
            self.send_error_alert(e, context="check_and_buy")
            raise  # Re-raise to let caller handle

    def run_loop(self):
        """Standalone loop for testing"""
        print("[SHOPPER] Searching for approved bets...")
        while True:
            try:
                keep_running = self.check_and_buy()
                if not keep_running:
                    break
            except Exception as e:
                print(f"[ERROR] Loop iteration failed: {e}")
            time.sleep(60)

if __name__ == "__main__":
    shopper = Shopper()
    shopper.run_loop()
