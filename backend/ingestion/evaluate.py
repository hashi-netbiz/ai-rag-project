"""
Ragas evaluation script — Phase 6.

Runs 30 RBAC-restricted test questions through the RAG pipeline and scores
them with Ragas metrics: faithfulness, answer_relevancy, context_precision,
context_recall. Exports results to evaluation_results.csv.

Run with:
    cd backend && uv run python -m ingestion.evaluate
"""

# ===========================================================================
# IMPORTANT: load_dotenv() must run before any app module import.
# pydantic-settings populates `settings` but does NOT write to os.environ.
# LangChain reads os.environ directly for tracing config.
# ===========================================================================
import os
import sys
import time
import importlib.metadata
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads backend/.env when cwd is backend/

# Fix Windows stdout encoding (handles ₹ and other non-ASCII in LLM answers)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Now safe to import app modules — os.environ is fully populated.
# ---------------------------------------------------------------------------
from pinecone import Pinecone                               # noqa: E402
from app.chat.rag_service import rag_query            # noqa: E402
from app.vector_store.pinecone_client import get_retriever  # noqa: E402
from app.rbac.permissions import get_allowed_departments    # noqa: E402
from app.config import settings                             # noqa: E402


# ===========================================================================
# Ragas API version detection — breaking change at 0.2
# ===========================================================================
_ragas_ver = tuple(
    int(x) for x in importlib.metadata.version("ragas").split(".")[:2]
)
RAGAS_NEW_API = _ragas_ver >= (0, 2)

if RAGAS_NEW_API:
    try:
        from ragas import evaluate as ragas_evaluate
        from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
        from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_groq import ChatGroq
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from app.config import settings as _settings
        _llm = LangchainLLMWrapper(
            ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=_settings.groq_api_key)
        )
        _embeddings = LangchainEmbeddingsWrapper(
            GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-2-preview",
                google_api_key=_settings.google_api_key,
                output_dimensionality=768,
            )
        )
        RAGAS_METRICS = [
            Faithfulness(llm=_llm),
            AnswerRelevancy(llm=_llm, embeddings=_embeddings),
            ContextPrecision(llm=_llm),
            ContextRecall(llm=_llm),
        ]
    except Exception as e:
        print(f"[ERROR] Failed to initialise ragas>=0.2 metrics: {e}", file=sys.stderr)
        sys.exit(1)
else:
    try:
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from datasets import Dataset
        RAGAS_METRICS = [faithfulness, answer_relevancy, context_precision, context_recall]
    except ImportError as e:
        print(f"[ERROR] ragas<0.2 import failed: {e}", file=sys.stderr)
        sys.exit(1)


