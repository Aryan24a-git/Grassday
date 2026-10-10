---
title: "Grassday 🌿: An Offline-First AI Companion That Tells You Exactly When to Go Outside"
published: false
description: "My submission for the DEV Hacktoberfest Open-Source AI Challenge. Grassday uses TabPFN and a local LLM to predict your perfect outdoor window so you can leave your screen behind."
tags: "ai, hacktoberfest, python, react, tabpfn"
---

## What I Built

**Grassday** is a local-first, privacy-respecting web app designed to minimize your screen time and maximize your time outdoors. 

Instead of forcing you to scroll through weather dashboards trying to guess the best time for a walk, Grassday gives you the answer in one glance. It learns your unique biometeorological preferences (e.g., do you love a crisp 15°C morning, or a warm 25°C afternoon with low wind?) using a local **TabPFN** regression model. It then generates a context-aware nudge using an offline **Ollama** LLM (like Qwen2.5 or Llama-3.2) and creates a printable PDF field card so you can literally leave your phone behind.

**Theme:** Touch Grass
**Track:** Best Use of TabPFN

## Demo

Here is Grassday in action:

*(Insert link to a short Loom/YouTube video here showing the UI, logging an outing, and downloading the PDF card)*

![Grassday Hero UI](https://raw.githubusercontent.com/yourusername/grassday/main/docs/hero_screenshot.png)
*(Replace with actual GitHub raw link to your screenshot)*

**Repository:** [Link to your GitHub repo here]

### How to test it right now (Demo Mode)
If you want to run this locally without spending weeks logging data, I built an offline Demo Mode. It seeds a SQLite database with 25 realistic outings from a synthetic user who secretly prefers 18–24°C, low wind, and no rain.
```bash
# Clone the repo and start the backend
pip install -r requirements.txt
python -m uvicorn api:app --host 127.0.0.1 --port 8000
# (Run python demo.py to seed the database instantly)

# Start the frontend
cd frontend
npm install
npm run dev
```

## My Journey

When I saw the "Touch Grass" theme, my immediate thought was the irony of building software that keeps you staring at a screen to figure out how to go outside. My core design principle became: *"The screen must be the shortest part of the experience."* 

To achieve this, the UI had to be instantly decisive. No infinite scrolling. Just one card, one specific time window, and a nudge.

### The TabPFN Magic
The biggest technical hurdle was personalization. Everyone likes different weather. But training a traditional neural network or XGBoost model locally for a single user with only 10-20 data points is notoriously difficult—they overfit instantly.

This is where **TabPFN** blew my mind. Because it's a pre-trained Prior-Data Fitted Network, it acts like a foundation model for tabular data. It performs in-context learning on small datasets in fractions of a second without gradient descent. 

I set up a regression pipeline mapping 14 environmental features (temperature, UV index, PM2.5, wind, daylight fraction, sunset proximity, etc.) to a subjective 1-5 user rating. 

**The Evaluation:**
I wrote a Leave-One-Out Cross-Validation (LOOCV) script (`loocv_eval.py`) against 25 synthetic outings with complex, non-linear preferences. 
- **Naive Baseline MAE** (just guessing the user's average rating): `0.92`
- **Grassday TabPFN MAE**: `0.82`
- **Improvement:** An `11.4%` reduction in absolute error with only 25 rows of data. 

To handle the "Cold Start" problem (when a user has logged 0 outings), I implemented a hybrid biometeorological heuristic. It gently blends TabPFN's predictions with a physical prior that penalizes extreme UV or gale-force winds, ensuring the app is actually useful on Day 1.

### The UI and the PDF Card
I wanted the app to feel like a calm invitation. I built a custom "Living Nature" glassmorphism UI in React + Vite. The app runs completely locally via a FastAPI backend, meaning your location and preferences never leave your machine.

Finally, to truly commit to the "Touch Grass" theme, I added a feature that generates a beautiful, printable **PDF Field Card** (using `reportlab`). It includes your window time, weather, and the LLM's suggested things to notice—so you can print it, grab your keys, and leave the glowing rectangle on your desk. 🌿
