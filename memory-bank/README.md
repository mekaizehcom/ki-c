# Tessa — Memory Bank (Cline-Stil)

Diese Memory Bank ist die kuratierte Wissensbasis über das Tessa-Projekt.
Sie ist so geschrieben, dass jede neue Arbeits-Session (Mensch oder KI)
das Projekt **kalt lesen und sofort weiterarbeiten** kann.

## Lese-Reihenfolge

Die Dateien bauen aufeinander auf:

```
1. projectbrief.md       Fundament — was ist Tessa, Scope, Ziele
2. productContext.md     Warum es existiert, Benutzer, UX-Prinzipien
3. systemPatterns.md     Architektur, Muster, Komponenten-Beziehungen
4. techContext.md        Stack, Setup, Deployment, Constraints
5. activeContext.md      Aktueller Fokus, jüngste Entscheidungen, nächste Schritte
6. progress.md           Was läuft, was fehlt, Status pro Phase, bekannte Probleme
```

`activeContext.md` und `progress.md` sind die lebendigsten Dateien —
hier soll am häufigsten aktualisiert werden.

## Update-Regeln

- **Nach jeder relevanten Änderung** mindestens `activeContext.md` und
  `progress.md` aktualisieren.
- **Nach Architektur-/Vertrags­änderungen** auch `systemPatterns.md` oder
  `techContext.md`.
- **Bei Scope-Verschiebung** auch `projectbrief.md`/`productContext.md`.
- **Niemals Secrets oder API-Keys hier ablegen** — die wohnen in `.env`
  (gitignored). Hier nur "wo zu finden" / "wo zu setzen".
- Daten konkret halten: Dateipfade, Endpunkte, Commit-Hashes wo nützlich.
  Relative Daten ("nächste Woche") in absolute umwandeln.

## Verhältnis zur Architektur-Quelle

`docs/architecture.md` (= `TESSA_SYSTEM_ARCHITECTURE.md`) ist die **eingefrorene
Originalspezifikation** (Version 1.0, 18.05.2026). Die Memory Bank ist die
**lebendige** Sicht: was tatsächlich gebaut wurde, welche Entscheidungen wir
getroffen haben, was sich seitdem verändert hat. Bei Konflikt gewinnt die
Memory Bank — und ein Eintrag in `progress.md` markiert die Abweichung.

## Stand

Letzte Vollaktualisierung: **2026-05-18**. Wenn die Memory Bank älter
als ein paar Wochen ist und sich seither viel im Code geändert hat:
zuerst `git log --since=...` durchsehen und die Bank refreshen, bevor
Empfehlungen daraus abgeleitet werden.
