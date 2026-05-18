# Agent Bootstrap — Lies das zuerst

Wenn du als KI-Agent eine neue Session auf diesem Repo startest:

1. **Lies die Memory Bank vollständig**, in dieser Reihenfolge:
   - `memory-bank/projectbrief.md`
   - `memory-bank/productContext.md`
   - `memory-bank/systemPatterns.md`
   - `memory-bank/techContext.md`
   - `memory-bank/activeContext.md`
   - `memory-bank/progress.md`

2. **Verifiziere die Wirklichkeit**, bevor du Empfehlungen aus der
   Memory Bank ableitest:
   - `git log --oneline | head -10` — neuere Commits als `progress.md`?
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps`
     — sind die Container noch healthy?
   - `curl -s https://tessa.ki-c.pro/api/health` — ist die Live-Instanz
     noch oben?
   - Eine genannte Datei/Funktion/Endpunkt: per Read/grep prüfen, dass
     sie noch existiert (Memory-Einträge sind nicht garantiert aktuell).

3. **Aktualisiere die Memory Bank**, wenn du substantielle Änderungen
   machst — insbesondere `activeContext.md` und `progress.md`.

4. **Niemals Secrets committen.** Vor jedem Commit:
   `git status --porcelain | grep -E '(^|/)\.env$'` muss leer sein.

5. **Niemals SSH/Deploy-Keys oder Provider-API-Keys in die Memory
   Bank schreiben.** Hier sind nur "wo zu finden" / "wie zu setzen"
   erlaubt.

## Schnell-Cheatsheet

```bash
# Prod-Stack-Befehle
COMPOSE='docker compose -f /home/ubuntu/tessa/docker-compose.yml \
         -f /home/ubuntu/tessa/docker-compose.prod.yml'

sudo $COMPOSE ps
sudo $COMPOSE logs --tail=100 tessa-api | grep -v /api/health
sudo $COMPOSE up -d --no-deps --build tessa-api    # nach Code-Änderung
sudo $COMPOSE exec -T postgres psql -U tessa -d tessa

# Tests
cd /home/ubuntu/tessa
sudo docker run --rm -v $PWD/services/api:/srv -w /srv python:3.12-slim \
  sh -c "pip install -q -r requirements.txt && python -m pytest -q -p no:warnings"
```
