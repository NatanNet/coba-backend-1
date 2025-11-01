from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import shutil
import os

# ======================
# KONFIGURASI DATABASE
# ======================
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_cabai"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    """Dependency untuk mendapatkan session database"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ======================
# MODEL DATABASE
# ======================
class Klasifikasi(Base):
    __tablename__ = "klasifikasi"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    path = Column(String(255), nullable=False)
    hasil = Column(Integer, nullable=False)  # 0 = Sakit, 1 = Sehat
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

# ======================
# KONFIGURASI FASTAPI
# ======================
app = FastAPI(
    title="API Klasifikasi Cabai",
    version="1.0.0",
    description="API untuk menerima gambar dari ESP32-CAM dan menyimpan hasil klasifikasi cabai",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Buat direktori uploads jika belum ada
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ======================
# ENDPOINT ROOT (Health Check)
# ======================
@app.get("/", tags=["Health"])
def root():
    """Cek status API"""
    return {
        "status": "success",
        "message": " API Klasifikasi Cabai Aktif!",
        "timestamp": datetime.now().isoformat()
    }

# ======================
# ENDPOINT UPLOAD
# ======================
@app.post("/upload", tags=["Upload"])
async def upload_data(
    file: UploadFile = File(...),
    hasil: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload gambar hasil klasifikasi cabai dari ESP32-CAM
    
    **Parameter:**
    - file: Gambar hasil deteksi (jpg, jpeg, png, bmp)
    - hasil: 1 = Sehat, 0 = Sakit
    """
    try:
        # Validasi file type
        allowed_extensions = {"jpg", "jpeg", "png", "bmp"}
        file_extension = file.filename.split(".")[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type tidak didukung. Gunakan: {', '.join(allowed_extensions)}"
            )
        
        # Validasi hasil value
        if hasil not in [0, 1]:
            raise HTTPException(
                status_code=400,
                detail="Nilai hasil harus 0 (Sakit) atau 1 (Sehat)"
            )
        
        # Simpan file
        file_location = f"{UPLOAD_DIR}/{file.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Simpan ke database
        new_data = Klasifikasi(
            path=file_location,
            hasil=hasil
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)

        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "message": " Data berhasil disimpan",
                "data": {
                    "id": new_data.id,
                    "path": new_data.path,
                    "hasil": "Sehat" if new_data.hasil == 1 else "Sakit",
                    "created_at": str(new_data.created_at),
                    "updated_at": str(new_data.updated_at)
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ======================
# ENDPOINT GET ALL
# ======================
@app.get("/klasifikasi", tags=["Data"])
def get_all_data(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Ambil semua data klasifikasi
    
    **Parameter:**
    - skip: Jumlah data yang dilewatkan (pagination)
    - limit: Jumlah data yang diambil (default: 100)
    """
    records = db.query(Klasifikasi).order_by(Klasifikasi.id.desc()).offset(skip).limit(limit).all()
    total = db.query(Klasifikasi).count()

    result = [
        {
            "id": r.id,
            "path": r.path,
            "hasil": "Sehat" if r.hasil == 1 else "Sakit",
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at)
        }
        for r in records
    ]
    
    return {
        "status": "success",
        "total_data": total,
        "data": result
    }

# ======================
# ENDPOINT GET BY ID
# ======================
@app.get("/klasifikasi/{id}", tags=["Data"])
def get_data_by_id(id: int, db: Session = Depends(get_db)):
    """Ambil data klasifikasi berdasarkan ID"""
    record = db.query(Klasifikasi).filter(Klasifikasi.id == id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    
    return {
        "status": "success",
        "data": {
            "id": record.id,
            "path": record.path,
            "hasil": "Sehat" if record.hasil == 1 else "Sakit",
            "created_at": str(record.created_at),
            "updated_at": str(record.updated_at)
        }
    }

# ======================
# ENDPOINT GET BY STATUS
# ======================
@app.get("/klasifikasi/status/{hasil}", tags=["Data"])
def get_by_status(hasil: int, db: Session = Depends(get_db)):
    """Ambil data berdasarkan status (0=Sakit, 1=Sehat)"""
    if hasil not in [0, 1]:
        raise HTTPException(status_code=400, detail="Hasil harus 0 atau 1")
    
    records = db.query(Klasifikasi).filter(Klasifikasi.hasil == hasil).order_by(Klasifikasi.id.desc()).all()
    status_label = "Sehat" if hasil == 1 else "Sakit"
    
    result = [
        {
            "id": r.id,
            "path": r.path,
            "hasil": "Sehat" if r.hasil == 1 else "Sakit",
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at)
        }
        for r in records
    ]
    
    return {
        "status": "success",
        "filter": f"Status {status_label}",
        "total_data": len(result),
        "data": result
    }

# ======================
# ENDPOINT STATISTIK
# ======================
@app.get("/statistik", tags=["Analytics"])
def get_statistics(db: Session = Depends(get_db)):
    """Ambil statistik data klasifikasi"""
    total = db.query(Klasifikasi).count()
    sehat = db.query(Klasifikasi).filter(Klasifikasi.hasil == 1).count()
    sakit = db.query(Klasifikasi).filter(Klasifikasi.hasil == 0).count()
    
    return {
        "status": "success",
        "data": {
            "total_data": total,
            "status_sehat": sehat,
            "status_sakit": sakit,
            "persentase_sehat": round((sehat / total * 100), 2) if total > 0 else 0,
            "persentase_sakit": round((sakit / total * 100), 2) if total > 0 else 0
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)