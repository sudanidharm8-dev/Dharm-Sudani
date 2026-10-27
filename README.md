# 🛡️ FairShift Guardian

> **Prompt Wars 2026 · SRM ACM Student Chapter**
> UN SDG 8 — Decent Work and Economic Growth

An AI-powered workforce fairness platform for construction sites and college campuses. Workers get cryptographic wage proof, near-miss safety reporting, and anonymous mood tracking. Employers get real-time fairness scores and AI-driven workforce insights.

---

## 🚀 Features

| # | Feature | Who |
|---|---|---|
| 1 | ✅ Shift Check-In with zone tagging | Worker |
| 2 | ⚠️ Near-Miss Icon Reporter (AI severity classification) | Worker |
| 3 | 😊 Anonymous Mood Pulse | Worker |
| 4 | 🔐 Cryptographic Wage Proof (SHA-256) | Worker |
| 5 | 📄 Wage Dispute PDF Generator | Worker |
| 6 | 📊 Fairness Score per Industry | Admin |
| 7 | 🗺️ Workforce Health Map | Admin |
| 8 | 🤖 AI Insight Chatbot (Gemini, rate-limited) | Admin |

---

## 🏗️ Tech Stack

- **Backend**: Python 3.11 · FastAPI · slowapi (rate limiting)
- **AI**: Google Gemini 1.5 Flash
- **PDF**: ReportLab
- **Frontend**: Plain HTML + Tailwind CSS (CDN)
- **Hosting**: Google Cloud Run ✅

---

## ⚙️ Local Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/workpulse-ai.git
cd workpulse-ai
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set environment variables
```bash
copy .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

### 5. Run the app
```bash
uvicorn backend.main:app --reload --port 8080
```

Open **http://localhost:8080** for the Worker UI.
Open **http://localhost:8080/admin** for the Admin Dashboard.
Open **http://localhost:8080/docs** for API documentation.

---

## 🧪 Run Tests

```bash
pytest tests/ -v
```

All 20 tests cover: cryptographic security, fairness score, and all API routes.

---

## 🚢 Deploy to Google Cloud Run

### 1. Build and push the Docker image
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/workpulse-ai
```

### 2. Deploy to Cloud Run
```bash
gcloud run deploy workpulse-ai \
  --image gcr.io/YOUR_PROJECT_ID/workpulse-ai \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key_here,APP_ENV=production
```

### 3. Copy the Cloud Run URL → submit on Innovator Dashboard ✅

---

## 🔐 Security

- ✅ All API keys loaded from Cloud Run environment variables — never in code
- ✅ `.env` excluded from Git via `.gitignore`
- ✅ Input validated with Pydantic strict types (Literal enums)
- ✅ AI endpoints rate-limited to 5 requests/minute
- ✅ CORS restricted to allowed origins only (not wildcard)
- ✅ Docker runs as non-root user
- ✅ SHA-256 cryptographic hashing for tamper-proof wage records
- ✅ No PII stored — anonymous worker IDs only

---

## 🏭 Industries Supported

| Mode | Focus |
|---|---|
| 🏗️ Construction | Daily shift workers, heavy machinery safety, site hazard reporting |
| 🎓 College Campus | Campus support staff, facility equipment, hostel maintenance |

---

## 📁 Project Structure

```
workpulse-ai/
├── backend/
│   ├── main.py           # App entry point + middleware
│   ├── config.py         # Settings from env vars only
│   ├── database.py       # In-memory store (replace with Firebase in prod)
│   ├── security.py       # SHA-256 hashing + input sanitization
│   ├── gemini_helper.py  # Gemini AI wrapper (rate-safe)
│   └── routes/
│       ├── checkin.py    # Worker shift check-in
│       ├── near_miss.py  # Near-miss safety reports
│       ├── mood.py       # Anonymous mood pulse
│       ├── wage_proof.py # Cryptographic wage records + PDF
│       └── dashboard.py  # Fairness score + AI chatbot
├── frontend/
│   ├── worker.html       # Worker UI (mobile-first)
│   └── admin.html        # Admin dashboard
├── tests/
│   ├── test_security.py  # Crypto hash unit tests
│   ├── test_fairness.py  # Fairness score unit tests
│   └── test_routes.py    # API endpoint tests
├── .gitignore
├── .env.example
├── Dockerfile            # Multi-stage, non-root
└── README.md
```

---

*Built with ❤️ for Prompt Wars 2026 · SRM ACM Student Chapter*
