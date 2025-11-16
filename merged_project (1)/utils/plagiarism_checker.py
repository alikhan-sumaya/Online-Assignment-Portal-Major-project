import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from docx import Document
from PyPDF2 import PdfReader

ALLOWED_EXT = {'.txt', '.pdf', '.docx'}

def extract_text_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    text = ""
    try:
        if ext == '.txt':
            with open(filepath, 'r', encoding='utf-8', errors="ignore") as f:
                text = f.read()
        elif ext == '.docx':
            doc = Document(filepath)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext == '.pdf':
            reader = PdfReader(filepath)
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
    except Exception as e:
        print("Error extracting text:", e)
    return text

def compute_similarity_between_texts(a, b):
    try:
        vect = TfidfVectorizer().fit_transform([a, b])
        sim = cosine_similarity(vect[0:1], vect[1:2])[0][0]
        return sim
    except Exception as e:
        print("Error computing similarity:", e)
        return 0.0

def compare_file_against_folder(target_filepath, folder):
    """
    Compare target_filepath against all files in folder.
    Returns the maximum similarity percentage found (0-100) and details list.
    """
    target_text = extract_text_from_file(target_filepath)
    if not target_text.strip():
        return 0.0, []
    results = []
    max_sim = 0.0
    for root, dirs, files in os.walk(folder):
        for fname in files:
            path = os.path.join(root, fname)
            if os.path.abspath(path) == os.path.abspath(target_filepath):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in ALLOWED_EXT:
                continue
            text = extract_text_from_file(path)
            if not text.strip():
                continue
            sim = compute_similarity_between_texts(target_text, text)
            perc = round(sim * 100, 2)
            results.append((path, perc))
            if perc > max_sim:
                max_sim = perc
    return max_sim, results
