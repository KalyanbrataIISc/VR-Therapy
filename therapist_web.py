from flask import Flask, request, jsonify
import threading
import asyncio
import sys
import os
import time
import signal

# Import your existing therapist code
from therapist import VirtualTherapist, AUDIO_DIR, THERAPIST_AUDIO_DIR

# Create Flask app
app = Flask(__name__)

# Global session state
therapist = None
session_active = False

def run_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Set up asyncio event loop for the Flask application
loop = asyncio.new_event_loop()
t = threading.Thread(target=run_async_loop, args=(loop,), daemon=True)
t.start()

# HTML, CSS and JavaScript content as strings
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Virtual Therapist</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6a8caf;
            --primary-light: #a6c0dd;
            --primary-dark: #4a6e99;
            --accent: #ff8fab;
            --accent-light: #ffc2d1;
            --accent-dark: #ff5c8d;
            --background: #f9f7f7;
            --card-bg: #ffffff;
            --text: #333333;
            --text-light: #666666;
            --shadow: 0 8px 25px rgba(0, 0, 0, 0.05);
            --shadow-hover: 0 12px 30px rgba(0, 0, 0, 0.08);
            --border-radius: 20px;
            --transition: all 0.3s ease;
            --flower-1: #f8b6cd;
            --flower-2: #c9dce6;
            --flower-3: #cee5d5;
            --flower-4: #f3e7d3;
            --flower-5: #d1c2e0;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Quicksand', sans-serif;
            background: var(--background);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow-x: hidden;
        }

        /* Flower decorations */
        .flower {
            position: absolute;
            z-index: -1;
            opacity: 0.7;
            border-radius: 50%;
        }

        .flower-1 {
            top: 5vh;
            left: 5vw;
            width: 100px;
            height: 100px;
            background: var(--flower-1);
            animation: float 8s ease-in-out infinite;
        }

        .flower-2 {
            top: 15vh;
            right: 8vw;
            width: 120px;
            height: 120px;
            background: var(--flower-2);
            animation: float 12s ease-in-out infinite 1s;
        }

        .flower-3 {
            bottom: 10vh;
            left: 10vw;
            width: 80px;
            height: 80px;
            background: var(--flower-3);
            animation: float 10s ease-in-out infinite 0.5s;
        }

        .flower-4 {
            bottom: 15vh;
            right: 5vw;
            width: 90px;
            height: 90px;
            background: var(--flower-4);
            animation: float 9s ease-in-out infinite 1.5s;
        }

        @keyframes float {
            0%, 100% {
                transform: translateY(0) rotate(0deg);
            }
            50% {
                transform: translateY(-20px) rotate(5deg);
            }
        }

        /* Petal shapes for flowers */
        .flower::before, .flower::after {
            content: "";
            position: absolute;
            border-radius: 50%;
            background: inherit;
            opacity: 0.7;
        }

        .flower::before {
            width: 100%;
            height: 100%;
            top: -30%;
            left: 15%;
        }

        .flower::after {
            width: 100%;
            height: 100%;
            top: 15%;
            left: -30%;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            flex: 1;
            display: flex;
            flex-direction: column;
            position: relative;
            z-index: 1;
        }

        header {
            text-align: center;
            padding: 0 0 30px 0;
            margin-bottom: 30px;
            position: relative;
        }

        header::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 60px;
            height: 4px;
            background: var(--accent);
            border-radius: 2px;
        }

        h1 {
            font-size: 3rem;
            font-weight: 700;
            color: var(--primary-dark);
            position: relative;
            display: inline-block;
        }

        h1 span {
            position: relative;
        }

        h1::before {
            content: '✿';
            color: var(--accent);
            margin-right: 15px;
            font-size: 0.8em;
        }

        h1::after {
            content: '✿';
            color: var(--accent);
            margin-left: 15px;
            font-size: 0.8em;
        }

        .subtitle {
            color: var(--text-light);
            font-size: 1.2rem;
            margin-top: 10px;
        }

        .main-content {
            display: grid;
            grid-template-columns: 1fr;
            gap: 40px;
            align-items: center;
        }

        .avatar-container {
            position: relative;
            height: 300px;
            border-radius: var(--border-radius);
            overflow: hidden;
            background: var(--card-bg);
            box-shadow: var(--shadow);
            transition: var(--transition);
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .avatar-container:hover {
            box-shadow: var(--shadow-hover);
            transform: translateY(-5px);
        }

        .avatar-image {
            width: 200px;
            height: 200px;
            background: var(--primary-light);
            border-radius: 50%;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: flex-end;
            overflow: hidden;
        }

        .avatar-image::before {
            content: '';
            position: absolute;
            top: 20%;
            left: 10%;
            width: 80%;
            height: 60%;
            background: var(--card-bg);
            border-radius: 50%;
        }

        /* Eyes */
        .avatar-eyes {
            position: absolute;
            top: 35%;
            width: 100%;
            display: flex;
            justify-content: center;
            gap: 40px;
        }

        .eye {
            width: 30px;
            height: 30px;
            background: var(--text);
            border-radius: 50%;
            position: relative;
        }

        .eye::after {
            content: '';
            position: absolute;
            top: 5px;
            left: 5px;
            width: 10px;
            height: 10px;
            background: white;
            border-radius: 50%;
        }

        /* Mouth */
        .avatar-mouth {
            position: absolute;
            bottom: 25%;
            width: 80px;
            height: 40px;
            background: var(--accent);
            border-radius: 0 0 40px 40px;
            overflow: hidden;
        }

        .avatar-mouth.speaking {
            animation: speaking 0.5s infinite alternate;
        }

        @keyframes speaking {
            from { height: 40px; }
            to { height: 50px; }
        }

        /* Teeth */
        .avatar-teeth {
            position: absolute;
            top: 0;
            width: 100%;
            height: 15px;
            background: white;
            display: flex;
        }

        .tooth {
            flex: 1;
            height: 100%;
            border-right: 1px solid rgba(0,0,0,0.1);
        }

        /* Flower on top */
        .avatar-flower {
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%) translateY(-50%);
            width: 60px;
            height: 60px;
        }

        .flower-center {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 20px;
            height: 20px;
            background: #ffdf80;
            border-radius: 50%;
            z-index: 2;
        }

        .flower-petal {
            position: absolute;
            width: 25px;
            height: 25px;
            background: var(--accent);
            border-radius: 50%;
        }

        .petal-1 { top: 0; left: 50%; transform: translateX(-50%); }
        .petal-2 { top: 50%; right: 0; transform: translateY(-50%); }
        .petal-3 { bottom: 0; left: 50%; transform: translateX(-50%); }
        .petal-4 { top: 50%; left: 0; transform: translateY(-50%); }
        .petal-5 { top: 15%; right: 15%; }
        .petal-6 { bottom: 15%; right: 15%; }
        .petal-7 { bottom: 15%; left: 15%; }
        .petal-8 { top: 15%; left: 15%; }

        .status-indicator {
            position: absolute;
            bottom: 20px;
            right: 20px;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background-color: var(--text-light);
            transition: var(--transition);
        }

        .status-indicator.listening {
            background-color: #35d0ba;
            box-shadow: 0 0 10px #35d0ba;
            animation: pulse 1.5s infinite;
        }

        .status-indicator.speaking {
            background-color: var(--accent);
            box-shadow: 0 0 10px var(--accent);
            animation: pulse 0.75s infinite;
        }

        .status-indicator.idle {
            background-color: var(--primary);
        }

        @keyframes pulse {
            0% {
                transform: scale(1);
                opacity: 1;
            }
            50% {
                transform: scale(1.2);
                opacity: 0.7;
            }
            100% {
                transform: scale(1);
                opacity: 1;
            }
        }

        .controls {
            display: flex;
            flex-direction: column;
            gap: 30px;
            padding: 40px;
            background: var(--card-bg);
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            transition: var(--transition);
        }

        .controls:hover {
            box-shadow: var(--shadow-hover);
        }

        .controls-header {
            text-align: center;
            margin-bottom: 10px;
        }

        .controls-header h2 {
            font-size: 1.75rem;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--primary-dark);
        }

        .controls-header p {
            color: var(--text-light);
            font-size: 0.95rem;
        }

        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 50px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            outline: none;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-family: 'Quicksand', sans-serif;
        }

        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(to right, rgba(255,255,255,0.1), rgba(255,255,255,0.2));
            transform: translateX(-100%);
            transition: transform 0.6s;
        }

        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 7px 15px rgba(0, 0, 0, 0.15);
        }

        .btn:hover::before {
            transform: translateX(100%);
        }

        .btn:active {
            transform: translateY(1px);
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }

        .btn:disabled {
            background: var(--text-light);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .btn:disabled::before {
            display: none;
        }

        .btn.accent {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
        }

        .status {
            font-size: 18px;
            margin-top: 10px;
            text-align: center;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 500;
            color: var(--text);
            background: rgba(0, 0, 0, 0.03);
            border-radius: 25px;
            position: relative;
            overflow: hidden;
        }

        .status::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent 0%, 
                rgba(255, 255, 255, 0.5) 50%, 
                transparent 100%);
            transform: translateX(-100%);
        }

        .status.animated::before {
            animation: shine 2s infinite;
        }

        @keyframes shine {
            100% {
                transform: translateX(100%);
            }
        }

        .instructions {
            background: var(--card-bg);
            padding: 30px;
            border-radius: var(--border-radius);
            margin-top: 40px;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }

        .instructions:hover {
            box-shadow: var(--shadow-hover);
        }

        .instructions h3 {
            margin-bottom: 20px;
            color: var(--primary-dark);
            font-size: 1.5rem;
            font-weight: 600;
            display: flex;
            align-items: center;
        }

        .instructions h3::before {
            content: '❀';
            color: var(--accent);
            margin-right: 15px;
        }

        .instructions-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        .instruction-card {
            background: rgba(0, 0, 0, 0.02);
            padding: 25px;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            transition: var(--transition);
            border: 1px solid rgba(0, 0, 0, 0.03);
        }

        .instruction-card:hover {
            transform: translateY(-5px);
            background: rgba(0, 0, 0, 0.03);
        }

        .instruction-number {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary) 100%);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: 600;
            margin-bottom: 15px;
            color: white;
        }

        .instruction-text {
            font-size: 0.95rem;
            line-height: 1.5;
            color: var(--text);
        }

        .audio-player {
            margin-top: 40px;
            text-align: center;
            position: relative;
        }

        .audio-player::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 2px;
            background: rgba(0, 0, 0, 0.05);
            z-index: -1;
        }

        .audio-player audio {
            width: 100%;
            max-width: 600px;
            border-radius: 50px;
            background: var(--card-bg);
            height: 50px;
            box-shadow: var(--shadow);
        }

        footer {
            text-align: center;
            padding: 30px;
            color: var(--text-light);
            font-size: 14px;
            margin-top: auto;
            position: relative;
        }

        footer::before {
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 100px;
            height: 1px;
            background: rgba(0, 0, 0, 0.1);
        }

        .heart {
            color: var(--accent);
            animation: heartbeat 1.5s infinite;
            display: inline-block;
        }

        @keyframes heartbeat {
            0%, 100% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.2);
            }
        }

        /* Debug section */
        .debug-panel {
            background: var(--card-bg);
            padding: 20px;
            margin-top: 30px;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            display: none;
        }

        .debug-panel h3 {
            margin-bottom: 15px;
            font-size: 1.2rem;
            color: var(--primary-dark);
        }

        .debug-log {
            background: rgba(0, 0, 0, 0.03);
            padding: 15px;
            border-radius: 8px;
            height: 150px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.9rem;
            white-space: pre-wrap;
        }

        .debug-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }

        .debug-btn {
            padding: 8px 15px;
            border-radius: 6px;
            background: var(--primary-light);
            color: var(--text);
            border: none;
            cursor: pointer;
            font-size: 0.9rem;
        }

        .debug-btn:hover {
            background: var(--primary);
            color: white;
        }

        @media (max-width: 768px) {
            .instructions-grid {
                grid-template-columns: 1fr;
            }
            
            .container {
                padding: 20px 15px;
            }
            
            h1 {
                font-size: 2.2rem;
            }
            
            .controls {
                padding: 25px;
            }
        }
    </style>
