import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        # Try to import database module
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    import os as _os

    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Utility to persist uploads (for later processing/emailing)
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_files(files: List[UploadFile], subdir: str) -> List[str]:
    saved_paths: List[str] = []
    if not files:
        return saved_paths
    dest_dir = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    for f in files:
        filename = f.filename or "file"
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        safe_name = filename.replace("/", "_").replace("\\", "_")
        out_path = os.path.join(dest_dir, f"{ts}_{safe_name}")
        with open(out_path, "wb") as out:
            out.write(f.file.read())
        saved_paths.append(out_path)
    return saved_paths


@app.post("/api/submit-plan")
async def submit_plan(
    plan: str = Form(...),
    max_photos: int = Form(...),
    brand: str = Form(...),
    email: str = Form(...),
    products: Optional[int] = Form(None),
    files_0: Optional[List[UploadFile]] = File(default=None),
    files_1: Optional[List[UploadFile]] = File(default=None),
    files_2: Optional[List[UploadFile]] = File(default=None),
    files_3: Optional[List[UploadFile]] = File(default=None),
):
    try:
        batches: List[List[UploadFile]] = []
        for batch in [files_0, files_1, files_2, files_3]:
            if batch:
                # FastAPI gives a single UploadFile when only one selected; normalize to list
                if isinstance(batch, list):
                    batches.append(batch)
                else:
                    batches.append([batch])

        # Flatten all uploads
        all_uploads: List[UploadFile] = [uf for group in batches for uf in (group or [])]

        if not all_uploads:
            raise HTTPException(status_code=422, detail="Nenhum ficheiro enviado")

        subdir = f"plan_{plan}_{datetime.utcnow().strftime('%Y%m%d')}"
        saved = _save_files(all_uploads, subdir)

        # In a real setup, you'd email attachments to the target address here.
        # For this environment, we acknowledge receipt and store files for processing.
        payload = {
            "plan": plan,
            "max_photos": max_photos,
            "brand": brand,
            "email": email,
            "products": products,
            "saved_count": len(saved),
        }
        return JSONResponse({"ok": True, "message": "Recebido", "data": payload})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/custom-request")
async def custom_request(
    description: str = Form(...),
    brand: str = Form(...),
    email: str = Form(...),
    reference: Optional[UploadFile] = File(default=None),
):
    try:
        saved = []
        if reference is not None:
            saved = _save_files([reference], "custom")
        payload = {
            "description": description,
            "brand": brand,
            "email": email,
            "saved_count": len(saved),
        }
        return JSONResponse({"ok": True, "message": "Pedido recebido", "data": payload})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
