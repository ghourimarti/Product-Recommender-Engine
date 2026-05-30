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
# P1-Video-SEO-Engine.git
##########################################

cd your-project-folder
git init
git add .
git commit -m "Initial commit"

git remote add origin git@github-account1:ghourimarti/P1-Video-SEO-Engine.git

git remote set-url --add --push origin git@github-account1:ghourimarti/P1-Video-SEO-Engine.git
git remote set-url --add --push origin git@github-account2:ghourimartin/P1-Video-SEO-Engine.git

git branch -M main
git push -u origin main

git add . ; git commit -m "v1 ... " ; git push
########################################
# P2-Product-Recommender-Engine
##########################################

cd P2-Product-Recommender-Engine
git init
git add .
git commit -m "Initial commit"

git remote add origin git@github-account1:ghourimarti/P2-Product-Recommender-Engine.git

git remote set-url --add --push origin git@github-account1:ghourimarti/P2-Product-Recommender-Engine.git
git remote set-url --add --push origin git@github-account2:ghourimartin/P2-Product-Recommender-Engine.git
git branch -M main
git push origin main

git add . ; git commit -m "v1 ... " ; git push


##########################################
# P3-AI-Travel-Planner
##########################################

cd P3-AI-Travel-Planner

git init
git add .
git commit -m "Initial commit"

git remote add origin git@github-account1:ghourimarti/P3-AI-Travel-Planner.git

git remote set-url --add --push origin git@github-account1:ghourimarti/P3-AI-Travel-Planner.git
git remote set-url --add --push origin git@github-account2:ghourimartin/P3-AI-Travel-Planner.git
git branch -M main
git push -u origin main --force

git add . ; git commit -m "v1 ... " ; git push
