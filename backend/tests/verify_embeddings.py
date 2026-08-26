import chromadb
import os
import json

VECTOR_DB_DIR = "vector_db/chroma_storage"
COLLECTION_NAME = "saulgpt_indian_laws"

def verify_chroma():
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        count = collection.count()
        print(f"Total chunks in collection '{COLLECTION_NAME}': {count}")
        
        if count > 0:
            # Peek at the first few items
            results = collection.peek(limit=5)
            print("\n--- Sample Document and Metadata ---")
            for i in range(len(results["ids"])):
                print(f"ID: {results['ids'][i]}")
                print(f"Metadata: {results['metadatas'][i]}")
                print(f"Document snippet: {results['documents'][i][:200]}...")
                print("-" * 30)
            
            # Semantic search test
            print("\n--- Semantic Search Test ---")
            results = collection.query(
                query_texts=["What are the definitions in the Specific Relief Act?"],
                n_results=1
            )
            print(f"Top Result ID: {results['ids'][0][0]}")
            print(f"Top Result Text Preview: {results['documents'][0][0][:200]}...")
            
    except Exception as e:
        print(f"Error accessing collection: {e}")

if __name__ == "__main__":
    verify_chroma()
