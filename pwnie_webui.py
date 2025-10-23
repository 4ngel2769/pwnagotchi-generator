#!/usr/bin/env python3
"""
Pwnagotchi Fleet Web UI - Dashboard for monitoring fake pwnies
Real-time web interface with animated "faces" for each pwnie
"""

import os
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

# Configuration
PWNIES_DIR = "./fake_pwnies"
FACES = [
    "(◕‿◕)", "(⌐■_■)", "(ಠ_ಠ)", "(◕‿◕✿)", "(｡◕‿◕｡)",
    "( ͡° ͜ʖ ͡°)", "(づ｡◕‿‿◕｡)づ", "ヽ(°◇° )ノ", "(｡♥‿♥｡)",
    "(>ᴗ<)", "(≧◡≦)", "♥‿♥", "(✿◠‿◠)", "◕‿↼",
    "(ʘ‿ʘ)", "¯\\_(ツ)_/¯", "(☞ﾟヮﾟ)☞", "☜(ﾟヮﾟ☜)", "(¬‿¬)",
    "(◔_◔)", "(•‿•)", "(⊙_⊙)", "(҂◡_◡)", "ᕕ( ᐛ )ᕗ"
]

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pwnie-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global manager reference (set by main())
manager = None


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/pwnies')
def get_pwnies():
    """Get all pwnies status"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    pwnies = manager.list_all()
    
    # Add face to each pwnie
    for pwnie in pwnies:
        pwnie['face'] = FACES[pwnie['id'] % len(FACES)]
    
    return jsonify(pwnies)


@app.route('/api/pwnie/<int:pwnie_id>')
def get_pwnie(pwnie_id):
    """Get specific pwnie details"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    pwnie = manager.get_pwnie_status(pwnie_id)
    
    if not pwnie:
        return jsonify({'error': 'Pwnie not found'}), 404
    
    pwnie['face'] = FACES[pwnie_id % len(FACES)]
    
    # Get Tor info if enabled
    if pwnie['use_tor']:
        pwnie['tor_info'] = manager.get_tor_info(pwnie_id)
    
    return jsonify(pwnie)


@app.route('/api/pwnie/<int:pwnie_id>/boot', methods=['POST'])
def boot_pwnie(pwnie_id):
    """Boot a pwnie"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    success, msg = manager.boot_pwnie(pwnie_id)
    
    if success:
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'success': False, 'message': msg}), 400


@app.route('/api/pwnie/<int:pwnie_id>/shutdown', methods=['POST'])
def shutdown_pwnie(pwnie_id):
    """Shutdown a pwnie"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    success, msg = manager.shutdown_pwnie(pwnie_id)
    
    if success:
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'success': False, 'message': msg}), 400


@app.route('/api/pwnie/<int:pwnie_id>/reboot', methods=['POST'])
def reboot_pwnie(pwnie_id):
    """Reboot a pwnie"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    success, msg = manager.reboot_pwnie(pwnie_id)
    
    if success:
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'success': False, 'message': msg}), 400


@app.route('/api/pwnie/<int:pwnie_id>/addnets', methods=['POST'])
def add_networks(pwnie_id):
    """Add networks to a pwnie"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    data = request.get_json()
    count = data.get('count', 1)
    
    if count < 1 or count > 100:
        return jsonify({'success': False, 'message': 'Count must be between 1 and 100'}), 400
    
    success, msg = manager.add_pwned_networks(pwnie_id, count)
    
    if success:
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'success': False, 'message': msg}), 400


