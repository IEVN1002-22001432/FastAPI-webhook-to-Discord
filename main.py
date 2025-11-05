import os
from fastapi import FastAPI, Request
import httpx

app = FastAPI()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
print("DISCORD_WEBHOOK =", DISCORD_WEBHOOK)

@app.post("/webhook")
async def receibve_webhool(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "details": "invalid json"}

    resource = body.get("resource", {})
    fields = resource.get("fields", {})
    title = fields.get("System.Title", "-")
    changed_by = fields.get("System.ChangedBy", "-")
    work_id = body.get("id", "-")
    link = resource.get("_links", {}).get("html", {}).get("href", "-")

    message = {
        "context": (
            f"**Azure Boards Update**\n"
            f"**Work item**: {work_id}\n"
            f"**Título**: {title}\n"
            f"**Usuario**: {changed_by}\n"
            f"🔗 {link}"
        )
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(DISCORD_WEBHOOK, json=message, timeout=10)
            
            if resp.status_code == 429:
                return {"status": "error", "details": "Discord rate limited"}
    except Exception as e:
        return {"status": "error", "details": str(e)}
    
    return {"status": "ok"}
