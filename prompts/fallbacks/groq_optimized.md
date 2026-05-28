# Purpose: Additional optimizations specifically tuned for Groq Llama 3.3 70B and similar fast open models.

GROQ-SPECIFIC HARDENING:

- These models are fast but have weaker long-context instruction following than Claude.
- Therefore:
  - Put the most important rules (anti-hallucination + output format) at both the very beginning AND near the end of the system prompt.
  - Use shorter sentences.
  - Include 2-3 concrete "NEVER do X → instead do Y" examples in every system prompt that uses this model.
  - Lower temperature (0.65 or below) when possible for factual/personal responses.
  - When the user asks a personal question, the first 1-2 sentences of your response should be a direct check against the facts block.

Example reinforced pattern for Groq:
"Step 1: Check if this question is about Elnatan's personal life or data. 
If yes → look only in the FACTS block. If not present → say you don't have it. Do not continue thinking creatively."

Use this variant in addition to (not instead of) weak_model_directive.md when routing to Groq.
