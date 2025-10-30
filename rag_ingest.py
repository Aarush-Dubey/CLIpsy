import os
import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.docstore.document import Document

DATA_DIR = "rag_files"
DB_DIR = "chroma_bash"
os.makedirs(DB_DIR, exist_ok=True)

# === Load CSV ===
csv_path = os.path.join(DATA_DIR, "commandBashRAG.csv")
df = pd.read_csv(csv_path)
csv_docs = [
    Document(page_content=f"Category: {row.Category}\nCommand: {row.Command}\nPurpose: {row.Purpose}\nSyntax: {row.Syntax}\nOption: {row.Option}\nDescription: {row.Description}")
    for _, row in df.iterrows()
]

# === Load TXT ===
txt_path = os.path.join(DATA_DIR, "additionalNotesBashRAG.txt")
text_docs = []
if os.path.exists(txt_path):
    text_docs = TextLoader(txt_path).load()

# === Load PDF ===
pdf_path = os.path.join(DATA_DIR, "gitRAG.pdf")
pdf_docs = []
if os.path.exists(pdf_path):
    pdf_docs = PyPDFLoader(pdf_path).load()

# === Combine all ===
all_docs = csv_docs + text_docs + pdf_docs

# === Chunk ===
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
split_docs = splitter.split_documents(all_docs)

# === Use open-source embedding ===
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# === Create and persist vector store ===
db = Chroma.from_documents(split_docs, embeddings, persist_directory=DB_DIR)
db.persist()

print(f"✅ Ingestion complete! {len(split_docs)} chunks stored in {DB_DIR}")
