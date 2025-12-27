"""
FastAPI server for Robot web interface.

Provides a REST API for managing conversations with coding agents,
user authentication, folder browsing, and real-time chat functionality.
Uses SQLite with Peewee for persistence and JWT for authentication.
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from peewee import (
    Model, SqliteDatabase, CharField, TextField, DateTimeField,
    ForeignKeyField, BooleanField, IntegerField
)
from pydantic import BaseModel

from robot import Robot
from robot.base import AgentConfig

logger = logging.getLogger(__name__)

# Database setup
DB_PATH = Path("/tmp/robot/robot_web.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = SqliteDatabase(str(DB_PATH))

# JWT configuration
JWT_SECRET = os.getenv("ROBOT_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 1 week

# Default working directory for projects
DEFAULT_CODE_DIR = Path.home() / "Code"

# Security
security = HTTPBearer()


# Database models
class BaseDBModel(Model):
    class Meta:
        database = db


class User(BaseDBModel):
    """User account for authentication."""
    id = CharField(primary_key=True, default=lambda: str(uuid.uuid4()))
    username = CharField(unique=True, max_length=64)
    password_hash = CharField(max_length=128)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_active = BooleanField(default=True)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with SHA256."""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return self.password_hash == self.hash_password(password)


class Conversation(BaseDBModel):
    """Chat conversation with an agent."""
    id = CharField(primary_key=True, default=lambda: str(uuid.uuid4()))
    user = ForeignKeyField(User, backref='conversations')
    title = CharField(max_length=256, default="New Conversation")
    working_dir = CharField(max_length=512)
    agent = CharField(max_length=32, default="claude")
    model = CharField(max_length=64, default="opus")
    session_id = CharField(max_length=128, null=True)  # Claude session for resume
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    updated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_active = BooleanField(default=True)


class Message(BaseDBModel):
    """Individual message in a conversation."""
    id = CharField(primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation = ForeignKeyField(Conversation, backref='messages')
    role = CharField(max_length=16)  # user, assistant, system
    content = TextField()
    raw_response = TextField(null=True)  # Raw JSON from agent
    files_modified = TextField(null=True)  # JSON list of modified files
    duration = IntegerField(null=True)  # Response time in ms
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))


class ModifiedFile(BaseDBModel):
    """Track files modified during a conversation."""
    id = CharField(primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation = ForeignKeyField(Conversation, backref='modified_files')
    file_path = CharField(max_length=512)
    original_hash = CharField(max_length=64, null=True)
    modified_hash = CharField(max_length=64, null=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))


# Create tables
db.connect()
db.create_tables([User, Conversation, Message, ModifiedFile])


# Pydantic models for API
class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    working_dir: str
    agent: str = "claude"
    model: str = "opus"


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_active: Optional[bool] = None


class MessageCreate(BaseModel):
    content: str


class FolderCreate(BaseModel):
    name: str
    parent_path: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    working_dir: str
    agent: str
    model: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    files_modified: Optional[list] = None
    duration: Optional[int] = None
    created_at: datetime


class ModifiedFileResponse(BaseModel):
    id: str
    file_path: str
    can_diff: bool = True


class FolderItem(BaseModel):
    name: str
    path: str
    is_dir: bool


# Web-specific prompt prefix for UI feedback
WEB_PROMPT_PREFIX = """
You are running in a web interface. Provide clear, concise status updates as you work.
Format your responses for readability in a chat UI. Use markdown formatting.

When working on tasks:
1. Briefly acknowledge what you're doing
2. Show key findings or changes
3. Summarize results clearly

Keep explanations focused and avoid unnecessary verbosity.
If you modify files, mention which files were changed.
"""


