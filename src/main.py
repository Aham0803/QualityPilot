"""
Command Line Interface for QualityPilot.
Usage:
  python -m src.main run-pipeline [--sample 5000]
  python -m src.main start-dashboard
  python -m src.main test-ai
"""

import sys
import argparse
import subprocess
from src.pipeline import DQStewardPipeline

def main():
    parser = argparse.ArgumentParser(description="QualityPilot Master CLI")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Run Pipeline
    run_parser = subparsers.add_parser("run-pipeline", help="Execute end-to-end data quality & stewardship pipeline")
    run_parser.add_argument("--sample", type=int, default=None, help="Sample size for interactive fast testing (e.g. 5000)")

    # Start Dashboard
    subparsers.add_parser("start-dashboard", help="Launch Streamlit Operational Analytics Dashboard")

    # Run AI regression
    subparsers.add_parser("test-ai", help="Run AI Evaluation & Regression suite against golden dataset")

    args = parser.parse_args()

    if args.command == "run-pipeline":
        pipeline = DQStewardPipeline()
        pipeline.run_full_pipeline(sample_size=args.sample)

    elif args.command == "start-dashboard":
        print("[*] Launching Streamlit Dashboard on http://localhost:8501 ...")
        subprocess.run(["streamlit", "run", "dashboards/streamlit_app.py"])

    elif args.command == "test-ai":
        print("[*] Running AI Golden Evaluation Suite...")
        subprocess.run(["pytest", "tests/ai_eval/test_ai_regression.py", "-v"])

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
