#!/usr/bin/env python3
"""
SaulGPT Single-Launcher
 Starts backend + frontend with one click and opens browser
"""

import subprocess
import sys
import os
import time
import webbrowser
import threading

# Colors for terminal
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def log(msg, color=GREEN):
    print(f"{color}{msg}{RESET}")

def is_backend_running():
    try:
        import urllib.request
        urllib.request.urlopen('http://localhost:8000/docs', timeout=2)
        return True
    except:
        return False

def is_frontend_running():
    try:
        import urllib.request
        urllib.request.urlopen('http://localhost:5173', timeout=2)
        return True
    except:
        return False

def start_backend():
    log("[1/2] Starting Backend API...", YELLOW)
    # Change to backend directory and run
    os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
    subprocess.Popen(
        [sys.executable, 'api_server.py'],
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )

def start_frontend():
    log("[2/2] Starting Frontend...", YELLOW)
    os.chdir(os.path.join(os.path.dirname(__file__), 'saulgpt-ui'))
    subprocess.Popen(
        ['npm', 'run', 'dev'],
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )

def main():
    os.chdir(os.path.dirname(__file__))
    
    print("\n" + "="*50)
    print("  SaulGPT - Starting All Services")
    print("="*50 + "\n")

    # Start backend
    start_backend()
    
    # Wait for backend to initialize
    log("Waiting for backend to initialize...", YELLOW)
    for i in range(10):
        if is_backend_running():
            log("✓ Backend API ready!", GREEN)
            break
        time.sleep(1)
    else:
        log("⚠ Backend may take longer to start...", YELLOW)

    # Start frontend
    start_frontend()
    
    # Wait for frontend
    log("Waiting for frontend...", YELLOW)
    for i in range(10):
        if is_frontend_running():
            log("✓ Frontend ready!", GREEN)
            break
        time.sleep(1)

    # Open browser
    log("\nopening browser...", GREEN)
    time.sleep(2)
    webbrowser.open('http://localhost:5173')

    print("\n" + "="*50)
    print("  SaulGPT is running!")
    print("="*50)
    print("\n  Backend API:  http://localhost:8000")
    print("  Frontend:     http://localhost:5173")
    print("\n  Press Enter to exit...")
    print("="*50 + "\n")
    
    input()

if __name__ == '__main__':
    main()