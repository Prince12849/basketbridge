from utils.llm import generate_json

result = generate_json(
    "Return ONLY valid JSON.",
    'Return exactly: {"status":"working"}'
)

print(result)