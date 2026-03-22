"""
install_and_run.py — Download Ollama model and start automation
"""

import urllib.request
import json
import time
import sys
import io

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.2"

def check_model_ready():
    """Check if model is downloaded and ready."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = data.get('models', [])
            for m in models:
                if MODEL in m.get('name', ''):
                    return True
    except Exception as e:
        pass
    return False

def pull_model():
    """Start pulling the model."""
    print(f"Downloading {MODEL} model (this may take 2-5 minutes)...")
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/pull",
            data=json.dumps({"name": MODEL}).encode(),
            headers={"Content-Type": "application/json"}
        )
        # Non-blocking pull
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Error starting pull: {e}")
        return False

def wait_for_model(timeout=300):
    """Wait for model to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        if check_model_ready():
            print(f"\n[OK] {MODEL} is ready!")
            return True
        print(".", end="", flush=True)
        time.sleep(5)
    return False

def main():
    print("=" * 60)
    print("Ollama Model Installer & Automation Starter")
    print("=" * 60)
    print()
    
    # Check if Ollama is running
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        urllib.request.urlopen(req, timeout=5)
        print("[OK] Ollama server is running")
    except Exception as e:
        print(f"[ERROR] Ollama server is not running!")
        print("Please install Ollama from: https://ollama.com/download/windows")
        return 1
    
    # Check if model already exists
    if check_model_ready():
        print(f"[OK] {MODEL} is already downloaded")
    else:
        # Start download
        if not pull_model():
            print("[ERROR] Could not start model download")
            return 1
        
        # Wait for download
        if not wait_for_model(timeout=300):  # 5 minutes timeout
            print("\n[ERROR] Model download timed out")
            print("You can continue using the system - model will download in background")
        else:
            print("[OK] Model download complete!")
    
    print()
    print("=" * 60)
    print("Starting Automation...")
    print("=" * 60)
    
    # Now run workflow_runner.py
    import subprocess
    print("\nRunning workflow_runner.py to process pending emails...")
    subprocess.run([sys.executable, "workflow_runner.py"])
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
