"""Git-style design history."""

import json
import re
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

HISTORY_DIR = Path(__file__).parent.parent / "static" / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


class CommitData(BaseModel):
    design_id: str
    parent_id: Optional[str] = None
    branch: str = "main"
    message: str = "design update"
    params: dict
    estimates: dict


class CommitResult(BaseModel):
    commit_id: str
    timestamp: float
    branch: str
    message: str


class HistoryTree(BaseModel):
    design_id: str
    branches: List[str]
    commits: List[dict]


def _validate_design_id(design_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_-]+$', design_id):
        raise HTTPException(status_code=400, detail="Invalid design_id")
    return design_id


def _design_file(design_id: str) -> Path:
    return HISTORY_DIR / f"{design_id}.json"


@router.post("/commit", response_model=CommitResult)
async def commit(data: CommitData):
    _validate_design_id(data.design_id)
    commit_id = str(uuid.uuid4())[:12]
    timestamp = time.time()

    record = {
        "commit_id": commit_id,
        "parent_id": data.parent_id,
        "branch": data.branch,
        "message": data.message,
        "timestamp": timestamp,
        "params": data.params,
        "estimates": data.estimates,
    }

    filepath = _design_file(data.design_id)
    history = []
    if filepath.exists():
        history = json.loads(filepath.read_text())

    history.append(record)
    filepath.write_text(json.dumps(history, indent=2))

    return CommitResult(commit_id=commit_id, timestamp=timestamp, branch=data.branch, message=data.message)


@router.get("/tree/{design_id}", response_model=HistoryTree)
async def tree(design_id: str):
    _validate_design_id(design_id)
    filepath = _design_file(design_id)
    if not filepath.exists():
        return HistoryTree(design_id=design_id, branches=["main"], commits=[])

    history = json.loads(filepath.read_text())
    branches = list({c["branch"] for c in history})

    return HistoryTree(design_id=design_id, branches=branches, commits=history)


@router.post("/branch/{design_id}")
async def create_branch(design_id: str, new_branch: str, from_commit: Optional[str] = None):
    _validate_design_id(design_id)
    filepath = _design_file(design_id)
    if not filepath.exists():
        raise ValueError("Design not found")

    history = json.loads(filepath.read_text())
    # Mark branch point
    history.append({
        "commit_id": str(uuid.uuid4())[:12],
        "parent_id": from_commit,
        "branch": new_branch,
        "message": f"branched from {from_commit or 'main'}",
        "timestamp": time.time(),
        "params": {},
        "estimates": {},
    })
    filepath.write_text(json.dumps(history, indent=2))

    return {"status": "ok", "branch": new_branch}


@router.get("/checkout/{design_id}/{commit_id}")
async def checkout(design_id: str, commit_id: str):
    _validate_design_id(design_id)
    filepath = _design_file(design_id)
    if not filepath.exists():
        raise ValueError("Design not found")

    history = json.loads(filepath.read_text())
    for c in history:
        if c["commit_id"] == commit_id:
            return c

    raise ValueError("Commit not found")
