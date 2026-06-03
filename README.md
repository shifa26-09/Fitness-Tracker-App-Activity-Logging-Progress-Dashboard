# 💪 FitPulse — Enhanced Fitness Tracker App

A launch-level fitness tracking web app with full backend, beautiful dark UI, and 7 feature modules.

## ✨ Features

### 📊 Dashboard
- Live metrics: steps, water, calories, streak
- Weekly bar charts (steps, calories, hydration)

### 👣 Steps + Auto-Calorie Estimate
- Log step count daily
- Auto-calculates calories: `steps × 0.04 × (weight/70kg)`
- Animated ring progress toward goal
- Quick-add buttons (+1k, +2.5k, +5k)

### 💧 Water Intake Tracker
- Quick-add presets (espresso, glass, can, bottle)
- Visual glass grid (each = 250ml)
- Daily log with timestamps
- Hydration ring with progress bar

### ⚖️ BMI Calculator
- Height + weight → instant BMI with category
- Visual gradient gauge with needle
- BMI history line chart (tracks changes over time)
- Personalised health tip

### 🔥 Streaks Counter
- Counts consecutive days with any activity logged
- 7-day calendar heatmap
- Achievement milestones (3, 7, 14, 30, 100 days)

### 🏋️ Workout Logger
- 12 exercise types (Running, HIIT, Yoga, etc.)
- MET-based calorie calculation (per exercise × intensity × weight)
- Intensity selector (Low / Medium / High)
- Live calorie preview before logging

### 👤 Profile & Goals
- Custom step/water/calorie goals
- Personal stats (height, weight, age, gender)
- Updates BMI history on save

## Setup & Run
```bash
pip install flask
python app.py
```
Open: http://localhost:5003
