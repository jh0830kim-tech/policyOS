"""Compatibility ASGI entry point; injected deployments import app.application."""

from app.application import create_app, lifespan

app = create_app()

__all__ = ("app", "create_app", "lifespan")
