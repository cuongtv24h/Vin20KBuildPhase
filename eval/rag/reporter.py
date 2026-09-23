from datetime import datetime
from pathlib import Path
from typing import Any


class ReportGenerator:
    def __init__(self, results: list[dict[str, Any]], performance_metrics: dict[str, float]):
        self.results = results
        self.performance_metrics = performance_metrics

    def generate_markdown(self, output_dir: str):
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = out_path / f"rag_eval_report_{timestamp}.md"

        # Calculate aggregates
        total_cases = len(self.results)
        avg_leakage = sum(r["leakage"] for r in self.results) / total_cases if total_cases else 0
        avg_recall = sum(r["recall"] for r in self.results) / total_cases if total_cases else 0
        avg_integrity = sum(r["integrity"] for r in self.results) / total_cases if total_cases else 0
        avg_completeness = sum(r["completeness"] for r in self.results) / total_cases if total_cases else 0

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# RAG Evaluation Report\n\n")
            f.write(f"**Date generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Test Cases:** {total_cases}\n\n")

            f.write("## 1. Core Metrics Summary\n\n")
            f.write(f"- **Time-Travel Leakage:** {avg_leakage * 100:.2f}% *(Target: 0.0%)*\n")
            f.write(f"- **Clause-Level Recall@k:** {avg_recall * 100:.2f}% *(Target: 100.0%)*\n")
            f.write(f"- **Conflict Completeness:** {avg_completeness * 100:.2f}% *(Target: 100.0%)*\n")
            f.write(f"- **Cryptographic Integrity:** {avg_integrity * 100:.2f}% *(Target: 100.0%)*\n\n")

            f.write("## 2. Performance Metrics\n\n")
            f.write(f"- **p50 Latency:** {self.performance_metrics['p50']:.2f} ms\n")
            f.write(f"- **p95 Latency:** {self.performance_metrics['p95']:.2f} ms *(Target: < 300 ms)*\n")
            f.write(f"- **p99 Latency:** {self.performance_metrics['p99']:.2f} ms\n")
            f.write(f"- **Mean Latency:** {self.performance_metrics['mean']:.2f} ms\n\n")

            f.write("## 3. Detailed Results\n\n")
            f.write("| Case ID | Leakage | Recall | Completeness | Integrity | Latency (ms) |\n")
            f.write("|---|---|---|---|---|---|\n")
            for r in self.results:
                f.write(f"| {r['case_id']} | {r['leakage']:.2f} | {r['recall']:.2f} | {r['completeness']:.2f} | {r['integrity']:.2f} | {r['latency_ms']:.2f} |\n")

        print(f"Report successfully generated at: {filepath}")
