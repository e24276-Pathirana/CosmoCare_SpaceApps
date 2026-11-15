import urllib.request
import json

# LM Studio එකේ Local Server URL එක
url = "http://localhost:1234/v1/chat/completions"

# AI එකට යවන මැසේජ් එක
payload = json.dumps({
    "model": "local-model",
    "messages": [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Hello! Are you working?"}
    ],
    "temperature": 0.5,
    "max_tokens": 100
}).encode("utf-8")

req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

try:
    print("⏳ Sending request to LM Studio...")
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
        ai_reply = data["choices"][0]["message"]["content"]

        print("\n✅ AI Chatbot is WORKING!")
        print(f"🤖 AI says: {ai_reply}")

except Exception as e:
    print(f"\n❌ Error connecting to AI: {e}")
    print("කරුණාකර LM Studio එකේ Local Server එක On කර ඇත්දැයි බලන්න.")