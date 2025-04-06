from flask import Flask, request, jsonify
import threading
import asyncio
import sys
import os
import time
import json
import base64

# Import your existing therapist code
from therapist import VirtualTherapist, AUDIO_DIR, THERAPIST_AUDIO_DIR

# Create Flask app
app = Flask(__name__)

# Global session state
therapist = None
session_active = False
therapist_responses = []
user_inputs = []

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
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #7668cb;
            --primary-light: #9d92e6;
            --primary-dark: #5a4dab;
            --secondary: #ff7eb3;
            --secondary-light: #ffa7cc;
            --secondary-dark: #e45c9a;
            --dark: #1a1a2e;
            --dark-light: #2a2a45;
            --light: #f8f9fa;
            --gray: #6c757d;
            --success: #35d0ba;
            --warning: #ff9a3c;
            --danger: #ff5252;
            --gradient: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            --shadow-hover: 0 8px 30px rgba(0, 0, 0, 0.25);
            --border-radius: 16px;
            --transition: all 0.3s ease;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background: var(--dark);
            color: var(--light);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow-x: hidden;
        }

        body::before {
            content: '';
            position: absolute;
            top: -200px;
            right: -200px;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            background: var(--primary);
            opacity: 0.2;
            filter: blur(100px);
            z-index: -1;
        }

        body::after {
            content: '';
            position: absolute;
            bottom: -200px;
            left: -200px;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            background: var(--secondary);
            opacity: 0.2;
            filter: blur(100px);
            z-index: -1;
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
            padding: 0 0 40px 0;
            margin-bottom: 40px;
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
            background: var(--gradient);
            border-radius: 2px;
        }

        h1 {
            font-size: 3rem;
            font-weight: 700;
            background: var(--gradient);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            position: relative;
            display: inline-block;
        }

        h1 span {
            position: relative;
        }

        .main-content {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 40px;
            align-items: center;
        }

        .avatar-container {
            position: relative;
            height: 500px;
            border-radius: var(--border-radius);
            overflow: hidden;
            background: var(--dark-light);
            box-shadow: var(--shadow);
            transition: var(--transition);
        }

        .avatar-container:hover {
            box-shadow: var(--shadow-hover);
            transform: translateY(-5px);
        }

        #avatar {
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .status-indicator {
            position: absolute;
            bottom: 20px;
            right: 20px;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background-color: var(--gray);
            transition: var(--transition);
        }

        .status-indicator.listening {
            background-color: var(--success);
            box-shadow: 0 0 10px var(--success);
            animation: pulse 1.5s infinite;
        }

        .status-indicator.speaking {
            background-color: var(--secondary);
            box-shadow: 0 0 10px var(--secondary);
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
            background: var(--dark-light);
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
            color: var(--light);
        }

        .controls-header p {
            color: var(--gray);
            font-size: 0.95rem;
        }

        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 50px;
            background: var(--gradient);
            color: white;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: var(--transition);
            outline: none;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 1px;
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
            box-shadow: 0 7px 15px rgba(0, 0, 0, 0.3);
        }

        .btn:hover::before {
            transform: translateX(100%);
        }

        .btn:active {
            transform: translateY(1px);
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }

        .btn:disabled {
            background: var(--gray);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .btn:disabled::before {
            display: none;
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
            color: var(--light);
            background: rgba(255, 255, 255, 0.05);
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
                rgba(255, 255, 255, 0.05) 50%, 
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
            grid-column: span 2;
            background: var(--dark-light);
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
            color: var(--light);
            font-size: 1.5rem;
            font-weight: 600;
            display: flex;
            align-items: center;
        }

        .instructions h3::before {
            content: '';
            display: inline-block;
            width: 8px;
            height: 30px;
            background: var(--gradient);
            margin-right: 15px;
            border-radius: 4px;
        }

        .instructions-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }

        .instruction-card {
            background: rgba(255, 255, 255, 0.05);
            padding: 25px;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            transition: var(--transition);
        }

        .instruction-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.08);
        }

        .instruction-number {
            width: 40px;
            height: 40px;
            background: var(--gradient);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            font-weight: 600;
            margin-bottom: 15px;
        }

        .instruction-text {
            font-size: 0.95rem;
            line-height: 1.5;
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
            background: rgba(255, 255, 255, 0.05);
            z-index: -1;
        }

        .audio-player audio {
            width: 100%;
            max-width: 600px;
            border-radius: 50px;
            background: var(--dark-light);
            height: 50px;
        }

        audio::-webkit-media-controls-panel {
            background: var(--dark-light);
        }

        audio::-webkit-media-controls-play-button {
            background-color: var(--primary);
            border-radius: 50%;
        }

        audio::-webkit-media-controls-play-button:hover {
            background-color: var(--primary-dark);
        }

        audio::-webkit-media-controls-timeline {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 25px;
            margin: 0 15px;
        }

        footer {
            text-align: center;
            padding: 30px;
            color: var(--gray);
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
            background: rgba(255, 255, 255, 0.1);
        }

        .heart {
            color: var(--danger);
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

        @media (max-width: 1024px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            
            .avatar-container {
                height: 400px;
            }
            
            .instructions-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 576px) {
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
    <div class="container">
        <header>
            <h1><span>Virtual Therapist</span></h1>
        </header>
        
        <div class="main-content">
            <div class="avatar-container">
                <div id="avatar"></div>
                <div class="status-indicator" id="status-indicator"></div>
            </div>
            
            <div class="controls">
                <div class="controls-header">
                    <h2>Therapy Session</h2>
                    <p>Your AI companion is ready to listen</p>
                </div>
                
                <button id="start-session" class="btn">Start Session</button>
                <button id="end-session" class="btn" disabled>End Session</button>
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
        </div>
        
        <div class="audio-player">
            <audio id="therapist-audio" controls autoplay></audio>
        </div>
    </div>
    
    <footer>
        <p>Virtual Therapist - Created with <span class="heart">♥</span> - Powered by Google Gemini AI</p>
    </footer>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // DOM elements
            const startButton = document.getElementById('start-session');
            const endButton = document.getElementById('end-session');
            const statusMessage = document.getElementById('status-message');
            const statusIndicator = document.getElementById('status-indicator');
            const therapistAudio = document.getElementById('therapist-audio');
            
            // State variables
            let sessionActive = false;
            let pollTimer = null;
            let lastTherapistAudio = null;
            
            // Initialize
            updateStatus('Ready to start');
            
            // Start session button
            startButton.addEventListener('click', async () => {
                try {
                    startButton.disabled = true;
                    updateStatus('Starting session...', true);
                    
                    const response = await fetch('/start_session', {
                        method: 'POST'
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        sessionActive = true;
                        endButton.disabled = false;
                        updateStatus('Session started', true);
                        setStatusIndicator('listening');
                        
                        // Start polling for audio files
                        startPolling();
                    } else {
                        updateStatus(`Error: ${data.message}`, true);
                        startButton.disabled = false;
                    }
                } catch (error) {
                    console.error('Error starting session:', error);
                    updateStatus('Failed to start session', true);
                    startButton.disabled = false;
                }
            });
            
            // End session button
            endButton.addEventListener('click', async () => {
                try {
                    updateStatus('Say "goodbye" to end the session', true);
                } catch (error) {
                    console.error('Error ending session:', error);
                    updateStatus('Failed to end session', true);
                }
            });
            
            // Poll for new audio files
            function startPolling() {
                if (pollTimer) clearInterval(pollTimer);
                
                pollTimer = setInterval(async () => {
                    try {
                        const response = await fetch('/get_audio_files');
                        const data = await response.json();
                        
                        // Update session status
                        sessionActive = data.session_active;
                        
                        if (!sessionActive) {
                            stopPolling();
                            updateStatus('Session ended', false);
                            setStatusIndicator('idle');
                            startButton.disabled = false;
                            endButton.disabled = true;
                            return;
                        }
                        
                        // Check for new therapist audio
                        if (data.therapist_audio && data.therapist_audio !== lastTherapistAudio) {
                            lastTherapistAudio = data.therapist_audio;
                            playTherapistAudio(data.therapist_audio);
                        }
                        
                    } catch (error) {
                        console.error('Error polling for audio:', error);
                    }
                }, 1000);
            }
            
            function stopPolling() {
                if (pollTimer) {
                    clearInterval(pollTimer);
                    pollTimer = null;
                }
            }
            
            // Play therapist audio
            function playTherapistAudio(audioUrl) {
                setStatusIndicator('speaking');
                updateStatus('Therapist is speaking...', true);
                
                therapistAudio.src = audioUrl;
                therapistAudio.onended = () => {
                    setStatusIndicator('listening');
                    updateStatus('Listening...', true);
                };
                therapistAudio.play().catch(error => {
                    console.error('Error playing audio:', error);
                    // Fall back to listening state if audio fails
                    setStatusIndicator('listening');
                    updateStatus('Listening...', true);
                });
            }
            
            // Update status message
            function updateStatus(message, animated = false) {
                statusMessage.textContent = message;
                statusMessage.className = 'status' + (animated ? ' animated' : '');
            }
            
            // Set status indicator
            function setStatusIndicator(state) {
                statusIndicator.className = 'status-indicator';
                if (state) {
                    statusIndicator.classList.add(state);
                }
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
                    }
                } catch (error) {
                    console.error('Error checking session status:', error);
                }
            }
            
            // Initialize by checking session status
            checkSessionStatus();
        });

        // Advanced 3D Avatar script
        document.addEventListener('DOMContentLoaded', () => {
            // Get the container element
            const container = document.getElementById('avatar');
            
            // Create a scene
            const scene = new THREE.Scene();
            
            // Create camera
            const camera = new THREE.PerspectiveCamera(
                45, 
                container.clientWidth / container.clientHeight, 
                0.1, 
                1000
            );
            camera.position.z = 5;
            
            // Create renderer with anti-aliasing and alpha
            const renderer = new THREE.WebGLRenderer({ 
                antialias: true,
                alpha: true 
            });
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setClearColor(0x000000, 0);
            container.appendChild(renderer.domElement);
            
            // Add lights
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(0, 1, 1);
            scene.add(directionalLight);
            
            // Add point lights for more dramatic lighting
            const pointLight1 = new THREE.PointLight(0x7668cb, 1, 10);
            pointLight1.position.set(2, 1, 2);
            scene.add(pointLight1);
            
            const pointLight2 = new THREE.PointLight(0xff7eb3, 1, 10);
            pointLight2.position.set(-2, -1, 2);
            scene.add(pointLight2);
            
            // Create an advanced head group
            const headGroup = new THREE.Group();
            scene.add(headGroup);
            
            // Create a more detailed head base
            const headGeometry = new THREE.SphereGeometry(1, 64, 64);
            
            // Create custom shader material for the head
            const headMaterial = new THREE.MeshPhysicalMaterial({
                color: 0x7668cb,
                metalness: 0.2,
                roughness: 0.5,
                clearcoat: 1.0,
                clearcoatRoughness: 0.1,
                transmission: 0.5,
                thickness: 0.5,
                transparent: true,
                opacity: 0.9
            });
            
            const head = new THREE.Mesh(headGeometry, headMaterial);
            headGroup.add(head);
            
            // Add a subtle inner glow to the head
            const innerGeometry = new THREE.SphereGeometry(0.95, 64, 64);
            const innerMaterial = new THREE.MeshBasicMaterial({
                color: 0x9d92e6,
                transparent: true,
                opacity: 0.3
            });
            const innerGlow = new THREE.Mesh(innerGeometry, innerMaterial);
            head.add(innerGlow);
            
            // Create more detailed eyes
            const eyeGeometry = new THREE.SphereGeometry(0.15, 32, 32);
            
            // Iris material with emissive properties
            const irisMaterial = new THREE.MeshPhongMaterial({
                color: 0x35d0ba,
                emissive: 0x35d0ba,
                emissiveIntensity: 0.5,
                shininess: 90
            });
            
            // Eye white material
            const eyeWhiteMaterial = new THREE.MeshPhongMaterial({
                color: 0xffffff,
                shininess: 70
            });
            
            // Left eye group
            const leftEyeGroup = new THREE.Group();
            leftEyeGroup.position.set(-0.35, 0.1, 0.85);
            headGroup.add(leftEyeGroup);
            
            // Eye white
            const leftEyeWhite = new THREE.Mesh(eyeGeometry, eyeWhiteMaterial);
            leftEyeGroup.add(leftEyeWhite);
            
            // Iris (smaller sphere inside)
            const leftIrisGeometry = new THREE.SphereGeometry(0.09, 32, 32);
            const leftIris = new THREE.Mesh(leftIrisGeometry, irisMaterial);
            leftIris.position.z = 0.08;
            leftEyeGroup.add(leftIris);
            
            // Pupil (even smaller black sphere)
            const pupilGeometry = new THREE.SphereGeometry(0.04, 32, 32);
            const pupilMaterial = new THREE.MeshBasicMaterial({ color: 0x000000 });
            const leftPupil = new THREE.Mesh(pupilGeometry, pupilMaterial);
            leftPupil.position.z = 0.11;
            leftEyeGroup.add(leftPupil);
            
            // Right eye (same structure)
            const rightEyeGroup = new THREE.Group();
            rightEyeGroup.position.set(0.35, 0.1, 0.85);
            headGroup.add(rightEyeGroup);
            
            const rightEyeWhite = new THREE.Mesh(eyeGeometry, eyeWhiteMaterial);
            rightEyeGroup.add(rightEyeWhite);
            
            const rightIris = new THREE.Mesh(leftIrisGeometry, irisMaterial);
            rightIris.position.z = 0.08;
            rightEyeGroup.add(rightIris);
            
            const rightPupil = new THREE.Mesh(pupilGeometry, pupilMaterial);
            rightPupil.position.z = 0.11;
            rightEyeGroup.add(rightPupil);
            
            // Create a more sophisticated mouth
            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, -0.3, 0.85);
            headGroup.add(mouthGroup);
            
            // Create a curved line for the mouth using a custom curve
            const mouthCurve = new THREE.QuadraticBezierCurve3(
                new THREE.Vector3(-0.3, -0.1, 0),
                new THREE.Vector3(0, 0.1, 0),
                new THREE.Vector3(0.3, -0.1, 0)
            );
            
            const mouthGeometry = new THREE.TubeGeometry(mouthCurve, 30, 0.03, 20, false);
            const mouthMaterial = new THREE.MeshBasicMaterial({ color: 0xff7eb3 });
            const mouth = new THREE.Mesh(mouthGeometry, mouthMaterial);
            mouthGroup.add(mouth);
            
            // Add a slight glow to the mouth
            const mouthGlowGeo = new THREE.TubeGeometry(mouthCurve, 30, 0.05, 20, false);
            const mouthGlowMat = new THREE.MeshBasicMaterial({ 
                color: 0xff7eb3, 
                transparent: true, 
                opacity: 0.3 
            });
            const mouthGlow = new THREE.Mesh(mouthGlowGeo, mouthGlowMat);
            mouthGroup.add(mouthGlow);
            
            // Create brain waves/thought particles around the head
            const particlesGroup = new THREE.Group();
            scene.add(particlesGroup);
            
            // Main particles system
            const particlesGeometry = new THREE.BufferGeometry();
            const particleCount = 300;
            
            const positions = new Float32Array(particleCount * 3);
            const colors = new Float32Array(particleCount * 3);
            const sizes = new Float32Array(particleCount);
            
            const color1 = new THREE.Color(0x7668cb);
            const color2 = new THREE.Color(0xff7eb3);
            
            for (let i = 0; i < particleCount; i++) {
                // Position - create a spiral pattern around the head
                const t = i / particleCount;
                const radius = 1.3 + t * 0.9;
                const theta = t * Math.PI * 20;
                const y = (t - 0.5) * 2;
                
                positions[i * 3] = radius * Math.cos(theta);
                positions[i * 3 + 1] = y;
                positions[i * 3 + 2] = radius * Math.sin(theta);
                
                // Size - vary the size a bit
                sizes[i] = 0.02 + Math.random() * 0.05;
                
                // Color - gradient between two colors
                const mixedColor = new THREE.Color().lerpColors(color1, color2, t);
                colors[i * 3] = mixedColor.r;
                colors[i * 3 + 1] = mixedColor.g;
                colors[i * 3 + 2] = mixedColor.b;
            }
            
            particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            particlesGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            particlesGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
            
            // Create a custom shader material for better looking particles
            const particlesMaterial = new THREE.ShaderMaterial({
                uniforms: {
                    time: { value: 0 }
                },
                vertexShader: `
                    attribute float size;
                    attribute vec3 color;
                    varying vec3 vColor;
                    uniform float time;
                    
                    void main() {
                        vColor = color;
                        
                        // Animate position
                        vec3 pos = position;
                        float angle = time * 0.2;
                        float x = pos.x;
                        float z = pos.z;
                        
                        // Rotate particles around y axis
                        pos.x = x * cos(angle) - z * sin(angle);
                        pos.z = x * sin(angle) + z * cos(angle);
                        
                        // Add subtle wave movement
                        pos.y += sin(time * 0.5 + pos.x * 2.0) * 0.05;
                        
                        // Project to screen
                        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
                        gl_Position = projectionMatrix * mvPosition;
                        
                        // Size attenuation
                        gl_PointSize = size * (300.0 / -mvPosition.z);
                    }
                `,
                fragmentShader: `
                    varying vec3 vColor;
                    
                    void main() {
                        // Create a soft, circular particle
                        float r = distance(gl_PointCoord, vec2(0.5));
                        if (r > 0.5) discard;
                        
                        // Smooth edges
                        float alpha = 1.0 - smoothstep(0.3, 0.5, r);
                        gl_FragColor = vec4(vColor, alpha);
                    }
                `,
                transparent: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending
            });
            
            const particles = new THREE.Points(particlesGeometry, particlesMaterial);
            particlesGroup.add(particles);
            
            // Add secondary energy rays
            const energyGroup = new THREE.Group();
            scene.add(energyGroup);
            
            for (let i = 0; i < 5; i++) {
                const energyGeometry = new THREE.CylinderGeometry(0.01, 0.01, 3, 8, 1);
                const energyMaterial = new THREE.MeshBasicMaterial({
                    color: new THREE.Color().lerpColors(color1, color2, i / 5),
                    transparent: true,
                    opacity: 0.3
                });
                
                const energy = new THREE.Mesh(energyGeometry, energyMaterial);
                energy.rotation.z = Math.PI / 2;
                energy.rotation.y = i * Math.PI / 2.5;
                energyGroup.add(energy);
            }
            
            // Add a subtle outer glow
            const glowGeometry = new THREE.SphereGeometry(1.1, 32, 32);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: 0x9d92e6,
                transparent: true,
                opacity: 0.1,
                side: THREE.BackSide
            });
            
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            glow.scale.multiplyScalar(1.2);
            headGroup.add(glow);
            
            // Animation variables
            let animationFrameId;
            let speaking = false;
            const mouthOriginalPosition = mouthGroup.position.clone();
            
            // Audio element to detect when therapist is speaking
            const therapistAudio = document.getElementById('therapist-audio');
            therapistAudio.addEventListener('play', () => {
                speaking = true;
            });
            
            therapistAudio.addEventListener('pause', () => {
                speaking = false;
                // Reset mouth
                mouthGroup.position.copy(mouthOriginalPosition);
                mouthCurve.v1.y = 0.1; // Reset to smile
                updateMouthGeometry();
            });
            
            therapistAudio.addEventListener('ended', () => {
                speaking = false;
                // Reset mouth
                mouthGroup.position.copy(mouthOriginalPosition);
                mouthCurve.v1.y = 0.1; // Reset to smile
                updateMouthGeometry();
            });
            
            // Function to update mouth geometry dynamically
            function updateMouthGeometry() {
                // Update mouth curves
                mouthGroup.remove(mouth);
                mouthGroup.remove(mouthGlow);
                
                const newMouthGeometry = new THREE.TubeGeometry(mouthCurve, 30, 0.03, 20, false);
                mouth.geometry.dispose();
                mouth.geometry = newMouthGeometry;
                
                const newMouthGlowGeo = new THREE.TubeGeometry(mouthCurve, 30, 0.05, 20, false);
                mouthGlow.geometry.dispose();
                mouthGlow.geometry = newMouthGlowGeo;
            }
            
            // Animation loop
            function animate() {
                animationFrameId = requestAnimationFrame(animate);
                
                // Update particle shader time
                particles.material.uniforms.time.value = Date.now() * 0.001;
                
                // Subtle head movement
                headGroup.rotation.y = Math.sin(Date.now() * 0.001) * 0.1;
                headGroup.rotation.x = Math.sin(Date.now() * 0.0008) * 0.05;
                headGroup.position.y = Math.sin(Date.now() * 0.002) * 0.05;
                
                // Animate eye movement - make eyes look around occasionally
                const eyeTime = Date.now() * 0.001;
                const eyeMovementX = Math.sin(eyeTime * 0.3) * 0.1;
                const eyeMovementY = Math.cos(eyeTime * 0.2) * 0.1;
                
                leftIris.position.x = eyeMovementX * 0.5;
                leftIris.position.y = eyeMovementY * 0.5;
                leftPupil.position.x = eyeMovementX * 0.5;
                leftPupil.position.y = eyeMovementY * 0.5;
                
                rightIris.position.x = eyeMovementX * 0.5;
                rightIris.position.y = eyeMovementY * 0.5;
                rightPupil.position.x = eyeMovementX * 0.5;
                rightPupil.position.y = eyeMovementY * 0.5;
                
                // Animate blinking
                const blinkInterval = 4000; // Blink every 4 seconds
                const blinkDuration = 150; // Blink lasts 150ms
                
                const time = Date.now();
                const blinkPhase = time % blinkInterval;
                
                if (blinkPhase < blinkDuration) {
                    const blinkProgress = blinkPhase / blinkDuration;
                    const eyeScale = blinkProgress < 0.5 
                        ? 1 - blinkProgress * 2 
                        : (blinkProgress - 0.5) * 2;
                    
                    leftEyeGroup.scale.y = eyeScale;
                    rightEyeGroup.scale.y = eyeScale;
                } else {
                    leftEyeGroup.scale.y = 1;
                    rightEyeGroup.scale.y = 1;
                }
                
                // Animate mouth when speaking
                if (speaking) {
                    const talkTime = Date.now() * 0.01;
                    // Animate multiple mouth shapes to simulate talking
                    const openAmount = Math.sin(talkTime) * 0.5 + 0.5;
                    mouthCurve.v1.y = -0.1 - openAmount * 0.15; // Make the mouth open and close
                    
                    // Update mouth geometry to show new curve
                    updateMouthGeometry();
                    
                    // Add subtle movement to the head when speaking
                    headGroup.position.y += Math.sin(talkTime * 2) * 0.01;
                    headGroup.rotation.z = Math.sin(talkTime) * 0.02;
                }
                
                // Animate energy rays
                energyGroup.rotation.y += 0.003;
                
                // Animate the outer glow pulsing
                const glowScale = 1.2 + Math.sin(Date.now() * 0.001) * 0.05;
                glow.scale.set(glowScale, glowScale, glowScale);
                
                // Render
                renderer.render(scene, camera);
            }
            
            // Handle window resize
            function onWindowResize() {
                const width = container.clientWidth;
                const height = container.clientHeight;
                
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                
                renderer.setSize(width, height);
            }
            
            window.addEventListener('resize', onWindowResize);
            
            // Start animation
            animate();
            
            // Clean up on page unload
            window.addEventListener('beforeunload', () => {
                cancelAnimationFrame(animationFrameId);
                window.removeEventListener('resize', onWindowResize);
                renderer.dispose();
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return HTML_CONTENT

@app.route('/start_session', methods=['POST'])
def start_session():
    global therapist, session_active
    
    if session_active:
        return jsonify({'status': 'error', 'message': 'Session already active'})
    
    therapist = VirtualTherapist()
    session_active = True
    
    # Start the session in a separate thread to not block the Flask server
    async def start_therapist_session():
        global session_active
        try:
            await therapist.start_session()
        finally:
            session_active = False
    
    future = asyncio.run_coroutine_threadsafe(start_therapist_session(), loop)
    
    return jsonify({'status': 'success', 'message': 'Session started'})

@app.route('/end_session', methods=['POST'])
def end_session():
    global session_active
    
    if not session_active:
        return jsonify({'status': 'error', 'message': 'No active session'})
    
    # We'll rely on the user saying "goodbye" to end the session naturally
    return jsonify({'status': 'success', 'message': 'Say "goodbye" to end the session'})

@app.route('/get_audio_files', methods=['GET'])
def get_audio_files():
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

@app.route('/audio/therapist/<filename>')
def therapist_audio(filename):
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

@app.route('/audio/user/<filename>')
def user_audio(filename):
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

@app.route('/session_status', methods=['GET'])
def session_status():
    return jsonify({'active': session_active})

if __name__ == '__main__':
    # Create empty directories if they don't exist
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(THERAPIST_AUDIO_DIR, exist_ok=True)
    
    # Start the Flask application
    print("\n=== Virtual Therapist Web Interface ===")
    print("Starting server at http://localhost:3000")
    print("Use Ctrl+C to exit")
    app.run(host='0.0.0.0', port=3000, debug=True, use_reloader=False)