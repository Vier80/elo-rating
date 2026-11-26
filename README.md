# ELO Rating – agente-elo

App con i rating ELO di badminton, judo, lotta, scherma, squash, tennis, tennistavolo e vela.
Ogni giorno l'agente legge i database Notion degli agenti, scarica le classifiche ELO del tennis
da Tennis Abstract, ricalcola tutto e ripubblica la pagina su **https://vier80.github.io/elo-rating**.

## File del repository

| File | A cosa serve |
|---|---|
| `agente_elo.py` | L'agente: legge Notion e Tennis Abstract, calcola, rigenera `index.html` |
| `template.html` | La grafica dell'app (non toccare la riga `__DATA__`) |
| `index.html` | L'app pubblicata (la rigenera l'agente) |
| `tennis_atp.csv`, `tennis_wta.csv` | Ultime classifiche tennis salvate (servono se Tennis Abstract non risponde) |
| `.github/workflows/aggiorna.yml` | Il "motore" che fa girare l'agente su GitHub |

## Secret necessari

- `NOTION_TOKEN`: token dell'integrazione Notion "Agente ELO", collegata alla pagina "⚙️ Agenti".

## Se qualcosa va storto

- **Errore Notion 404 / object_not_found**: la connessione "Agente ELO" non è collegata alla pagina "⚙️ Agenti".
- **Errore Notion 401 / unauthorized**: il secret `NOTION_TOKEN` è sbagliato o scaduto.
- **Tennis non aggiornato**: Tennis Abstract non ha risposto; l'app usa le ultime classifiche salvate.

## Come è calcolato il rating

Si parte da 1500 per categoria; formula ELO classica con K = 32, pesi per livello del torneo
(Mondiali ×1,3 ecc.), ×1,5 nei primi 8 incontri. Vela: ogni regata è un confronto con tutte le
barche della classifica (×3). Tennis: ELO di Tennis Abstract, non ricalcolato.
