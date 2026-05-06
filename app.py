from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq
import os
import re
import logging

# ---------------- INIT ----------------
load_dotenv()

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

ALLOWED_LANGUAGES = ["english", "hindi", "marathi"]

# ---------------- LOAD DATA ----------------
def load_data():
    data = {}
    for lang in ALLOWED_LANGUAGES:
        try:
            with open(os.path.join(DATA_DIR, f"{lang}.txt"), "r", encoding="utf-8") as f:
                data[lang] = f.read()
        except Exception as e:
            logging.warning(f"{lang}.txt load failed: {e}")
            data[lang] = ""
    return data

DATA_STORE = load_data()

# ---------------- GROQ ----------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    logging.error("❌ GROQ_API_KEY not found in environment variables")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

# ---------------- LANGUAGE DETECTION ----------------
def detect_language(text):
    if re.search(r'[\u0900-\u097F]', text):

        marathi_words = [
            "kay", "tumcha", "ahe", "madhe",
            "kuthe", "kasa", "kaay", "aahe"
        ]

        text_lower = text.lower()

        if any(word in text_lower for word in marathi_words):
            return "marathi"

        return "hindi"

    return "english"

# ---------------- DOMAIN FILTER ----------------
def is_sandip_related(question):
    q = question.lower()

    blocked = [
        "weather", "bitcoin", "ipl", "movie",
        "actor", "politics", "stock", "news"
    ]

    return not any(b in q for b in blocked)

# ---------------- CONTEXT SEARCH ----------------
def get_relevant_context(text, question):
    paragraphs = text.split("\n\n")
    scored = []

    for para in paragraphs:
        score = 0
        for word in question.lower().split():
            if word in para.lower():
                score += 2

        if len(para.strip()) > 30:
            scored.append((score, para))

    scored.sort(key=lambda x: x[0], reverse=True)

    best = [p for s, p in scored[:5] if s > 0]

    if not best:
        return text[:1500]

    return "\n\n".join(best)[:2000]

# ---------------- DEBUG MATCH CHECK ----------------
def is_context_used(context, question):
    matches = 0
    for word in question.lower().split():
        if word in context.lower():
            matches += 1
    return matches

# ---------------- RESPONSE GENERATOR ----------------
def generate_answer(question, context, lang):

    if not client:
        return "⚠️ AI service not configured properly."

    system_prompt = f"""
You are a smart AI assistant for Sandip University 🎓

STRICT RULES:
- Answer ONLY about Sandip University
- Use given context first
- You MUST reply ONLY in {lang}
- Do NOT use English if {lang} is hindi or marathi
- Always try to answer in {lang}
- Keep answer short and clear
- Add emojis naturally 😊
"""

    user_prompt = f"""
Context:
{context}

Question:
{question}
"""

    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )
            return response.choices[0].message.content

        except Exception as e:
            logging.error(f"{model} failed: {e}")

    return "⚠️ AI service temporarily unavailable. Please try again later."

# ---------------- ROUTES ----------------
@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# ---------------- CHAT API ----------------
@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"answer": "⚠️ Please ask a question."})

        lang = detect_language(question)

        if not is_sandip_related(question):
            return jsonify({
                "answer": "❌ Only Sandip University related questions allowed 🎓"
            })

        context_full = DATA_STORE.get(lang, "")
        context = get_relevant_context(context_full, question)

        match_score = is_context_used(context, question)

        logging.info(f"Question: {question}")
        logging.info(f"Match Score: {match_score}")

        answer = generate_answer(question, context, lang)

        if lang in ["marathi", "hindi"]:
            answer = "उत्तर: " + answer

        return jsonify({"answer": answer})

    except Exception as e:
        logging.error(f"ERROR: {e}")
        return jsonify({
            "answer": "⚠️ Server issue aaya hai, please dubara try karo."
        })

# ---------------- HEALTH ----------------
@app.route('/health')
def health():
    return jsonify({"status": "OK"})

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run()