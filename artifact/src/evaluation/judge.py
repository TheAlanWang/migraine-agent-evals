"""RAGAS judge layer (Level 3) for the regression harness.

No agent-driving code lives here: harness.py runs the real agent and hands
finished (question, answer, contexts, reference) samples to judge_samples().

Judged with Gemini: faithfulness + answer_relevancy always; reference-based
metrics only when every sample carries a reference. Set GEMINI_API_KEY in
the environment or a local .env.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def judge_samples(samples: list[dict]):
    """Score (question, answer, contexts[, reference]) samples with RAGAS.

    Imports are deferred so importing this module stays cheap for callers
    that never reach level 3.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "placeholder":
        raise RuntimeError("GEMINI_API_KEY missing/placeholder in .env")

    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.run_config import RunConfig
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        Faithfulness,
        ResponseRelevancy,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        AnswerCorrectness,
    )

    rows = [SingleTurnSample(user_input=s["question"], response=s["answer"],
                             retrieved_contexts=s["contexts"],
                             reference=s.get("reference"))
            for s in samples]
    metrics = [Faithfulness(), ResponseRelevancy()]
    if all(s.get("reference") for s in samples):
        metrics += [LLMContextPrecisionWithReference(), LLMContextRecall(),
                    AnswerCorrectness()]

    judge_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key))
    judge_emb = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001",
                                     google_api_key=api_key))
    result = evaluate(EvaluationDataset(samples=rows), metrics=metrics,
                      llm=judge_llm, embeddings=judge_emb,
                      run_config=RunConfig(max_workers=4), raise_exceptions=False)
    return result.to_pandas()
