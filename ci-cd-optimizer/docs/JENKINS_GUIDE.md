# 🚀 Jenkins Integration Guide

## 1. Architecture Explanation
(Same as before...)

## 2. Jenkins Setup Guide
(Same as before...)

### Step 3: Create a Test Job (Updated for Windows)
1.  Dashboard -> **New Item** -> **Pipeline** -> Name it `test-job`.
2.  Scroll to **Pipeline** section and paste this script:
    ```groovy
    pipeline {
        agent any
        stages {
            stage('Build') {
                steps {
                    echo 'Building...'
                    // Robust delay for Windows (ping localhost)
                    bat 'ping 127.0.0.1 -n 20 > nul' 
                }
            }
            stage('Test') {
                steps {
                    echo 'Testing...'
                    bat 'ping 127.0.0.1 -n 10 > nul'
                }
            }
        }
    }
    ```
3.  Save and click **Build Now**.
