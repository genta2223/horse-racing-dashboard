# Operational Manual

## 1. Setup & Requirements

### Windows Environment (Local PC)
- **OS**: Windows 10/11 (Required for JRA-VAN JVLink)
- **Software**:
    - JRA-VAN Data Lab Client (JV-Link) installed and active.
    - Python 3.9+
    - Google Chrome (latest)

### Installation
1. Navigate to the project directory:
   ```powershell
   cd c:\TFJV\my-racing-dashboard
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
   *(Ensure `selenium`, `supabase`, `pandas`, `lightgbm`, `pywin32` are installed)*

3. Configure `.env`:
   Ensure your `.env` file contains:
   ```ini
   SUPABASE_URL=your_url
   SUPABASE_KEY=your_key
   IPAT_INET_ID=your_id
   IPAT_SUBSCRIBER_ID=your_sub_id
   IPAT_PARS_NUM=your_pars
   IPAT_PIN=your_pin
   DAILY_CAP=10000
   SEMI_AUTO_MODE=True  # True=Ask for permission, False=Fully Auto
   MAIL_SENDER=your_gmail@gmail.com
   MAIL_APP_PASS=your_app_password
   MAIL_RECEIVER=your_email@example.com
   ```

## 2. Daily Operation

### Step 1: Data Collection
Run the collector to fetch upcoming race cards (usually Friday night for Weekend races).
```powershell
python worker_collector.py
```
- **Output**: Uploads raw data to Supabase.

### Step 2: Prediction (Hybrid EV 2.0)
Run the V2 predictor script (Logic: EV > 2.0 + Fixed Betting).
```powershell
python worker_predictor_v2.py
```
- **Behavior**:
    1. Fetches JIT Odds (0B31 + 0B32).
    2. Aligns with Race Card.
    3. Queues bets with **EV > 2.0**.
    4. Records Distortion data for future analysis.
- **Schedule**: Run this periodically (e.g., every 10 mins) or manually before race.

### Step 3: Automated Betting
Run the Shopper to execute bets in the queue.
```powershell
python worker_shopper.py
```
- **Behavior**:
    - Logs into IPAT.
    - Checks `bet_queue` for `status="approved"`.
    - Buys tickets and updates status to `purchased`.
- **Note**: Keep this window open during race hours.

### Step 4: Monitoring
Open the Dashboard to track status.
```powershell
streamlit run app.py
```
*(Or access the deployed Cloud URL)*
