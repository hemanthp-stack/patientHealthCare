import sys
import os
from pathlib import Path

# Add project root directory to sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    @app.api_route('/api/{full_path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    async def fallback_api(full_path: str):
        return JSONResponse({'status': 'fallback', 'path': full_path, 'error': str(e)})
