"""Datas e horas: sempre com fuso, gravadas em ISO 8601."""

from __future__ import annotations

from datetime import date, datetime


def agora() -> datetime:
    """Hora local com fuso (usada em logs e registros)."""
    return datetime.now().astimezone()


def agora_iso() -> str:
    return agora().isoformat(timespec="seconds")


def hoje() -> date:
    return agora().date()
