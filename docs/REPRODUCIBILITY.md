# Reproducibility

The five reports are invented for software testing. The selected intervals are printed inputs, not clinical recommendations. No clinical accuracy claim is made.

## Prompt preparation

The prompts were exercised directly against a local model endpoint, the local equivalent of testing in a provider playground. There is no hosted-provider playground session or paid API credential in this submission. The final extraction prompt requests verbatim fields, empty strings for missing ranges and preserved comparison symbols. Both complete prompts are in `prompts.py` and the report.

## Environment

- Python 3.12.14, Linux x86_64, CPU inference
- llama.cpp b12503 (commit 4577932fa)
- Qwen/Qwen2.5-1.5B-Instruct-GGUF, qwen2.5-1.5b-instruct-q4_k_m.gguf
- Context: 8192; temperature: 0; maximum generated tokens per call: 2200
- Dependencies are pinned in requirements files; model weights require a separate download.

## Evidence

`evaluate.py` sends each sample through both model calls and records the observed flags and explanations. Tests in `tests/` include mocked provider responses to isolate error handling; these mocks are distinct from the live model evidence. Screenshots are browser captures of the running app after real model calls, not reconstructed mockups. Only synthetic report data is published.

## Human review

Compare extracted names, values, units and reference ranges with the source text. Check that no rows are omitted. Explanation prose remains unverified medical content from a small general model. Review the code, prompts and viva notes before presenting the assignment, and follow your institution's assistance/disclosure rules.

The explanation prompt supplies test names only. Patient values, ranges and flags are withheld from that call; Python appends the comparison sentence. This change prevents the model from contradicting the numerical flag, an issue found during initial testing. One validated extraction retry is allowed when the first response is malformed or untraceable.

For recognised four-column tables, printed source cells take precedence over model-returned units and ranges. This fixes column shifts observed during testing. The model must still identify the correct test and value, and an explicit completeness check catches missing rows. Other text layouts use exact source-field checks and may require reformatting.
