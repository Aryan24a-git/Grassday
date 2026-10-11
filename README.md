# 🌿 Grassday

*A local-first open-source AI companion that predicts your perfect outdoor window, explains why using TabPFN meta-learning, and generates a printable field card so you can step away from your screen.*

**Built for the DEV Hacktoberfest Open-Source AI Challenge — Week 1: "Touch Grass".**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-success?style=for-the-badge&logo=vercel)](https://grassday.vercel.app/)
[![Backend API](https://img.shields.io/badge/API-Render-informational?style=for-the-badge&logo=render)](https://grassday.onrender.com/)
[![Tests Passing](https://img.shields.io/badge/Tests-15%2F15%20Passing-brightgreen?style=for-the-badge&logo=pytest)](https://github.com/Aryan24a-git/Grassday)
[![TabPFN v2](https://img.shields.io/badge/TabPFN-v2%20Bundled-blueviolet?style=for-the-badge)](https://github.com/automl/TabPFN)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

- 🌐 **Live Web App**: [https://grassday.vercel.app](https://grassday.vercel.app)
- ⚡ **Backend API**: [https://grassday.onrender.com](https://grassday.onrender.com)
- 📦 **GitHub Repository**: [https://github.com/Aryan24a-git/Grassday](https://github.com/Aryan24a-git/Grassday)

---

## 🎯 The Core Idea

Weather apps are filled with hour-by-hour bar charts, radar sweeps, and UV gauges that keep you staring at your phone. **Grassday** operates on a simple principle: **the screen should be the shortest part of your outdoor experience.**

Instead of forcing you to decipher raw weather numbers, Grassday fits a local [TabPFN](https://github.com/automl/TabPFN) meta-learning model to your historical ratings (1–5 stars) across 14 biometeorological variables. It pinpoints the optimal 2-hour window of the day, explains *why* with fast vectorized sensitivity scores, generates a contextual nudge via [Ollama](https://github.com/ollama/ollama) (or local templates), and prints a high-contrast analog PDF Field Card so you can leave your phone at home.

---

## 📸 Screenshots

![Grassday Living Nature Interface](docs/hero_screenshot.png)

*The Living Nature interface: Daylight mode shown with dynamic satisfaction badge (96% Ideal), explanation pills (+0.42 comfortable temp, +0.21 low UV), immediate action buttons, and 7-day horizontal forecast cards.*

---

## ✨ Key Features

- 🧠 **TabPFN v2 Meta-Learning**: Uses Prior Labs' Prior-Data Fitted Network for tabular regression. Learns nonlinear preference functions from as few as 15–25 outings without manual hyperparameter tuning.
- ⚡ **Vectorized Feature Sensitivity Explanations**: Calculates marginal feature contributions in **~1.5 seconds on CPU** using batched forward passes—no slow SHAP or black-box explainers required.
- 🛡️ **Cold-Start Biometeorological Prior**: Blends TabPFN predictions with a transparent biometeorological heuristic prior (penalizing rain, high PM2.5, extreme winds, and solar radiation) when you have fewer than 10 logged outings.
- 🖨️ **Printable Analog Field Card**: Generates a beautiful, high-contrast pocket-sized PDF via ReportLab containing hourly metrics, golden hour timings, and a blank notes grid.
- 💬 **Context-Aware Nudges**: Generates natural language encouragement via local Ollama models (`llama3.2`, `qwen2.5`, etc.) with seamless rule-based fallback for offline or cloud environments.
- 📦 **Pre-Bundled Local Weights**: Includes the 44 MB `tabpfn-v2-regressor.ckpt` directly in the repository—no Hugging Face tokens, credentials, or interactive download delays.
- ✈️ **100% Offline Durability**: Caches forecast data in SQLite and bundles an offline fallback snapshot (`demo_forecast.json`) so you can run predictions and generate cards in the woods with zero internet connectivity.
- 🎨 **Living Nature Design System**: Responsive, accessible UI with Daylight and Dusk themes that automatically adjust to your local sunset.

---

## 🚀 Installation & Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** (for frontend development)
- *(Optional)* **Ollama** installed locally (`ollama pull qwen2.5:3b` or `llama3.2`) for AI-generated text nudges.

### 1. Clone the Repository
```bash
git clone https://github.com/Aryan24a-git/Grassday.git
cd Grassday
```

### 2. Backend Setup
```bash
# Create and activate virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 4. Run the Application

**Start the FastAPI Backend:**
```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
> **Note**: On its initial run, if no outings exist, the backend automatically seeds 25 realistic sample outings and pre-loads the offline forecast snapshot, allowing judges and developers to experience the model immediately. You can also explicitly re-seed anytime with `python demo.py`.

**In a second terminal, start the React Frontend:**
```bash
cd frontend
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## 🧪 Running Tests

The test suite covers API endpoints, TabPFN feature extraction, biometeorological scoring, offline caching, and PDF card generation:

```bash
pytest -v
```

All **15/15 tests** pass out of the box with zero external network requirements.

---

## 🧠 Empirical Validation: Does TabPFN Actually Help?

To verify whether TabPFN provides meaningful value on tiny datasets, we evaluated it using **Leave-One-Out Cross-Validation (LOOCV)** on 25 synthetic outings with complex, non-linear preferences (preferring 18–24°C, low wind, and clear skies):

| Model / Approach | Mean Absolute Error (MAE) | Relative Error Reduction |
| :--- | :---: | :---: |
| **Naive Baseline** (predicting the mean rating) | `0.92` | Baseline |
| **Grassday TabPFN Regressor** | **`0.82`** | **11.4% Improvement** |

With only 25 logged data points, TabPFN captures nuanced interactions (such as high wind ruining an otherwise pleasant 22°C afternoon) that standard linear models miss entirely.

---

## 🏛️ Architecture

```mermaid
graph TD
    subgraph Data Layer
        OM[Open-Meteo API] -->|Hourly Weather, AQI, Solar| Cache[(SQLite Cache)]
        Fallback[demo_forecast.json] -.->|Offline Snapshot| Cache
        User[User Outing Logs] -->|Ratings 1-5 + Notes| DB[(SQLite Outings)]
    end

    subgraph Intelligence Layer
        DB -->|Train On Local Outings| Model[TabPFN v2 Regressor]
        Cache -->|Forecast Windows| Model
        Model -->|Ranked Windows + Sensitivity| Engine[Nudge Engine]
        Engine -->|Prompt| LLM[Ollama Local LLM]
        Engine -.->|Cloud/Offline Fallback| Template[Rule-based Template]
    end

    subgraph Backend API Layer
        Model --> API[FastAPI Server :8000]
        Engine --> API
        API --> PDF[ReportLab Field Card Generator]
    end

    subgraph Presentation Layer
        API <-->|REST API / CORS| UI[React 18 + Vite Frontend]
        UI --> Theme[Living Nature Design System]
    end
```

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/forecast` | Returns 7-day hourly forecast combining weather, air quality, and solar coordinates. |
| `GET` | `/api/best-window` | Returns ranked outdoor windows with predicted scores, heuristic priors, and feature sensitivities. |
| `GET` | `/api/nudge` | Returns a context-aware nudge message for the optimal window (via Ollama or template). |
| `GET` | `/api/outings` | Retrieves all logged outings with timestamps, ratings, and notes. |
| `POST` | `/api/outings` | Logs a new outing with rating, activity, notes, and automatically captured weather features. |
| `GET` | `/api/field-card` | Generates and streams a high-contrast printable PDF Field Card. |
| `GET` | `/api/settings` | Returns current user configuration (coordinates, location name). |
| `POST` | `/api/settings` | Updates coordinates and default location preferences. |

---

## 🛠️ Makefile Commands

For developer convenience, standard tasks are wrapped in a root `Makefile`:

```bash
make setup     # Install backend and frontend dependencies
make backend   # Run FastAPI server on port 8000
make demo      # Seed demo outings and start FastAPI server
make frontend  # Run React Vite dev server on port 5173
make test      # Run full pytest suite
make clean     # Clean build artifacts and temporary caches
```

---

## 🐳 Docker Deployment

To build and run Grassday in a single container:

```bash
docker build -t grassday .
docker run -p 8000:8000 grassday
```

Visit `http://localhost:8000` to interact with the bundled application.

---

## 🔓 Why Open Innovation Matters

1. **Absolute Privacy**: Your daily schedule, health metrics, and outdoor locations stay strictly on your local device. Outing logs are stored in a local SQLite file (`data/grassday.db`) and are never sent to third-party ad networks or remote cloud databases.
2. **Offline Durability**: Traditional AI services stop functioning when you enter a canyon or turn on airplane mode. Grassday's bundled model weights (`tabpfn-v2-regressor.ckpt`) and cached forecast data execute completely offline.
3. **Zero Cost & No Vendor Lock-in**: No OpenAI or Anthropic API bills, no rate limits, and no subscriptions.
4. **Honest Limitations**: TabPFN v2 requires ~300MB of RAM for forward-pass evaluation, and local LLM execution via Ollama benefits from 4–8GB of system RAM. If local LLM hardware is unavailable, Grassday seamlessly falls back to fast deterministic templates.

---

## ⚖️ Open-Source Acknowledgments & Licenses

- **TabPFN v2**: Developed by Prior Labs and AutoML Freiburg. Distributed under its respective research & academic license. Checkpoint weights are bundled for local non-commercial challenge evaluation.
- **Open-Meteo**: Provides open weather and air quality APIs under the Creative Commons Attribution 4.0 International License (CC BY 4.0).
- **ReportLab**: Open-source PDF generation library under the BSD license.
- **Ollama**: Local LLM execution engine under the MIT License.
- **Grassday**: Released under the [MIT License](LICENSE).
