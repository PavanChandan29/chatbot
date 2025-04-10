import os
import logging
import pinecone
from configparser import ConfigParser
from sentence_transformers import SentenceTransformer
from logging_config import configure_logging
from langchain.docstore.document import Document

# Configure logging using your custom function
configure_logging(log_file="scraping.log", log_level=logging.INFO)

# Load configuration from config.ini if needed
config = ConfigParser()
config.read('config.ini')

# Initialize the SentenceTransformer model
model_name = "all-MiniLM-L6-v2"
embedding_model = SentenceTransformer(model_name)
logging.info(f"Loaded embedding model: {model_name}")

# Pinecone configuration (replace with your actual key, environment, and index name)
PINECONE_API_KEY = "pcsk_6R2ucq_J4vEtoSvYHs21aTArmsRzqRpE6SSgYvV6DKtm3kDZCe6Bei8nVK8jUZoJmbL9f4"
PINECONE_ENV = "us-east-1"
INDEX_NAME = "chatbotv1"

# Initialize Pinecone using the new interface
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key=PINECONE_API_KEY, spec=ServerlessSpec(cloud='aws', region=PINECONE_ENV))
if INDEX_NAME not in pc.list_indexes().names():
    logging.error(f"Index '{INDEX_NAME}' not found in Pinecone.")
    exit(1)
index = pc.Index(INDEX_NAME)
logging.info(f"Connected to Pinecone index: {INDEX_NAME}")

def split_text_into_overlapping_chunks(file_path, max_chunk_chars=2000, overlap_chars=400):
    """
    Splits the file content into overlapping chunks.
    - Splitting is performed on paragraph boundaries.
    - When a chunk reaches max_chunk_chars, it is saved and the next chunk is
      started with the last `overlap_chars` of the previous chunk.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read().strip()

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current_chunk = ""
    i = 0

    while i < len(paragraphs):
        para = paragraphs[i]
        # If adding this paragraph (with separator) stays within the limit, add it.
        if current_chunk:
            tentative = current_chunk + "\n\n" + para
        else:
            tentative = para

        if len(tentative) <= max_chunk_chars:
            current_chunk = tentative
            i += 1
        else:
            # If current_chunk is empty (i.e. a single paragraph is too long),
            # then split the paragraph itself.
            if not current_chunk:
                for j in range(0, len(para), max_chunk_chars):
                    chunk_piece = para[j:j+max_chunk_chars]
                    chunks.append(chunk_piece.strip())
                i += 1
            else:
                chunks.append(current_chunk.strip())
                # Start next chunk with overlap: last overlap_chars of the current chunk.
                if len(current_chunk) > overlap_chars:
                    current_chunk = current_chunk[-overlap_chars:]
                else:
                    current_chunk = ""
    if current_chunk:
        chunks.append(current_chunk.strip())

    logging.info(f"Split text into {len(chunks)} overlapping chunks.")
    return chunks

def create_documents(chunks):
    """
    Creates Document objects from text chunks with minimal metadata.
    """
    documents = []
    for i, chunk in enumerate(chunks):
        doc = Document(page_content=chunk, metadata={"chunk_index": i})
        documents.append(doc)
    return documents

def embed_and_upsert_documents(documents):
    """
    Generates embeddings for each Document's page_content using the SentenceTransformer model,
    then upserts them into the Pinecone index with minimal metadata that includes the full text.
    """
    texts = [doc.page_content for doc in documents]
    embeddings = embedding_model.encode(texts, show_progress_bar=True)
    logging.info("Generated embeddings for all documents.")

    vectors = []
    for doc, embedding in zip(documents, embeddings):
        vector = {
            "id": f"chunk_{doc.metadata['chunk_index']}",
            "values": embedding.tolist(),
            "metadata": {"text": doc.page_content, "chunk_index": doc.metadata["chunk_index"]}
        }
        vectors.append(vector)

    upsert_response = index.upsert(vectors=vectors)
    logging.info(f"Upserted {len(vectors)} vectors into Pinecone.")
    return upsert_response

if __name__ == "__main__":
    cleaned_file = "../processed_data/cleaned_merged_text.txt"
    if not os.path.exists(cleaned_file):
        logging.error(f"File {cleaned_file} does not exist.")
        exit(1)
    chunks = split_text_into_overlapping_chunks(cleaned_file, max_chunk_chars=2000, overlap_chars=400)
    documents = create_documents(chunks)
    response = embed_and_upsert_documents(documents)
    logging.info(f"Pinecone upsert response: {response}")
