# 💰 BudgetIQ — Personal Finance Prototype

A Streamlit-based budgeting app with onboarding, budget vs expense tracking, savings goal planning, and smart alerts.

## Setup

```bash
cd budgeting_app
pip install -r requirements.txt
streamlit run app.py
```

The app opens at **http://localhost:8501**

## Features (Phase 1)

- **Onboarding** — 3-step setup: profile → financial goals → budget categories
- **Dashboard** — budget vs expense per category with visual progress bars, savings rate, goal tracking
- **Expense logging** — log expenses with category, amount, and notes
- **Smart alerts** — auto-fires when you hit 80%+ of any category budget; manage from the Alerts page
- **SQLite storage** — all data persists locally in `budget_data.db`

## File structure

```
budgeting_app/
├── app.py                  # Entry point + routing
├── db.py                   # All SQLite queries
├── requirements.txt
├── pages/
│   ├── onboarding.py       # 3-step onboarding flow
│   ├── dashboard.py        # Main budget dashboard
│   └── alerts.py           # Alert management
└── utils/
    └── calculations.py     # Financial math (savings plan, thresholds)
```

## Roadmap

### Phase 2 — Web app
- React + FastAPI backend
- User authentication
- Receipt OCR (Google Vision or Tesseract)
- GPS-based expense context

### Phase 3 — Mobile
- React Native or Flutter
- Push notifications for alerts
- Camera receipt scanning
