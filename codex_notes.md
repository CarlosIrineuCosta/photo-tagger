# Operator Notes

- Always document the end-to-end workflow when UI changes land. Users should know which buttons to press and why, before we expect feedback.
- When introducing new steps (e.g., Review & Write), update the README with the exact sequence, prerequisites, and expected outputs.
- Surface clear error messages in the UI (e.g., missing config path) rather than letting exceptions leak to the console.
- Before asking the user to test, confirm that the default `config/config.yaml` loads and that the smoke test runs successfully.