</head>
<body>
    <!-- Decorative flower elements -->
    <div class="flower flower-1"></div>
    <div class="flower flower-2"></div>
    <div class="flower flower-3"></div>
    <div class="flower flower-4"></div>

    <div class="container">
        <header>
            <h1><span>Virtual Therapist</span></h1>
            <div class="subtitle">Your AI companion for emotional well-being</div>
        </header>
        
        <div class="main-content">
            <div class="avatar-container">
                <div class="avatar-image">
                    <div class="avatar-eyes">
                        <div class="eye"></div>
                        <div class="eye"></div>
                    </div>
                    <div class="avatar-mouth" id="avatar-mouth">
                        <div class="avatar-teeth">
                            <div class="tooth"></div>
                            <div class="tooth"></div>
                            <div class="tooth"></div>
                            <div class="tooth"></div>
                        </div>
                    </div>
                    <div class="avatar-flower">
                        <div class="flower-center"></div>
                        <div class="flower-petal petal-1"></div>
                        <div class="flower-petal petal-2"></div>
                        <div class="flower-petal petal-3"></div>
                        <div class="flower-petal petal-4"></div>
                        <div class="flower-petal petal-5"></div>
                        <div class="flower-petal petal-6"></div>
                        <div class="flower-petal petal-7"></div>
                        <div class="flower-petal petal-8"></div>
                    </div>
                </div>
                <div class="status-indicator" id="status-indicator"></div>
            </div>
            
            <div class="controls">
                <div class="controls-header">
                    <h2>Therapy Session</h2>
                    <p>Your AI companion is ready to listen</p>
                </div>
                
                <button id="start-session" class="btn">Start Session</button>
                <button id="end-session" class="btn accent" disabled>End Session</button>
                <div class="status" id="status-message">Ready to start</div>
            </div>
            
            <div class="instructions">
                <h3>How It Works</h3>
                <div class="instructions-grid">
                    <div class="instruction-card">
                        <div class="instruction-number">1</div>
                        <div class="instruction-text">Click "Start Session" to begin your therapy conversation</div>
                    </div>
                    <div class="instruction-card">
                        <div class="instruction-number">2</div>
                        <div class="instruction-text">Speak naturally when the status shows "Listening..."</div>
                    </div>
                    <div class="instruction-card">
                        <div class="instruction-number">3</div>
                        <div class="instruction-text">Your therapist will respond with helpful insights</div>
                    </div>
                    <div class="instruction-card">
                        <div class="instruction-number">4</div>
                        <div class="instruction-text">Say "goodbye" or "end session" when you're done</div>
                    </div>
                </div>
            </div>

            <!-- Hidden debug panel - can be enabled with keyboard shortcut Ctrl+D -->
            <div class="debug-panel" id="debug-panel">
                <h3>Debug Panel</h3>
                <div class="debug-log" id="debug-log">Debug information will appear here...</div>
                <div class="debug-buttons">
                    <button class="debug-btn" id="debug-check-session">Check Session</button>
                    <button class="debug-btn" id="debug-clear">Clear Log</button>
                </div>
            </div>
        </div>
        
        <div class="audio-player">
            <audio id="therapist-audio" controls autoplay></audio>
        </div>
    </div>
    
    <footer>
        <p>Virtual Therapist - Created with <span class="heart">♥</span> - Powered by Google Gemini AI</p>
    </footer>
    
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // DOM elements
            const startButton = document.getElementById('start-session');
            const endButton = document.getElementById('end-session');
            const statusMessage = document.getElementById('status-message');
            const statusIndicator = document.getElementById('status-indicator');
            const therapistAudio = document.getElementById('therapist-audio');
            const avatarMouth = document.getElementById('avatar-mouth');
            const debugPanel = document.getElementById('debug-panel');
            const debugLog = document.getElementById('debug-log');
            const debugCheckSession = document.getElementById('debug-check-session');
            const debugClear = document.getElementById('debug-clear');
            
            // State variables
            let sessionActive = false;
            let pollTimer = null;
            let lastTherapistAudio = null;
            let consecutiveErrors = 0;
            
            // Debug helpers
            function logDebug(message, type = 'info') {
                const timestamp = new Date().toLocaleTimeString();
                const msgType = type.toUpperCase();
                const msgText = `[${timestamp}] [${msgType}] ${message}`;
                
                const logElement = document.getElementById('debug-log');
                if (logElement) {
                    logElement.innerHTML += msgText + '\\n';
                    logElement.scrollTop = logElement.scrollHeight;
                }
                
                if (type === 'error') {
                    console.error(message);
                } else {
                    console.log(message);
                }
            }
            
            // Enable debug panel with Ctrl+D
            document.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'd') {
                    e.preventDefault();
                    debugPanel.style.display = debugPanel.style.display === 'none' ? 'block' : 'none';
                    logDebug('Debug panel toggled');
                }
            });
            
            // Debug buttons
            debugCheckSession.addEventListener('click', async () => {
                try {
                    const response = await fetch('/session_status');
                    const data = await response.json();
                    logDebug(`Session status: ${JSON.stringify(data)}`);
                } catch (error) {
                    logDebug(`Error checking session: ${error}`, 'error');
                }
            });
            
            debugClear.addEventListener('click', () => {
                debugLog.innerHTML = '';
            });
            
            // Initialize
            updateStatus('Ready to start');
            
            // Start session button
            startButton.addEventListener('click', async () => {
                try {
                    startButton.disabled = true;
                    updateStatus('Starting session...', true);
                    logDebug('Starting new session');
                    
                    const response = await fetch('/start_session', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        sessionActive = true;
                        endButton.disabled = false;
                        updateStatus('Session started', true);
                        setStatusIndicator('listening');
                        
                        // Reset error counters
                        consecutiveErrors = 0;
                        
                        // Start polling for audio files
                        startPolling();
                        logDebug('Session started successfully');
                    } else {
                        updateStatus(`Error: ${data.message}`, true);
                        startButton.disabled = false;
                        logDebug(`Error starting session: ${data.message}`, 'error');
                    }
                } catch (error) {
                    console.error('Error starting session:', error);
                    updateStatus('Failed to start session', true);
                    startButton.disabled = false;
                    logDebug(`Exception starting session: ${error}`, 'error');
                }
            });
            
            // End session button
            endButton.addEventListener('click', async () => {
                try {
                    updateStatus('Say "goodbye" to end the session', true);
                    logDebug('User requested to end session - instructed to say "goodbye"');
                } catch (error) {
                    console.error('Error ending session:', error);
                    updateStatus('Failed to end session', true);
                    logDebug(`Error ending session: ${error}`, 'error');
                }
            });
            
            // Poll for new audio files with error handling
            function startPolling() {
                if (pollTimer) clearInterval(pollTimer);
                
                pollTimer = setInterval(async () => {
                    try {
                        const response = await fetch('/get_audio_files');
                        const data = await response.json();
                        
                        // Reset consecutive errors on successful poll
                        consecutiveErrors = 0;
                        
                        // Update session status
                        sessionActive = data.session_active;
                        
                        if (!sessionActive) {
                            stopPolling();
                            updateStatus('Session ended', false);
                            setStatusIndicator('idle');
                            startButton.disabled = false;
                            endButton.disabled = true;
                            logDebug('Session has ended');
                            return;
                        }
                        
                        // Check for new therapist audio
                        if (data.therapist_audio && data.therapist_audio !== lastTherapistAudio) {
                            lastTherapistAudio = data.therapist_audio;
                            playTherapistAudio(data.therapist_audio);
                            logDebug(`Playing new audio: ${data.therapist_audio}`);
                        }
                        
                    } catch (error) {
                        console.error('Error polling for audio:', error);
                        logDebug(`Poll error: ${error}`, 'error');
                        
                        // Count consecutive errors
                        consecutiveErrors++;
                        
                        // If we've had too many consecutive errors, try to restart the session
                        if (consecutiveErrors > 5 && sessionActive) {
                            logDebug(`Too many consecutive errors (${consecutiveErrors}), checking session status`, 'error');
                            
                            try {
                                const statusResponse = await fetch('/session_status');
                                const statusData = await statusResponse.json();
                                
                                if (!statusData.active && sessionActive) {
                                    logDebug('Session inconsistency detected - session is reported as inactive but UI shows active', 'error');
                                    
                                    // Update UI to reflect actual session state
                                    sessionActive = false;
                                    stopPolling();
                                    updateStatus('Session disconnected - please restart', false);
                                    setStatusIndicator('idle');
                                    startButton.disabled = false;
                                    endButton.disabled = true;
                                }
                            } catch (statusError) {
                                logDebug(`Error checking session status: ${statusError}`, 'error');
                            }
                        }
                    }
                }, 1000);
                
                logDebug('Started polling for audio files');
            }
            
            function stopPolling() {
                if (pollTimer) {
                    clearInterval(pollTimer);
                    pollTimer = null;
                    logDebug('Stopped polling for audio files');
                }
            }
            
            // Play therapist audio with error handling
            function playTherapistAudio(audioUrl) {
                setStatusIndicator('speaking');
                updateStatus('Therapist is speaking...', true);
                
                // Animate the avatar mouth
                avatarMouth.classList.add('speaking');
                
                therapistAudio.src = audioUrl;
                therapistAudio.onended = () => {
                    setStatusIndicator('listening');
                    updateStatus('Listening...', true);
                    avatarMouth.classList.remove('speaking');
                    logDebug('Audio playback finished, now listening');
                };
                
                therapistAudio.onerror = (e) => {
                    logDebug(`Audio error: ${e.target.error}`, 'error');
                    setStatusIndicator('listening');
                    updateStatus('Error playing audio. Listening...', true);
                    avatarMouth.classList.remove('speaking');
                };
                
                therapistAudio.play().catch(error => {
                    console.error('Error playing audio:', error);
                    logDebug(`Error playing audio: ${error}`, 'error');
                    // Fall back to listening state if audio fails
                    setStatusIndicator('listening');
                    updateStatus('Listening...', true);
                    avatarMouth.classList.remove('speaking');
                });
            }
            
            // Update status message
            function updateStatus(message, animated = false) {
                statusMessage.textContent = message;
                statusMessage.className = 'status' + (animated ? ' animated' : '');
                logDebug(`Status updated: ${message}`);
            }
            
            // Set status indicator
            function setStatusIndicator(state) {
                statusIndicator.className = 'status-indicator';
                if (state) {
                    statusIndicator.classList.add(state);
                }
                logDebug(`Status indicator changed to: ${state}`);
            }
            
            // Check if session is active on page load
            async function checkSessionStatus() {
                try {
                    const response = await fetch('/session_status');
                    const data = await response.json();
                    
                    if (data.active) {
                        sessionActive = true;
                        startButton.disabled = true;
                        endButton.disabled = false;
                        updateStatus('Session active', true);
                        setStatusIndicator('listening');
                        startPolling();
                        logDebug('Existing session detected on page load');
                    } else {
                        logDebug('No active session on page load');
                    }
                } catch (error) {
                    console.error('Error checking session status:', error);
                    logDebug(`Error checking initial session status: ${error}`, 'error');
                }
            }
            
            // Initialize by checking session status
            checkSessionStatus();
            
            // Animate the blinking
            setInterval(() => {
                const eyes = document.querySelectorAll('.eye');
                eyes.forEach(eye => {
                    eye.style.transform = 'scaleY(0.1)';
                    setTimeout(() => {
                        eye.style.transform = 'scaleY(1)';
                    }, 150);
                });
            }, 5000);
            
            // Add subtle head animation
            const avatarImage = document.querySelector('.avatar-image');
            let animationFrame;
            
            function animateAvatar() {
                const time = Date.now() * 0.001;
                avatarImage.style.transform = `translateY(${Math.sin(time) * 5}px)`;
                animationFrame = requestAnimationFrame(animateAvatar);
            }
            
            animateAvatar();
            
            // Clean up on page unload
            window.addEventListener('beforeunload', () => {
                cancelAnimationFrame(animationFrame);
            });
        });
    </script>
