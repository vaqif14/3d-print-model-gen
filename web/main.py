"""FastAPI entry point for the 3D CAD Studio."""

import os
import sys
from pathlib import Path

# Add parent to path for cad_engine imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="3D Print CAD Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Import API routers
from api import design, geometry, mesh, history, image

app.include_router(design.router, prefix="/api/design", tags=["design"])
app.include_router(geometry.router, prefix="/api/geometry", tags=["geometry"])
app.include_router(mesh.router, prefix="/api/mesh", tags=["mesh"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(image.router, prefix="/api/image", tags=["image"])


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = static_dir / "index.html"
    return HTMLResponse(content=index_path.read_text())


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
