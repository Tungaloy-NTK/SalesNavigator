#!/bin/bash
# Sales Navigator — startup script
# Place this in your app directory on the server

cd /home/YOUR_CPANEL_USERNAME/salesnavigator
source venv/bin/activate
streamlit run app.py --server.port 8501 --server.headless true
