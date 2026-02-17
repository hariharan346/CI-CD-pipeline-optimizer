import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from analyzer import analyze_pipeline_v2
from optimizer import optimize_pipeline_v2
from jenkins_fetch import fetch_jenkins_data
from database import get_job_history
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for flash messages

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'json'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', metrics=None, suggestions=None)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the file
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Analyze using v2 logic
                metrics = analyze_pipeline_v2(data)
                suggestions = optimize_pipeline_v2(metrics)
                
                if metrics is None:
                    flash('Error parsing pipeline log metrics.', 'error')
                    return redirect(request.url)

                return render_template('index.html', metrics=metrics, suggestions=suggestions)
            
            except json.JSONDecodeError:
                flash('Invalid JSON file.', 'error')
                return redirect(request.url)
            except Exception as e:
                flash(f'An error occurred: {str(e)}', 'error')
                return redirect(request.url)

    return render_template('index.html', metrics=None, suggestions=None)

@app.route('/fetch_jenkins', methods=['POST'])
def fetch_jenkins():
    try:
        JENKINS_URL = os.environ.get('JENKINS_URL', 'http://localhost:8080')
        JOB_NAME = os.environ.get('JENKINS_JOB_NAME', 'test-job')
        JENKINS_USER = os.environ.get('JENKINS_USER', 'admin')
        JENKINS_TOKEN = os.environ.get('JENKINS_TOKEN', '')

        # 1. Fetch Data (v2)
        data, error_msg = fetch_jenkins_data(JENKINS_URL, JOB_NAME, JENKINS_USER, JENKINS_TOKEN)
        
        if error_msg:
            flash(f"Failed to fetch data: {error_msg}", 'error')
            return redirect(url_for('index'))
            
        if not data:
            flash("No data returned from Jenkins analysis.", 'error')
            return redirect(url_for('index'))

        # 2. Analyze (v2 - DB Save, RCA, Regression)
        metrics = analyze_pipeline_v2(data)
        
        # 3. Optimize (v2 - Snippets)
        suggestions = optimize_pipeline_v2(metrics)
        
        # Save logs for debugging 
        with open('pipeline_log.json', 'w') as f:
           json.dump(data, f, indent=4)

        if metrics is None:
             flash('Error analyzing Jenkins data.', 'error')
             return redirect(url_for('index'))

        # Fetch history for charts
        history = get_job_history(JOB_NAME, limit=20)
        history_data = {
            'labels': [f"#{b['build_number']}" for b in reversed(history)],
            'durations': [b['total_duration'] for b in reversed(history)],
            'scores': [b['efficiency_score'] for b in reversed(history)]
        }

        flash(f"Successfully fetched and analyzed build: {JOB_NAME} #{metrics.get('build_number')}", 'success')
        return render_template('index.html', metrics=metrics, suggestions=suggestions, history=history_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
