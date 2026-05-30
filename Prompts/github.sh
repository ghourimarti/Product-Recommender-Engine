cd your-project-folder
git init
git add .
git commit -m "Initial commit"


ssh-keygen -t ed25519 -C "ghourimarti@email.com" -f ~/.ssh/id_ed25519_ghourimarti
ssh-keygen -t ed25519 -C "ghourimartin@email.com" -f ~/.ssh/id_ed25519_ghourimartin

cat ~/.ssh/id_ed25519_ghourimarti
cat ~/.ssh/id_ed25519_ghourimarti.pub

cat ~/.ssh/id_ed25519_ghourimartin
cat ~/.ssh/id_ed25519_ghourimartin.pub

cd ~/.ssh
touch config
nano config

chmod 600 ~/.ssh/config


ssh -T git@github-ghourimarti
ssh -T git@github-ghourimartin


##########################################
# P1-Video-SEO-Engine
##########################################


# 1. Go to your project folder first
cd "/d/Generative AI & ML/Portpholios/P1-Video-SEO-Engine"

# 2. Initialize git if not already initialized
git init

# 3. Create/update .gitignore to avoid committing Python cache files
cat >> .gitignore << 'EOF'

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual environments
.venv/
venv/
env/

# Environment variables
.env

# OS/editor files
.DS_Store
.vscode/
.idea/
EOF

# 4. Add all current files
git add .

# 5. Commit files
git commit -m "Initial commit"

# 6. Rename branch to main
git branch -M main

# 7. Remove old origin if it already exists
git remote remove origin 2>/dev/null

# 8. Add Account 1 as origin fetch URL
git remote add origin git@github-account1:ghourimarti/P1-Video-SEO-Engine.git

# 9. Add both GitHub accounts as push URLs
git remote set-url --add --push origin git@github-account1:ghourimarti/P1-Video-SEO-Engine.git
git remote set-url --add --push origin git@github-account2:ghourimartin/P1-Video-SEO-Engine.git

# 10. Push to both GitHub accounts
git push -u origin main --force


##############################
git message for .gitignore update: 
git add . ; git commit -m "Update .gitignore to exclude Python cache files, virtual environments, and OS/editor files" ; git push

# git message for demo project addition:
git add . ; git commit -m "Add demo project files for P1-Video-SEO-Engine" ; git push


# git message for adding the project file from the current project progress files:
git add . ; git commit -m "Add current project progress files for P1-Video-SEO-Engine" ; git push

git add . ; git commit -m "feat(retrieval): hybrid + bge-reranker + MMR" ; git push


