# tunnel_manager.py
# Runs a robust SSH tunnel with keepalive, auto-reconnect, and dynamic URL discovery

import subprocess
import time
import re
import json
import socket
import os

TUNNEL_STATE_FILE = os.path.join(os.path.dirname(__file__), "tunnel_state.json")

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "10.212.70.57"

def write_state(active, url):
    lan_ip = get_lan_ip()
    state = {
        "active": active,
        "url": url,
        "lan_ip": lan_ip,
        "local_url": f"http://{lan_ip}:8000",
        "timestamp": time.time()
    }
    try:
        with open(TUNNEL_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print("Error writing state:", e)

def run_tunnel():
    print("Starting robust tunnel manager...")
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-R", "80:localhost:8000",
        "nokey@localhost.run"
    ]
    
    while True:
        try:
            print(f"[{time.strftime('%X')}] Launching SSH tunnel to localhost.run...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            tunnel_url = None
            for line in iter(proc.stdout.readline, ''):
                print(line.strip())
                match = re.search(r'https://[a-zA-Z0-9\.\-]+\.lhr\.life', line)
                if match:
                    tunnel_url = match.group(0)
                    print(f"[{time.strftime('%X')}] >>> ACTIVE TUNNEL URL: {tunnel_url} <<<")
                    write_state(True, tunnel_url)
            
            proc.wait()
            print(f"[{time.strftime('%X')}] Tunnel process exited with code {proc.returncode}. Reconnecting in 3s...")
            write_state(False, None)
            time.sleep(3)
        except Exception as e:
            print("Tunnel loop exception:", e)
            write_state(False, None)
            time.sleep(3)

if __name__ == "__main__":
    write_state(False, None)
    run_tunnel()
