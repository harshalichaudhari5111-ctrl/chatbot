from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq
import os
import re

load_dotenv()

app = Flask(__name__)

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
        except:
            data[lang] = ""
    return data

DATA_STORE = load_data()

# ---------------- GROQ ----------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

# ---------------- LANGUAGE DETECTION (FIXED) ----------------
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

    if any(b in q for b in blocked):
        return False

    return True

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

# ---------------- RESPONSE GENERATOR (FIXED 🔥) ----------------
def generate_answer(question, context, lang):

    system_prompt = f"""
You are a smart AI assistant for Sandip University 🎓

STRICT RULES:
- Answer ONLY about Sandip University
- Use given context first
- You MUST reply ONLY in {lang}
- Do NOT use English if {lang} is hindi or marathi
- Never say you cannot speak {lang}
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
            print(f"{model} failed:", e)

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

        # 🌐 Language detect
        lang = detect_language(question)

        # 🚫 Domain filter
        if not is_sandip_related(question):
            return jsonify({
                "answer": "❌ Only Sandip University related questions allowed 🎓"
            })

        # 📚 Context fetch
        context_full = DATA_STORE.get(lang, "")
        context = get_relevant_context(context_full, question)

        # 🔍 DEBUG PRINT
        match_score = is_context_used(context, question)

        print("\n========= DEBUG =========")
        print("Question:", question)
        print("Match Score:", match_score)

        if match_score > 2:
            print("✅ DATA SOURCE: TEXT FILE (context used)")
        elif match_score > 0:
            print("⚠️ DATA SOURCE: PARTIAL MATCH (LLM may enhance)")
        else:
            print("❌ NO DATA FOUND → AI GUESS MODE")

        print("=========================\n")

        # 🤖 Answer generate
        answer = generate_answer(question, context, lang)

        # 🔥 FINAL LANGUAGE FORCE FIX
        if lang == "marathi":
            answer = "उत्तर: " + answer
        elif lang == "hindi":
            answer = "उत्तर: " + answer

        return jsonify({"answer": answer})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({
            "answer": "⚠️ Server issue aaya hai, please dubara try karo."
        })

# ---------------- HEALTH ----------------
@app.route('/health')
def health():
    return jsonify({"status": "OK"})

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)