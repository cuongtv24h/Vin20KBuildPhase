import logging
import time
from datetime import datetime
from pathlib import Path

from eval.rag.metrics_integrity import verify_cryptographic_integrity
from eval.rag.metrics_performance import LatencyTracker
from eval.rag.metrics_retrieval import calculate_clause_recall, calculate_conflict_completeness
from eval.rag.metrics_temporal import calculate_time_travel_leakage
from eval.rag.reporter import ReportGenerator
from eval.rag.scenarios import ScenarioLoader
from src.services.rag.service import PolicyRAGService
from src.models.pec_contracts import PolicyQuery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGEvaluator:
    def __init__(self, dataset_path: str, policies_dir: str, canonical_dir: str):
        self.scenario_loader = ScenarioLoader(dataset_path)
        self.rag_service = PolicyRAGService(
            policies_dir=Path(policies_dir),
            canonical_dir=Path(canonical_dir)
        )
        self.latency_tracker = LatencyTracker()
        self.results = []

    def setup(self):
        logger.info("Ingesting policies for evaluation...")
        self.rag_service.ingest_from_directory()
        logger.info("Ingestion complete.")

    def run(self):
        test_cases = self.scenario_loader.load_test_cases()
        if not test_cases:
            logger.error("No test cases found!")
            return

        for case in test_cases:
            logger.info(f"Evaluating case: {case.case_id}...")
            start_time = time.time()

            # Run RAG using new PEC-RAG pipeline
            query_date_str = case.query_date
            
            policy_query = PolicyQuery(
                query_text=case.query_text,
                transaction_date=query_date_str,
                project_scope=None
            )
            
            bundle, cert = self.rag_service.compile_and_retrieve_bundle(
                policy_query=policy_query
            )

            latency_ms = (time.time() - start_time) * 1000
            self.latency_tracker.record(latency_ms)

            # Metrics
            leakage = calculate_time_travel_leakage(bundle, case.expected_policy_ids)
            recall = calculate_clause_recall(bundle, case.expected_policy_ids)
            integrity = verify_cryptographic_integrity(bundle)
            
            if case.is_conflict_test:
                completeness = calculate_conflict_completeness(bundle, case.expected_policy_ids)
            else:
                completeness = 1.0

            evidences_count = len(bundle.applied_rules) if bundle else 0

            self.results.append({
                "case_id": case.case_id,
                "query": case.query_text,
                "latency_ms": latency_ms,
                "leakage": leakage,
                "recall": recall,
                "integrity": integrity,
                "completeness": completeness,
                "evidences_count": evidences_count
            })

        logger.info("Evaluation run complete.")

    def generate_report(self, output_dir: str):
        reporter = ReportGenerator(self.results, self.latency_tracker.calculate_metrics())
        reporter.generate_markdown(output_dir)

