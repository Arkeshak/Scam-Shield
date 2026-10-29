"""STEP 3 - run this first to check your key works:  python test_call.py"""
from app import config
from app.llm import get_client

response = get_client().responses.create(
    model=config.MODEL_NAME,
    input="Say hello in one short sentence.",
)
print(response.output_text)
