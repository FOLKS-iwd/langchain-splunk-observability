"""Genere du trafic LLM fictif pour tester l'ingestion Splunk."""

import argparse
import random
import sys
import time

sys.path.insert(0, ".")

from splunk_logger import SplunkHECLogger

QUESTIONS = [
    "Comment detecter une attaque par brute force dans les logs Windows ?",
    "Quels sont les indicateurs d'un mouvement lateral dans un SI ?",
    "Comment configurer une alerte Splunk pour les connexions suspectes ?",
    "Quelle est la difference entre un IDS et un IPS ?",
    "Comment analyser un binaire suspect dans une sandbox ?",
    "Quels sont les TTPs les plus courants du groupe APT29 ?",
    "Comment detecter une exfiltration DNS dans les logs reseau ?",
    "Quelle strategie adopter pour le durcissement d'un serveur Windows ?",
    "Comment correler les evenements entre un EDR et un SIEM ?",
    "Quels sont les risques lies aux injections de prompt sur un LLM ?",
    "Comment mettre en place un honeypot pour detecter les intrusions ?",
    "Quelle est la methodologie MITRE ATT&CK pour le threat hunting ?",
    "Comment securiser les communications inter-services dans un SOC ?",
    "Quels logs collecter en priorite pour la detection d'incidents ?",
    "Comment automatiser la reponse a un incident de phishing ?",
]

MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]


def generate_event(error_rate: float) -> dict:
    is_error = random.random() < error_rate
    question = random.choice(QUESTIONS)
    model = random.choice(MODELS)
    latency = random.uniform(50, 2000)
    prompt_tokens = random.randint(100, 800)
    completion_tokens = random.randint(50, 3200)

    event = {
        "timestamp": time.time(),
        "event_type": "query",
        "model_name": model,
        "query_text": question[:200],
        "latency_ms": round(latency, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "source_documents_count": random.randint(1, 6),
        "status": "error" if is_error else "success",
        "error_message": "Simulated API timeout" if is_error else "",
    }
    return event


def main():
    parser = argparse.ArgumentParser(
        description="Simuler du trafic LLM pour Splunk HEC"
    )
    parser.add_argument(
        "--count", type=int, default=100, help="Nombre d'evenements a generer"
    )
    parser.add_argument(
        "--rate", type=float, default=5.0, help="Evenements par seconde"
    )
    parser.add_argument(
        "--error-rate", type=float, default=0.05, help="Taux d'erreur (0.0 a 1.0)"
    )
    args = parser.parse_args()

    logger = SplunkHECLogger()
    delay = 1.0 / args.rate if args.rate > 0 else 0

    sent = 0
    errors = 0

    print(f"Envoi de {args.count} evenements (rate={args.rate}/s, erreurs={args.error_rate:.0%})")

    for i in range(args.count):
        event = generate_event(args.error_rate)
        success = logger.send_event(event)

        if success:
            sent += 1
        else:
            errors += 1

        if (i + 1) % 10 == 0 or (i + 1) == args.count:
            print(f"  [{i + 1}/{args.count}] envoyes={sent} echecs={errors}")

        if delay > 0 and i < args.count - 1:
            time.sleep(delay)

    print(f"Termine. {sent} evenements envoyes, {errors} echecs.")


if __name__ == "__main__":
    main()
