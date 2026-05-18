import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": "You are a finantial research assistant.Be concise and accurate.",
        },
        {"role": "user", "content": "Should I invest in Apple stocks?"},
    ],
)

answer = response.choices[0].message.content
print(answer)

pri
