import os
import re
import json
from fastapi import FastAPI, Request
import httpx
from urllib.parse import unquote_plus

app = FastAPI()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_WEBHOOK2 = os.getenv("DISCORD_WEBHOOK2")
AZURE_ORG = os.getenv("AZURE_ORG")
AZURE_PROJECT = os.getenv("AZURE_PROJECT")
AZURE_PAT = os.getenv("AZURE_PAT")

# ---------------- Azure Boards ---------------- #

@app.post("/update")
async def update(request: Request):
    try:
        body = await request.json()
        print("Received body:", body)
    except Exception as e:
        print("JSON parse error:", e)
        return {"status": "error", "details": "invalid json"}

    resource = body.get("resource", {})
    fields = resource.get("revision", {}).get("fields", {})
    title = fields.get("System.Title", "Sin título")
    user = fields.get("System.ChangedBy", "Desconocido")
    work_id = resource.get("revision", {}).get("id", "-")

    discord_payload = {
        "content": f"🔔 **Actualización en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
        print("Discord response:", response.status_code)
    return {"status": "ok"}


@app.post("/create")
async def create(request: Request):
    try:
        body = await request.json()
        print("Received body:", body)
    except Exception as e:
        print("JSON parse error:", e)
        return {"status": "error", "details": "invalid json"}

    resource = body.get("resource", {})
    fields = resource.get("fields", {})
    title = fields.get("System.Title", "Sin título")
    user = fields.get("System.ChangedBy", "Desconocido")
    work_id = resource.get("id", "—")

    discord_payload = {
        "content": f"🔔 **Nuevo trabajo en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
        print("Discord response:", response.status_code)
    return {"status": "ok"}


@app.post("/delete")
async def delete(request: Request):
    try:
        body = await request.json()
        print("Received body:", body)
    except Exception as e:
        print("JSON parse error:", e)
        return {"status": "error", "details": "invalid json"}

    resource = body.get("resource", {})
    fields = resource.get("fields", {})
    title = fields.get("System.Title", "Sin título")
    user = fields.get("System.ChangedBy", "Desconocido")
    work_id = resource.get("id", "—")

    discord_payload = {
        "content": f"🔔 **Trabajo eliminado en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
        print("Discord response:", response.status_code)
    return {"status": "ok"}

# ---------------- GitHub ---------------- #

@app.post("/github")
async def github_webhook(request: Request):
    event = request.headers.get("X-GitHub-Event")
    print(f"🔔 Evento recibido de GitHub: {event}")

    if event == "ping":
        print("✅ GitHub webhook verificado correctamente (ping recibido)")
        return {"status": "pong"}

    try:
        try:
            body = await request.json()
        except Exception:
            raw_data = await request.body()
            raw_str = raw_data.decode("utf-8")

            if raw_str.startswith("payload="):
                json_str = unquote_plus(raw_str.replace("payload=", ""))
                body = json.loads(json_str)
            else:
                raise ValueError("Formato desconocido en el body")
    except Exception as e:
        print("❌ Error leyendo el body:", e)
        raw = await request.body()
        print("📦 Cuerpo recibido (raw):", raw[:500])
        return {"status": "error", "details": str(e)}

    if "commits" not in body:
        return {"status": "ignored", "reason": "no commits"}

    repo_name = body.get("repository", {}).get("full_name", "Repositorio desconocido")

    async with httpx.AsyncClient() as client:
        for commit in body["commits"]:
            message = commit.get("message", "")
            url = commit.get("url", "")
            author = commit.get("author", {}).get("name", "Desconocido")

            match_doing = re.search(r"[Ww]orking on AB#(\d+)", message)
            match_done = re.search(r"[Ff]ixes AB#(\d+)", message)

            if match_doing:
                await update_azure_state(match_doing.group(1), "Doing")
            if match_done:
                await update_azure_state(match_done.group(1), "Done")

            discord_message = {
                "content": (
                    f"🧩 **Nuevo commit en GitHub**\n"
                    f"📁 **Repositorio:** {repo_name}\n"
                    f"👤 **Autor:** {author}\n"
                    f"💬 **Mensaje:** {message}\n"
                    f"🔗 [Ver commit]({url})"
                )
            }

            discord_response = await client.post(DISCORD_WEBHOOK2, json=discord_message, timeout=10)
            print("✅ Enviado a Discord:", discord_response.status_code)

    return {"status": "ok"}


async def update_azure_state(work_item_id, new_state):
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/wit/workitems/{work_item_id}?api-version=7.0"
    headers = {"Content-Type": "application/json-patch+json"}
    data = [{"op": "replace", "path": "/fields/System.State", "value": new_state}]

    async with httpx.AsyncClient() as client:
        response = await client.patch(url, headers=headers, json=data, auth=("", AZURE_PAT))
        print(f"Azure update {work_item_id} → {new_state}: {response.status_code}")
        if response.status_code >= 400:
            print("Azure error:", response.text)
