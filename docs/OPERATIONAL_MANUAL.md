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
   ```

## 2. Daily Operation

### Step 1: Data Collection
Run the collector to fetch upcoming race cards (usually Friday night for Weekend races).
```powershell
python worker_collector.py
```
- **Output**: Uploads raw data to Supabase.

### Step 2: Prediction (The Brain)
*(Currently manual or script-based)*
- Run the prediction script (to be integrated) which:
    1. Reads `raw_race_data`.
    2. Runs `local_engine/brain.py`.
    3. Inserts profitable bets into `bet_queue`.

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
