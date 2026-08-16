"""Exporte les statistiques d'observabilite vers un fichier JSON."""

import argparse
import json
import sys
import time

import requests

sys.path.insert(0, ".")

from config import Config


def fetch_stats_from_api(base_url: str = "http://localhost:5000") -> dict:
    """Recupere les stats depuis l'endpoint /stats de l'API Flask."""
    resp = requests.get(f"{base_url}/stats", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_stats_from_splunk(
    splunk_url: str,
    token: str,
    index: str,
) -> dict:
    """Recupere les stats agregees via une recherche SPL."""
    search_query = (
        f'search index={index} sourcetype=langchain_events event_type=query earliest=-24h '
        f'| stats count as total_queries '
        f'avg(latency_ms) as avg_latency_ms '
        f'perc95(latency_ms) as p95_latency_ms '
        f'sum(eval(if(status="error",1,0))) as total_errors '
        f'sum(total_tokens) as total_tokens '
        f'| eval error_rate=round(total_errors/total_queries, 4)'
    )

    search_url = f"{splunk_url}/services/search/jobs/export"
    resp = requests.post(
        search_url,
        data={
            "search": search_query,
            "output_mode": "json",
            "earliest_time": "-24h",
            "latest_time": "now",
        },
        headers={"Authorization": f"Bearer {token}"},
        verify=False,
        timeout=60,
    )
    resp.raise_for_status()

    results = []
    for line in resp.text.strip().split("\n"):
        if line.strip():
            results.append(json.loads(line))

    if not results:
        return {}

    return results[0].get("result", {})


def build_report(stats: dict) -> dict:
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_queries": stats.get("total_queries", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0),
        "p95_latency_ms": stats.get("p95_latency_ms", "N/A"),
        "error_rate": stats.get("error_rate", 0),
        "total_tokens_used": stats.get("total_tokens_used", 0),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Exporter les stats d'observabilite en JSON"
    )
    parser.add_argument(
        "-o", "--output", type=str, default="stats_export.json",
        help="Chemin du fichier de sortie"
    )
    parser.add_argument(
        "--source", choices=["api", "splunk"], default="api",
        help="Source des donnees (api=endpoint Flask, splunk=recherche SPL)"
    )
    parser.add_argument(
        "--api-url", type=str, default="http://localhost:5000",
        help="URL de base de l'API Flask"
    )
    args = parser.parse_args()

    if args.source == "api":
        print("Recuperation des stats depuis l'API Flask...")
        raw_stats = fetch_stats_from_api(args.api_url)
    else:
        print("Recuperation des stats depuis Splunk...")
        splunk_base = Config.SPLUNK_HEC_URL.replace(":8088", ":8089")
        raw_stats = fetch_stats_from_splunk(
            splunk_url=splunk_base,
            token=Config.SPLUNK_HEC_TOKEN,
            index=Config.SPLUNK_INDEX,
        )

    report = build_report(raw_stats)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Stats exportees vers {args.output}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
