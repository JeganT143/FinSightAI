"""Fixed refusal copy (SAAS §8.2/§9).

Non-generative on purpose: the same string, verbatim, every time — a model
asked to 'politely decline' will eventually improvise its way into advice.
The UI renders this with its own distinct treatment (SAAS_DESIGN §6), and
the text itself names the boundary so it's legible without color or styling.
"""

ADVICE_REFUSAL_TEXT = (
    "I can share research and data, but I can't give personalized investment "
    "advice — whether to buy or sell is a decision that depends on your "
    "situation, and FinSightAI doesn't know it. What I can do: run or pull up "
    "the research on the ticker you're considering, show you what the "
    "specialists and the adversarial critic found, and explain any metric in "
    "it. The decision stays yours."
)
