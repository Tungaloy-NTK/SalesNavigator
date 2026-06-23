"""
Start both Streamlit and the tracker server together.
Usage:  python start.py
"""
import subprocess, sys, os, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))

def run_tracker():
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "tracker:app", "--host", "0.0.0.0", "--port", "8502", "--log-level", "warning"
    ], cwd=HERE)

def run_streamlit():
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", "8501", "--server.address", "0.0.0.0"
    ], cwd=HERE)

if __name__ == "__main__":
    print("Starting Tungaloy Sales Navigator...")
    print("  App:     http://localhost:8501")
    print("  Tracker: http://localhost:8502")
    print("")

    t = threading.Thread(target=run_tracker, daemon=True)
    t.start()
    time.sleep(1)
    run_streamlit()
