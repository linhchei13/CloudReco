from fastapi import FastAPI, UploadFile, File, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .models import Base, Image
from .database import engine, SessionLocal
from .auth import (
    get_db, create_user, auth_user,
    get_current_user, create_token
)
import os
from .aws import get_labels
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi.responses import Response
from swiftclient.client import Connection as SwiftConnection
from jose import jwt as jose_jwt
from .auth import SECRET
from dotenv import load_dotenv
load_dotenv()
Base.metadata.create_all(bind=engine)
app = FastAPI()

# Enable CORS for local frontend development. Adjust origins for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates directory (templates is located at ../templates relative to src)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), '..', 'templates'))
# OpenStack Swift configuration (optional)
SWIFT_AUTH_URL = os.getenv('SWIFT_AUTH_URL')
SWIFT_USER = os.getenv('SWIFT_USER')
SWIFT_KEY = os.getenv('SWIFT_KEY')
SWIFT_TENANT = os.getenv('SWIFT_TENANT')
SWIFT_CONTAINER = os.getenv('SWIFT_CONTAINER')

# lazy init swift client
swift_client = None
print("AUTH_URL =", os.getenv("SWIFT_AUTH_URL"))
print("USER =", os.getenv("SWIFT_USER"))
print("KEY =", os.getenv("SWIFT_KEY"))
print("TENANT =", os.getenv("SWIFT_TENANT"))
try:
    if SWIFT_AUTH_URL and SWIFT_USER and SWIFT_KEY:
       swift_client = SwiftConnection(authurl=SWIFT_AUTH_URL, user=SWIFT_USER, key=SWIFT_KEY, tenant_name=SWIFT_TENANT, auth_version='3')
    else:
        print("Swift configuration not fully provided; skipping Swift client initialization.")
except Exception:
    print("Warning: failed to initialize Swift client; continuing without Swift support.")
    swift_client = None
@app.post("/api/signup")
def signup(username: str, password: str, db: Session = Depends(get_db)):
    user = create_user(db, username, password)
    return {"message": "ok"}

@app.post("/api/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user = auth_user(db, username, password)
    if not user:
        return {"error": "invalid"}
    token = create_token(user)
    return {"token": token}

@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # read file bytes
    print("Swift client initialized." if swift_client else "Swift client not configured.")
    try:
        content = await file.read()
    except Exception:
        file.file.seek(0)
        content = file.file.read()

    try:
        labels = get_labels(content)
    except NoCredentialsError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"AWS error: {e}")

    img = Image(
        filename=file.filename,
        labels=",".join(labels),
        owner_id=user.id
    )
    db.add(img)
    db.commit()

    # upload bytes to Swift under per-user path and save swift_path
    if swift_client and SWIFT_CONTAINER:
        try:
            # store under numeric user id to avoid username collisions/changes
            user_id_prefix = f"users/{user.id}"
            obj_name = f"{user_id_prefix}/images/{img.id}_{file.filename}"
            swift_client.put_object(SWIFT_CONTAINER, obj_name, contents=content, content_type=getattr(file, 'content_type', 'application/octet-stream'))
            img.swift_path = obj_name
            db.add(img)
            db.commit()
        except Exception as e:
            print(f"Warning: failed to save to Swift: {e}")
    else :
        print("Swift client not configured; skipping upload to Swift.")
    return {"filename": file.filename, "labels": labels}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Serve a simple frontend to interact with signup/login/upload/list/delete."""
    return templates.TemplateResponse('dashboard.html', {"request": request})

@app.get("/api/images")
def list_images(
    request: Request,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # include token as query param so browser <img> can fetch the proxied image
    auth_header = request.headers.get('authorization') or ''
    token = None
    if auth_header.lower().startswith('bearer '):
        token = auth_header.split(None, 1)[1]

    images = db.query(Image).filter(Image.owner_id == user.id).all()
    return [
        {
            "id": img.id,
            "filename": img.filename,
            "labels": img.labels.split(","),
            "image_url": f"/api/images/{img.id}/image" + (f"?token={token}" if token else ""),
            "created_at": img.created_at.isoformat() if img.created_at else None
        }
        for img in images
    ]


@app.get("/api/images/{image_id}/image")
def get_image(image_id: int, request: Request, db: Session = Depends(get_db)):
    # Accept token either via Authorization header or query param `token`
    token = None
    auth_header = request.headers.get('authorization')
    if auth_header and auth_header.lower().startswith('bearer '):
        token = auth_header.split(None, 1)[1]
    else:
        token = request.query_params.get('token')

    if not token:
        raise HTTPException(status_code=401, detail='Missing token')

    try:
        payload = jose_jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid token')

    user_id = payload.get('id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Invalid token payload')

    img = db.query(Image).filter(Image.id == image_id, Image.owner_id == user_id).first()
    if not img:
        raise HTTPException(status_code=404, detail='not found')

    # If image stored in Swift, proxy it
    if swift_client and img.swift_path:
        try:
            headers, body = swift_client.get_object(SWIFT_CONTAINER, img.swift_path)
            content_type = headers.get('content-type', 'application/octet-stream')
            return Response(content=body, media_type=content_type)
        except Exception as e:
            print(f"Warning: failed to fetch image from Swift: {e}")
            raise HTTPException(status_code=502, detail='failed to fetch image')
    else:   
        print("Swift client not configured or no swift_path; cannot fetch image.")
    # Fallback: no swift object
    raise HTTPException(status_code=404, detail='image not available')

@app.delete("/api/images/{image_id}")
def delete_image(
    image_id: int,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    img = db.query(Image).filter(
        Image.id == image_id,
        Image.owner_id == user.id
    ).first()

    if not img:
        return {"error": "not found"}

    # try delete from Swift if present
    if swift_client and img.swift_path:
        try:
            swift_client.delete_object(SWIFT_CONTAINER, img.swift_path)
        except Exception as e:
            print(f"Warning: failed to delete object from Swift: {e}")

    db.delete(img)
    db.commit()
    return {"ok": True}
