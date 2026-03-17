import requests
import re
import os
import logging

from config import Config

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

# Path to the reference uploads directory
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

def refine_ocr_text(ocr_text):
    if not ocr_text or not ocr_text.strip():
        return ocr_text

    # ---------- REMOVE OCR DEBUG LOGS ----------
    ocr_text = re.sub(r"\[.*?ppocr.*?\].*", "", ocr_text)
    ocr_text = re.sub(r"Namespace\(.*?\)", "", ocr_text)

    lines = ocr_text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line or "DEBUG" in line or len(line) > 200:
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)[:1200]

def get_rag_context():
    """Load the reference RAG content to provide context to the AI."""
    context_parts = []
    seen_content = set() # For basic deduplication
    
    try:
        if not os.path.exists(UPLOADS_DIR):
            return ""
            
        # Collect context from all .txt files in the uploads directory
        for filename in os.listdir(UPLOADS_DIR):
            if filename.endswith(".txt"):
                file_path = os.path.join(UPLOADS_DIR, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Use first 100 chars to avoid exact duplicate reference files
                    preview = content[:100].strip()
                    if preview and preview not in seen_content:
                        context_parts.append(f"Source {filename}:\n{content}")
                        seen_content.add(preview)
        
        # Combine all parts, but limit total size for the AI model (approx 4k-6k tokens)
        full_context = "\n\n".join(context_parts)
        return full_context[:6000] 
    except Exception as e:
        logging.error(f"Error reading RAG context: {e}")
    return ""

def generate_rag_evaluation(student_answer, model_answer, question_text=""):
    """
    Uses Ollama with RAG context to evaluate student answers more intelligently.
    """
    if not Config.OLLAMA_ENABLED:
        return None

    context = get_rag_context()
    
    prompt = f"""
You are an expert academic evaluator. You are provided with:
1. A Reference Knowledge Base (RAG Context)
2. A Teacher's Model Answer
3. A Student's Answer

### Reference Knowledge Base:
{context} 

### Question:
{question_text}

### Teacher's Model Answer:
{model_answer}

### Student's Answer to Evaluate:
{student_answer}

### Instructions:
- Compare the student's answer against BOTH the Teacher's Model Answer and the Reference Knowledge Base.
- Evaluate the conceptual depth, accuracy, and use of relevant keywords.
- Provide a similarity score between 0.0 and 1.0.
- Provide constructive feedback for the student.

### Response Format (JSON only):
{{
  "score": 0.85,
  "feedback": "The student has a good grasp of the concept but missed the specific example mentioned in the reference material.",
  "key_points_covered": ["point1", "point2"],
  "missing_points": ["point3"]
}}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=8
        )
        
        if response.status_code == 200:
            return response.json().get('response')
    except Exception as e:
        logging.error(f"Ollama RAG Evaluation Error: {e}")
    
    return None
