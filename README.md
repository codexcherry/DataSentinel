# DataSentinel

A full-stack Django web application for automated data quality analysis, intelligent cleaning, and exploratory data analysis. Built for users who need to profile, clean, and analyze CSV/Excel datasets through a browser-based interface without writing code.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Data Pipeline Workflow](#data-pipeline-workflow)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)

---

## Overview

DataSentinel takes a raw CSV or Excel file through a four-stage pipeline:

```
Upload  -->  Profile  -->  Clean  -->  Analyze
```

At each stage the system detects issues, generates recommendations, applies fixes with retry logic, tracks every transformation as a versioned snapshot, and produces statistical analysis with interactive charts.

---

## Architecture

```
Browser (HTML/CSS/JS + Lucide Icons + Plotly.js)
        |
        | HTTP Requests
        v
+-----------------------------------------------+
|              Django Application               |
|                                               |
|  Views Layer (views.py)                       |
|  - Authentication views                       |
|  - Dataset CRUD views                         |
|  - Profiling trigger view                     |
|  - Batch cleaning view (retry logic)          |
|  - Analysis view                              |
|  - Export view (CSV / Excel)                  |
|                                               |
|  URL Router (urls.py)                         |
|  - 15 named URL patterns                      |
|                                               |
|  Utils Layer                                  |
|  +------------------+  +------------------+  |
|  |  DataProfiler    |  |  CleaningEngine  |  |
|  |  - missing vals  |  |  - 12 actions    |  |
|  |  - duplicates    |  |  - retry x10     |  |
|  |  - outliers(IQR) |  |  - verification  |  |
|  |  - type issues   |  +------------------+  |
|  |  - invalid vals  |  +------------------+  |
|  |  - statistics    |  |   EDAEngine      |  |
|  +------------------+  |  - summary stats |  |
|                        |  - correlation   |  |
|                        |  - KPI calc      |  |
|                        |  - custom charts |  |
|                        +------------------+  |
|                                               |
|  ORM Layer (models.py)                        |
|  7 models - see Database Schema below         |
+-----------------------------------------------+
        |
        v
   SQLite (dev) / PostgreSQL (prod)
        |
        v
   Media Storage (local /media or cloud)
```

---

## Project Structure

```
DataSentinel/
|
├── Finalproject/                  # Django project config
│   ├── settings.py                # Settings (SECRET_KEY via env var)
│   ├── urls.py                    # Root URL config
│   ├── wsgi.py
│   └── asgi.py
|
├── DataSentinel/                  # Main application
│   ├── models.py                  # 7 database models
│   ├── views.py                   # All view functions
│   ├── urls.py                    # 15 URL patterns
│   ├── admin.py                   # Django admin registration
│   ├── apps.py
│   ├── tests.py
│   |
│   ├── utils/
│   │   ├── data_profiler.py       # Issue detection engine
│   │   ├── cleaning_engine.py     # Cleaning + recommendation engine
│   │   └── eda_engine.py          # EDA + Plotly chart engine
│   |
│   ├── templates/
│   │   ├── base.html              # Base layout, nav, dark theme CSS
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── dashboard/
│   │   │   └── index.html
│   │   ├── datasets/
│   │   │   ├── list.html          # Upload + dataset list
│   │   │   └── detail.html        # Pipeline UI, issues, lineage, versions
│   │   └── analysis/
│   │       └── results.html       # KPIs, stats, custom chart builder
│   |
│   ├── static/
│   └── migrations/
|
├── media/                         # User-uploaded files (gitignored)
│   ├── datasets/                  # Original uploaded files
│   └── dataset_versions/          # Versioned snapshots after each clean
|
├── manage.py
├── requirements.txt
├── Procfile                       # gunicorn for deployment
├── runtime.txt                    # Python version pin
├── sample_dataset.csv             # Built-in sample for new users
└── README.md
```

---

## Data Pipeline Workflow

```
+------------------+
|   User Uploads   |
|   CSV / Excel    |
+--------+---------+
         |
         v
+------------------+     Creates: Dataset record (status=uploaded)
|  STAGE 1: UPLOAD |     Stores:  file to /media/datasets/YYYY/MM/DD/
|                  |     Reads:   row count, column count
+--------+---------+
         |
         v
+------------------+     Runs:   DataProfiler.profile_data()
|  STAGE 2: PROFILE|     Detects:
|                  |       - Missing values (per column, count + %)
|  DataProfiler    |       - Duplicate rows (IQR method)
|                  |       - Outliers (IQR bounds per numeric col)
|                  |       - Type mismatches (object vs numeric)
|                  |       - Invalid values (email, phone, negatives)
|                  |     Creates: DataProfile record
|                  |     Creates: CleaningRecommendation records
|                  |       priority 1 = HIGH (errors)
|                  |       priority 2 = MEDIUM (warnings)
|                  |       priority 3 = LOW (info)
+--------+---------+
         |
         v
+------------------+     User selects issues via checkboxes
|  STAGE 3: CLEAN  |     Runs:   apply_batch_cleaning()
|                  |
|  CleaningEngine  |     For each selected issue:
|                  |       Attempt 1-10 with different strategies:
|                  |         missing  -> median, mean, mode,
|                  |                     ffill, bfill, drop_rows
|                  |         outlier  -> cap_outliers, remove_outliers
|                  |         duplicate-> remove_duplicates
|                  |         type     -> convert_type
|                  |
|                  |     After each attempt:
|                  |       verify_issue_resolved() checks:
|                  |         missing  -> 90% reduction required
|                  |         outlier  -> 80% reduction required
|                  |         duplicate-> 0 remaining
|                  |
|                  |     On success:
|                  |       - Saves versioned snapshot to
|                  |         /media/dataset_versions/YYYY/MM/DD/
|                  |       - Creates DatasetVersion record (v1, v2...)
|                  |       - Creates CleaningLog (status, exec time)
|                  |       - Re-profiles dataset automatically
|                  |
|                  |     On failure after 10 attempts:
|                  |       - Logs CleaningLog with status=failed
|                  |       - Shows 500 status in Data Lineage
+--------+---------+
         |
         v
+------------------+     Runs:   EDAEngine
|  STAGE 4: ANALYZE|       - generate_summary_statistics()
|                  |       - generate_correlation_matrix()
|  EDAEngine       |       - calculate_kpis()
|                  |       - generate_insights()
|                  |     Creates: AnalysisResult records (summary, kpi)
|                  |     Renders: Interactive Plotly charts
|                  |     Builder: Custom chart (bar/line/scatter/
|                  |              pie/box/histogram)
+------------------+
         |
         v
+------------------+
|  EXPORT          |     Formats: CSV, Excel
|                  |     Source:  current dataset file
+------------------+
```

---

## Database Schema

```
User (Django built-in)
  |
  +-- Dataset (many)
        |-- id, name, original_filename
        |-- file_path (FileField -> /media/datasets/)
        |-- file_size, file_type (csv/xlsx)
        |-- rows_count, columns_count
        |-- status: uploaded|profiling|profiled|cleaning|
        |           cleaned|analyzing|completed|failed
        |-- created_at, updated_at
        |
        +-- DatasetVersion (many)
        |     |-- version_number (1, 2, 3...)
        |     |-- file_path (FileField -> /media/dataset_versions/)
        |     |-- description (what cleaning was applied)
        |     |-- rows_count, columns_count
        |     |-- created_at
        |
        +-- DataProfile (one-to-one)
        |     |-- column_info (JSONField)
        |     |-- missing_values (JSONField)
        |     |-- duplicates (JSONField)
        |     |-- outliers (JSONField)
        |     |-- data_types_issues (JSONField)
        |     |-- invalid_values (JSONField)
        |     |-- statistics (JSONField)
        |     |
        |     +-- CleaningRecommendation (many)
        |           |-- issue_type: missing|duplicate|outlier|
        |           |               type_mismatch|invalid
        |           |-- column_name
        |           |-- affected_rows (JSONField - list of indices)
        |           |-- issue_description
        |           |-- recommended_action (12 action types)
        |           |-- action_params (JSONField)
        |           |-- priority (1=high, 2=medium, 3=low)
        |           |-- is_applied (bool)
        |
        +-- CleaningLog (many)
        |     |-- recommendation (FK, nullable)
        |     |-- action_taken, column_name
        |     |-- rows_affected
        |     |-- details (JSONField)
        |     |-- applied_by (FK -> User)
        |     |-- applied_at
        |     |-- execution_time (float, seconds)
        |     |-- status: success|failed|partial
        |
        +-- AnalysisResult (many)
              |-- analysis_type: summary|correlation|kpi
              |-- result_data (JSONField)
              |-- visualizations (JSONField - Plotly chart config)
              |-- insights (TextField)

AuditLog
  |-- user (FK), action, dataset (FK)
  |-- details (JSONField), ip_address, timestamp
```

---

## API Endpoints

| Method | URL | View | Description |
|--------|-----|------|-------------|
| GET/POST | `/` | login_view | Login page |
| GET/POST | `/register/` | register_view | Registration page |
| GET | `/logout/` | logout_view | Logout |
| GET | `/dashboard/` | dashboard | Dashboard with dataset list |
| GET | `/datasets/` | datasets_list | All datasets + upload form |
| POST | `/datasets/upload/` | upload_dataset | Upload CSV/Excel file |
| POST | `/datasets/load-sample/` | load_sample_dataset | Load built-in sample data |
| GET | `/datasets/<id>/` | dataset_detail | Pipeline UI, issues, lineage |
| GET | `/datasets/<id>/preview/` | dataset_preview | JSON preview (first 100 rows) |
| POST | `/datasets/<id>/profile/` | profile_dataset | Run data profiling |
| GET | `/datasets/<id>/analyze/` | analyze_dataset | Run full EDA |
| GET | `/datasets/<id>/export/` | export_dataset | Download CSV or Excel |
| POST | `/datasets/<id>/create-chart/` | create_visualization | Generate custom Plotly chart |
| POST | `/datasets/<id>/apply-batch/` | apply_batch_cleaning | Apply selected cleaning actions |
| GET | `/recommendations/<id>/details/` | get_issue_details | Get affected rows for an issue |
| POST | `/recommendations/<id>/apply/` | apply_cleaning | Apply single cleaning action |

---

## Features

**Data Profiling**
- Detects missing values per column with count and percentage
- Identifies duplicate rows
- Finds outliers using IQR method on all numeric columns
- Detects type mismatches (string columns that should be numeric)
- Validates email, phone, and negative value patterns

**Intelligent Cleaning**
- 12 cleaning action types: fill_mean, fill_median, fill_mode, fill_forward, fill_backward, drop_rows, drop_column, remove_duplicates, cap_outliers, remove_outliers, convert_type, replace_invalid
- Batch selection with checkboxes and Select All
- Retry logic: up to 10 attempts per issue with alternative strategies
- Verification after each attempt (90% reduction for missing, 80% for outliers)
- Automatic re-profiling after successful cleaning

**Data Lineage**
- Visual pipeline showing every transformation step
- Status codes: 200 (success) / 500 (failed) per step
- Execution time per operation
- Download button on final cleaned dataset

**Version History**
- Snapshot saved after every successful cleaning operation
- Version number increments automatically (v1, v2, v3...)
- Download any previous version

**Analysis**
- Summary statistics for numeric and categorical columns
- KPI calculation (revenue, count, rate columns auto-detected)
- Correlation matrix
- Custom chart builder: bar, line, scatter, pie, box, histogram
- Smart column selection (chart types filtered by X/Y selection)

**UI**
- Dark neon enterprise theme (API gateway style)
- Inline status response bars (202/422/500) instead of browser alerts
- Search and filter on Data Quality Issues (by column, type, severity)
- Severity badges: HIGH / MEDIUM / LOW with impact scores
- Performance metrics panel: processing time, throughput, quality score

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 4.2 |
| Data Processing | pandas 2.1, numpy 1.25, scipy 1.11 |
| Visualization | Plotly 5.17 |
| Frontend | HTML/CSS/JS, Lucide Icons, Plotly.js CDN |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL (psycopg2-binary) |
| File Export | openpyxl (Excel), xlrd |
| Deployment | gunicorn, whitenoise |
| Auth | Django built-in auth |

---

## Local Setup

**Requirements:** Python 3.11+

```bash
# 1. Clone the repository
git clone https://github.com/your-username/datasentinel.git
cd datasentinel

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Create a superuser (optional)
python manage.py createsuperuser

# 6. Run the development server
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser.

On first load, register an account and click "Try with Sample Data" on the dashboard to explore the full pipeline immediately.

---

## Environment Variables

For production, set these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | insecure dev key |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `*` |
| `DATABASE_URL` | PostgreSQL connection string | SQLite |

Create a `.env` file locally (it is gitignored):

```
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

---

## Deployment

The project includes a `Procfile` for Heroku/Render deployment:

```
web: gunicorn Finalproject.wsgi --log-file -
```

**Steps for Render/Heroku:**

1. Set environment variables in the platform dashboard
2. Set `DEBUG=False` and `ALLOWED_HOSTS` to your domain
3. Run `python manage.py migrate` as a release command
4. Static files are served via whitenoise (already configured)

**Static files** are collected to `/staticfiles/` (gitignored, generated at deploy time).

**Media files** (user uploads) are stored in `/media/` (gitignored). For production, configure cloud storage (S3 or similar) and update `DEFAULT_FILE_STORAGE` in settings.

---

## License

MIT
