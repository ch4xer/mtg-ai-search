from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-large-en")

sentences = ["Hello, how are you?", "What is your name?", "Zhulodok, Void Gorger"]

embeddings = model.encode(sentences)

print(embeddings.shape)
