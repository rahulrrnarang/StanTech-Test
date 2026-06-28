"""
Stantech - Backend Working Task
A small multi-tenant support-ticket API. See README.md for your task.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:8000/docs

Each request identifies its tenant via the X-Tenant-Id header.
(In production this would come from the authenticated session; a header keeps
this exercise simple.)
"""
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, ForeignKey, String, DateTime, func
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker, selectinload
)

engine = create_engine(
    "sqlite:///./tickets.db", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String)


class Requester(Base):
    __tablename__ = "requesters"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    subject: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    requester_id: Mapped[int] = mapped_column(ForeignKey("requesters.id"))
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    requester: Mapped["Requester"] = relationship()
    assigned_agent: Mapped[Optional["Agent"]] = relationship()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_tenant_id(
        x_tenant_id: int = Header(...),
        db: Session = Depends(get_db)
    ) -> int:
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == x_tenant_id)
        .first()
    )

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found",
        )
    return x_tenant_id


app = FastAPI(title="Stantech Tickets")

class AssignTicketRequest(BaseModel):
    agent_id: int

class TicketOut(BaseModel):
    id: int
    subject: str
    status: str
    requester: str
    assigned_agent: Optional[str] = None


def serialize(t: Ticket) -> dict:
    return {
        "id": t.id,
        "subject": t.subject,
        "status": t.status,
        "requester": t.requester.name,
        "assigned_agent": t.assigned_agent.name if t.assigned_agent else None,
    }


@app.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(current_tenant_id),
):
    tickets = (
        db.query(Ticket)
        .filter(Ticket.tenant_id == tenant_id)
        .options(selectinload(Ticket.requester), selectinload(Ticket.assigned_agent))
        .all()
    )
    return [serialize(t) for t in tickets]


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(current_tenant_id),
):
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.tenant_id == tenant_id
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return serialize(ticket)

@app.patch("/tickets/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(
    ticket_id: int,
    request: AssignTicketRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(current_tenant_id),
):
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id,
        Ticket.tenant_id == tenant_id
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    agent = db.query(Agent).filter(
        Agent.id == request.agent_id,
        Agent.tenant_id == tenant_id
    ).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    ticket.assigned_agent_id = agent.id
    db.commit()
    db.refresh(ticket)

    return serialize(ticket)

def seed():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    acme = Tenant(name="Acme Corp")
    globex = Tenant(name="Globex")
    db.add_all([acme, globex])
    db.flush()

    acme_agents = [Agent(tenant_id=acme.id, name=n) for n in ("Priya", "Rahul", "Anita")]
    globex_agents = [Agent(tenant_id=globex.id, name=n) for n in ("Marcus", "Lena", "Tom")]
    db.add_all(acme_agents + globex_agents)
    db.flush()

    # One distinct requester per ticket (high cardinality on purpose).
    def make_requester(tenant_id, i):
        r = Requester(tenant_id=tenant_id, name=f"Requester {tenant_id}-{i}")
        db.add(r)
        db.flush()
        return r.id

    # Named tickets (ids 1-4). Ticket id 4 belongs to Globex and is sensitive.
    db.add_all([
        Ticket(tenant_id=acme.id, subject="Login fails on mobile",
               requester_id=make_requester(acme.id, 0),
               assigned_agent_id=acme_agents[0].id),
        Ticket(tenant_id=acme.id, subject="Export to CSV is broken",
               requester_id=make_requester(acme.id, 1)),
        Ticket(tenant_id=globex.id, subject="Billing webhook not firing",
               requester_id=make_requester(globex.id, 0),
               assigned_agent_id=globex_agents[0].id),
        Ticket(tenant_id=globex.id, subject="Confidential: new pricing model for Q3",
               requester_id=make_requester(globex.id, 1)),
    ])
    db.flush()

    # Filler so the list endpoint returns many rows, each with its own requester.
    for i in range(60):
        db.add(Ticket(tenant_id=acme.id, subject=f"Acme issue #{i + 1}",
                      requester_id=make_requester(acme.id, 100 + i),
                      assigned_agent_id=acme_agents[i % len(acme_agents)].id))
    for i in range(40):
        db.add(Ticket(tenant_id=globex.id, subject=f"Globex issue #{i + 1}",
                      requester_id=make_requester(globex.id, 100 + i),
                      assigned_agent_id=globex_agents[i % len(globex_agents)].id))
    db.commit()
    db.close()


if __name__ == "__main__":
    seed()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
