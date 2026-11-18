# Browser validation

Executed with headless Chromium against the running Streamlit app and the real local Qwen2.5-1.5B model.

- Selected each of the five synthetic samples in the UI.
- Submitted each report and downloaded its generated JSON.
- Asserted all 12 flags matched the sample expectations and no explanation warnings appeared.
- Captured the five PNGs in screenshots/ directly from the browser.
- Uploaded samples/normal_report.pdf, generated results, downloaded CSV and checked three rows were within range.
- Compared the displayed source data with the synthetic inputs.

UI-generated results are in the *_ui.json files. The PDF upload result is pdf_upload_results.csv. Unit tests are a separate 45-check suite (unit_tests.txt). These checks demonstrate software behavior on synthetic examples; they do not establish clinical accuracy.
