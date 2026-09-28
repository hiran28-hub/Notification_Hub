"""
Convenience root entrypoint allowing 'python app.py' to run from the root directory.
"""
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.join(current_dir, "notification-prototype")
sys.path.insert(0, project_dir)

from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
