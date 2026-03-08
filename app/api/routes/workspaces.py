"""Team Workspaces API - create, manage, invite members, tasks, notes."""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.workspace import (
    Workspace, WorkspaceMember, WorkspaceInvite, WorkspaceTask, WorkspaceNote,
    WorkspaceRole, InviteStatus, TaskStatus, TaskPriority,
)

router = APIRouter(prefix="/workspaces", tags=["Team Workspaces"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class InviteCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    role: str = "member"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    priority: str = "medium"
    assigned_to: Optional[int] = None
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[str] = None


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    content: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_membership(db: AsyncSession, workspace_id: int, user_id: int) -> WorkspaceMember | None:
    return (await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )).scalar_one_or_none()


async def _require_member(db: AsyncSession, workspace_id: int, user_id: int) -> WorkspaceMember:
    mem = await _get_membership(db, workspace_id, user_id)
    if not mem:
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")
    return mem


async def _require_admin(db: AsyncSession, workspace_id: int, user_id: int) -> WorkspaceMember:
    mem = await _require_member(db, workspace_id, user_id)
    if mem.role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
        raise HTTPException(status_code=403, detail="Admin or owner role required")
    return mem


def _serialize_workspace(ws, member_count: int = 0, task_count: int = 0, my_role: str = "member"):
    return {
        "id": ws.id,
        "name": ws.name,
        "description": ws.description,
        "created_by": ws.created_by,
        "is_active": ws.is_active,
        "member_count": member_count,
        "task_count": task_count,
        "my_role": my_role,
        "created_at": str(ws.created_at) if ws.created_at else None,
    }


# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------

@router.get("/", summary="List my workspaces")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Get all workspaces where user is a member
    memberships = (await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    )).scalars().all()

    result = []
    for mem in memberships:
        ws = (await db.execute(
            select(Workspace).where(Workspace.id == mem.workspace_id, Workspace.is_active == True)
        )).scalar_one_or_none()
        if not ws:
            continue
        mc = (await db.execute(
            select(func.count(WorkspaceMember.id)).where(WorkspaceMember.workspace_id == ws.id)
        )).scalar() or 0
        tc = (await db.execute(
            select(func.count(WorkspaceTask.id)).where(WorkspaceTask.workspace_id == ws.id)
        )).scalar() or 0
        result.append(_serialize_workspace(ws, mc, tc, mem.role.value))

    return {"items": result, "total": len(result)}


@router.post("/", summary="Create workspace")
async def create_workspace(
    payload: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ws = Workspace(
        name=payload.name,
        description=payload.description,
        created_by=user.id,
    )
    db.add(ws)
    await db.flush()
    await db.refresh(ws)

    # Add creator as owner
    db.add(WorkspaceMember(
        workspace_id=ws.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
    ))
    await db.flush()

    return _serialize_workspace(ws, 1, 0, "owner")


@router.get("/{ws_id}", summary="Get workspace details")
async def get_workspace(
    ws_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = await _require_member(db, ws_id, user.id)
    ws = (await db.execute(select(Workspace).where(Workspace.id == ws_id))).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Get members with user info
    members_q = (await db.execute(
        select(WorkspaceMember, User).join(User, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == ws_id)
    )).all()

    members = [{
        "id": m.WorkspaceMember.id,
        "user_id": m.User.id,
        "email": m.User.email,
        "full_name": m.User.full_name,
        "role": m.WorkspaceMember.role.value,
        "profile_picture": m.User.profile_picture,
        "joined_at": str(m.WorkspaceMember.joined_at) if m.WorkspaceMember.joined_at else None,
    } for m in members_q]

    # Get pending invites
    invites = (await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.workspace_id == ws_id,
            WorkspaceInvite.status == InviteStatus.PENDING,
        )
    )).scalars().all()

    pending_invites = [{
        "id": inv.id,
        "email": inv.email,
        "role": inv.role.value,
        "created_at": str(inv.created_at) if inv.created_at else None,
    } for inv in invites]

    tc = (await db.execute(
        select(func.count(WorkspaceTask.id)).where(WorkspaceTask.workspace_id == ws_id)
    )).scalar() or 0

    return {
        **_serialize_workspace(ws, len(members), tc, mem.role.value),
        "members": members,
        "pending_invites": pending_invites,
    }


