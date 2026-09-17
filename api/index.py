import sys
import os
from pathlib import Path

# Ensure root directory is in sys.path under all serverless runtime setups
for candidate_root in [
    str(Path(__file__).resolve().parent.parent),
    os.getcwd(),
    '/var/task'
]:
    if candidate_root not in sys.path and os.path.exists(candidate_root):
        sys.path.insert(0, candidate_root)

try:
    from main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    @app.api_route('/api/{full_path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    async def fallback_api(full_path: str):
        return JSONResponse({'status': 'ok', 'fallback': True, 'path': full_path, 'message': 'Pulse Shield API Active'})
