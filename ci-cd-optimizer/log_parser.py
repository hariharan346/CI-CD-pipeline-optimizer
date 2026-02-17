import re
import logging

class LogIntelligenceEngine:
    """
    Parses Jenkins console logs to identify specific failure patterns and root causes.
    """
    
    PATTERNS = {
        "TIMEOUT": {
            "regex": [r"TimeoutException", r"Build timed out", r"Aborted by timeout"],
            "cause": "Pipeline Timeout",
            "suggestion": "Increase timeout limit or optimize slow stages."
        },
        "NETWORK": {
            "regex": [r"Connection refused", r"502 Bad Gateway", r"Could not resolve host", r"Network is unreachable"],
            "cause": "Network/Connectivity Issue",
            "suggestion": "Check network configuration, proxy settings, or external service availability."
        },
        "DOCKER": {
            "regex": [r"DockerException", r"Cannot connect to the Docker daemon", r"docker: command not found"],
            "cause": "Docker Infrastructure Failure",
            "suggestion": "Ensure Docker daemon is running and the agent has permissions."
        },
        "DEPENDENCY_NODE": {
            "regex": [r"npm ERR!", r"yarn error", r"Module not found"],
            "cause": "Node.js Dependency Failure",
            "suggestion": "Check package.json, clean cache (npm cache clean --force), or check registry."
        },
        "DEPENDENCY_PYTHON": {
            "regex": [r"pip install failed", r"No matching distribution found", r"ModuleNotFoundError"],
            "cause": "Python Dependency Failure",
            "suggestion": "Check requirements.txt and PyPI connectivity."
        },
        "TEST_FAILURE": {
            "regex": [r"Tests failed", r"AssertionError", r"1\) Failure", r"FAILuates"],
            "cause": "Unit/Integration Test Failure",
            "suggestion": "Review test logs and fix the failing test cases."
        }
    }

    def analyze_log(self, console_text):
        """
        Scans values for patterns.
        Returns list of found issues: [{'type': 'TIMEOUT', 'cause': '...', 'suggestion': '...'}, ...]
        """
        issues = []
        if not console_text:
            return issues

        for issue_type, rules in self.PATTERNS.items():
            for pattern in rules["regex"]:
                if re.search(pattern, console_text, re.IGNORECASE):
                    issues.append({
                        "type": issue_type,
                        "cause": rules["cause"],
                        "suggestion": rules["suggestion"],
                        "confidence": 1.0 # Regex matches are high confidence
                    })
                    break # Found one match for this category, move to next category
        
        return issues
