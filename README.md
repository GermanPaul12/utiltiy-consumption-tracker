# ⚡ Utility Consumption Tracker & Financial Planner

A secure, multi-tenant Streamlit dashboard designed to monitor home utility consumption (Electricity, District Heating, and Water), analyze usage efficiency, and predict annual utility bill settlements. 

The application is tailored for households in **Germany (Mannheim/MVV tariffs)**, utilizing localized standard formulas to compare your actual consumption against official German benchmarks.

---

## 📌 What You Get From This Project

* **Actual Cost & Consumption Overview:** Tracks cumulative costs, daily/monthly consumption rates, and total expenses.
* **Prepayment Settlement Predictor:** Compares your monthly prepayments (*Abschlagszahlungen*) against actual pro-rated costs to estimate whether you are currently on track for a **refund (Guthaben)** or a **backpayment (Nachzahlung)**.
* **Personalized German Benchmarking:** Dynamically calculates consumption benchmarks based on your household size (number of occupants) and apartment area ($m^2$) using official German standards:
  * **Electricity:** Dynamic VDE formula.
  * **Heating & Hot Water:** `co2online` guidelines (standardized to $130 \text{ kWh/m}^2/\text{year}$).
  * **Cold Water:** Municipal average benchmarks ($125 \text{ Liters/person/day}$).
* **Carbon Footprint Tracking:** Translates your physical consumption into greenhouse gas emissions ($kg \text{ CO}_2 \text{ equivalent}$) using regional grid and Mannheim MVV district heating emission factors.
* **Interactive Efficiency Visualizations:** Displays cumulative spending lines and normalized daily usage rates over time, helping you identify seasonal spikes and shifts in usage behavior.
* **Data Security & Isolation:** A secure, password-hashed authentication portal guarantees that multiple users can register on the same deployed app; everyone only sees, edits, and manages their own private data rows.

---

## 🛠️ How It Works (Under the Hood)

### 1. Unified Relational Database Schema
The database (local SQLite or cloud-hosted PostgreSQL/Supabase) coordinates three primary tables:
* **`users`**: Manages secure user profiles. Passwords are cryptographically protected using Python's native `PBKDF2_HMAC_SHA256` key-derivation function with unique per-user salts. Plain text passwords are never stored.
* **`rates`**: Stores user-scoped tariff settings (unit rates, base prices, prepayments, household size, and apartment area).
* **`logs`**: Stores physical cumulative meter readings, timestamps, and utility types.

### 2. Time-Normalized Calculation Engine
Rather than relying on flat monthly approximations, the calculation engine evaluates the **exact number of days elapsed** between sequential logged readings. 
* This normalizes calculations so that even if you record readings at irregular intervals (e.g., once after 10 days, then again after 42 days), the daily consumption rate is calculated accurately.
* Projections are then pro-rated up to a standard month ($30.44 \text{ days}$) or a standard year ($365.25 \text{ days}$) to calculate accurate annual estimates.

### 3. Dual-Environment Database Integration
The database engine automatically handles deployment environments:
* **Locally:** If no external configuration is found, it automatically initializes a local SQLite file (`utility_tracker.db`) in your project folder.
* **In production:** If a `DATABASE_URL` is found in your environment, it routes queries to your remote PostgreSQL/Supabase database over a secure SSL handshake on port `6543`.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.10 or higher
* A free [Supabase](https://supabase.com/) or [Neon](https://neon.tech/) PostgreSQL database (optional, only if deploying online)

### Local Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/utility-consumption-tracker.git
   cd utility-consumption-tracker
   ```

2. **Create a Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Local Environment Variables:**
   Create a file named `.env` in the root directory:
   ```env
   # Leave blank to use local SQLite, or add your Supabase connection string:
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.reqassdcxcsvrxalmmsh.supabase.co:6543/postgres?sslmode=require
   ```
   *(Note: The database password should have special characters URL-encoded, e.g., `@` replaced by `%40`).*

5. **Run the Application:**
   ```bash
   streamlit run app.py
   ```

---

## ☁️ Cloud Deployment Guidelines

This application is designed to be easily deployed on platforms like **Streamlit Community Cloud**, **Render**, or **Heroku**.

Since cloud servers use ephemeral containers that wipe local files on reboot, you must configure a persistent database:

1. **Host your repository publicly on GitHub** (excluding your `.env` file via `.gitignore`).
2. Deploy the repository on **Streamlit Community Cloud**.
3. In your Streamlit App Dashboard, navigate to **Settings** -> **Secrets** (or **Environment Variables** on other platforms).
4. Paste your production database connection URL:
   ```toml
   DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@db.reqassdcxcsvrxalmmsh.supabase.co:6543/postgres?sslmode=require"
   ```
5. Save the configuration. The remote server will securely initialize the tables and sync with your cloud database.

---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.