# ===========================================================================
# 30 Test Cases: (question, role, ground_truth)
# Questions grounded in actual document content from resources/data/.
# Role determines Pinecone department filter.
# ===========================================================================
TEST_CASES: list[tuple[str, str, str]] = [
    # --- Finance (6) — role: finance → [finance, general] ---
    (
        "What was FinSolve Technologies's gross margin in 2024?",
        "finance",
        "The gross margin was 60% in 2024, up from 55% in 2023.",
    ),
    (
        "By what percentage did FinSolve Technologies's revenue grow year-over-year in 2024?",
        "finance",
        "Revenue grew by 25% in 2024.",
    ),
    (
        "What was the total vendor services expense in 2024?",
        "finance",
        "Vendor services totaled $30 million, an 18% increase from the prior year.",
    ),
    (
        "What was the cash flow from operations in 2024?",
        "finance",
        "Cash flow from operations was $50 million, a 20% increase over the prior year.",
    ),
    (
        "What was the Q1 2024 revenue for FinSolve Technologies?",
        "finance",
        "Q1 2024 revenue was $2.1 billion, up 22% year-over-year.",
    ),
    (
        "What is the Days Sales Outstanding (DSO) for FinSolve Technologies?",
        "finance",
        "The DSO is 45 days, compared to an industry benchmark of 30 days.",
    ),

    # --- Marketing (6) — role: marketing → [marketing, general] ---
    (
        "What was the total marketing budget for FinSolve Technologies in 2024?",
        "marketing",
        "The total marketing budget was $15 million in 2024.",
    ),
    (
        "What was the customer acquisition cost (CAC) in 2024?",
        "marketing",
        "The CAC was $150 per new customer in 2024, down from $180 in 2023.",
    ),
    (
        "What ROI did the digital marketing campaigns achieve in 2024?",
        "marketing",
        "Digital campaigns achieved a 3.5x return on investment, generating $17.5 million in revenue.",
    ),
    (
        "By how much did new customer acquisition grow in 2024?",
        "marketing",
        "New customer acquisition grew by 20%, outpacing the industry average of 10%.",
    ),
    (
        "What was the Return on Ad Spend (ROAS) for digital campaigns in 2024?",
        "marketing",
        "The ROAS for digital campaigns was 4.5x, up from 3x in 2023.",
    ),
    (
        "Which marketing campaign generated the highest conversions in 2024?",
        "marketing",
        "The InstantWire Global Expansion campaign generated the highest conversions, with a 25% increase in website traffic and a 12% increase in sign-ups.",
    ),

    # --- HR (6) — role: hr → [hr, general] ---
    (
        "What is the performance rating for employee FINEMP1001?",
        "hr",
        "Employee FINEMP1001 has a performance rating of 5.",
    ),
    (
        "What department does employee Aadhya Patel (FINEMP1000) work in?",
        "hr",
        "Aadhya Patel (FINEMP1000) works in the Sales department.",
    ),
    (
        "What is the salary of Shaurya Joshi (FINEMP1005)?",
        "hr",
        "Shaurya Joshi (FINEMP1005) has a salary of 1,085,205.18.",
    ),
    (
        "What is the attendance percentage for Sara Sharma (FINEMP1006)?",
        "hr",
        "Sara Sharma (FINEMP1006) has an attendance percentage of 96.49%.",
    ),
    (
        "How many leaves has Isha Chowdhury (FINEMP1001) taken?",
        "hr",
        "Isha Chowdhury (FINEMP1001) has taken 3 leaves.",
    ),
    (
        "What is the leave balance for employee FINEMP1004?",
        "hr",
        "Employee FINEMP1004 has a leave balance of 21 days.",
    ),

    # --- Engineering (6) — role: engineering → [engineering, general] ---
    (
        "What type of architecture does FinSolve use for its systems?",
        "engineering",
        "FinSolve uses a microservices-based, cloud-native architecture designed for scalability, resilience, and security.",
    ),
    (
        "What mobile development languages are used at FinSolve Technologies?",
        "engineering",
        "FinSolve uses Swift for iOS and Kotlin for Android mobile development.",
    ),
    (
        "What databases does FinSolve use in its data layer?",
        "engineering",
        "FinSolve uses PostgreSQL for transactional data, MongoDB for user profiles and metadata, Redis for caching, and Amazon S3 for documents and backups.",
    ),
    (
        "What authentication standard does FinSolve's Authentication Service use?",
        "engineering",
        "The Authentication Service uses OAuth 2.0 with JWT tokens, supporting multi-factor authentication and Single Sign-On.",
    ),
    (
        "What is the primary cloud infrastructure provider for FinSolve?",
        "engineering",
        "FinSolve's primary cloud infrastructure uses AWS (EC2, ECS, Lambda) with Kubernetes for container orchestration.",
    ),
    (
        "What frontend framework is FinSolve's web application built with?",
        "engineering",
        "FinSolve's web application is built with React, Redux, and Tailwind CSS.",
    ),

    # --- General / Employee Handbook (6) — role: employee → [general] ---
    (
        "How many days of annual leave are employees entitled to at FinSolve Technologies?",
        "employee",
        "Employees are entitled to 15-21 days of annual leave per year, accrued monthly.",
    ),
    (
        "What is the work-from-home policy at FinSolve Technologies?",
        "employee",
        "Employees may work from home up to 2 days per week for eligible roles, subject to manager approval.",
    ),
    (
        "How is overtime compensated at FinSolve Technologies?",
        "employee",
        "Overtime is paid at double the regular wage rate and requires prior manager approval.",
    ),
    (
        "What is the reward for the employee referral program at FinSolve?",
        "employee",
        "Employees receive Rs. 10,000 for successful referrals, paid after the new hire completes 6 months.",
    ),
    (
        "When is salary credited to employee bank accounts at FinSolve?",
        "employee",
        "Salary is credited to bank accounts on the last working day of each month.",
    ),
    (
        "What is the annual tuition and certification reimbursement limit at FinSolve?",
        "employee",
        "Employees can claim up to Rs. 50,000 per year for relevant courses, subject to manager and HR approval.",
    ),
]


