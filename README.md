# LangChain RAG avec Observabilite Splunk

Pipeline RAG (Retrieval-Augmented Generation) base sur LangChain, avec instrumentation complete des appels LLM et envoi des metriques vers Splunk via HEC. Concu pour un contexte SOC ou la visibilite sur les systemes d'IA en production est critique.

## Ce que ca fait

- Ingestion de documents texte, decoupage en chunks, indexation dans FAISS
- Recherche semantique + generation de reponses via OpenAI
- Chaque appel est instrumente : tokens, latence, erreurs, documents sources
- Les evenements sont envoyes en temps reel vers Splunk (HTTP Event Collector)
- Dashboards Splunk fournis pour le monitoring et la detection d'anomalies

## Architecture

```
Utilisateur -> Flask API -> RAG Engine (LangChain + FAISS)
                                |
                          LLMObserver
                                |
                      SplunkHECLogger -> Splunk (index llm_observability)
                                              |
                                    Dashboards + Alertes SOC
```

Le flux est simple. Une requete arrive sur l'API Flask, passe dans le moteur RAG qui recupere les documents pertinents et genere une reponse. L'observer capture les metriques (tokens, latence, erreurs) et les pousse vers Splunk. Cote Splunk, deux dashboards couvrent le monitoring operationnel et la detection securite.

## Prerequis

- Python 3.11+
- Un compte OpenAI avec cle API
- Une instance Splunk avec HEC active (token + index configures)
- pip

## Installation

```bash
git clone https://github.com/votre-user/langchain-splunk-observability.git
cd langchain-splunk-observability

python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sur Windows

pip install -r requirements.txt
```

## Configuration

Copier le fichier d'exemple et renseigner les valeurs :

```bash
cp .env.example .env
```

Variables a configurer :

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Cle API OpenAI |
| `OPENAI_MODEL` | Modele a utiliser (defaut: gpt-4o-mini) |
| `SPLUNK_HEC_URL` | URL du collecteur HEC Splunk |
| `SPLUNK_HEC_TOKEN` | Token d'authentification HEC |
| `SPLUNK_INDEX` | Index cible (defaut: llm_observability) |

## Utilisation

### Demarrer l'API

```bash
python app.py
```

L'API ecoute sur le port 5000.

### Envoyer une requete

```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelles sont les bonnes pratiques de securite pour les LLM ?"}'
```

Reponse :

```json
{
  "answer": "Les bonnes pratiques incluent...",
  "metadata": {
    "latency_ms": 1523.4,
    "tokens": {"prompt_tokens": 312, "completion_tokens": 89, "total_tokens": 401},
    "sources_count": 4,
    "model": "gpt-4o-mini"
  }
}
```

### Endpoints

| Methode | Route | Description |
|---------|-------|-------------|
| POST | `/query` | Envoyer une question au RAG |
| GET | `/health` | Verification de sante |
| GET | `/stats` | Statistiques d'observabilite (compteurs en memoire) |

## Tests

Lancer les tests unitaires :

```bash
make test
# ou directement :
python -m pytest tests/ -v
```

Les tests couvrent `LLMObserver` (suivi de stats, mesure de latence, formatage des evenements) et `SplunkHECLogger` (construction de payloads, retry, envoi batch). Les appels HTTP sont mockes, aucune instance Splunk n'est necessaire.

## Simulation

Le script `scripts/simulate_traffic.py` genere du trafic LLM fictif et l'envoie vers Splunk HEC. Utile pour alimenter les dashboards sans deployer le pipeline RAG complet.

```bash
make simulate
# ou avec des parametres personnalises :
python scripts/simulate_traffic.py --count 500 --rate 10 --error-rate 0.1
```

Options disponibles :

| Option | Description | Defaut |
|--------|-------------|--------|
| `--count` | Nombre d'evenements a generer | 100 |
| `--rate` | Evenements par seconde | 5 |
| `--error-rate` | Taux d'erreur simule (0.0 a 1.0) | 0.05 |

Pour exporter les statistiques en JSON :

```bash
python scripts/export_stats.py -o rapport.json
python scripts/export_stats.py --source splunk -o rapport.json
```

## Dashboards Splunk

Deux fichiers Simple XML dans `splunk_dashboards/` :

**llm_observability.xml** : monitoring operationnel. Tokens consommes, latence moyenne et P95, taux d'erreur, top requetes, repartition par modele.

**alertes_soc.xml** : detection securite. Pics de tokens anormaux (> 2 sigma), depassements du seuil d'erreur, patterns de prompt injection (regex sur les techniques connues), requetes a consommation excessive.

Pour les importer : Splunk Web > Tableaux de bord > Creer un tableau de bord > Source XML, puis coller le contenu.

## Structure du projet

```
.
├── app.py                  # API Flask
├── rag_engine.py           # Pipeline RAG (LangChain + FAISS)
├── observability.py        # Instrumentation et stats
├── splunk_logger.py        # Client Splunk HEC
├── config.py               # Chargement de la config
├── utils/
│   └── token_counter.py    # Estimation de tokens et couts
├── tests/
│   ├── test_observability.py
│   └── test_splunk_logger.py
├── scripts/
│   ├── simulate_traffic.py # Generateur de trafic fictif
│   └── export_stats.py     # Export des stats en JSON
├── docs/
│   └── sample.txt
├── splunk_dashboards/
│   ├── llm_observability.xml
│   └── alertes_soc.xml
├── Makefile
├── requirements.txt
├── .env.example
└── .gitignore
```

## Notes

- L'index FAISS est persiste sur disque apres le premier chargement. Les relances suivantes le reutilisent sans re-embedder.
- Les requetes sont tronquees a 200 caracteres dans les logs Splunk pour eviter de stocker des donnees sensibles en clair.
- Le retry sur HEC est configure a 3 tentatives avec backoff exponentiel.
- Les stats en memoire (`/stats`) sont remises a zero a chaque redemarrage, les donnees persistantes sont dans Splunk.
