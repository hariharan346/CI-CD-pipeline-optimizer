class DecisionEngine:
    """
    Engine 6 & 5: Optimization Decision & Root Cause Mapper
    """
    def __init__(self):
        self.knowledge_base = {
            "DEPENDENCY_NODE": {
                "title": "Enable NPM Caching",
                "impact_factor": 0.4, 
                "snippet": "stage('Install') {\n  steps {\n    sh 'npm ci --cache .npm'\n  }\n}"
            },
            "DEPENDENCY_PYTHON": {
                "title": "Enable Pip Caching",
                "impact_factor": 0.3,
                "snippet": "environment {\n  PIP_CACHE_DIR = \"${WORKSPACE}/.pip-cache\"\n}"
            },
            "DOCKER": {
                "title": "Fix Docker Daemon",
                "impact_factor": 1.0, 
                "snippet": "// Ensure Docker socker is mounted\nargs '-v /var/run/docker.sock:/var/run/docker.sock'"
            },
            "TIMEOUT": {
                "title": "Increase Stage Timeout",
                "impact_factor": 0.0, 
                "snippet": "options {\n    timeout(time: 60, unit: 'MINUTES')\n}"
            },
            "NETWORK": {
                 "title": "Network Retry Logic",
                 "impact_factor": 0.5,
                 "snippet": "retry(3) {\n    sh 'curl -f ...'\n}"
            },
            "TEST_FAILURE": {
                "title": "Quarantine Flaky Tests",
                "impact_factor": 0.0,
                "snippet": "// Mark test stage as unstable but don't fail build\ncatchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {\n    sh 'make test'\n}"
            }
        }

    def generate_plan(self, metrics):
        suggestions = []
        
        # 1. Map Log Issues -> Optimization Actions
        for issue in metrics.get('issues', []):
            issue_type = issue['type']
            action = self.knowledge_base.get(issue_type)
            
            if action:
                # Estimate Impact
                # If we save impact_factor % of the regression deviation?
                # Or just heuristics.
                estimated_saving = "N/A"
                if metrics.get('regression') and metrics['regression']['is_regression']:
                    dev = metrics['regression']['deviation_seconds']
                    if dev > 0:
                        saved = int(dev * action['impact_factor'])
                        estimated_saving = f"~{saved} seconds"

                suggestions.append({
                    'title': f"🔧 {action['title']}",
                    'description': f"Root Cause: {issue['cause']}. Fix this to improve stability.",
                    'confidence': f"{int(issue['confidence'] * 100)}%",
                    'impact': estimated_saving,
                    'severity': 'HIGH',
                    'snippet': action['snippet']
                })
        
        # 2. Regression Suggestions
        reg = metrics.get('regression')
        if reg and reg['is_regression']:
             suggestions.append({
                'title': "⚠️ Regression Detected",
                'description': f"Build is {reg['increase_percent']}% slower than baseline ({reg['baseline_avg']}s).",
                'confidence': "100%",
                'impact': "Variable",
                'severity': 'MEDIUM',
                'snippet': "// Check commit history for heavy changes"
            })
            
        return suggestions

def optimize_pipeline_v2(metrics):
    if not metrics:
        return []

    engine = DecisionEngine()
    return engine.generate_plan(metrics)