@app.route('/api/pwnie/create', methods=['POST'])
def create_pwnie():
    """Create a new pwnie"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    data = request.get_json()
    name = data.get('name', '')
    pwned = data.get('pwned', 0)
    use_tor = data.get('use_tor', False)
    threads = data.get('threads', 1)
    
    try:
        success, msg = manager.create_pwnie(name=name, pwned=pwned, use_tor=use_tor, threads=threads)
        if success:
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/pwnie/<int:pwnie_id>/edit', methods=['POST'])
def edit_pwnie(pwnie_id):
    """Edit pwnie settings"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    data = request.get_json()
    
    try:
        success, msg = manager.edit_pwnie(pwnie_id, data)
        if success:
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/failsafe/tor', methods=['POST'])
def enable_tor_failsafe():
    """Enable Tor failsafe - stops all non-Tor pwnies, enables Tor, restarts them"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    try:
        success, msg, count = manager.enable_tor_failsafe()
        if success:
            return jsonify({'success': True, 'message': msg, 'count': count})
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Get aggregate stats"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    pwnies = manager.list_all()
    
    stats = {
        'total': len(pwnies),
        'running': sum(1 for p in pwnies if p['running']),
        'stopped': sum(1 for p in pwnies if not p['running']),
        'enrolled': sum(1 for p in pwnies if p['enrolled']),
        'with_tor': sum(1 for p in pwnies if p['use_tor']),
        'total_pwned': sum(p['pwned'] for p in pwnies),
        'total_handshakes': sum(p['handshakes'] for p in pwnies),
        'total_deauths': sum(p['deauths'] for p in pwnies),
        'avg_pwned': sum(p['pwned'] for p in pwnies) / len(pwnies) if pwnies else 0,
    }
    
    return jsonify(stats)


@app.route('/api/stats/history')
def get_stats_history():
    """Get historical stats for graphing"""
    if not manager:
        return jsonify({'error': 'Manager not initialized'}), 500
    
    return jsonify(manager.get_stats_history())


@app.route('/stats')
def stats_page():
    """Stats and graphs page"""
    return render_template('stats.html')


# Real-time updates via WebSocket
def background_updates():
    """Send real-time updates to connected clients"""
    while True:
        time.sleep(2)  # Update every 2 seconds
        
        if manager:
            pwnies = manager.list_all()
            
            # Add faces
            for pwnie in pwnies:
                pwnie['face'] = FACES[pwnie['id'] % len(FACES)]
            
            stats = {
                'total': len(pwnies),
                'running': sum(1 for p in pwnies if p['running']),
                'stopped': sum(1 for p in pwnies if not p['running']),
                'enrolled': sum(1 for p in pwnies if p['enrolled']),
                'with_tor': sum(1 for p in pwnies if p['use_tor']),
                'total_pwned': sum(p['pwned'] for p in pwnies),
                'total_handshakes': sum(p['handshakes'] for p in pwnies),
                'total_deauths': sum(p['deauths'] for p in pwnies),
            }
            
            socketio.emit('update', {
                'pwnies': pwnies,
                'stats': stats,
                'timestamp': datetime.now().isoformat()
            })


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('message', {'data': 'Connected to Pwnie Fleet'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


def create_stats_template():
    """Create the stats page HTML template"""
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    stats_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fleet Statistics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff00; padding: 20px; }
        .header { text-align: center; padding: 20px; border: 2px solid #00ff00; margin-bottom: 20px; background: #111; }
        .header h1 { font-size: 2em; margin-bottom: 10px; text-shadow: 0 0 10px #00ff00; }
        .back-btn { display: inline-block; padding: 10px 20px; border: 2px solid #00ff00; background: transparent; color: #00ff00; text-decoration: none; margin: 20px; }
        .back-btn:hover { background: #00ff00; color: #000; }
        .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; }
        .chart-card { background: #111; border: 2px solid #00ff00; padding: 20px; }
        .chart-title { text-align: center; margin-bottom: 15px; font-size: 1.2em; }
        canvas { max-height: 300px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 FLEET STATISTICS 📊</h1>
        <p>Real-time graphs and metrics</p>
    </div>
    
    <a href="/" class="back-btn">← Back to Dashboard</a>
    
    <div class="charts-grid">
        <div class="chart-card">
            <div class="chart-title">Total Networks Over Time</div>
            <canvas id="networksChart"></canvas>
        </div>
        <div class="chart-card">
            <div class="chart-title">Handshakes Over Time</div>
            <canvas id="handshakesChart"></canvas>
        </div>
        <div class="chart-card">
            <div class="chart-title">Active Pwnies</div>
            <canvas id="activeChart"></canvas>
        </div>
        <div class="chart-card">
            <div class="chart-title">Deauths Over Time</div>
            <canvas id="deauthsChart"></canvas>
        </div>
    </div>
    
    <script>
        const socket = io();
        
        const chartConfig = {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: { ticks: { color: '#00ff00' }, grid: { color: '#333' } },
                x: { ticks: { color: '#00ff00' }, grid: { color: '#333' } }
            },
            plugins: { legend: { labels: { color: '#00ff00' } } }
        };
        
        const networksChart = new Chart(document.getElementById('networksChart'), {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Total Networks', data: [], borderColor: '#00ff00', backgroundColor: 'rgba(0,255,0,0.1)' }] },
            options: chartConfig
        });
        
        const handshakesChart = new Chart(document.getElementById('handshakesChart'), {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Total Handshakes', data: [], borderColor: '#00ccff', backgroundColor: 'rgba(0,204,255,0.1)' }] },
            options: chartConfig
        });
        
        const activeChart = new Chart(document.getElementById('activeChart'), {
            type: 'line',
            data: { labels: [], datasets: [
                { label: 'Running', data: [], borderColor: '#00ff00', backgroundColor: 'rgba(0,255,0,0.1)' },
                { label: 'Stopped', data: [], borderColor: '#ff0000', backgroundColor: 'rgba(255,0,0,0.1)' }
            ]},
            options: chartConfig
        });
        
        const deauthsChart = new Chart(document.getElementById('deauthsChart'), {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Total Deauths', data: [], borderColor: '#ff00ff', backgroundColor: 'rgba(255,0,255,0.1)' }] },
            options: chartConfig
        });
        
        socket.on('update', (data) => {
            const time = new Date().toLocaleTimeString();
            
            // Update networks chart
            networksChart.data.labels.push(time);
            networksChart.data.datasets[0].data.push(data.stats.total_pwned);
            if (networksChart.data.labels.length > 20) {
                networksChart.data.labels.shift();
                networksChart.data.datasets[0].data.shift();
            }
            networksChart.update();
            
            // Update handshakes chart
            handshakesChart.data.labels.push(time);
            handshakesChart.data.datasets[0].data.push(data.stats.total_handshakes);
            if (handshakesChart.data.labels.length > 20) {
                handshakesChart.data.labels.shift();
                handshakesChart.data.datasets[0].data.shift();
            }
            handshakesChart.update();
            
            // Update active chart
            activeChart.data.labels.push(time);
            activeChart.data.datasets[0].data.push(data.stats.running);
            activeChart.data.datasets[1].data.push(data.stats.stopped);
            if (activeChart.data.labels.length > 20) {
                activeChart.data.labels.shift();
                activeChart.data.datasets[0].data.shift();
                activeChart.data.datasets[1].data.shift();
            }
            activeChart.update();
            
            // Update deauths chart
            deauthsChart.data.labels.push(time);
            deauthsChart.data.datasets[0].data.push(data.stats.total_deauths);
            if (deauthsChart.data.labels.length > 20) {
                deauthsChart.data.labels.shift();
                deauthsChart.data.datasets[0].data.shift();
            }
            deauthsChart.update();
        });
    </script>
</body>
</html>
"""
    
    with open(templates_dir / 'stats.html', 'w', encoding='utf-8') as f:
        f.write(stats_html)