@router.put("/{ws_id}", summary="Update workspace")
async def update_workspace(
    ws_id: int,
    payload: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_admin(db, ws_id, user.id)
    ws = (await db.execute(select(Workspace).where(Workspace.id == ws_id))).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if payload.name is not None:
        ws.name = payload.name
    if payload.description is not None:
        ws.description = payload.description
    await db.flush()
    return {"ok": True}


@router.delete("/{ws_id}", summary="Delete workspace")
async def delete_workspace(
    ws_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = await _require_member(db, ws_id, user.id)
    if mem.role != WorkspaceRole.OWNER:
        raise HTTPException(status_code=403, detail="Only workspace owner can delete")
    ws = (await db.execute(select(Workspace).where(Workspace.id == ws_id))).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.is_active = False
    await db.flush()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Invitations (email-based)
# ---------------------------------------------------------------------------

@router.post("/{ws_id}/invite", summary="Invite member by email")
async def invite_member(
    ws_id: int,
    payload: InviteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_admin(db, ws_id, user.id)

    ws = (await db.execute(select(Workspace).where(Workspace.id == ws_id))).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check if already a member
    invitee = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if invitee:
        existing_mem = await _get_membership(db, ws_id, invitee.id)
        if existing_mem:
            raise HTTPException(status_code=400, detail="User is already a member")

    # Check for existing pending invite
    existing_invite = (await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.workspace_id == ws_id,
            WorkspaceInvite.email == payload.email,
            WorkspaceInvite.status == InviteStatus.PENDING,
        )
    )).scalar_one_or_none()
    if existing_invite:
        raise HTTPException(status_code=400, detail="Invite already sent to this email")

    role = WorkspaceRole(payload.role) if payload.role in [r.value for r in WorkspaceRole] else WorkspaceRole.MEMBER
    invite = WorkspaceInvite(
        workspace_id=ws_id,
        invited_by=user.id,
        email=payload.email,
        role=role,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()
    await db.refresh(invite)

    # If user exists in system, create a notification
    if invitee:
        from app.api.routes.notifications import create_and_emit_notification
        from app.models.features import NotificationType
        await create_and_emit_notification(
            user_id=invitee.id,
            title="Workspace Invitation",
            message=f"{user.full_name} invited you to join '{ws.name}'",
            notif_type=NotificationType.SYSTEM,
            link=f"/team-workspaces?invite={invite.token}",
        )

    return {
        "ok": True,
        "invite_id": invite.id,
        "token": invite.token,
        "invite_link": f"/team-workspaces?invite={invite.token}",
    }


@router.post("/{ws_id}/invite/{invite_id}/cancel", summary="Cancel invite")
async def cancel_invite(
    ws_id: int,
    invite_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_admin(db, ws_id, user.id)
    invite = (await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.id == invite_id,
            WorkspaceInvite.workspace_id == ws_id,
            WorkspaceInvite.status == InviteStatus.PENDING,
        )
    )).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.status = InviteStatus.EXPIRED
    await db.flush()
    return {"ok": True}


@router.get("/invites/pending", summary="Get my pending invitations")
async def my_pending_invites(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invites = (await db.execute(
        select(WorkspaceInvite, Workspace).join(Workspace, WorkspaceInvite.workspace_id == Workspace.id)
        .where(
            WorkspaceInvite.email == user.email,
            WorkspaceInvite.status == InviteStatus.PENDING,
            WorkspaceInvite.expires_at > datetime.utcnow(),
        )
    )).all()

    return [{
        "id": inv.WorkspaceInvite.id,
        "workspace_id": inv.Workspace.id,
        "workspace_name": inv.Workspace.name,
        "role": inv.WorkspaceInvite.role.value,
        "token": inv.WorkspaceInvite.token,
        "created_at": str(inv.WorkspaceInvite.created_at) if inv.WorkspaceInvite.created_at else None,
    } for inv in invites]


@router.post("/invites/accept", summary="Accept invitation by token")
async def accept_invite(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invite = (await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.token == token,
            WorkspaceInvite.status == InviteStatus.PENDING,
        )
    )).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")

    if invite.expires_at and invite.expires_at < datetime.utcnow():
        invite.status = InviteStatus.EXPIRED
        await db.flush()
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Email must match or user must be the invitee
    if invite.email != user.email:
        raise HTTPException(status_code=403, detail="This invite was sent to a different email")

    # Check not already a member
    existing = await _get_membership(db, invite.workspace_id, user.id)
    if existing:
        invite.status = InviteStatus.ACCEPTED
        await db.flush()
        return {"ok": True, "workspace_id": invite.workspace_id, "message": "Already a member"}

    db.add(WorkspaceMember(
        workspace_id=invite.workspace_id,
        user_id=user.id,
        role=invite.role,
    ))
    invite.status = InviteStatus.ACCEPTED
    await db.flush()

    return {"ok": True, "workspace_id": invite.workspace_id}


@router.post("/invites/decline", summary="Decline invitation by token")
async def decline_invite(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invite = (await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.token == token,
            WorkspaceInvite.email == user.email,
            WorkspaceInvite.status == InviteStatus.PENDING,
        )
    )).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.status = InviteStatus.DECLINED
    await db.flush()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------

@router.put("/{ws_id}/members/{member_id}/role", summary="Change member role")
async def change_member_role(
    ws_id: int,
    member_id: int,
    role: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_admin(db, ws_id, user.id)
    mem = (await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == ws_id,
        )
    )).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail="Member not found")
    if mem.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot change owner role")
    mem.role = WorkspaceRole(role) if role in [r.value for r in WorkspaceRole] else WorkspaceRole.MEMBER
    await db.flush()
    return {"ok": True}


@router.delete("/{ws_id}/members/{member_id}", summary="Remove member")
async def remove_member(
    ws_id: int,
    member_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_admin(db, ws_id, user.id)
    mem = (await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == ws_id,
        )
    )).scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail="Member not found")
    if mem.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")
    await db.delete(mem)
    return {"ok": True}