# FastAPI app
app = FastAPI(
    title="Robot Web API",
    description="API for Robot coding agent web interface",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Auth utilities
def create_token(user: User) -> str:
    """Create JWT token for user."""
    payload = {
        "sub": user.id,
        "username": user.username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Verify JWT token and return user."""
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        user = User.get_or_none(User.id == payload["sub"])
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Auth endpoints
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    """Register a new user."""
    if User.get_or_none(User.username == user_data.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User.create(
        username=user_data.username,
        password_hash=User.hash_password(user_data.password)
    )
    token = create_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username
    )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login and get access token."""
    user = User.get_or_none(User.username == user_data.username)
    if not user or not user.verify_password(user_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username
    )


@app.get("/api/auth/me")
async def get_current_user(user: User = Depends(verify_token)):
    """Get current user info."""
    return {"id": user.id, "username": user.username}


# Folder endpoints
@app.get("/api/folders", response_model=list[FolderItem])
async def list_folders(
    path: Optional[str] = None,
    user: User = Depends(verify_token)
):
    """List folders in a directory."""
    base_path = Path(path) if path else DEFAULT_CODE_DIR

    if not base_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    if not base_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    items = []
    try:
        for item in sorted(base_path.iterdir()):
            # Skip hidden files and common non-project dirs
            if item.name.startswith('.'):
                continue
            if item.name in ['node_modules', '__pycache__', 'venv', '.venv']:
                continue

            items.append(FolderItem(
                name=item.name,
                path=str(item),
                is_dir=item.is_dir()
            ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return items


@app.post("/api/folders", response_model=FolderItem)
async def create_folder(
    folder: FolderCreate,
    user: User = Depends(verify_token)
):
    """Create a new folder."""
    parent = Path(folder.parent_path)
    if not parent.exists():
        raise HTTPException(status_code=404, detail="Parent directory not found")

    new_folder = parent / folder.name
    if new_folder.exists():
        raise HTTPException(status_code=400, detail="Folder already exists")

    try:
        new_folder.mkdir(parents=True)
        return FolderItem(
            name=folder.name,
            path=str(new_folder),
            is_dir=True
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


# Conversation endpoints
@app.get("/api/conversations", response_model=list[ConversationResponse])
async def list_conversations(user: User = Depends(verify_token)):
    """List all conversations for the current user."""
    conversations = (
        Conversation
        .select()
        .where(
            (Conversation.user == user) &
            (Conversation.is_active == True)
        )
        .order_by(Conversation.updated_at.desc())
    )

    result = []
    for conv in conversations:
        msg_count = Message.select().where(Message.conversation == conv).count()
        result.append(ConversationResponse(
            id=conv.id,
            title=conv.title,
            working_dir=conv.working_dir,
            agent=conv.agent,
            model=conv.model,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count
        ))
    return result


@app.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(
    conv_data: ConversationCreate,
    user: User = Depends(verify_token)
):
    """Create a new conversation."""
    working_dir = Path(conv_data.working_dir)
    if not working_dir.exists():
        raise HTTPException(status_code=404, detail="Working directory not found")

    title = conv_data.title or working_dir.name
    conv = Conversation.create(
        user=user,
        title=title,
        working_dir=str(working_dir),
        agent=conv_data.agent,
        model=conv_data.model
    )

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        working_dir=conv.working_dir,
        agent=conv.agent,
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0
    )


@app.get("/api/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str, user: User = Depends(verify_token)):
    """Get a specific conversation."""
    conv = Conversation.get_or_none(
        (Conversation.id == conv_id) &
        (Conversation.user == user)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_count = Message.select().where(Message.conversation == conv).count()
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        working_dir=conv.working_dir,
        agent=conv.agent,
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=msg_count
    )


@app.patch("/api/conversations/{conv_id}", response_model=ConversationResponse)
async def update_conversation(
    conv_id: str,
    updates: ConversationUpdate,
    user: User = Depends(verify_token)
):
    """Update a conversation."""
    conv = Conversation.get_or_none(
        (Conversation.id == conv_id) &
        (Conversation.user == user)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if updates.title is not None:
        conv.title = updates.title
    if updates.is_active is not None:
        conv.is_active = updates.is_active

    conv.updated_at = datetime.now(timezone.utc)
    conv.save()

    msg_count = Message.select().where(Message.conversation == conv).count()
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        working_dir=conv.working_dir,
        agent=conv.agent,
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=msg_count
    )


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str, user: User = Depends(verify_token)):
    """Delete (deactivate) a conversation."""
    conv = Conversation.get_or_none(
        (Conversation.id == conv_id) &
        (Conversation.user == user)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.is_active = False
    conv.save()
    return {"status": "deleted"}


# Message endpoints
@app.get("/api/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def list_messages(conv_id: str, user: User = Depends(verify_token)):
    """List all messages in a conversation."""
    conv = Conversation.get_or_none(
        (Conversation.id == conv_id) &
        (Conversation.user == user)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        Message
        .select()
        .where(Message.conversation == conv)
        .order_by(Message.created_at)
    )

    result = []
    for msg in messages:
        files = json.loads(msg.files_modified) if msg.files_modified else None
        result.append(MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            files_modified=files,
            duration=msg.duration,
            created_at=msg.created_at
        ))
    return result


def compute_file_hash(file_path: Path) -> Optional[str]:
    """Compute SHA256 hash of a file."""
    if not file_path.exists():
        return None
    try:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
    except Exception:
        return None


def track_modified_files(conv: Conversation, working_dir: Path) -> list[str]:
    """Track which files have been modified since last check."""
    modified = []

    # Get all tracked files for this conversation
    tracked = {f.file_path: f for f in conv.modified_files}

    # Check git status for modifications
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    file_path = str(working_dir / line)
                    if file_path not in tracked:
                        ModifiedFile.create(
                            conversation=conv,
                            file_path=file_path,
                            original_hash=compute_file_hash(Path(file_path))
                        )
                    modified.append(file_path)
    except Exception as e:
        logger.warning(f"Failed to track files: {e}")

    return modified


@app.post("/api/conversations/{conv_id}/messages", response_model=MessageResponse)
async def send_message(
    conv_id: str,
    message: MessageCreate,
    user: User = Depends(verify_token)
):
    """Send a message and get agent response."""
    conv = Conversation.get_or_none(
        (Conversation.id == conv_id) &
        (Conversation.user == user)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Store user message
    user_msg = Message.create(
        conversation=conv,
        role="user",
        content=message.content
    )

    # Configure agent
    config = AgentConfig(
        model=conv.model,
        working_dir=Path(conv.working_dir),
        prompt_prefix=WEB_PROMPT_PREFIX,
        session_id=conv.session_id,
        resume=conv.session_id is not None
    )

    # Run agent
    start_time = time.time()
    try:
        agent = Robot.get(conv.agent, config=config)
        response = agent.run(
            prompt=message.content,
            working_dir=Path(conv.working_dir)
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Track modified files
        files_modified = track_modified_files(conv, Path(conv.working_dir))

        # Update session ID for resume capability
        if hasattr(response, 'session_id') and response.session_id:
            conv.session_id = response.session_id
            conv.save()

        # Store assistant message
        assistant_msg = Message.create(
            conversation=conv,
            role="assistant",
            content=response.content if response.success else f"Error: {response.error}",
            raw_response=response.raw_output,
            files_modified=json.dumps(files_modified) if files_modified else None,
            duration=duration_ms
        )

        # Update conversation timestamp
        conv.updated_at = datetime.now(timezone.utc)
        conv.save()

        return MessageResponse(
            id=assistant_msg.id,
            role="assistant",
            content=assistant_msg.content,
            files_modified=files_modified,
            duration=duration_ms,
            created_at=assistant_msg.created_at
        )

    except Exception as e:
        logger.error(f"Agent error: {e}")

        error_msg = Message.create(
            conversation=conv,
            role="assistant",
            content=f"Error running agent: {str(e)}",
            duration=int((time.time() - start_time) * 1000)
        )

        return MessageResponse(
            id=error_msg.id,
            role="assistant",
            content=error_msg.content,
            files_modified=None,
            duration=error_msg.duration,
            created_at=error_msg.created_at
        )


# Modified files endpoints
@app.get("/api/conversations/{conv_id}/files", response_model=list[ModifiedFileResponse])
async def list_modified_files(conv_id: str, user: User = Depends(verify_token)):
    """List files modified in a conversation."""
    conv = Conversation.get_or_none(
        (Conversation.id == conv_id) &
        (Conversation.user == user)
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    files = ModifiedFile.select().where(ModifiedFile.conversation == conv)
    return [
        ModifiedFileResponse(
            id=f.id,
            file_path=f.file_path,
            can_diff=Path(f.file_path).exists()
        )
        for f in files
    ]


@app.get("/api/files/diff")
async def get_file_diff(
    file_path: str,
    conv_id: Optional[str] = None,
    user: User = Depends(verify_token)
):
    """Get git diff for a file."""
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", str(path)],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=10
        )
        return {"diff": result.stdout, "file_path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {e}")


@app.get("/api/files/content")
async def get_file_content(
    file_path: str,
    user: User = Depends(verify_token)
):
    """Get file content."""
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = path.read_text()
        return {"content": content, "file_path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


# Available models endpoint
@app.get("/api/models")
async def list_models(user: User = Depends(verify_token)):
    """List available models."""
    return {
        "claude": [
            {"id": "opus", "name": "Claude Opus 4", "default": True},
            {"id": "sonnet", "name": "Claude Sonnet 4"},
            {"id": "haiku", "name": "Claude Haiku 4"}
        ],
        "openrouter": [
            {"id": "opus", "name": "Claude Opus 4"},
            {"id": "sonnet", "name": "Claude Sonnet 4"},
            {"id": "deepseek", "name": "DeepSeek Chat"},
            {"id": "gpt5", "name": "GPT 5.2"},
            {"id": "gemini", "name": "Gemini 3 Pro"}
        ]
    }


# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve the main frontend page."""
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