def create_html_template():
    """Create the dashboard HTML template"""
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pwnagotchi Fleet Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Courier New', monospace;
            background: #0a0a0a;
            color: #00ff00;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            padding: 20px;
            border: 2px solid #00ff00;
            margin-bottom: 20px;
            background: #111;
        }
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
            text-shadow: 0 0 10px #00ff00;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: #111;
            border: 2px solid #00ff00;
            padding: 15px;
            text-align: center;
        }
        
        .stat-card .label {
            color: #888;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        
        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #00ff00;
            text-shadow: 0 0 5px #00ff00;
        }
        
        .pwnies-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .pwnie-card {
            background: #111;
            border: 2px solid #444;
            padding: 20px;
            position: relative;
            transition: all 0.3s ease;
        }
        
        .pwnie-card.running {
            border-color: #00ff00;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
        }
        
        .pwnie-card.stopped {
            border-color: #ff0000;
        }
        
        .pwnie-face {
            font-size: 4em;
            text-align: center;
            margin: 10px 0;
            animation: pulse 2s infinite;
        }
        
        .pwnie-name {
            text-align: center;
            font-size: 1.5em;
            margin-bottom: 15px;
            color: #00ff00;
        }
        
        .status-leds {
            position: absolute;
            bottom: 10px;
            left: 10px;
            display: flex;
            gap: 10px;
        }
        
        .led {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.7em;
        }
        
        .led-light {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            border: 1px solid #333;
        }
        
        .led-light.on {
            background: #00ff00;
            box-shadow: 0 0 8px #00ff00;
        }
        
        .led-light.off {
            background: #333;
        }
        
        .led-light.blink {
            animation: blink 0.5s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        .pwnie-info {
            margin: 10px 0;
            font-size: 0.9em;
        }
        
        .pwnie-info .label {
            color: #888;
            display: inline-block;
            width: 120px;
        }
        
        .pwnie-info .value {
            color: #00ff00;
        }
        
        .pwnie-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        .btn {
            flex: 1;
            padding: 10px;
            border: 1px solid #00ff00;
            background: transparent;
            color: #00ff00;
            cursor: pointer;
            font-family: 'Courier New', monospace;
            transition: all 0.2s;
        }
        
        .btn:hover {
            background: #00ff00;
            color: #000;
        }
        
        .btn.danger {
            border-color: #ff0000;
            color: #ff0000;
        }
        
        .btn.danger:hover {
            background: #ff0000;
            color: #000;
        }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        
        .status-indicator.running {
            background: #00ff00;
            box-shadow: 0 0 10px #00ff00;
        }
        
        .status-indicator.stopped {
            background: #ff0000;
        }
        
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #111;
            border: 2px solid #00ff00;
            padding: 15px 20px;
            min-width: 250px;
            transform: translateX(400px);
            transition: transform 0.3s;
        }
        
        .toast.show {
            transform: translateX(0);
        }
        
        .screen {
            background: #000;
            border: 2px solid #333;
            padding: 10px;
            margin: 10px 0;
            font-family: 'Courier New', monospace;
            font-size: 0.8em;
        }
        
        .screen-line {
            color: #00ff00;
            margin: 2px 0;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        
        .modal.show {
            display: flex;
        }
        
        .modal-content {
            background: #111;
            border: 2px solid #00ff00;
            padding: 30px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #888;
        }
        
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 10px;
            background: #000;
            border: 1px solid #00ff00;
            color: #00ff00;
            font-family: 'Courier New', monospace;
        }
        
        .form-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎮 PWNAGOTCHI FLEET DASHBOARD 🎮</h1>
        <p>Real-time monitoring of fake pwnagotchi instances</p>
        <div style="margin-top: 15px; display: flex; gap: 10px; justify-content: center;">
            <button class="btn" onclick="showCreateModal()">+ Create New Pwnie</button>
            <button class="btn" onclick="window.location.href='/stats'">📊 View Statistics</button>
            <button class="btn danger" onclick="enableTorFailsafe()" title="Stop all non-Tor pwnies, enable Tor, restart">🔒 TOR FAILSAFE</button>
        </div>
    </div>
    
    <div class="stats-grid" id="stats">
        <div class="stat-card">
            <div class="label">Total Pwnies</div>
            <div class="value" id="stat-total">0</div>
        </div>
        <div class="stat-card">
            <div class="label">Running</div>
            <div class="value" id="stat-running">0</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Networks</div>
            <div class="value" id="stat-pwned">0</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Handshakes</div>
            <div class="value" id="stat-handshakes">0</div>
        </div>
    </div>
    
    <div class="pwnies-grid" id="pwnies-grid"></div>
    
    <!-- Create Modal -->
    <div class="modal" id="createModal">
        <div class="modal-content">
            <div class="modal-title">Create New Pwnie</div>
            <div class="form-group">
                <label>Name (optional, random if empty)</label>
                <input type="text" id="create-name" placeholder="pwnie-1">
            </div>
            <div class="form-group">
                <label>Pwned Networks</label>
                <input type="number" id="create-pwned" value="100" min="0">
            </div>
            <div class="form-group">
                <label>Reporting Threads</label>
                <input type="number" id="create-threads" value="1" min="1" max="50">
            </div>
            <div class="form-group">
                <label>Use Tor</label>
                <select id="create-tor">
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                </select>
            </div>
            <div class="form-actions">
                <button class="btn" onclick="createPwnie()">Create</button>
                <button class="btn danger" onclick="hideModal('createModal')">Cancel</button>
            </div>
        </div>
    </div>
    
    <!-- Edit Modal -->
    <div class="modal" id="editModal">
        <div class="modal-content">
            <div class="modal-title">Edit Pwnie Settings</div>
            <input type="hidden" id="edit-id">
            
            <div class="form-group">
                <label>Name</label>
                <input type="text" id="edit-name" placeholder="Pwnie name">
                <small>Note: Changing name will rename the pwnie file</small>
            </div>
            
            <div class="form-group">
                <label>Personality</label>
                <select id="edit-personality">
                    <option value="passive">Passive</option>
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Version</label>
                <input type="text" id="edit-version" placeholder="1.5.5">
            </div>
            
            <div class="form-group">
                <label>Pwned Networks</label>
                <input type="number" id="edit-pwned" min="0" placeholder="Total pwned count">
            </div>
            
            <div class="form-group">
                <label>Epoch</label>
                <input type="number" id="edit-epoch" min="0" placeholder="Current epoch">
            </div>
            
            <div class="form-group">
                <label>Add Networks</label>
                <input type="number" id="edit-addnets" value="0" min="0" placeholder="Add N more networks">
                <small>This will add to the current pwned count</small>
            </div>
            
            <div class="form-group">
                <label>Reporting Threads</label>
                <input type="number" id="edit-threads" value="1" min="1" max="50">
            </div>
            
            <div class="form-group">
                <label>Use Tor</label>
                <select id="edit-tor">
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                </select>
            </div>
            
            <div class="form-actions">
                <button class="btn" onclick="savePwnieEdit()">Save Changes</button>
                <button class="btn danger" onclick="hideModal('editModal')">Cancel</button>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        const socket = io();
        
        socket.on('connect', () => {
            console.log('Connected to server');
            showToast('Connected to Fleet Manager');
        });
        
        socket.on('update', (data) => {
            updateStats(data.stats);
            updatePwnies(data.pwnies);
        });
        
        function updateStats(stats) {
            document.getElementById('stat-total').textContent = stats.total;
            document.getElementById('stat-running').textContent = stats.running;
            document.getElementById('stat-pwned').textContent = stats.total_pwned;
            document.getElementById('stat-handshakes').textContent = stats.total_handshakes;
        }
        
        function updatePwnies(pwnies) {
            const grid = document.getElementById('pwnies-grid');
            
            pwnies.forEach(pwnie => {
                let card = document.getElementById(`pwnie-${pwnie.id}`);
                
                if (!card) {
                    card = createPwnieCard(pwnie);
                    grid.appendChild(card);
                } else {
                    updatePwnieCard(card, pwnie);
                }
            });
        }
        
        function createPwnieCard(pwnie) {
            const card = document.createElement('div');
            card.id = `pwnie-${pwnie.id}`;
            card.className = `pwnie-card ${pwnie.running ? 'running' : 'stopped'}`;
            
            card.innerHTML = `
                <div class="pwnie-face">${pwnie.face}</div>
                <div class="pwnie-name">${pwnie.name}</div>
                
                <div class="screen">
                    <div class="screen-line">CH * APs${pwnie.aps_count} [${pwnie.pwned}]</div>
                    <div class="screen-line">Next Age== ${pwnie.epoch + 1}</div>
                    <div class="screen-line">PWND ${pwnie.pwned} [${pwnie.handshakes}] [${pwnie.personality}]</div>
                </div>
                
                <div class="pwnie-info">
                    <span class="label">Status:</span>
                    <span class="value status-${pwnie.id}">${pwnie.running ? 'RUNNING' : 'STOPPED'}</span>
                </div>
                <div class="pwnie-info">
                    <span class="label">Version:</span>
                    <span class="value">${pwnie.version}</span>
                </div>
                <div class="pwnie-info">
                    <span class="label">Epoch:</span>
                    <span class="value epoch-${pwnie.id}">${pwnie.epoch}</span>
                </div>
                <div class="pwnie-info">
                    <span class="label">Networks:</span>
                    <span class="value pwned-${pwnie.id}">${pwnie.pwned}</span>
                </div>
                <div class="pwnie-info">
                    <span class="label">Handshakes:</span>
                    <span class="value hs-${pwnie.id}">${pwnie.handshakes}</span>
                </div>
                <div class="pwnie-info">
                    <span class="label">Deauths:</span>
                    <span class="value deauth-${pwnie.id}">${pwnie.deauths}</span>
                </div>
                
                <div class="pwnie-actions">
                    ${pwnie.running ? 
                        `<button class="btn danger" onclick="shutdownPwnie(${pwnie.id})">Shutdown</button>` :
                        `<button class="btn" onclick="bootPwnie(${pwnie.id})">Boot</button>`
                    }
                    <button class="btn" onclick="rebootPwnie(${pwnie.id})">Reboot</button>
                    <button class="btn" onclick="showEditModal(${pwnie.id}, '${pwnie.name}', ${pwnie.use_tor}, ${pwnie.threads || 1})">Edit</button>
                </div>
                
                <div class="status-leds">
                    <div class="led">
                        <div class="led-light ${pwnie.running ? 'on' : 'off'}" id="led-power-${pwnie.id}"></div>
                        <span>PWR</span>
                    </div>
                    <div class="led">
                        <div class="led-light ${pwnie.running ? 'blink' : 'off'}" id="led-act-${pwnie.id}"></div>
                        <span>ACT</span>
                    </div>
                </div>
            `;
            
            return card;
        }
        
        function updatePwnieCard(card, pwnie) {
            card.className = `pwnie-card ${pwnie.running ? 'running' : 'stopped'}`;
            
            card.querySelector(`.status-${pwnie.id}`).textContent = pwnie.running ? 'RUNNING' : 'STOPPED';
            card.querySelector(`.epoch-${pwnie.id}`).textContent = pwnie.epoch;
            card.querySelector(`.pwned-${pwnie.id}`).textContent = pwnie.pwned;
            card.querySelector(`.hs-${pwnie.id}`).textContent = pwnie.handshakes;
            card.querySelector(`.deauth-${pwnie.id}`).textContent = pwnie.deauths;
            
            // Update screen
            const screenLines = card.querySelectorAll('.screen-line');
            screenLines[0].textContent = `CH * APs${pwnie.aps_count} [${pwnie.pwned}]`;
            screenLines[1].textContent = `Next Age== ${pwnie.epoch + 1}`;
            screenLines[2].textContent = `PWND ${pwnie.pwned} [${pwnie.handshakes}] [${pwnie.personality}]`;
            
            // Update LEDs
            const powerLed = card.querySelector(`#led-power-${pwnie.id}`);
            const actLed = card.querySelector(`#led-act-${pwnie.id}`);
            powerLed.className = `led-light ${pwnie.running ? 'on' : 'off'}`;
            actLed.className = `led-light ${pwnie.running ? 'blink' : 'off'}`;
            
            // Update buttons
            const actionsDiv = card.querySelector('.pwnie-actions');
            actionsDiv.innerHTML = `
                ${pwnie.running ? 
                    `<button class="btn danger" onclick="shutdownPwnie(${pwnie.id})">Shutdown</button>` :
                    `<button class="btn" onclick="bootPwnie(${pwnie.id})">Boot</button>`
                }
                <button class="btn" onclick="rebootPwnie(${pwnie.id})">Reboot</button>
                <button class="btn" onclick="showEditModal(${pwnie.id}, '${pwnie.name}', ${pwnie.use_tor}, ${pwnie.threads || 1})">Edit</button>
            `;
        }
        
        function bootPwnie(id) {
            fetch(`/api/pwnie/${id}/boot`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message);
                })
                .catch(err => showToast('Error: ' + err, true));
        }
        
        function shutdownPwnie(id) {
            fetch(`/api/pwnie/${id}/shutdown`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message);
                })
                .catch(err => showToast('Error: ' + err, true));
        }
        
        function rebootPwnie(id) {
            fetch(`/api/pwnie/${id}/reboot`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message);
                })
                .catch(err => showToast('Error: ' + err, true));
        }
        
        function showCreateModal() {
            document.getElementById('createModal').classList.add('show');
        }
        
        async function showEditModal(id, name, useTor, threads) {
            // Fetch current pwnie data
            try {
                const response = await fetch(`/api/pwnie/${id}`);
                const pwnie = await response.json();
                
                document.getElementById('edit-id').value = id;
                document.getElementById('edit-name').value = pwnie.name;
                document.getElementById('edit-personality').value = pwnie.personality;
                document.getElementById('edit-version').value = pwnie.version;
                document.getElementById('edit-pwned').value = pwnie.pwned;
                document.getElementById('edit-epoch').value = pwnie.epoch;
                document.getElementById('edit-tor').value = pwnie.use_tor ? 'true' : 'false';
                document.getElementById('edit-threads').value = threads || 1;
                document.getElementById('edit-addnets').value = 0;
                document.getElementById('editModal').classList.add('show');
            } catch (err) {
                showToast('Error loading pwnie data: ' + err, true);
            }
        }
        
        function hideModal(modalId) {
            document.getElementById(modalId).classList.remove('show');
        }
        
        function createPwnie() {
            const data = {
                name: document.getElementById('create-name').value,
                pwned: parseInt(document.getElementById('create-pwned').value) || 0,
                use_tor: document.getElementById('create-tor').value === 'true',
                threads: parseInt(document.getElementById('create-threads').value) || 1
            };
            
            fetch('/api/pwnie/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(data => {
                showToast(data.message);
                if (data.success) {
                    hideModal('createModal');
                    setTimeout(() => location.reload(), 2000);
                }
            })
            .catch(err => showToast('Error: ' + err, true));
        }
        
        function savePwnieEdit() {
            const id = parseInt(document.getElementById('edit-id').value);
            const data = {
                name: document.getElementById('edit-name').value,
                personality: document.getElementById('edit-personality').value,
                version: document.getElementById('edit-version').value,
                pwned: parseInt(document.getElementById('edit-pwned').value),
                epoch: parseInt(document.getElementById('edit-epoch').value),
                use_tor: document.getElementById('edit-tor').value === 'true',
                threads: parseInt(document.getElementById('edit-threads').value) || 1,
                add_networks: parseInt(document.getElementById('edit-addnets').value) || 0
            };
            
            fetch(`/api/pwnie/${id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(data => {
                showToast(data.message);
                if (data.success) {
                    hideModal('editModal');
                }
            })
            .catch(err => showToast('Error: ' + err, true));
        }
            })
            .catch(err => showToast('Error: ' + err, true));
        }
        
        function enableTorFailsafe() {
            if (!confirm('This will stop all non-Tor pwnies, enable Tor for them, and restart. Continue?')) {
                return;
            }
            
            fetch('/api/failsafe/tor', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    showToast(data.message + ` (${data.count} pwnies affected)`);
                })
                .catch(err => showToast('Error: ' + err, true));
        }
        
        function showToast(message, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.style.borderColor = isError ? '#ff0000' : '#00ff00';
            toast.classList.add('show');
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
        
        // Initial load
        fetch('/api/pwnies')
            .then(r => r.json())
            .then(pwnies => updatePwnies(pwnies));
        
        fetch('/api/stats')
            .then(r => r.json())
            .then(stats => updateStats(stats));
    </script>
</body>
</html>
"""
    
    with open(templates_dir / 'dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html_content)


def start_webui(pwnie_manager, host='0.0.0.0', port=5000):
    """Start the web UI server"""
    global manager
    manager = pwnie_manager
    
    # Create HTML templates
    create_html_template()
    create_stats_template()
    
    # Start background update thread
    update_thread = threading.Thread(target=background_updates, daemon=True)
    update_thread.start()
    
    print(f"\n🌐 Web UI started at http://{host}:{port}")
    print(f"   Open this URL in your browser to view the dashboard")
    print(f"   Stats page: http://{host}:{port}/stats\n")
    
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    print("This module should be imported by pwnie-manager.py")
    print("Run: python pwnie-manager.py --webui")
