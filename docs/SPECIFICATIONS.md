# JRA-VAN AI Prediction System - Specifications

## 1. System Architecture

The system follows a microservices-like architecture where independent Python scripts handle data collection, prediction, and visualization, orchestrated by a central scheduler. All components share a common database (Supabase) for data persistence.

```mermaid
graph TD
    JV[JRA-VAN Data Lab SDK] -->|JVRead Stream| WC[worker_collector.py]
    WC -->|Parse & Upload| DB[(Supabase PostgreSQL)]
    
    DB -->|Fetch Raw Data| WP[worker_predictor.py]
    WP -->|LightGBM Inference| WP
    WP -->|Store Results| DB
    
    DB -->|Query Latest Odds| APP[app.py (Streamlit)]
    DB -->|Query Predictions| APP
    APP -->|Visualize| USER((User Dashboard))

    AUTO[worker_autopilot.py] -->|Trigger| WC
    AUTO -->|Trigger| WP
```

## 2. Database Schema (Supabase)

### 2.1 `raw_race_data` Table
Stores raw binary data and parsed JSON content from JRA-VAN.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | uuid | Primary Key |
| `race_id` | text | Unique Race Identifier (YYYYMMDDJJKKHHRR) |
| `data_type` | text | JRA Data Spec (e.g., `0B15`, `0B31`, `0B32`) |
| `race_date` | date | Date of the race |
| `content` | jsonb | Parsed JSON content (Human-readable) |
| `raw_string` | text | Base64 encoded raw binary string (for re-parsing) |
| `created_at` | timestamp | Insertion timestamp |

### 2.2 `prediction_results` Table
Stores AI model predictions.

| Column | Type | Description |
| :--- | :--- | :--- |
| `race_id` | text | Foreign Key -> `raw_race_data.race_id` |
| `horse_num` | text | Horse Number (01-18) |
| `predict_score` | float | Model output score (winning probability/EV) |
| `model_version` | text | Version of the model used (e.g., `v1.0`, `v2.0-svm`) |
| `created_at` | timestamp | Prediction timestamp |

## 3. Component Details

### 3.1 Data Collector (`worker_collector.py`)
- **Library**: `win32com.client` (accesses JV-Link 32-bit COM object).
- **Execution**: Must run in a 32-bit Python environment (`py -3.11-32`).
- **Data Handling**:
    - **Phase 1**: Fetches Race Cards (`0B15`).
    - **Phase 2**: Fetches Odds (`0B31`, `0B32`).
    - **Critical Logic**: Uses the **returned filename** from `JVRead` (e.g., `0B32xxxx.jvd`) to identify the data type, rather than relying on the request parameter. This prevents mixing Quinella odds (`0B32`) into Win odds (`0B31`) records.
    - **Deduplication**: Uses `UPSERT` on Supabase based on `race_id` + `data_type`.

### 3.2 JRA Parser (`jra_parser.py`)
- **Function**: Parses byte streams (`cp932` encoded) into structured dictionaries derived from `jra_specs.py`.
- **Validation**:
    - Validates `Record Type` (e.g., `SE` for `0B15`, `O1` for `0B31`).
    - **Strict Gatekeeper**: Rejects invalid data divisions but **allows** `SE9` (Race Cancellation/Special State) to ensure race data is captured even during irregularities (e.g., snow cancellations).

### 3.3 Web Dashboard (`app.py`)
- **Framework**: Streamlit.
- **Features**:
    - **AI Score Display**: Displays a calculated "Value Score" defined as `Odds / Popularity`. This highlights horses with high returns relative to their popularity.
    - **Deduplication**: Implements logic to remove duplicate horse entries from the display dataframe, prioritizing the latest record.

### 3.4 Autopilot (`worker_autopilot.py`)
- **Function**: Orchestrates the daily workflow.
- **Parameters**: Accepts `--date YYYYMMDD` to target specific race days. Defaults to current date if omitted.

## 4. Operational Workflow
1. **09:00**: `worker_autopilot` starts.
2. **09:05**: `worker_collector` fetches initial `0B15` (Race Cards) and `0B31` (Morning Odds).
3. **09:10**: `worker_predictor` generates initial predictions based on morning line.
4. **09:20**: Dashboard (`app.py`) is updated with initial data.
5. **Continuous**: `worker_collector` polls for real-time odds updates every few minutes (or on demand).
