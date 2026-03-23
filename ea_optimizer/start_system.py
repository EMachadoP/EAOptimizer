#!/usr/bin/env python3
"""
EA Configuration Optimizer v1.2
System Launcher

Inicia o backend Flask e fornece instruções para o frontend.
"""

import subprocess
import sys
import os
import time
import webbrowser
from pathlib import Path

def print_banner():
    """Print system banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           EA Configuration Optimizer v1.2 - Sistema Quantitativo             ║
║                                                                              ║
║   FR-14: Regime Detection (Hurst + ADX)                                      ║
║   FR-15: Survival Analysis (Kaplan-Meier)                                    ║
║   FR-16: Robustness Mapping (3D Surface)                                     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_dependencies():
    """Check if required dependencies are installed"""
    print("Checking dependencies...")
    
    try:
        import flask
        import pandas
        import numpy
        import scipy
        import sqlalchemy
        print("✓ All dependencies found")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("\nPlease install dependencies:")
        print("  pip install -r backend/requirements.txt")
        return False

def init_database():
    """Initialize the database"""
    print("\nInitializing database...")
    
    sys.path.append('backend')
    from models.database import init_database
    
    db_path = "ea_optimizer.db"
    if os.path.exists(db_path):
        print(f"✓ Database found: {db_path}")
    else:
        engine = init_database(db_path)
        print(f"✓ Database created: {db_path}")
    
    return True

def start_backend():
    """Start the Flask backend"""
    print("\n" + "="*80)
    print("STARTING BACKEND SERVER")
    print("="*80 + "\n")
    
    backend_path = Path("backend/api/server.py")
    if not backend_path.exists():
        print(f"✗ Backend not found: {backend_path}")
        return None
    
    # Start Flask server
    process = subprocess.Popen(
        [sys.executable, str(backend_path)],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(2)
    
    if process.poll() is None:
        print("✓ Backend server started on http://localhost:5000")
        print("  API Documentation:")
        print("    - Health Check:  GET  http://localhost:5000/api/health")
        print("    - Dashboard:     GET  http://localhost:5000/api/dashboard/summary")
        print("    - Regime:        POST http://localhost:5000/api/regime/analyze")
        print("    - Survival:      POST http://localhost:5000/api/survival/analyze")
        print("    - Robustness:    POST http://localhost:5000/api/robustness/analyze")
        print("    - Optimization:  POST http://localhost:5000/api/optimization/run")
        return process
    else:
        stdout, stderr = process.communicate()
        print(f"✗ Failed to start backend")
        print(f"  stdout: {stdout}")
        print(f"  stderr: {stderr}")
        return None

def print_frontend_instructions():
    """Print instructions for starting the frontend"""
    print("\n" + "="*80)
    print("FRONTEND INSTRUCTIONS")
    print("="*80 + "\n")
    
    print("To start the React frontend:\n")
    print("  1. Open a new terminal")
    print("  2. Navigate to the frontend directory:")
    print("     cd frontend")
    print("  3. Install dependencies (if not done):")
    print("     npm install")
    print("  4. Start the development server:")
    print("     npm run dev")
    print("\n  The frontend will be available at: http://localhost:5173")
    print("\n" + "="*80 + "\n")

def main():
    """Main function"""
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Initialize database
    init_database()
    
    # Start backend
    backend_process = start_backend()
    
    if backend_process:
        print_frontend_instructions()
        
        print("\nPress Ctrl+C to stop the server\n")
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            backend_process.terminate()
            backend_process.wait()
            print("✓ Server stopped")
    else:
        print("\n✗ Failed to start system")
        sys.exit(1)

if __name__ == "__main__":
    main()
