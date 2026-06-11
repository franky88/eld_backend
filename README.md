# 🚛 ELD Trip Planner

A full-stack web application that accepts truck trip details and outputs **FMCSA-compliant route maps** and **auto-filled Driver's Daily Log sheets** — ready to download as PDF.

Built with **Django** (backend) + **React/Vite** (frontend) as a full-stack assessment project.

---

## ✨ Features

- 📍 **Geocode autocomplete** — location search powered by OpenRouteService
- 🗺️ **Interactive route map** — full route with pickup, dropoff, fuel, and rest stop markers
- 📋 **FMCSA-compliant HOS engine** — enforces 11-hr driving, 14-hr window, 10-hr off-duty, 30-min break, and 70-hr/8-day cycle rules
- 📄 **Authentic paper log sheets** — canvas-rendered Driver's Daily Logs in dot-connect-drop style with brackets, remarks, and totals
- 📅 **Multi-day support** — generates one log sheet per duty day, navigable via tabs
- ⬇️ **PDF export** — download all log sheets as a single PDF
- 💾 **Draft saving** — save and reload trip form data via localStorage

---

## 🗂️ Project Structure

```
eld-trip-planner/
├── backend/                        # Django REST API
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── eld_planner/
│   │   ├── hos_engine.py           # Core FMCSA HOS calculation logic
│   │   ├── routing.py              # OpenRouteService geocoding + directions
│   │   ├── log_renderer.py         # Log sheet JSON builder + validator
│   │   ├── views.py                # API endpoints
│   │   └── urls.py
│   ├── manage.py
│   ├── requirements.txt
│   └── .env
│
└── frontend/                       # React + Vite SPA
    ├── src/
    │   ├── components/
    │   │   ├── MapView.jsx          # React Leaflet map
    │   │   └── LogSheet.jsx         # Canvas log sheet renderer + PDF export
    │   ├── utils/
    │   │   ├── drawLogSheet.js      # All canvas drawing logic
    │   │   └── hosHelpers.js
    │   ├── pages/
    │   │   └── Home.jsx             # Single-page layout
    │   └── store.js                 # Zustand global state + draft helpers
    ├── vite.config.js
    └── .env
```

---

## ⚙️ Tech Stack