# ===========================================================================
# Evaluation runner
# ===========================================================================

def run_evaluation() -> None:
    """Run all test cases, score with Ragas, export CSV, print mean scores."""
    print(f"Starting Ragas evaluation — {len(TEST_CASES)} test cases")
    print(f"Ragas version: {importlib.metadata.version('ragas')} (new API: {RAGAS_NEW_API})")
    print("-" * 60)

    questions: list[str] = []
    answers: list[str] = []
    contexts: list[list[str]] = []
    ground_truths: list[str] = []

    for i, (question, role, ground_truth) in enumerate(TEST_CASES, start=1):
        print(f"[{i:02d}/{len(TEST_CASES)}] role={role} | {question[:65]}...")
        try:
            # Step A: get answer from RAG pipeline (also creates Langsmith trace)
            rag_result = rag_query(question, role)
            answer = rag_result["answer"]

            # Step B: get raw context texts — rag_query does not expose
            # the retrieved Document objects, but Ragas requires context strings
            allowed_depts = get_allowed_departments(role)
            if allowed_depts:
                retriever = get_retriever(allowed_depts, k=10)
                docs = retriever.invoke(question)
                # Rerank to top 3 to match production behaviour
                if len(docs) > 3:
                    try:
                        _pc = Pinecone(api_key=settings.pinecone_api_key)
                        reranked = _pc.inference.rerank(
                            model="bge-reranker-v2-m3",
                            query=question,
                            documents=[d.page_content for d in docs],
                            top_n=3,
                            return_documents=False,
                        )
                        docs = [docs[item.index] for item in reranked.data]
                    except Exception:
                        docs = docs[:3]
                context_texts = [doc.page_content for doc in docs]
            else:
                context_texts = []

            questions.append(question)
            answers.append(answer)
            contexts.append(context_texts)
            ground_truths.append(ground_truth)

            print(f"         answer: {answer[:80]}")
            print(f"         contexts: {len(context_texts)} chunks retrieved")

        except Exception as exc:
            print(f"[WARN] Case {i} failed and will be skipped: {exc}", file=sys.stderr)

        # Respect API rate limits (Groq free tier + Google embedding)
        time.sleep(1)

    if not questions:
        print("[ERROR] No test cases succeeded — cannot evaluate.", file=sys.stderr)
        sys.exit(1)

    print(f"\nCollected {len(questions)}/{len(TEST_CASES)} successful cases.")
    print("Running Ragas evaluation (this may take a few minutes)...")

    # ---------------------------------------------------------------------------
    # Ragas scoring — branched by API version
    # ---------------------------------------------------------------------------
    if RAGAS_NEW_API:
        samples = [
            SingleTurnSample(
                user_input=q,
                response=a,
                retrieved_contexts=c,
                reference=g,
            )
            for q, a, c, g in zip(questions, answers, contexts, ground_truths)
        ]
        eval_dataset = EvaluationDataset(samples=samples)
        result = ragas_evaluate(eval_dataset, metrics=RAGAS_METRICS)
    else:
        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })
        result = ragas_evaluate(dataset, metrics=RAGAS_METRICS)

    # ---------------------------------------------------------------------------
    # Export CSV
    # ---------------------------------------------------------------------------
    df = result.to_pandas()
    output_path = Path(__file__).resolve().parent.parent / "evaluation_results.csv"
    df.to_csv(output_path, index=False)
    print(f"\nResults exported to: {output_path}")

    # ---------------------------------------------------------------------------
    # Print mean scores (handle both 0.1.x and 0.2.x column name conventions)
    # ---------------------------------------------------------------------------
    print("\n--- Mean Ragas Scores ---")
    target_metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    for metric in target_metrics:
        # Try exact match first, then fuzzy match (0.2+ may use different names)
        if metric in df.columns:
            print(f"  {metric:<25}: {df[metric].mean():.4f}")
        else:
            candidates = [c for c in df.columns if metric.replace("_", "") in c.replace("_", "")]
            for col in candidates:
                print(f"  {col:<25}: {df[col].mean():.4f}")

    print("\nEvaluation complete.")


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    run_evaluation()
