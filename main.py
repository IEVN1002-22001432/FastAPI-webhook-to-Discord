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
    resource = body.get("resource", {})
    fields = resource.get("fields", {})
    title = fields.get("System.Title", "Sin título")
    user = fields.get("System.ChangedBy", "Desconocido")
    work_id = resource.get("id", "—")
    link = resource.get("_links", {}).get("html", {}).get("href", "")

    # Discord message format
    discord_payload = {
        "content": f"🔔 **Update en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
                   f"🔗 {link}"
    }

    print("Sending to Discord:", discord_payload)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
            print("Discord response:", response.status_code, response.text)

            if response.status_code not in (200, 204):
                return {"status": "error", "discord": response.text}

    except Exception as e:
        print("Discord error:", e)
        return {"status": "error", "details": str(e)}

    return {"status": "ok", "sent": True}