</body>
</html>
"""

# Fixed API routes with better error handling
@app.route('/')
def index():
    return HTML_CONTENT

@app.route('/start_session', methods=['POST'])
def start_session():
    global therapist, session_active
    
    if session_active:
        return jsonify({'status': 'error', 'message': 'Session already active'})
    
    try:
        therapist = VirtualTherapist()
        session_active = True
        
        # Start the session in a separate thread to not block the Flask server
        async def start_therapist_session():
            global session_active
            try:
                await therapist.start_session()
            except Exception as e:
                print(f"Error in therapy session: {e}")
            finally:
                session_active = False
        
        future = asyncio.run_coroutine_threadsafe(start_therapist_session(), loop)
        
        return jsonify({'status': 'success', 'message': 'Session started'})
    except Exception as e:
        print(f"Error starting session: {e}")
        return jsonify({'status': 'error', 'message': f'Error starting session: {str(e)}'})

@app.route('/end_session', methods=['POST'])
def end_session():
    global session_active, therapist
    
    if not session_active:
        return jsonify({'status': 'error', 'message': 'No active session'})
    
    # Reset the therapist instance to ensure we break any stuck sessions
    try:
        asyncio.run_coroutine_threadsafe(therapist.cleanup_audio_directory(), loop)
        return jsonify({'status': 'success', 'message': 'Say "goodbye" to end the session'})
    except Exception as e:
        print(f"Error ending session: {e}")
        return jsonify({'status': 'error', 'message': f'Error ending session: {str(e)}'})

@app.route('/get_audio_files', methods=['GET'])
def get_audio_files():
    try:
        # Check if directories exist
        if not os.path.exists(THERAPIST_AUDIO_DIR) or not os.path.exists(AUDIO_DIR):
            os.makedirs(THERAPIST_AUDIO_DIR, exist_ok=True)
            os.makedirs(AUDIO_DIR, exist_ok=True)
            return jsonify({
                'therapist_audio': None,
                'user_audio': None,
                'session_active': session_active
            })
            
        # Get the most recent therapist audio file
        therapist_files = [f for f in os.listdir(THERAPIST_AUDIO_DIR) if f.endswith('.wav')]
        therapist_files.sort(key=lambda x: os.path.getmtime(os.path.join(THERAPIST_AUDIO_DIR, x)), reverse=True)
        
        # Get the most recent user audio file
        user_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.wav')]
        user_files.sort(key=lambda x: os.path.getmtime(os.path.join(AUDIO_DIR, x)), reverse=True)
        
        therapist_audio = therapist_files[0] if therapist_files else None
        user_audio = user_files[0] if user_files else None
        
        return jsonify({
            'therapist_audio': f'/audio/therapist/{therapist_audio}' if therapist_audio else None,
            'user_audio': f'/audio/user/{user_audio}' if user_audio else None,
            'session_active': session_active
        })
    except Exception as e:
        print(f"Error getting audio files: {e}")
        return jsonify({
            'therapist_audio': None,
            'user_audio': None,
            'session_active': session_active,
            'error': str(e)
        })

@app.route('/audio/therapist/<filename>')
def therapist_audio(filename):
    try:
        file_path = os.path.join(THERAPIST_AUDIO_DIR, filename)
        
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                audio_data = file.read()
            
            # Return the audio file directly
            response = app.response_class(
                response=audio_data,
                status=200,
                mimetype='audio/wav'
            )
            return response
        else:
            return "File not found", 404
    except Exception as e:
        print(f"Error serving therapist audio: {e}")
        return f"Error: {str(e)}", 500

@app.route('/audio/user/<filename>')
def user_audio(filename):
    try:
        file_path = os.path.join(AUDIO_DIR, filename)
        
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                audio_data = file.read()
            
            # Return the audio file directly
            response = app.response_class(
                response=audio_data,
                status=200,
                mimetype='audio/wav'
            )
            return response
        else:
            return "File not found", 404
    except Exception as e:
        print(f"Error serving user audio: {e}")
        return f"Error: {str(e)}", 500

@app.route('/session_status', methods=['GET'])
def session_status():
    return jsonify({'active': session_active})

# Handle graceful shutdown
def signal_handler(sig, frame):
    print("\nShutting down server...")
    # Clean up audio directories
    try:
        if os.path.exists(AUDIO_DIR):
            for filename in os.listdir(AUDIO_DIR):
                file_path = os.path.join(AUDIO_DIR, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        
        if os.path.exists(THERAPIST_AUDIO_DIR):
            for filename in os.listdir(THERAPIST_AUDIO_DIR):
                file_path = os.path.join(THERAPIST_AUDIO_DIR, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
    except Exception as e:
        print(f"Error cleaning up: {e}")
    
    # Stop the event loop
    if loop and loop.is_running():
        loop.call_soon_threadsafe(loop.stop)
    
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    # Create empty directories if they don't exist
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(THERAPIST_AUDIO_DIR, exist_ok=True)
    
    # Start the Flask application
    print("\n=== Virtual Therapist Web Interface ===")
    print("Starting server at http://localhost:3000")
    print("Use Ctrl+C to exit")
    app.run(host='0.0.0.0', port=3000, debug=False, use_reloader=False)