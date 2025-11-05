import os
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
print("DISCORD_WEBHOOK =", DISCORD_WEBHOOK)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        body = await request.json()
        print("Received body:", body)
    except Exception as e:
        print("JSON parse error:", e)
        return {"status": "error", "details": "invalid json"}

    # Extract fields safely
    work_id = data["resource"]["id"]
    title = data["resource"]["fields"]["System.Title"]
    user = data["resource"]["fields"]["System.ChangedBy"]["displayName"]
    url = data["resource"]["_links"]["html"]["href"]

    message = f"""
        🔔 Update en Azure Boards
        **ID:** {work_id}
        **Título:** {title}
        **Usuario:** {user}
        🔗 {url}
        """

    print("Sending to Discord:", message)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(DISCORD_WEBHOOK, json=message, timeout=10)
            print("Discord response:", response.status_code, response.text)

            if response.status_code not in (200, 204):
                return {"status": "error", "discord": response.text}

    except Exception as e:
        print("Discord error:", e)
        return {"status": "error", "details": str(e)}

    return {"status": "ok", "sent": True}
