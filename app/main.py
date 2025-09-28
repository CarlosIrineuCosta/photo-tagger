from fastapi import FastAPI
import gradio as gr

from app.ui import build_ui

app = FastAPI(title="photo-tag-pipeline")

demo = build_ui()

gradio_app = gr.mount_gradio_app(app, demo, path="/")

__all__ = ["app", "gradio_app"]