| Layer    | Technology                                 |
| -------- | ------------------------------------------ |
| Backend  | Django 4.2+, Django REST Framework         |
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui    |
| Map      | React Leaflet + OpenStreetMap (no API key) |
| Routing  | OpenRouteService API (free tier)           |
| State    | Zustand                                    |
| Forms    | React Hook Form                            |
| PDF      | jsPDF                                      |
| Hosting  | Vercel (frontend) + Railway (backend)      |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenRouteService API key — free at [openrouteservice.org](https://openrouteservice.org)

---

### Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Fill in ORS_API_KEY and DJANGO_SECRET_KEY

# 5. Run migrations
python manage.py migrate

# 6. Start development server
python manage.py runserver
```

Backend runs at `http://localhost:8000`

---

### Frontend Setup

```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Create .env file
cp .env.example .env
# Set VITE_API_BASE_URL=http://localhost:8000

# 4. Start development server
npm run dev
```

Frontend runs at `http://localhost:5173`

---

## 🔑 Environment Variables

### `backend/.env`

```env
ORS_API_KEY=your_openrouteservice_key_here
DJANGO_SECRET_KEY=your_long_random_secret_here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 📡 API Reference

### `POST /api/plan-trip/`

Plans a full trip and returns route geometry + HOS log sheets.

**Request body:**

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Indianapolis, IN",
  "dropoff_location": "Nashville, TN",
  "cycle_used_hours": 14.5,
  "carrier": "FastHaul Logistics",
  "tractor_number": "TRK-204",
  "trailer_number": "TRL-089",
  "driver_signature": "John E. Doe",
  "main_office": "123 Main St, Chicago IL"
}
```

**Response shape:**

```json
{
  "route": {
    "geometry": "<encoded polyline>",
    "total_miles": 470.2,
    "total_drive_hours": 11.1,
    "stops": [
      {
        "type": "pickup",
        "label": "Indianapolis, IN",
        "coords": [39.78, -86.14],
        "eta_hours": 2.1
      },
      {
        "type": "dropoff",
        "label": "Nashville, TN",
        "coords": [36.23, -86.83],
        "eta_hours": 8.5
      }
    ]
  },
  "logs": [
    {
      "day": 1,
      "fields": {
        "date": "2026-06-10",
        "total_miles": 470.2,
        "carrier": "FastHaul Logistics",
        "tractor_number": "TRK-204",
        "trailer_number": "TRL-089",
        "home_terminal": "Chicago, IL",
        "driver_signature": "John E. Doe"
      },
      "events": [
        {
          "status": "offDuty",
          "start_hour": 0.0,
          "end_hour": 6.0,
          "is_stationary": false
        },
        {
          "status": "onDutyNotDriving",
          "start_hour": 6.0,
          "end_hour": 6.5,
          "is_stationary": true
        },
        {
          "status": "driving",
          "start_hour": 6.5,
          "end_hour": 14.5,
          "is_stationary": false
        }
      ],
      "remarks": [
        {
          "time": "06:00",
          "location": "Chicago, IL",
          "activity": "On duty / pre-trip inspection"
        }
      ],
      "totals": {
        "offDuty": 13.0,
        "sleeperBerth": 0.0,
        "driving": 8.5,
        "onDutyNotDriving": 2.5
      }
    }
  ]
}
```

> `totals` always sums to exactly **24.0** for every day.

---

### `GET /api/geocode/?q=Chicago`

Returns location suggestions for autocomplete.

**Response:**

```json
{
  "features": [
    {
      "properties": {
        "label": "Chicago, Illinois, USA",
        "region": "Illinois"
      },
      "geometry": { "coordinates": [-87.6298, 41.8781] }
    }
  ]
}
```

---

## 🧮 HOS Rules Applied

| Rule                              | Value                                              |
| --------------------------------- | -------------------------------------------------- |
| Max driving per duty window       | 11 hours                                           |
| Driving window (wall clock)       | 14 consecutive hours from shift start              |
| Off duty required between windows | 10 consecutive hours                               |
| Rest break required after         | 8 **cumulative** driving hours                     |
| Rest break duration               | 30 minutes                                         |
| Weekly cycle                      | 70 hours / 8 days (property carrier)               |
| Fuel stop interval                | Every 1,000 miles                                  |
| Pickup / dropoff time             | 1 hour on-duty not driving                         |
| Pre-trip inspection               | 30 min on-duty not driving at start of every shift |

> All rules per **49 CFR Part 395** — no adverse driving conditions exception applied.

---

## 🖊️ Log Sheet Canvas Format

Log sheets are rendered on HTML5 `<canvas>` in authentic FMCSA paper log style:

- **Dot-connect-drop** lines — dot at status change → horizontal line → vertical drop to next row
- **Brackets** above stationary on-duty events (inspections, loading, fueling)
- **Four status rows** — Off Duty, Sleeper Berth, Driving, On Duty Not Driving
- **Remarks section** — diagonal location labels below the grid
- **Totals column** — hours per row, always summing to 24.0
- **Full header** — date, carrier, tractor/trailer numbers, driver signature

---

## 🌐 Deployment

### Frontend → Vercel

```bash
# Push frontend/ to GitHub, then:
# 1. Connect repo at vercel.com
# 2. Set root directory to: frontend
# 3. Add environment variable:
#    VITE_API_BASE_URL = https://your-backend.up.railway.app
```

### Backend → Railway

```bash
# 1. Connect GitHub repo to Railway
# 2. Set root directory to: backend
# 3. Start command: gunicorn config.wsgi:application
# 4. Add environment variables:
#    ORS_API_KEY, DJANGO_SECRET_KEY, ALLOWED_HOSTS, DEBUG=False
```

**Production `settings.py` checklist:**

- `DEBUG = False`
- `ALLOWED_HOSTS` includes Railway domain
- `CORS_ALLOWED_ORIGINS` includes Vercel frontend URL
- `SECRET_KEY` from environment variable only
- `STATIC_ROOT` + whitenoise configured

---

## 📦 Dependencies

### Backend (`requirements.txt`)

```
django>=4.2
djangorestframework
django-cors-headers
requests
python-dotenv
gunicorn
whitenoise
Pillow
```

### Frontend (`package.json`)

```
react, react-dom
vite, @vitejs/plugin-react
react-leaflet, leaflet, @mapbox/polyline
axios
tailwindcss, shadcn/ui
react-hook-form
zustand
jspdf
lucide-react
```

---

## 📋 Common Issues

| Issue                                  | Fix                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------ |
| `KeyError: 'segments'` on ORS response | Use `way_points` indices to compute leg distances instead of `segments`  |
| Log totals not summing to 24.0         | Check `_calc_totals()` padding logic in `hos_engine.py`                  |
| Leaflet markers missing                | Add `L.Icon.Default.mergeOptions()` fix in `MapView.jsx`                 |
| PDF pages blank                        | All canvases must be rendered in DOM (not just active tab) before export |
| CORS errors                            | Add Vercel URL to `CORS_ALLOWED_ORIGINS` in `settings.py`                |
| ORS uses `[lng, lat]`                  | Leaflet expects `[lat, lng]` — `polyline.decode()` returns correct order |

---

## 📄 License

MIT — free to use, modify, and deploy.

---

_ELD Trip Planner — Developer Guide v1.1 · June 2026_
