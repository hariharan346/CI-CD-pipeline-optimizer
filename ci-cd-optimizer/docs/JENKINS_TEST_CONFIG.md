# 🧪 Jenkins Test Configuration & Pipeline Script (Updated)

Use this **Self-Configuring Pipeline** to verify every feature of your CI/CD Optimizer v2. It allows you to simulate successes, failures, slow builds, and specific error types (Docker, Timeout, Network) on demand.

## 1. Updated Pipeline Script

Paste this into your existing `test-job` configuration. It now includes the `parameters {}` block, so Jenkins will automatically configure the job UI after one run.

```groovy
pipeline {
    agent any
    
    // Auto-Configure Parameters in Jenkins UI
    parameters {
        booleanParam(name: 'SIMULATE_SLOW_BUILD', defaultValue: false, description: 'Triggers a slow build (>25s) to cause a regression warning')
        booleanParam(name: 'SIMULATE_FAILURE', defaultValue: false, description: 'Fails the build instantly')
        booleanParam(name: 'SIMULATE_DOCKER_ERROR', defaultValue: false, description: 'Training scenario: Simulates Docker socket error')
        booleanParam(name: 'SIMULATE_TIMEOUT', defaultValue: false, description: 'Training scenario: Simulates a hung process timeout')
    }
    
    options {
        timeout(time: 5, unit: 'MINUTES')
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo "Checking out source code..."
                sleep 2 
            }
        }
        
        stage('Build') {
            steps {
                script {
                    if (params.SIMULATE_DOCKER_ERROR) {
                        echo "Starting Docker build..."
                        sleep 2
                        error "DockerException: Cannot connect to the Docker daemon. Is the docker daemon running?"
                    }
                    if (params.SIMULATE_SLOW_BUILD) {
                        echo "Running heavy build process..."
                        // Windows: ping localhost -n 25 (approx 24s)
                        if (isUnix()) {
                            sh 'sleep 25'
                        } else {
                            bat 'ping 127.0.0.1 -n 25 > nul'
                        }
                    } else {
                        echo "Standard build..."
                        sleep 2
                    }
                }
            }
        }
        
        stage('Test') {
            steps {
                script {
                    if (params.SIMULATE_FAILURE) {
                        echo "Running tests..."
                        sleep 3
                        error "Tests failed: 5 failures, 0 errors. See reports for details."
                    }
                    if (params.SIMULATE_TIMEOUT) {
                        echo "This stage is hanging..."
                        sleep 5
                        error "TimeoutException: Build timed out (after 5 minutes)."
                    }
                    echo "All tests passed!"
                }
            }
        }
        
        stage('Deploy') {
            steps {
                echo "Deploying to Staging..."
                sleep 2
            }
        }
    }
}
```

## 2. Updated Verification Steps

1.  **Run Once**: Save the new script and run the job once. It will likely run as a standard build.
2.  **Run with Parameters**: Now perform a "Build with Parameters" to trigger specific scenarios.

| Scenario | Check This Box | Expected Result in Localhost App |
| :--- | :--- | :--- |
| **Healthy Build** | (None) | **Efficiency Score: 100** (Green) ✅ |
| **Regression** | `SIMULATE_SLOW_BUILD` | **"Performance Regression" Warning** ⚠️ & Score drops (~70) |
| **RCA: Docker** | `SIMULATE_DOCKER_ERROR` | **CRITICAL Suggestion**: "Enable Docker BuildKit" snippet 🐳 |
| **RCA: Timeout** | `SIMULATE_TIMEOUT` | **CRITICAL Suggestion**: "Increase Timeout Limit" snippet ⏱️ |
| **Build Failure** | `SIMULATE_FAILURE` | **Status: FAILURE** ❌ |
