import streamlit as st
from datetime import datetime
import os
import json
import requests
import uuid
import torch
import whisper
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

st.set_page_config(page_title="Jugaadu Translator", layout="centered")

SUPPORTED_LANGUAGES = {
    "Hindi": {
        "code": "hi",
        "translation_model": "Helsinki-NLP/opus-mt-hi-en",
        "whisper_language": "hi"
    },
    "Telugu": {
        "code": "te",
        "translation_model": "Helsinki-NLP/opus-mt-te-en",
        "whisper_language": "te"
    },
    "Sanskrit": {
        "code": "sa",
        "translation_model": "Helsinki-NLP/opus-mt-sa-en",
        "whisper_language": "sa"
    }
}

AUDIO_SAVE_DIR = "data/audio"
RECORDS_PATH = "data/records.json"
os.makedirs(AUDIO_SAVE_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

def save_audio_file(uploaded_file, username):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = uploaded_file.name.split('.')[-1]
    filename = f"{username}_{timestamp}.{ext}"
    file_path = os.path.join(AUDIO_SAVE_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())
    return file_path, filename

@st.cache_resource(show_spinner="Loading Whisper model...")
def get_whisper_model():
    import os
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU
    model = whisper.load_model("tiny.en", device="cpu")
    return model

# ✅ FIXED: Use tokenizer and model explicitly
@st.cache_resource(show_spinner="Loading translation models...")
def get_translator(language):
    model_name = SUPPORTED_LANGUAGES[language]["translation_model"]
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return pipeline("translation", model=model, tokenizer=tokenizer)

@st.cache_resource(show_spinner="Loading summarizer...")
def get_summarizer():
    return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

def get_location():
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=5)
        data = resp.json()
        loc_str = f"{data.get('city', '')}, {data.get('region', '')}, {data.get('country', '')}"
        return loc_str.strip(", ")
    except:
        return "Unknown Location"

def save_record(record):
    if os.path.exists(RECORDS_PATH):
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    records.append(record)
    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def show_records():
    if not os.path.exists(RECORDS_PATH):
        st.info("No contributions yet.")
        return
    with open(RECORDS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    st.subheader("Previous Contributions")
    for rec in reversed(records[-5:]):
        st.markdown(f"**User:** {rec['username']}  \n"
                    f"**Time:** {rec['timestamp']}  \n"
                    f"**Location:** {rec['location']}  \n"
                    f"**Title:** {rec['title']}")
        st.markdown(f"**Idiom:** {rec['input_text']}")
        st.markdown(f"**Translation:** {rec['translation']}")
        st.markdown(f"**Description:** {rec['description']}")
        if rec['audio_path'] and os.path.exists(rec['audio_path']):
            with open(rec['audio_path'], 'rb') as f_:
                st.audio(f_.read())
        st.markdown("---")

if "username" not in st.session_state:
    st.title("Jugaadu Translator 🧠")
    st.markdown("Enter a username to begin contributing to the idioms corpus.")
    username = st.text_input("Username (choose a unique handle)", max_chars=30)
    if st.button("Continue") and username:
        st.session_state["username"] = username.strip()
        st.success(f"Welcome, {username.strip()}! Proceed to record or type idioms.")
        st.rerun()
    st.stop()

st.title("Jugaadu Translator 🧠")
st.markdown(f"Hi, **{st.session_state['username']}**!")

col1, col2 = st.columns(2)
with col1:
    language = st.selectbox("Pick Idiom Language", list(SUPPORTED_LANGUAGES.keys()))
with col2:
    input_mode = st.radio("Input Type", ["Type", "Upload Voice"])

input_text = ""
audio_path = None

if input_mode == "Type":
    input_text = st.text_area("Type the idiom/dialect phrase:", height=100)
else:
    st.markdown("Upload a short voice note of your idiom (.wav, .mp3):")
    audio_file = st.file_uploader("Choose audio file", type=['wav', 'mp3'])
    if audio_file:
        try:
            audio_path, _ = save_audio_file(audio_file, st.session_state["username"])
            st.success("Audio uploaded and saved.")
            asr_model = get_whisper_model()
            result = asr_model.transcribe(audio_path, language=SUPPORTED_LANGUAGES[language]['whisper_language'])
            input_text = result["text"]
            st.markdown("**Transcription:** " + input_text)
        except Exception as e:
            st.error(f"Failed to process audio: {e}")

if st.button("Translate", disabled=not input_text.strip()):
    with st.spinner("Translating and generating summary..."):
        translator = get_translator(language)
        translation = translator(input_text)[0]['translation_text']
        summarizer = get_summarizer()
        try:
            desc = summarizer(translation, max_length=60, min_length=15, do_sample=False)[0]['summary_text']
        except Exception:
            desc = translation
        title = desc.split(".")[0][:40]
        location = get_location()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "username": st.session_state['username'],
            "input_text": input_text,
            "translation": translation,
            "audio_path": audio_path if audio_path else "",
            "title": title,
            "description": desc,
            "timestamp": timestamp,
            "location": location
        }
        save_record(record)
        st.success("Submission saved!")
        st.markdown(f"#### Title: {title}")
        st.markdown(f"**Translation:** {translation}")
        st.markdown(f"**Description:** {desc}")
        st.markdown(f"**Location:** {location}")
        if audio_path and os.path.exists(audio_path):
            with open(audio_path, 'rb') as f:
                st.audio(f.read())
        st.balloons()

st.markdown("---")
show_records()
st.markdown("---")
st.markdown("**All data stays local! You can find files inside `data/` for research use. No cloud required.**")
