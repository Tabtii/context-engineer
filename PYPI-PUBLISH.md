# PyPI Publishing — Manual Steps

ConText v0.1.0 ist PyPI-ready. Build-Artefakte sind erstellt:

- `dist/context_engineer-0.1.0-py3-none-any.whl` (28 KB)
- `dist/context_engineer-0.1.0.tar.gz` (32 KB)

## Option A: PyPI-Account manuell erstellen + Upload

1. Account erstellen auf https://pypi.org/account/register/
2. Account verifizieren (Email)
3. 2FA einrichten
4. API-Token erstellen: https://pypi.org/manage/account/token/
5. Token sicher speichern in `~/.pypirc`:

```
[pypi]
username = __token__
password = pypi-XXXXXXXXXXXXXXXX
```

6. Hochladen:

```bash
cd /home/torben/projects/context-engineer
twine upload dist/*
```

## Option B: GitHub Trusted Publishing (nach Account-Erstellung)

1. Auf PyPI: https://pypi.org/manage/account/publishing/
2. "Add a new pending publisher"
3. GitHub-Repo: `Tabtii/context-engineer`
4. Workflow: `publish.yml`
5. Bei nächstem GitHub-Release wird automatisch gepublisht

## Verification nach Upload

```bash
# In neuem venv testen
python -m venv /tmp/test-context
source /tmp/test-context/bin/activate
pip install context-engineer
context --version
# Sollte: context, version 0.1.0

# End-to-end test
ollama pull nomic-embed-text llama3.2
mkdir -p /tmp/test-docs
echo "# Test\n\nThis is a test." > /tmp/test-docs/test.md
context build /tmp/test-docs
context query "What is this?"
```

## Release auf GitHub

Nach PyPI-Upload:

```bash
cd /home/torben/projects/context-engineer
git tag -a v0.1.0 -m "v0.1.0: ConText MVP"
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0: Initial Release" --notes "See CHANGELOG.md"
```
