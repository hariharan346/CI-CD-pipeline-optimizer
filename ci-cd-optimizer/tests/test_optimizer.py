import pytest
import json
import os
from analyzer import analyze_pipeline_metrics, load_pipeline_log
from optimizer import optimize_pipeline, analyze_single_job

# Test Data
SAMPLE_DATA = {
    "workflow_run_id": 123,
    "jobs": [
        {"name": "fast-job", "duration_seconds": 5, "steps": []},
        {"name": "slow-test-job", "duration_seconds": 120, "steps": [{"name": "npm install"}]},
        {"name": "very-slow-build", "duration_seconds": 400, "steps": [{"name": "docker build"}]}
    ]
}

def test_analyze_pipeline_metrics():
    metrics = analyze_pipeline_metrics(SAMPLE_DATA)
    assert metrics['total_duration'] == 525
    assert metrics['job_count'] == 3
    assert metrics['slowest_job_name'] == 'very-slow-build'
    assert metrics['slowest_job_duration'] == 400

def test_optimize_pipeline_suggestions():
    suggestions = optimize_pipeline(SAMPLE_DATA)
    assert len(suggestions) == 2  # fast-job (5s) should be ignored

    slow_test = next(s for s in suggestions if s['job_name'] == 'slow-test-job')
    assert slow_test['severity'] == 'HIGH'
    # Should suggest caching because of "npm install" and generic parallelization for "test"
    assert any("Caching" in s for s in slow_test['suggestions'])
    assert any("Parallelization" in s for s in slow_test['suggestions'])

    very_slow = next(s for s in suggestions if s['job_name'] == 'very-slow-build')
    assert very_slow['severity'] == 'CRITICAL'
    assert any("Docker" in s for s in very_slow['suggestions'])

def test_load_pipeline_log_success(tmp_path):
    # Create a temporary file
    d = tmp_path / "test_log.json"
    d.write_text(json.dumps(SAMPLE_DATA))
    
    loaded_data = load_pipeline_log(str(d))
    assert loaded_data == SAMPLE_DATA

def test_load_pipeline_log_not_found():
    loaded_data = load_pipeline_log("non_existent_file.json")
    assert loaded_data is None

def test_empty_log_handling():
    metrics = analyze_pipeline_metrics({})
    assert metrics is None
    suggestions = optimize_pipeline({})
    assert suggestions == []

def test_mixed_duration_formats():
    data = {
        "jobs": [
            {"name": "sec-job", "duration_seconds": 10},
            {"name": "dur-job", "duration": 20},
            {"name": "str-job", "duration": "30"}, # String number
            {"name": "none-job"}
        ]
    }
    metrics = analyze_pipeline_metrics(data)
    assert metrics['total_duration'] == 60 # 10 + 20 + 30
    assert metrics['slowest_job_duration'] == 30

def test_validation_logic():
    from analyzer import validate_pipeline_data
    
    # Valid
    assert validate_pipeline_data({"jobs": []})[0] == True
    
    # Invalid
    assert validate_pipeline_data({})[0] == False
    assert validate_pipeline_data({"jobs": "not-a-list"})[0] == False
    assert validate_pipeline_data("not-a-dict")[0] == False
