import logging
from database import save_build, save_stages, get_job_statistics, init_db
from log_parser import LogIntelligenceEngine

# Initialize DB
init_db()

class RegressionEngine:
    """
    Engine 3: Mathematical Regression Detection
    """
    def detect(self, current_duration, stats):
        avg = stats['avg_duration']
        std_dev = stats['std_dev']
        
        if avg == 0:
            return None # No baseline
            
        # 1. Z-Score Calculation (How many sigmas away?)
        deviation = current_duration - avg
        z_score = deviation / std_dev if std_dev > 0 else 0
        
        # Threshold: > 1.3 Sigma is suspicious, > 2 Sigma is a definite regression
        is_regression = z_score > 1.3
        
        return {
            "is_regression": is_regression,
            "baseline_avg": round(avg, 2),
            "current_duration": round(current_duration, 2),
            "deviation_seconds": round(deviation, 2),
            "increase_percent": round((deviation / avg) * 100, 1),
            "z_score": round(z_score, 2)
        }

class EfficiencyEngine:
    """
    Engine 7: Weighted Efficiency Scoring
    """
    def calculate(self, duration, stats, status, regression_data):
        # Base Components
        SPEED_WEIGHT = 0.4
        RELIABILITY_WEIGHT = 0.3
        STABILITY_WEIGHT = 0.3
        
        # 1. Reliability Score (Based on failure rate)
        fail_rate = stats['failure_rate']
        reliability_score = max(0, 100 - (fail_rate * 2)) # e.g., 10% fail rate = 80 score
        
        # 2. Stability Score (Based on regression)
        stability_score = 100
        if regression_data and regression_data['is_regression']:
            # Penalty based on severity (Z-Score)
            z = regression_data['z_score']
            penalty = min(100, z * 20) # 2 sigma = 40 point penalty
            stability_score -= penalty
            
        # 3. Speed Score (Comparison to arbitrary "Golden" standard or self-improvement)
        # For now, relative to Avg. If faster than avg, > 50. If slower, < 50.
        speed_score = 50 
        if stats['avg_duration'] > 0:
             ratio = stats['avg_duration'] / max(0.1, duration)
             speed_score = min(100, 50 * ratio) 
             
        # Build Failure Override
        if status != 'SUCCESS':
            total_score = 10 
        else:
            total_score = (speed_score * SPEED_WEIGHT) + \
                          (reliability_score * RELIABILITY_WEIGHT) + \
                          (stability_score * STABILITY_WEIGHT)

        return {
            "total_score": int(total_score),
            "breakdown": {
                "speed": int(speed_score),
                "reliability": int(reliability_score),
                "stability": int(stability_score)
            }
        }

class RiskEngine:
    """
    Engine 8: Failure Risk Prediction
    """
    def predict(self, stats, regression_data, detected_issues):
        probability = 10 # Base risk
        reasons = []
        
        # Factor 1: High Failure Rate
        if stats['failure_rate'] > 20:
            probability += 30
            reasons.append("High historical failure rate (>20%)")
            
        # Factor 2: Regression Trend
        if regression_data and regression_data['is_regression']:
            probability += 20
            reasons.append("Performance regression detected")
            
        # Factor 3: Open Issues
        if detected_issues:
            probability += 25
            reasons.append(f"{len(detected_issues)} active root cause patterns found")
            
        risk_level = "LOW"
        if probability > 75: risk_level = "CRITICAL"
        elif probability > 50: risk_level = "HIGH"
        elif probability > 25: risk_level = "MEDIUM"
        
        return {
            "risk_level": risk_level,
            "probability": min(100, probability),
            "reasons": reasons
        }

class StageAnalysisEngine:
    """
    Engine 1 & 2: Stage Level Regression & Impact Analysis
    """
    def analyze(self, current_stages, job_name):
        from database import get_stage_history
        
        # 1. Fetch History
        history_map = get_stage_history(job_name, limit=10)
        
        # 2. Calculate Baselines per Stage Name
        baselines = {}
        for b_num, stages in history_map.items():
            for s in stages:
                name = s['name']
                if name not in baselines:
                    baselines[name] = []
                baselines[name].append(s['duration'])
                
        stage_metrics = []
        total_duration = sum(s['durationMillis'] for s in current_stages) / 1000.0 or 1.0 # Avoid div/0
        
        for s in current_stages:
            name = s['name']
            curr_duration = s['durationMillis'] / 1000.0
            
            # Baseline Stats
            history_vals = baselines.get(name, [])
            avg = sum(history_vals) / len(history_vals) if history_vals else 0
            
            # Regression Logic
            is_regression = False
            regression_pct = 0
            if avg > 1.0 and curr_duration > (avg * 1.3): # 30% threshold
                is_regression = True
                regression_pct = int(((curr_duration - avg) / avg) * 100)
                
            # Impact Logic
            impact_pct = int((curr_duration / total_duration) * 100)
            
            stage_metrics.append({
                "name": name,
                "duration": round(curr_duration, 2),
                "baseline": round(avg, 2),
                "regression_pct": regression_pct if is_regression else 0,
                "impact_pct": impact_pct,
                "status": "REGRESSION" if is_regression else "HEALTHY"
            })
            
        return stage_metrics

def analyze_pipeline_v2(data):
    """
    Orchestrator for v3 Analyzer Engines.
    """
    if not data: return None

    # Extraction
    job_name = data.get('job_name', 'Unknown')
    build_num = data.get('build_number', 0)
    status = data.get('status', 'UNKNOWN')
    duration = data.get('duration_seconds', 0)
    stages_raw = data.get('stages', [])
    
    # --- ENGINE EXECUTION ---
    
    # 1. Historical Baseline
    stats = get_job_statistics(job_name)
    
    # 2. Log Intelligence
    log_engine = LogIntelligenceEngine()
    detected_issues = log_engine.analyze_log(data.get('console_log', ''))
    
    # 3. Regression Detection (Job Level)
    reg_engine = RegressionEngine()
    regression_data = reg_engine.detect(duration, stats)
    
    # 4. Stage Level Analysis (NEW)
    stage_engine = StageAnalysisEngine()
    stage_breakdown = stage_engine.analyze(stages_raw, job_name)
    
    # 5. Efficiency Scoring
    eff_engine = EfficiencyEngine()
    score_data = eff_engine.calculate(duration, stats, status, regression_data)
    
    # 6. Risk Prediction
    risk_engine = RiskEngine()
    risk_data = risk_engine.predict(stats, regression_data, detected_issues)
    
    # --- PERSISTENCE ---
    build_id = save_build(job_name, build_num, status, duration, score_data['total_score'])
    if build_id:
        save_stages(build_id, stages_raw)

    # --- FINAL PAYLOAD ---
    return {
        'job_name': job_name,
        'build_number': build_num,
        'status': status,
        'total_duration': duration,
        'stages': stages_raw,
        'stage_analysis': stage_breakdown, # NEW
        
        # New Engine Outputs
        'efficiency': score_data,
        'regression': regression_data,
        'risk': risk_data,
        'issues': detected_issues,
        'stats': stats
    }

