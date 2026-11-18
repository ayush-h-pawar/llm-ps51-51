# Viva preparation

1. **What does PS51 solve?** It turns lab-report rows into simple explanations and flags results outside the report's own reference range.
2. **Where is the LLM used?** First to extract structured JSON, then to explain what each test measures; Python adds the result comparison.
3. **Why use Python for flags?** Decimal comparisons are deterministic and avoid asking a language model to do clinical arithmetic.
4. **Is a high value a diagnosis?** No. Interpretation depends on clinical context, the lab method, age, sex and other factors.
5. **What if a range is missing?** The result is Not assessed; the program never supplies an assumed range.
6. **How are boundary values handled?** A closed interval includes both endpoints. A strict threshold such as <200 excludes 200.
7. **What happens with <5 as a result?** It is a censored measurement, not exactly 5; this mini project leaves it unassessed.
8. **How are hallucinations reduced?** Exact source-line checks, complete-row checks for recognised tables, structured output, printed ranges, limited prompts and visible source text. These cannot guarantee correctness.
9. **What is the model?** The tested model is Qwen2.5-1.5B-Instruct, Q4_K_M quantization, served locally with llama.cpp. Ollama and Groq are alternate adapters.
10. **Was the model trained?** No. The project uses inference and prompt design only.
11. **Why no vector database?** The short uploaded report fits in the prompt; retrieval is unnecessary for this scope.
12. **What are the limitations?** No OCR, no unit conversion, limited context, possible omitted/misassociated rows and unreliable medical wording from a small model.
13. **How is privacy handled?** No application database or report logging; local inference is supported. Remote mode needs consent. Downloaded exports must be handled privately.
14. **What would you improve?** Add a clinician-reviewed test glossary, extraction review before explanation, OCR and broader testing on anonymized formats.
15. **How would you demonstrate it?** Start the local model, run Streamlit, select the normal sample, then the low and boundary samples; show JSON and CSV export.
