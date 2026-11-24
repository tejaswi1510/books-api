#!/bin/bash
source .venv5/bin/activate
uvicorn app.main:app --reload --port 8100
