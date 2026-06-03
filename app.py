from flask import Flask, render_template, request, jsonify
import sqlite3, os
from datetime import date, timedelta, datetime

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), 'fitness.db')

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            name TEXT DEFAULT 'User',
            height_cm REAL DEFAULT 170,
            weight_kg REAL DEFAULT 70,
            age INTEGER DEFAULT 25,
            gender TEXT DEFAULT 'male',
            goal_steps INTEGER DEFAULT 10000,
            goal_water_ml INTEGER DEFAULT 2500,
            goal_calories INTEGER DEFAULT 500,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO profile (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS daily_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL DEFAULT (date('now')),
            steps INTEGER DEFAULT 0,
            calories_burned REAL DEFAULT 0,
            water_ml INTEGER DEFAULT 0,
            workout_minutes INTEGER DEFAULT 0,
            workout_type TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(log_date)
        );

        CREATE TABLE IF NOT EXISTS water_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL DEFAULT (date('now')),
            amount_ml INTEGER NOT NULL,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL DEFAULT (date('now')),
            exercise_type TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            intensity TEXT DEFAULT 'medium',
            calories_burned REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bmi_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight_kg REAL NOT NULL,
            height_cm REAL NOT NULL,
            bmi REAL NOT NULL,
            recorded_at TEXT DEFAULT (date('now'))
        );
        ''')
        conn.commit()

# ── Helpers ───────────────────────────────────────────────────────────────────
def calc_bmi(weight, height_cm):
    h = height_cm / 100
    return round(weight / (h * h), 1)

def bmi_category(bmi):
    if bmi < 18.5: return 'Underweight', '#3B82F6'
    if bmi < 25:   return 'Normal weight', '#43D9AD'
    if bmi < 30:   return 'Overweight', '#F59E0B'
    return 'Obese', '#ef4444'

def steps_to_calories(steps, weight_kg):
    """0.04 kcal per step per 70kg baseline, scaled by weight"""
    return round(steps * 0.04 * (weight_kg / 70), 1)

def get_streak():
    with get_db() as conn:
        rows = conn.execute("SELECT log_date FROM daily_log WHERE active=1 ORDER BY log_date DESC").fetchall()
        if not rows: return 0
        streak = 0
        today = date.today()
        for i, r in enumerate(rows):
            d = date.fromisoformat(r['log_date'])
            if d == today - timedelta(days=i):
                streak += 1
            else:
                break
        return streak

def get_or_create_today():
    with get_db() as conn:
        today = str(date.today())
        row = conn.execute("SELECT * FROM daily_log WHERE log_date=?", (today,)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO daily_log (log_date) VALUES (?)", (today,))
            conn.commit()
            row = conn.execute("SELECT * FROM daily_log WHERE log_date=?", (today,)).fetchone()
        return dict(row)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

# Profile
@app.route('/api/profile', methods=['GET','PUT'])
def profile():
    with get_db() as conn:
        if request.method == 'PUT':
            d = request.json
            conn.execute('''UPDATE profile SET name=?,height_cm=?,weight_kg=?,age=?,gender=?,
                goal_steps=?,goal_water_ml=?,goal_calories=?,updated_at=CURRENT_TIMESTAMP WHERE id=1''',
                (d.get('name','User'), d['height_cm'], d['weight_kg'], d.get('age',25),
                 d.get('gender','male'), d.get('goal_steps',10000),
                 d.get('goal_water_ml',2500), d.get('goal_calories',500)))
            # Log BMI
            bmi = calc_bmi(d['weight_kg'], d['height_cm'])
            conn.execute("INSERT INTO bmi_history (weight_kg,height_cm,bmi) VALUES (?,?,?)",
                         (d['weight_kg'], d['height_cm'], bmi))
            conn.commit()
            return jsonify({'success': True, 'bmi': bmi})
        row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
        p = dict(row)
        p['bmi'] = calc_bmi(p['weight_kg'], p['height_cm'])
        cat, color = bmi_category(p['bmi'])
        p['bmi_category'] = cat
        p['bmi_color'] = color
        return jsonify(p)

# Dashboard (today summary)
@app.route('/api/dashboard')
def dashboard():
    today = get_or_create_today()
    with get_db() as conn:
        profile = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
        water_today = conn.execute("SELECT COALESCE(SUM(amount_ml),0) as total FROM water_entries WHERE log_date=?", (str(date.today()),)).fetchone()['total']
        water_entries = conn.execute("SELECT * FROM water_entries WHERE log_date=? ORDER BY logged_at", (str(date.today()),)).fetchall()
        workouts_today = conn.execute("SELECT * FROM workouts WHERE log_date=? ORDER BY logged_at", (str(date.today()),)).fetchall()
        streak = get_streak()
        bmi = calc_bmi(profile['weight_kg'], profile['height_cm'])
        cat, color = bmi_category(bmi)
        bmi_hist = conn.execute("SELECT bmi, recorded_at FROM bmi_history ORDER BY id DESC LIMIT 10").fetchall()
        step_cal = steps_to_calories(today['steps'], profile['weight_kg'])
        workout_cal = sum(w['calories_burned'] for w in workouts_today)
        total_cal = round(step_cal + workout_cal, 1)
        return jsonify({
            'today': today,
            'profile': profile,
            'water_today': water_today,
            'water_entries': [dict(w) for w in water_entries],
            'workouts_today': [dict(w) for w in workouts_today],
            'streak': streak,
            'bmi': bmi, 'bmi_category': cat, 'bmi_color': color,
            'bmi_history': [dict(b) for b in bmi_hist],
            'step_calories': step_cal,
            'total_calories': total_cal
        })

# Steps
@app.route('/api/steps', methods=['POST'])
def log_steps():
    d = request.json
    steps = int(d.get('steps', 0))
    today = str(date.today())
    with get_db() as conn:
        profile = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
        cal = steps_to_calories(steps, profile['weight_kg'])
        conn.execute("INSERT OR IGNORE INTO daily_log (log_date) VALUES (?)", (today,))
        conn.execute("UPDATE daily_log SET steps=?, active=1 WHERE log_date=?", (steps, today))
        conn.commit()
        return jsonify({'steps': steps, 'calories': cal,
                        'goal': profile['goal_steps'],
                        'pct': min(100, round(steps/profile['goal_steps']*100))})

# Water
@app.route('/api/water', methods=['POST'])
def log_water():
    d = request.json
    amount = int(d.get('amount_ml', 250))
    today = str(date.today())
    with get_db() as conn:
        profile = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
        conn.execute("INSERT INTO water_entries (log_date, amount_ml) VALUES (?,?)", (today, amount))
        conn.execute("INSERT OR IGNORE INTO daily_log (log_date) VALUES (?)", (today,))
        conn.execute("UPDATE daily_log SET active=1 WHERE log_date=?", (today,))
        conn.commit()
        total = conn.execute("SELECT COALESCE(SUM(amount_ml),0) as t FROM water_entries WHERE log_date=?", (today,)).fetchone()['t']
        return jsonify({'total_ml': total, 'goal_ml': profile['goal_water_ml'],
                        'pct': min(100, round(total/profile['goal_water_ml']*100))})

# Workout
EXERCISE_MET = {
    'Running': 9.8, 'Walking': 3.5, 'Cycling': 7.5, 'Swimming': 8.0,
    'Yoga': 2.5, 'HIIT': 12.0, 'Weight Training': 5.0, 'Dancing': 5.5,
    'Basketball': 7.0, 'Soccer': 8.0, 'Tennis': 7.3, 'Other': 5.0
}
@app.route('/api/workout', methods=['POST'])
def log_workout():
    d = request.json
    ex = d.get('exercise_type', 'Other')
    mins = int(d.get('duration_minutes', 30))
    intensity = d.get('intensity', 'medium')
    today = str(date.today())
    with get_db() as conn:
        profile = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
        met = EXERCISE_MET.get(ex, 5.0)
        intensity_mul = {'low': 0.75, 'medium': 1.0, 'high': 1.3}.get(intensity, 1.0)
        cal = round(met * intensity_mul * profile['weight_kg'] * (mins / 60), 1)
        conn.execute("INSERT INTO workouts (log_date,exercise_type,duration_minutes,intensity,calories_burned,notes) VALUES (?,?,?,?,?,?)",
                     (today, ex, mins, intensity, cal, d.get('notes','')))
        conn.execute("INSERT OR IGNORE INTO daily_log (log_date) VALUES (?)", (today,))
        conn.execute("UPDATE daily_log SET workout_minutes=workout_minutes+?,workout_type=?,active=1 WHERE log_date=?",
                     (mins, ex, today))
        conn.commit()
        return jsonify({'calories': cal, 'exercise': ex, 'minutes': mins})

# Weekly data
@app.route('/api/weekly')
def weekly():
    today = date.today()
    dates = [str(today - timedelta(days=i)) for i in range(6,-1,-1)]
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM daily_log WHERE log_date >= ? ORDER BY log_date", (dates[0],)).fetchall()
        by_date = {r['log_date']: dict(r) for r in rows}
        result = []
        profile = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
        for d in dates:
            log = by_date.get(d, {})
            water = conn.execute("SELECT COALESCE(SUM(amount_ml),0) as t FROM water_entries WHERE log_date=?", (d,)).fetchone()['t']
            steps = log.get('steps', 0)
            cal = round(steps_to_calories(steps, profile['weight_kg']) + log.get('calories_burned', 0), 1)
            result.append({'date': d, 'steps': steps, 'water_ml': water, 'calories': cal, 'active': log.get('active', 0)})
        return jsonify(result)

# BMI history
@app.route('/api/bmi/history')
def bmi_history():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM bmi_history ORDER BY id DESC LIMIT 20").fetchall()
        return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5003)
