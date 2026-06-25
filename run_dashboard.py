#!/usr/bin/env python3
"""
Run Procurement Intelligence Dashboard
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # Get project root
    project_root = Path(__file__).resolve().parent
    
    # Change to project directory
    os.chdir(project_root)
    
    print("🚀 Starting Procurement Intelligence Dashboard...")
    print(f"📁 Working directory: {project_root}")
    print()
    
    # Run streamlit
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"],
            check=True
        )
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
