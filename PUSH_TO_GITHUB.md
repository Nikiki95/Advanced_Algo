# Push to GitHub

```bash
git init
git add .
git commit -m "Initial import: betting-algorithm-v3 known sports scope"
git branch -M main
git remote add origin <DEIN_GITHUB_REPO_URL>
git push -u origin main
```


Vor dem ersten echten Prop-Settlement kannst du lokal die neuen Commands prüfen:

```bash
python football/settle_props.py --help
python nba/settle_props.py --help
python nfl/settle_props.py --help
```