@router.post("/{ws_id}/leave", summary="Leave workspace")
async def leave_workspace(
    ws_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = await _require_member(db, ws_id, user.id)
    if mem.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Owner cannot leave. Transfer ownership or delete the workspace.")
    await db.delete(mem)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@router.get("/{ws_id}/tasks", summary="List workspace tasks")
async def list_tasks(
    ws_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)

    base = select(WorkspaceTask, User).outerjoin(User, WorkspaceTask.assigned_to == User.id).where(
        WorkspaceTask.workspace_id == ws_id
    )
    if status_filter:
        base = base.where(WorkspaceTask.status == status_filter)

    rows = (await db.execute(base.order_by(WorkspaceTask.created_at.desc()))).all()

    return [{
        "id": r.WorkspaceTask.id,
        "title": r.WorkspaceTask.title,
        "description": r.WorkspaceTask.description,
        "status": r.WorkspaceTask.status.value,
        "priority": r.WorkspaceTask.priority.value,
        "assigned_to": r.WorkspaceTask.assigned_to,
        "assigned_name": r.User.full_name if r.User else None,
        "due_date": str(r.WorkspaceTask.due_date) if r.WorkspaceTask.due_date else None,
        "created_at": str(r.WorkspaceTask.created_at) if r.WorkspaceTask.created_at else None,
    } for r in rows]


@router.post("/{ws_id}/tasks", summary="Create task")
async def create_task(
    ws_id: int,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)

    due = None
    if payload.due_date:
        try:
            due = datetime.fromisoformat(payload.due_date)
        except ValueError:
            pass

    task = WorkspaceTask(
        workspace_id=ws_id,
        title=payload.title,
        description=payload.description,
        priority=TaskPriority(payload.priority) if payload.priority in [p.value for p in TaskPriority] else TaskPriority.MEDIUM,
        assigned_to=payload.assigned_to,
        created_by=user.id,
        due_date=due,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return {"ok": True, "id": task.id}


@router.put("/{ws_id}/tasks/{task_id}", summary="Update task")
async def update_task(
    ws_id: int,
    task_id: int,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)
    task = (await db.execute(
        select(WorkspaceTask).where(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == ws_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.status is not None:
        task.status = TaskStatus(payload.status) if payload.status in [s.value for s in TaskStatus] else task.status
    if payload.priority is not None:
        task.priority = TaskPriority(payload.priority) if payload.priority in [p.value for p in TaskPriority] else task.priority
    if payload.assigned_to is not None:
        task.assigned_to = payload.assigned_to if payload.assigned_to > 0 else None
    if payload.due_date is not None:
        try:
            task.due_date = datetime.fromisoformat(payload.due_date) if payload.due_date else None
        except ValueError:
            pass
    await db.flush()
    return {"ok": True}


@router.delete("/{ws_id}/tasks/{task_id}", summary="Delete task")
async def delete_task(
    ws_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)
    task = (await db.execute(
        select(WorkspaceTask).where(WorkspaceTask.id == task_id, WorkspaceTask.workspace_id == ws_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@router.get("/{ws_id}/notes", summary="List workspace notes")
async def list_notes(
    ws_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)
    rows = (await db.execute(
        select(WorkspaceNote, User).join(User, WorkspaceNote.created_by == User.id)
        .where(WorkspaceNote.workspace_id == ws_id)
        .order_by(WorkspaceNote.updated_at.desc())
    )).all()

    return [{
        "id": r.WorkspaceNote.id,
        "title": r.WorkspaceNote.title,
        "content": r.WorkspaceNote.content,
        "created_by": r.WorkspaceNote.created_by,
        "author_name": r.User.full_name,
        "created_at": str(r.WorkspaceNote.created_at) if r.WorkspaceNote.created_at else None,
        "updated_at": str(r.WorkspaceNote.updated_at) if r.WorkspaceNote.updated_at else None,
    } for r in rows]


@router.post("/{ws_id}/notes", summary="Create note")
async def create_note(
    ws_id: int,
    payload: NoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)
    note = WorkspaceNote(
        workspace_id=ws_id,
        title=payload.title,
        content=payload.content,
        created_by=user.id,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return {"ok": True, "id": note.id}


@router.put("/{ws_id}/notes/{note_id}", summary="Update note")
async def update_note(
    ws_id: int,
    note_id: int,
    payload: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)
    note = (await db.execute(
        select(WorkspaceNote).where(WorkspaceNote.id == note_id, WorkspaceNote.workspace_id == ws_id)
    )).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content
    await db.flush()
    return {"ok": True}


@router.delete("/{ws_id}/notes/{note_id}", summary="Delete note")
async def delete_note(
    ws_id: int,
    note_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _require_member(db, ws_id, user.id)
    note = (await db.execute(
        select(WorkspaceNote).where(WorkspaceNote.id == note_id, WorkspaceNote.workspace_id == ws_id)
    )).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    return {"ok": True}
