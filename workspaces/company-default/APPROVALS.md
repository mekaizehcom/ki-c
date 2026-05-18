# APPROVALS.md

## low-risk
Beispiele: Dokument vektorisieren, Chat zusammenfassen, Memory-Vorschlag.
Freigabe: nicht erforderlich.

## medium-risk
Beispiele: Datei erstellen, Konfigurationsvorschlag schreiben,
nicht-produktiven Dienst neustarten.
Freigabe: Admin oder Developer.

## high-risk
Beispiele: Nginx ändern, Docker Compose Down, Firewall ändern,
Zertifikat ändern, Datenbankmigration, produktives Deployment.
Freigabe: Admin erforderlich. TOTP-Reconfirm empfohlen.

## critical
Beispiele: Benutzerrechte ändern, Provider-Keys ändern,
Vektorindex löschen, produktive Daten löschen.
Freigabe: Superadmin erforderlich. TOTP-Reconfirm erforderlich.
Audit zwingend.
