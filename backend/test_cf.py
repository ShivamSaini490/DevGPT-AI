import os, base64, requests
from dotenv import load_dotenv

load_dotenv()
acc = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
tok = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
print("account id length:", len(acc), "| token length:", len(tok))  # account id 32 ka hona chahiye

url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/black-forest-labs/flux-1-schnell"
r = requests.post(
    url,
    headers={"Authorization": f"Bearer {tok}"},
    json={"prompt": "a red apple on a wooden table, sharp focus", "steps": 8},
    timeout=60,
)
print("STATUS:", r.status_code)
print("BODY:", r.text[:500])

if r.status_code == 200:
    img = base64.b64decode(r.json()["result"]["image"])
    open("test.png", "wb").write(img)
    print("Saved test.png")