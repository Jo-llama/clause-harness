from dotenv import load_dotenv
load_dotenv()

import anthropic
client = anthropic.Anthropic()

msg = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=100,
    messages=[{"role": "user", "content": "ping"}],
)
print(msg.content[0].text)
