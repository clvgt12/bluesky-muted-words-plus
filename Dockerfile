# Base image
FROM python:3.11-slim

# Environment vars
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NLTK_DATA=/usr/local/nltk_data
ENV MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Download NLTK + SpaCy models
RUN python -m nltk.downloader -d $NLTK_DATA wordnet punkt stopwords && \
    python -m spacy download en_core_web_sm

# Copy full application code and supporting assets
COPY . /app

# Ensure database is included
COPY feed_database.db /app/feed_database.db

# Expose the port Waitress will listen on
EXPOSE 8000

# Build in the sentence transform into the docker container image
ARG MODEL_NAME
ENV MODEL_NAME=${MODEL_NAME}
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${MODEL_NAME}')"

# Entrypoint: use waitress to serve the Flask app
CMD ["python3", "-m", "server"]
