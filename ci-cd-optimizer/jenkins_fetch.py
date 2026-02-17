import requests
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _parse_wfapi_data(wfapi_json, job_name, build_number, console_text=""):
    """
    Parses Jenkins WFAPI JSON into our optimized format.
    """
    try:
        stages = []
        for stage in wfapi_json.get('stages', []):
            stages.append({
                'name': stage['name'],
                'status': stage['status'],
                'durationMillis': stage['durationMillis'],
                'startTimeMillis': stage['startTimeMillis'],
                # WFAPI often gives pauseDurationMillis, useful for manual approvals
                'pauseDurationMillis': stage.get('pauseDurationMillis', 0)
            })

        # Calculate total duration from stages or use top-level
        total_duration = sum(s['durationMillis'] for s in stages) / 1000.0

        return {
            "job_name": job_name,
            "build_number": build_number,
            "status": wfapi_json.get('status', 'UNKNOWN'),
            "duration_seconds": total_duration,
            "stages": stages,
            "console_log": console_text
        }
    except Exception as e:
        logging.error(f"Error parsing WFAPI data: {e}")
        return None

def _parse_standard_data(build_data, job_name, console_text=""):
    """
    Fallback parser for standard API response.
    """
    # Use the passed job_name directly to ensure consistency with DB queries
    duration = build_data.get('duration', 0) / 1000.0
    result = build_data.get('result', 'UNKNOWN')
    
    # Create a single "stage" for the whole build
    stages = [{
        'name': 'Full Build',
        'status': result,
        'durationMillis': build_data.get('duration', 0),
        'startTimeMillis': build_data.get('timestamp', 0),
        'pauseDurationMillis': 0
    }]
    
    return {
        "job_name": job_name,
        "build_number": build_data.get('number', 0),
        "status": result,
        "duration_seconds": duration,
        "stages": stages,
        "console_log": console_text
    }

def fetch_jenkins_data(jenkins_url, job_name, username, api_token):
    """
    Fetches rich build data using WFAPI and Console Text.
    Falls back to standard API if WFAPI is not available.
    Returns: (data_dict, error_message)
    """
    try:
        if not jenkins_url.endswith('/'):
            jenkins_url += '/'
        
        auth = (username, api_token) if username and api_token else None
        
        # 1. Get Job Info to find last build number
        job_url = f"{jenkins_url}job/{job_name}/api/json"
        resp = requests.get(job_url, auth=auth, timeout=10)
        if resp.status_code != 200:
             return None, f"Failed to get job info: {resp.status_code}"
             
        last_build = resp.json().get('lastBuild')
        if not last_build:
            return None, "No builds found for this job."
            
        build_number = last_build['number']
        
        # 2. Fetch Console Log (Common for both methods)
        console_url = f"{jenkins_url}job/{job_name}/{build_number}/consoleText"
        logging.info(f"Fetching Console: {console_url}")
        console_resp = requests.get(console_url, auth=auth, timeout=10)
        console_text = console_resp.text if console_resp.status_code == 200 else ""

        # 3. Try Fetching WFAPI (Pipeline Structure)
        wfapi_url = f"{jenkins_url}job/{job_name}/{build_number}/wfapi/describe"
        logging.info(f"Fetching WFAPI: {wfapi_url}")
        
        wfapi_resp = requests.get(wfapi_url, auth=auth, timeout=10)
        
        if wfapi_resp.status_code == 200:
            # Success - Parse WFAPI
            data = _parse_wfapi_data(wfapi_resp.json(), job_name, build_number, console_text)
            return data, None
        else:
            # Fallback to Standard API
            logging.info(f"WFAPI failed ({wfapi_resp.status_code}), falling back to Standard API.")
            build_url = f"{jenkins_url}job/{job_name}/{build_number}/api/json"
            build_resp = requests.get(build_url, auth=auth, timeout=10)
            
            if build_resp.status_code == 200:
                data = _parse_standard_data(build_resp.json(), job_name, console_text)
                return data, None
            else:
                 return None, f"Failed to fetch build data (API & WFAPI both failed): {build_resp.status_code}"

    except requests.exceptions.RequestException as e:
        logging.error(f"Connection Error: {e}")
        return None, f"Jenkins Connection Failed: {e}"
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return None, f"Unexpected Error: {e}"

# Backwards compatibility alias if needed, or we update app.py
fetch_last_build = fetch_jenkins_data
