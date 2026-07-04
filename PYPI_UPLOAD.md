# ConText PyPI Upload – Schritt-für-Schritt

## Status
- ✅ Wheel + sdist gebaut: `/home/torben/projects/context-engineer/dist/`
- ✅ `twine check` PASSED
- ✅ PEP 639 Lizenz-Warnung behoben
- ✅ Commit + Push auf `master` (f729b24)
- ⏳ PyPI-Upload ausstehend — Token fehlt

## 1. PyPI-Token erstellen

1. Auf https://pypi.org/manage/account/#api-tokens gehen
2. **Add API token**
3. Name: `ConText Upload`
4. Scope: `Entire account` (oder auf `context-engineer` project-scoped, sobald das Paket existiert)
5. Erstellen — Token wird **nur einmal** angezeigt (beginnt mit `pypi-`)
6. Token sicher kopieren

## 2. Upload ausführen

### Variante A: Umgebungsvariablen (empfohlen)
```bash
cd /home/torben/projects/context-engineer
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<dein-pypi-token>
python -m twine upload dist/*
```

### Variante B: .pypirc
Erstelle `~/.pypirc` mit chmod 600:
```ini
[pypi]
username = __token__
password = pypi-XXXXXXXX
```
Dann:
```bash
cd /home/torben/projects/context-engineer
python -m twine upload dist/*
```

## 3. Optional: Test-Upload auf TestPyPI
```bash
cd /home/torben/projects/context-engineer
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<testpypi-token>
python -m twine upload --repository testpypi dist/*
```

## 4. Danach
- `pip install context-engineer` testen
- Git Tag setzen: `git tag v0.1.0 && git push origin v0.1.0`
- GitHub Release anlegen

---
Sobald du den Token hast, gib ihn mir (wir speichern ihn sicher lokal, nicht im Chat) und ich führe den Upload aus.
