import asyncio
import os
from dotenv import load_dotenv

# Set a mock or look for the real api key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

from google import genai

async def main():
    if not API_KEY:
        print("GEMINI_API_KEY not found.")
        return

    _gemini_client = genai.Client(api_key=API_KEY)
    
    sanitized_message = "Where is Gate A?"
    
    current_status = {
        'gates': [{'id': 'Gate A', 'status': 'Green', 'density': 10}],
        'transport': [{'mode': 'Bus', 'wait_time': '10m'}]
    }

    gate_info = ", ".join([f"{g['id']}: {g['status']} (Density: {g['density']}%)" for g in current_status.get("gates", [])])
    transport_info = ", ".join([f"{t['mode']}: {t['wait_time']}" for t in current_status.get("transport", [])])
    
    prompt = (
        "You are a strictly constrained, helpful AI Concierge for Stadium Flow. "
        "Use the following real-time stadium context to answer the user's query intelligently:\n"
        f"[LIVE GATES]: {gate_info}\n"
        f"[LIVE TRANSPORT]: {transport_info}\n"
        "[STADIUM KNOWLEDGE]:\n"
        "- First Aid is located at Section 112, Section 340, and adjacent to the main concourse near Gate A.\n"
        "- For users looking to exit or find a gate, ALWAYS recommend the gates that are 'Green' (low density).\n"
        "- Mention that proceeding to a 'Green' gate grants a 10% food/beverage discount!\n"
        "If the user asks something completely unrelated to the stadium (e.g. coding, general facts), politely decline.\n\n"
        f"User query: {sanitized_message}\nConcierge:"
    )
    
    try:
        response = await _gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        print("SUCCESS:")
        print(response.text)
    except Exception as exc:
        print("ERROR OCCURRED:")
        print(type(exc))
        print(str(exc))

if __name__ == "__main__":
    asyncio.run(main())
