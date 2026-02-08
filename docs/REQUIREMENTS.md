# JRA-VAN AI Prediction System - Requirements

## 1. Project Overview
This project aims to build an automated horse racing prediction and investment system using JRA-VAN Data Lab SDK. The system collects real-time racing data, generates AI-based predictions, visualizes them on a web dashboard, and supports automated betting strategies.

## 2. Functional Requirements

### 2.1 Data Collection (`worker_collector.py`)
- **Real-time Data Fetching**: Automatically fetch race cards (0B15), odds (0B31), and race results (0B12) from JRA-VAN servers.
- **Historical Data**: Ability to download past data for model training.
- **Data Integrity**:
    - Ensure duplicate records are not stored in the database.
    - Handle cancelled races or irregular data divisions (e.g., `SE9`).
    - Distinguish between different data types (e.g., Win Odds `0B31` vs Quinella `0B32`) even if fetched in the same stream.
- **Storage**: Store raw binary data and parsed JSON content in a cloud database (Supabase).

### 2.2 AI Prediction (`worker_predictor.py`)
- **Model Execution**: Run pre-trained machine learning models (LightGBM/SVM) on fetched data.
- **Scoring**: Generate a score for each horse representing its winning probability or expected value.
- **Output**: Store prediction results in the database for access by the dashboard and betting agent.

### 2.3 Web Dashboard (`app.py`)
- **Real-time Visualization**: Display upcoming races, horse lists, and live odds.
- **AI Analysis**: Show AI confidence scores side-by-side with official odds.
- **Value Indicator**: Calculate and display "Value Score" (e.g., `Odds / Popularity` or `AI Score / Implied Odds`) to highlight undervalued horses.
- **Filtering**: Allow filtering by racecourse and race number.
- **Reliability**: Handle duplicate data gracefully and display the latest information.

### 2.4 Automation (`worker_autopilot.py`)
- **Scheduler**: Orchestrate the execution of collector, predictor, and uploader scripts based on race schedules.
- **Date Handling**: Automatically determine target dates or accept manual overrides (`--date YYYYMMDD`).

## 3. Non-Functional Requirements

### 3.1 Performance
- **Latency**: Dashboard updates should reflect real-time odds changes within 1-2 minutes of JRA publication.
- **Concurrency**: Handle concurrent database writes from multiple workers.

### 3.2 Reliability
- **Error Handling**: retry mechanisms for network failures or JRA-VAN SDK timeouts.
- **Data Validation**: Validate raw data headers (e.g., `SE`, `O1`) before processing to prevent corrupted data ingestion.

### 3.3 Maintainability
- **Code Structure**: Modular design separating collection, parsing, prediction, and visualization.
- **Configuration**: Use `.env` files for sensitive credentials (Supabase keys, API limits).

## 4. System Environment
- **OS**: Windows 10/11 (Required for JRA-VAN JV-Link SDK)
- **Runtime**: Python 3.11 (32-bit required for `win32com` interaction with JV-Link)
- **Database**: Supabase (PostgreSQL)
