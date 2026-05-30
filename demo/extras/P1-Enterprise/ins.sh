

uv venv
source .venv/Scripts/activate
uv pip install -r requirements.txt
uv pip list 
streamlit run app.py
##############################################################################
##############################################################################

# 1. Groq 
# ---> LLM 

# 2. HuggingFace 
# --> Embedding Model

# 3. Langchain 
# --> Generative AI Framework to interact with LLM

# 4. GCP VM 
# --> Virtual Machine that can be accesed on cloud. It's a service offered by Google Cloud.

# 5. Minikube 
# --> For making a Kubernetes Cluster where you can deploy your application

# 6. Streamlit 
# --> To make UI or frontend of the app

# 7. Docker 
# --> For containerization of the app during deployment

# 8. Grafana Cloud 
# --> Monitoring your Kubernetes Clusters

# 9. Chroma DB 
# --> Local Vector Store for storing Embeddings

# 10. Kubectl 
# --> Command Line Interface to interact with your Kubernetes

# 11. GitHub 
# --> It will work as a SCM for your project.


##############################################################################
##############################################################################
clear ; git add . ; git commit -m "v1 ... " ; git push


##############################################################################
##############################################################################

# Step 1 — Open terminal in the right folder
cd "d:\Generative AI & ML\Portpholios\P1-Video-SEO-Engine\P1-Enterprise"

# Step 2 — Install Python dependencies (one-time)
uv pip install -r backend/requirements.txt

# Step 3 — Build the vector store (one-time only)
python scripts/build_vector_store.py --csv data/anime_updated.csv

# Step 4 — Choose how to run: Local vs Docker
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
