import os

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT, BOT_NAME, SUGGESTED_QUESTIONS

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Maximum number of prior turns kept and replayed to the model per request,
# to keep requests small and on-topic.
MAX_HISTORY_TURNS = 10


def build_contents(history, message):
    """Turn the client-supplied history + new message into API contents."""
    contents = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        text = turn.get("text", "")
        if role not in ("user", "model") or not text:
            continue
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=text)])
        )
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    )
    return contents


@app.route("/")
def index():
    return render_template(
        "index.html", bot_name=BOT_NAME, suggestions=SUGGESTED_QUESTIONS
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify({"error": "Server is missing GEMINI_API_KEY."}), 500

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    if len(message) > 2000:
        return jsonify({"error": "Message is too long."}), 400

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=build_contents(history, message),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=1024,
            ),
        )
        reply = (response.text or "").strip()
        if not reply:
            reply = "I couldn't generate a response. Please try rephrasing your question."
    except Exception:
        app.logger.exception("Gemini API request failed")
        return jsonify({"error": "Something went wrong reaching CivicMate. Please try again."}), 502

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)
