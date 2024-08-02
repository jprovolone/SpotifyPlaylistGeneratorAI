from flask import Flask, request, render_template_string, jsonify, session, redirect, url_for
import threading
import queue
import uuid
from io import StringIO
import sys
from functools import wraps
from main import run_playlist_generator
import logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = '01J49M47GZYV0NETTJCPKE5DHJ'

HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spotify Playlist Generator</title>
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --input-bg: #f0f0f0;
            --button-bg: #1DB954;
            --button-text: #ffffff;
            --card-bg: #ffffff;
            --border-color: #e0e0e0;
        }
        [data-theme="dark"] {
            --bg-color: #121212;
            --text-color: #ffffff;
            --input-bg: #2a2a2a;
            --button-bg: #1DB954;
            --button-text: #ffffff;
            --card-bg: #1a1a1a;
            --border-color: #333333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2 {
            text-align: center;
            margin-bottom: 30px;
        }
        form {
            background-color: var(--card-bg);
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], input[type="number"] {
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            background-color: var(--input-bg);
            color: var(--text-color);
        }
        input[type="submit"] {
            background-color: var(--button-bg);
            color: var(--button-text);
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }
        input[type="submit"]:hover {
            background-color: #1ed760;
        }
        pre {
            background-color: var(--input-bg);
            padding: 20px;
            border-radius: 4px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .theme-switch-wrapper {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            margin-bottom: 20px;
        }
        .theme-switch {
            display: inline-block;
            height: 34px;
            position: relative;
            width: 60px;
        }
        .theme-switch input {
            display:none;
        }
        .slider {
            background-color: #ccc;
            bottom: 0;
            cursor: pointer;
            left: 0;
            position: absolute;
            right: 0;
            top: 0;
            transition: .4s;
        }
        .slider:before {
            background-color: #fff;
            bottom: 4px;
            content: "";
            height: 26px;
            left: 4px;
            position: absolute;
            transition: .4s;
            width: 26px;
        }
        input:checked + .slider {
            background-color: #1DB954;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .slider.round {
            border-radius: 34px;
        }
        .slider.round:before {
            border-radius: 50%;
        }
        .button-container {
            display: flex;
            justify-content: space-between;
            margin-top: 20px;
        }
        .reset-button {
            background-color: #ff4136;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }
        .reset-button:hover {
            background-color: #ff7066;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="theme-switch-wrapper">
            <label class="theme-switch" for="checkbox">
                <input type="checkbox" id="checkbox" />
                <div class="slider round"></div>
            </label>
            <em>Dark Mode</em>
        </div>

        <h1>Spotify Playlist Generator</h1>
        <form method="post">
            <label for="prompt">Prompt:</label>
            <input type="text" id="prompt" name="prompt" required>

            <label for="length">Number of songs:</label>
            <input type="number" id="length" name="length" value="10" required>

            <label for="name">Playlist name (optional):</label>
            <input type="text" id="name" name="name">

            <input type="submit" value="Generate Playlist">
        </form>

        <div class="button-container">
            <button type="button" class="reset-button" onclick="resetCredentials()">Reset Credentials</button>
        </div>

        <div id="output-container" style="display: none;">
            <h2>Output:</h2>
            <pre id="output"></pre>
        </div>
    </div>

    <script>
        const toggleSwitch = document.querySelector('.theme-switch input[type="checkbox"]');

        function switchTheme(e) {
            if (e.target.checked) {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }    
        }

        toggleSwitch.addEventListener('change', switchTheme, false);

        const currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;
        if (currentTheme) {
            document.documentElement.setAttribute('data-theme', currentTheme);

            if (currentTheme === 'dark') {
                toggleSwitch.checked = true;
            }
        }

        function checkJobStatus(jobId) {
            fetch(`/status/${jobId}/check`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('output-container').style.display = 'block';
                document.getElementById('output').textContent = data.output;
                if (data.status !== 'Complete' && data.status !== 'Error') {
                    setTimeout(() => checkJobStatus(jobId), 5000);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('output').textContent = 'Error checking job status';
            });
        }

        const urlParams = new URLSearchParams(window.location.search);
        const jobId = urlParams.get('job_id');
        if (jobId) {
            checkJobStatus(jobId);
        }

        function resetCredentials() {
            if (confirm("Are you sure you want to reset your credentials? This will remove all saved configuration.")) {
                fetch('/reset_config', {
                    method: 'POST',
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert("Credentials have been reset. You will be redirected to the configuration page.");
                        window.location.href = '/config';
                    } else {
                        alert("Failed to reset credentials. Please try again.");
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert("An error occurred while resetting credentials. Please try again.");
                });
            }
        }
    </script>
</body>
</html>
'''

STATUS_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Status</title>
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --input-bg: #f0f0f0;
            --button-bg: #1DB954;
            --button-text: #ffffff;
            --card-bg: #ffffff;
            --border-color: #e0e0e0;
        }
        [data-theme="dark"] {
            --bg-color: #121212;
            --text-color: #ffffff;
            --input-bg: #2a2a2a;
            --button-bg: #1DB954;
            --button-text: #ffffff;
            --card-bg: #1a1a1a;
            --border-color: #333333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2 {
            text-align: center;
        }
        pre {
            background-color: var(--input-bg);
            padding: 20px;
            border-radius: 4px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .status-card {
            background-color: var(--card-bg);
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }
        .theme-switch-wrapper {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            margin-bottom: 20px;
        }
        .theme-switch {
            display: inline-block;
            height: 34px;
            position: relative;
            width: 60px;
        }
        .theme-switch input {
            display:none;
        }
        .slider {
            background-color: #ccc;
            bottom: 0;
            cursor: pointer;
            left: 0;
            position: absolute;
            right: 0;
            top: 0;
            transition: .4s;
        }
        .slider:before {
            background-color: #fff;
            bottom: 4px;
            content: "";
            height: 26px;
            left: 4px;
            position: absolute;
            transition: .4s;
            width: 26px;
        }
        input:checked + .slider {
            background-color: #1DB954;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .slider.round {
            border-radius: 34px;
        }
        .slider.round:before {
            border-radius: 50%;
        }
        a {
            color: var(--button-bg);
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
    <script>
        function checkStatus() {
            fetch('/status/{{ job_id }}/check', {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('status').textContent = data.status;
                document.getElementById('output').textContent = data.output;
                if (data.status !== 'Complete' && data.status !== 'Error') {
                    setTimeout(checkStatus, 5000);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('status').textContent = 'Error checking status';
            });
        }
        window.onload = function() {
            checkStatus();
            const toggleSwitch = document.querySelector('.theme-switch input[type="checkbox"]');
            const currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;
            if (currentTheme) {
                document.documentElement.setAttribute('data-theme', currentTheme);
                if (currentTheme === 'dark') {
                    toggleSwitch.checked = true;
                }
            }
            toggleSwitch.addEventListener('change', switchTheme, false);
        }
        function switchTheme(e) {
            if (e.target.checked) {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }    
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="theme-switch-wrapper">
            <label class="theme-switch" for="checkbox">
                <input type="checkbox" id="checkbox" />
                <div class="slider round"></div>
            </label>
            <em>Dark Mode</em>
        </div>

        <h1>Job Status</h1>
        <div class="status-card">
            <p>Status: <span id="status">Checking...</span></p>
            <h2>Output:</h2>
            <pre id="output"></pre>
        </div>
        <a href="{{ url_for('index') }}">Back to generator</a>
    </div>
</body>
</html>
'''

CONFIG_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuration - Spotify Playlist Generator</title>
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --input-bg: #f0f0f0;
            --button-bg: #1DB954;
            --button-text: #ffffff;
            --card-bg: #ffffff;
            --border-color: #e0e0e0;
        }
        [data-theme="dark"] {
            --bg-color: #121212;
            --text-color: #ffffff;
            --input-bg: #2a2a2a;
            --button-bg: #1DB954;
            --button-text: #ffffff;
            --card-bg: #1a1a1a;
            --border-color: #333333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
        }
        form {
            background-color: var(--card-bg);
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 10px;
            margin-bottom: 20px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            background-color: var(--input-bg);
            color: var(--text-color);
        }
        input[type="submit"] {
            background-color: var(--button-bg);
            color: var(--button-text);
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }
        input[type="submit"]:hover {
            background-color: #1ed760;
        }
        .error {
            color: #ff4136;
            background-color: #fff5f5;
            border: 1px solid #ff4136;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 20px;
        }
        .theme-switch-wrapper {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            margin-bottom: 20px;
        }
        .theme-switch {
            display: inline-block;
            height: 34px;
            position: relative;
            width: 60px;
        }
        .theme-switch input {
            display:none;
        }
        .slider {
            background-color: #ccc;
            bottom: 0;
            cursor: pointer;
            left: 0;
            position: absolute;
            right: 0;
            top: 0;
            transition: .4s;
        }
        .slider:before {
            background-color: #fff;
            bottom: 4px;
            content: "";
            height: 26px;
            left: 4px;
            position: absolute;
            transition: .4s;
            width: 26px;
        }
        input:checked + .slider {
            background-color: #1DB954;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .slider.round {
            border-radius: 34px;
        }
        .slider.round:before {
            border-radius: 50%;
        }
        .button-container {
            display: flex;
            justify-content: space-between;
        }
        .reset-button {
            background-color: #ff4136;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s ease;
        }
        .reset-button:hover {
            background-color: #ff7066;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="theme-switch-wrapper">
            <label class="theme-switch" for="checkbox">
                <input type="checkbox" id="checkbox" />
                <div class="slider round"></div>
            </label>
            <em>Dark Mode</em>
        </div>

        <h1>Configuration</h1>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <label for="client_id">Spotify Client ID:</label>
            <input type="text" id="client_id" name="client_id" required>

            <label for="client_secret">Spotify Client Secret:</label>
            <input type="password" id="client_secret" name="client_secret" required>

            <label for="redirect_uri">Spotify Redirect URI:</label>
            <input type="text" id="redirect_uri" name="redirect_uri" required>

            <label for="openai_key">OpenAI API Key:</label>
            <input type="password" id="openai_key" name="openai_key" required>

            <div class="button-container">
                <input type="submit" value="Save Configuration">
                <button type="button" class="reset-button" onclick="resetCredentials()">Reset Credentials</button>
            </div>
        </form>
    </div>

    <script>
        const toggleSwitch = document.querySelector('.theme-switch input[type="checkbox"]');

        function switchTheme(e) {
            if (e.target.checked) {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }    
        }

        toggleSwitch.addEventListener('change', switchTheme, false);

        const currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : null;
        if (currentTheme) {
            document.documentElement.setAttribute('data-theme', currentTheme);

            if (currentTheme === 'dark') {
                toggleSwitch.checked = true;
            }
        }

        function resetCredentials() {
            if (confirm("Are you sure you want to reset your credentials? This will remove all saved configuration.")) {
                fetch('/reset_config', {
                    method: 'POST',
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert("Credentials have been reset. You will be redirected to the configuration page.");
                        window.location.href = '/config';
                    } else {
                        alert("Failed to reset credentials. Please try again.");
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert("An error occurred while resetting credentials. Please try again.");
                });
            }
        }
    </script>
</body>
</html>
'''

job_queue = queue.Queue()
job_results = {}

def worker():
    logging.info("Worker thread started")
    while True:
        try:
            job = job_queue.get(timeout=1)  # Wait for 1 second before checking again
            if job is None:
                break
            job_id, prompt, length, name, config = job
            
            logging.info(f"Processing job {job_id}")
            job_results[job_id] = {'status': 'In Progress', 'output': 'Starting playlist generation...'}
            
            # Capture stdout and stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = sys.stderr = output = StringIO()
            
            try:
                logging.info(f"Running playlist generator for job {job_id}")
                print(f"Received job: prompt='{prompt}', length={length}, name='{name}'")
                print("Checking credentials...")
                for key, value in config.items():
                    print(f"{key}: {'*' * len(value)}")  # Print asterisks instead of actual values for security
                
                result = run_playlist_generator(prompt, length, name, config)
                output.write(result)
                job_results[job_id] = {'status': 'Complete', 'output': output.getvalue()}
            except Exception as e:
                error_message = f"An error occurred: {str(e)}"
                logging.error(f"Error in job {job_id}: {error_message}")
                print(error_message)
                print(f"Exception details: {repr(e)}")
                output.write(error_message)
                job_results[job_id] = {'status': 'Error', 'output': output.getvalue()}
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            job_queue.task_done()
        except queue.Empty:
            continue  # If no job is available, continue the loop
        except Exception as e:
            logging.error(f"Unexpected error in worker: {str(e)}")

# Start worker thread
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

def config_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not all(key in session for key in ['client_id', 'client_secret', 'redirect_uri', 'openai_key']):
            logging.warning("Missing configuration. Redirecting to config page.")
            return redirect(url_for('config'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@config_required
def index():
    if request.method == 'POST':
        prompt = request.form['prompt']
        length = int(request.form['length'])
        name = request.form['name'] if request.form['name'] else None
        
        job_id = str(uuid.uuid4())
        logging.info(f"Creating new job {job_id}")
        job_queue.put((job_id, prompt, length, name, dict(session)))
        return redirect(url_for('index', job_id=job_id))
    
    return render_template_string(HTML)

@app.route('/status/<job_id>')
@config_required
def status(job_id):
    return render_template_string(STATUS_HTML, job_id=job_id)

@app.route('/status/<job_id>/check')
@config_required
def check_status(job_id):
    logging.info(f"Checking status for job {job_id}")
    if job_id in job_results:
        return jsonify(job_results[job_id])
    else:
        return jsonify({'status': 'Queued', 'output': 'Job is queued and waiting to start...\nPlease wait, this may take a few moments.'})

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        session['client_id'] = request.form['client_id']
        session['client_secret'] = request.form['client_secret']
        session['redirect_uri'] = request.form['redirect_uri']
        session['openai_key'] = request.form['openai_key']
        logging.info("Credentials saved to session.")
        return redirect(url_for('index'))
    return render_template_string(CONFIG_HTML, error=request.args.get('error'))

@app.route('/reset_config', methods=['POST'])
def reset_config():
    for key in ['client_id', 'client_secret', 'redirect_uri', 'openai_key']:
        session.pop(key, None)
    logging.info("Credentials reset.")
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=True, use_reloader=False)
