import sqlite3
import json
import logging
from datetime import datetime

DB_NAME = "cicd_optimizer.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Builds Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            build_number INTEGER NOT NULL,
            result TEXT,
            total_duration REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            efficiency_score REAL,
            UNIQUE(job_name, build_number)
        )
    ''')
    
    # 2. Stages Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER,
            name TEXT,
            duration REAL,
            status TEXT,
            FOREIGN KEY(build_id) REFERENCES builds(id)
        )
    ''')
    
    # 3. Log Analysis / RCA Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS log_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER,
            issue_type TEXT,
            root_cause TEXT,
            suggestion TEXT,
            FOREIGN KEY(build_id) REFERENCES builds(id)
        )
    ''')

    conn.commit()
    conn.close()
    logging.info(f"Database {DB_NAME} initialized.")

def save_build(job_name, build_number, result, duration, score=0):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR REPLACE INTO builds (job_name, build_number, result, total_duration, efficiency_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (job_name, build_number, result, duration, score))
        build_id = c.lastrowid
        # If REPLACE happened, lastrowid might be 0 or unexpected depending on sqlite version, 
        # so let's fetch it to be safe.
        if build_id == 0:
             c.execute('SELECT id FROM builds WHERE job_name=? AND build_number=?', (job_name, build_number))
             build_id = c.fetchone()[0]
        conn.commit()
        return build_id
    except Exception as e:
        logging.error(f"Error saving build: {e}")
        return None
    finally:
        conn.close()

def save_stages(build_id, stages):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Clear old stages if any (for updates)
        c.execute('DELETE FROM stages WHERE build_id=?', (build_id,))
        
        for stage in stages:
            c.execute('''
                INSERT INTO stages (build_id, name, duration, status)
                VALUES (?, ?, ?, ?)
            ''', (build_id, stage['name'], stage['durationMillis'] / 1000.0, stage['status']))
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving stages: {e}")
    finally:
        conn.close()

def get_job_history(job_name, limit=10):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM builds 
        WHERE job_name = ? 
        ORDER BY build_number DESC 
        LIMIT ?
    ''', (job_name, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_average_duration(job_name):
    # Legacy wrapper
    stats = get_job_statistics(job_name)
    return stats['avg_duration']

def get_job_statistics(job_name, limit=20):
    """
    Calculates detailed statistics for the "Historical Baseline Engine".
    Returns: {
        'avg_duration': float,
        'std_dev': float,
        'failure_rate': float,
        'total_builds': int
    }
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Fetch last N builds
    c.execute('''
        SELECT result, total_duration FROM builds 
        WHERE job_name = ? 
        ORDER BY build_number DESC 
        LIMIT ?
    ''', (job_name, limit))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return {'avg_duration': 0, 'std_dev': 0, 'failure_rate': 0, 'total_builds': 0}

    total_builds = len(rows)
    failures = sum(1 for r in rows if r['result'] != 'SUCCESS')
    success_durations = [r['total_duration'] for r in rows if r['result'] == 'SUCCESS']
    
    # 1. Failure Rate
    failure_rate = (failures / total_builds) * 100 if total_builds > 0 else 0
    
    # 2. Average & StdDev (only for successful builds)
    if not success_durations:
        return {'avg_duration': 0, 'std_dev': 0, 'failure_rate': failure_rate, 'total_builds': total_builds}
        
    avg = sum(success_durations) / len(success_durations)
    
    # Variance = sum((x - mean)^2) / N
    variance = sum((x - avg) ** 2 for x in success_durations) / len(success_durations)
    std_dev = variance ** 0.5
    
    return {
        'avg_duration': avg,
        'std_dev': std_dev,
        'failure_rate': failure_rate,
        'total_builds': total_builds
    }

def get_stage_history(job_name, limit=10):
    """
    Fetches stage-level data for the last N builds to calculate baselines.
    Returns: Dict organized by build_number -> list of stages
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Get recent build IDs
    c.execute('''
        SELECT id, build_number FROM builds 
        WHERE job_name = ? 
        ORDER BY build_number DESC 
        LIMIT ?
    ''', (job_name, limit))
    builds = c.fetchall()
    
    if not builds:
        conn.close()
        return {}
        
    build_ids = [b['id'] for b in builds]
    placeholders = ','.join('?' for _ in build_ids)
    
    # 2. Get stages for these builds
    query = f'''
        SELECT build_id, name as stage_name, duration as duration_seconds 
        FROM stages 
        WHERE build_id IN ({placeholders})
    '''
    c.execute(query, build_ids)
    stage_rows = c.fetchall()
    conn.close()
    
    # 3. Organize by build_number (via map)
    id_to_number = {b['id']: b['build_number'] for b in builds}
    history = {}
    
    for row in stage_rows:
        b_num = id_to_number.get(row['build_id'])
        if b_num not in history:
            history[b_num] = []
        history[b_num].append({
            'name': row['stage_name'],
            'duration': row['duration_seconds']
        })
        
    return history
