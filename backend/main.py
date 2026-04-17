"""
FastAPI backend for CrowdSync.
Handles stadium gate statuses, transport wait times, and AI Concierge chat.
"""
import os
import time
import random
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CrowdSync API", description="Proactive stadium crowd management system")

# Security: Add CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Secure in an actual prod environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Google Gemini
GENAI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)

# --- State & Caching ---
class StadiumState:
    def __init__(self):
        self.cached_status = None
        self.last_update_time = 0

state = StadiumState()

# --- Models ---
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

def sanitize_input(text: str) -> str:
    """Sanitize user input for chat to prevent basic injection."""
    return re.sub(r'[^\w\s\.,!?\'"-]', '', text)

def generate_simulated_status():
    """Generates simulated real-time data for stadium exit flow and transport."""
    colors = ["Red", "Yellow", "Green"]
    gates = [
        {"id": "Gate A", "status": random.choice(colors), "density": random.randint(10, 100)},
        {"id": "Gate B", "status": random.choice(colors), "density": random.randint(10, 100)},
        {"id": "Gate C", "status": random.choice(colors), "density": random.randint(10, 100)},
        {"id": "Gate D", "status": random.choice(colors), "density": random.randint(10, 100)}
    ]
    transport = [
        {"mode": "Metro", "wait_time": f"{random.randint(5, 30)}m"},
        {"mode": "Cabs", "wait_time": f"{random.randint(10, 60)}m"},
        {"mode": "Bus", "wait_time": f"{random.randint(5, 45)}m"}
    ]
    return {"gates": gates, "transport": transport}

@app.get("/api/stadium/status")
def get_stadium_status():
    """
    Returns real-time status of stadium gates and transportation.
    Efficiency: Implements a 30-second local cache.
    """
    current_time = time.time()
    if state.cached_status and (current_time - state.last_update_time < 30):
        return {"data": state.cached_status, "cached": True}
    
    new_data = generate_simulated_status()
    state.cached_status = new_data
    state.last_update_time = current_time
    return {"data": new_data, "cached": False}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_concierge(request: ChatRequest):
    """
    AI Concierge endpoint connecting to Gemini API.
    Provides stadium-related assistance based on user queries.
    """
    try:
        sanitized_message = sanitize_input(request.message)
        if not sanitized_message.strip():
            raise HTTPException(status_code=400, detail="Empty message")

        if not GENAI_API_KEY:
            # Fallback when no API Key is given
            return ChatResponse(reply=f"Simulated response to: {sanitized_message} (No Google API key found)")

        model = genai.GenerativeModel('gemini-pro')
        prompt = f"You are an AI Concierge for a stadium. Be helpful, concise, and polite. User asks: {sanitized_message}"
        response = model.generate_content(prompt)
        
        reply_text = response.text if response.parts else "I'm sorry, I couldn't understand that."
        return ChatResponse(reply=reply_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Serve Frontend Assets (For Docker/Cloud Run) ---
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{catchall:path}")
    def serve_frontend(catchall: str):
        file_path = os.path.join(frontend_dist, catchall)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
