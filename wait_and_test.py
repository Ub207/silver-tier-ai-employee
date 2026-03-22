import time
import subprocess
import sys

print("Waiting 30 seconds for model download...")
time.sleep(30)

print("Testing Ollama connection...")
subprocess.run([sys.executable, "test_ollama.py"])
