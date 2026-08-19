"""
Minimal Vector DB + Local LLM (RAG) demo
-----------------------------------------
Goal: understand the core concepts, not build something production-grade.

Pipeline:
1. INDEX  : read .txt files -> split into chunks -> embed each chunk -> store in ChromaDB
2. RETRIEVE: embed the user's question -> ask ChromaDB for the closest chunks
3. GENERATE: stuff those chunks into a prompt -> ask qwen2.5 (via Ollama) to answer

Requirements (see requirements.txt):
pip install chromadb ollama

Before running, make sure Ollama is installed and these models are pulled:
ollama pull qwen2.5
ollama pull nomic-embed-text     (a small dedicated embedding model)

Run:
python main.py
"""

import os
import glob
import ollama
import chromadb

# Constants
DOCS_FOLDER = "docs"
CHUNK_SIZE = 500          # characters per chunk (kept simple, not token-based)
CHUNK_OVERLAP = 50
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5"
TOP_K = 3                 # how many chunks to retrieve per question

def load_documents(folder: str) -> list:
    """Read every .txt file in the folder. Returns list of (filename, text)."""
    docs = []
    for path in glob.glob(os.path.join(folder, "*.txt")):
        with open(path, "r", encoding="utf-8") as f:
            docs.append((os.path.basename(path), f.read()))
    return docs

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Very simple fixed-size chunker with overlap so context isn't cut mid-idea."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]

def embed(text: str) -> dict:
    """Turn text into a vector using a local embedding model via Ollama."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]

def build_vector_db() -> chromadb.Client:
    """Step 1: INDEX. Chunk every doc, embed each chunk, store in ChromaDB."""
    client = chromadb.Client()  # in-memory DB; swap for chromadb.PersistentClient() to save to disk
    collection = client.get_or_create_collection(name="demo_docs")

    docs = load_documents(DOCS_FOLDER)
    chunk_id = 0
    for filename, text in docs:
        for chunk in chunk_text(text):
            collection.add(
                ids=[str(chunk_id)],
                embeddings=[embed(chunk)],
                documents=[chunk],
                metadatas=[{"source": filename}],
            )
            chunk_id += 1

    print(f"Indexed {chunk_id} chunks from {len(docs)} documents.\n")
    return client

def retrieve(collection: chromadb.Client, question: str, k: int = TOP_K) -> list:
    """Step 2: RETRIEVE. Embed the question, find the closest stored chunks."""
    results = collection.query(query_embeddings=[embed(question)], n_results=k)
    chunks = results["documents"][0]
    sources = [m["source"] for m in results["metadatas"][0]]
    return list(zip(chunks, sources))

def generate_answer(question: str, retrieved_chunks: list) -> str:
    """Step 3: GENERATE. Feed retrieved context + question to qwen2.5."""
    context = "\n\n".join(f"[{src}]\n{chunk}" for chunk, src in retrieved_chunks)

    prompt = f"""Answer the question using ONLY the context below.
If the context doesn't contain the answer, say you don't know.

Context:
{context}

Question: {question}

Answer:"""

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]

def main():
    collection = build_vector_db()

    print("Vector DB + local LLM demo ready. Ask a question (or 'exit').\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue

        retrieved = retrieve(collection, question)

        print("\n--- Retrieved chunks (this is what the vector DB matched) ---")
        for chunk, src in retrieved:
            print(f"  [{src}] {chunk[:80]}...")
        print("---------------------------------------------------------------\n")

        answer = generate_answer(question, retrieved)
        print(f"qwen2.5: {answer}\n")

if __name__ == "__main__":
    main()