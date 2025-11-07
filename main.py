import os
import re
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
print("DISCORD_WEBHOOK =", DISCORD_WEBHOOK)
DISCORD_WEBHOOK2 = os.getenv("DISCORD_WEBHOOK2")
AZURE_ORG = os.getenv("AZURE_ORG")
print("AZURE_ORG =", AZURE_ORG)
AZURE_PROJECT = os.getenv("AZURE_PROJECT")
print("AZURE_PROJECT =", AZURE_PROJECT)
AZURE_PAT = os.getenv("AZURE_PAT")
print("AZURE_PAT =", AZURE_PAT)

@app.post("/update")
async def update(request: Request):
    try:
        body = await request.json()
        print("Received body:", body)
    except Exception as e:
        print("JSON parse error:", e)
        return {"status": "error", "details": "invalid json"}

    # Extract fields safely
    resource = body.get("resource", {})
    fields = resource.get("revision", {}).get("fields", {})
    title = fields.get("System.Title", "Sin título")
    user = fields.get("System.ChangedBy", "Desconocido");
    work_id = resource.get("revision", {}).get("id", "-")

    # Discord message format
    discord_payload = {
        "content": f"🔔 **Actualización en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
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

@app.post("/create")
async def create(request: Request):
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
    user = fields.get("System.ChangedBy", "Desconocido");
    work_id = resource.get("id", "—")

    # Discord message format
    discord_payload = {
        "content": f"🔔 **Nuevo trabajo en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
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

@app.post("/delete")
async def delete(request: Request):
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
    user = fields.get("System.ChangedBy", "Desconocido");
    work_id = resource.get("id", "—")

    # Discord message format
    discord_payload = {
        "content": f"🔔 **Trabajo eliminado en Azure Boards**\n"
                   f"**ID:** {work_id}\n"
                   f"**Título:** {title}\n"
                   f"**Usuario:** {user}\n"
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


@app.post("/github")
async def github_webhook(request: Request):
    event = request.headers.get("X-GitHub-Event")
    print(f"📨 Evento recibido de GitHub: {event}")

    # ✅ Si el evento es "ping", simplemente respondemos OK
    if event == "ping":
        print("✅ GitHub webhook verificado correctamente (ping recibido)")
        return {"status": "pong"}

    # ✅ Intentamos leer el cuerpo, incluso si no es JSON puro
    try:
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8").strip()

        if not body_str:
            print("⚠️ Cuerpo vacío recibido del webhook")
            return {"status": "error", "details": "empty body"}

        # GitHub a veces envía application/x-www-form-urlencoded
        if body_str.startswith("payload="):
            body_str = body_str.replace("payload=", "", 1)
            body_str = httpx.URL(body_str).decode() if "%7B" in body_str else body_str  # decodifica %7B%7D

        body = json.loads(body_str)
        print("✅ Body leído correctamente")
    except Exception as e:
        print("❌ Error leyendo el body:", e)
        print("📦 Cuerpo recibido (raw):", raw_body)
        return {"status": "error", "details": str(e)}

    # ✅ Verificamos que tenga commits
    if "commits" not in body:
        print("⚠️ No se encontraron commits en el webhook")
        return {"status": "ignored", "reason": "no commits"}

    repo_name = body.get("repository", {}).get("full_name", "Repositorio desconocido")
    pusher = body.get("pusher", {}).get("name", "Desconocido")

    async with httpx.AsyncClient() as client:
        for commit in body["commits"]:
            message = commit.get("message", "")
            url = commit.get("url", "")
            author = commit.get("author", {}).get("name", "Desconocido")

            print(f"🔹 Procesando commit de {author}: {message}")

            # 🔍 Detectar referencias a work items
            match_doing = re.search(r"[Ww]orking on AB#(\d+)", message)
            match_done = re.search(r"[Ff]ixes AB#(\d+)", message)

            # 🔹 Actualizar en Azure si aplica
            if match_doing:
                work_id = match_doing.group(1)
                print(f"🔧 Work item {work_id} → Doing")
                await update_azure_state(work_id, "Doing")

            if match_done:
                work_id = match_done.group(1)
                print(f"✅ Work item {work_id} → Done")
                await update_azure_state(work_id, "Done")

            # 🔹 Enviar mensaje a Discord
            discord_message = {
                "content": f"🧩 **Nuevo commit en GitHub**\n"
                           f"📁 **Repositorio:** {repo_name}\n"
                           f"👤 **Autor:** {author}\n"
                           f"💬 **Mensaje:** {message}\n"
                           f"🔗 [Ver commit]({url})"
            }

            try:
                discord_response = await client.post(DISCORD_WEBHOOK2, json=discord_message, timeout=10)
                print(f"📨 Enviado a Discord → {discord_response.status_code}")
            except Exception as e:
                print("❌ Error enviando a Discord:", e)

    return {"status": "ok"}


async def update_azure_state(work_item_id, new_state):
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/wit/workitems/{work_item_id}?api-version=7.0"
    headers = {"Content-Type": "application/json-patch+json"}
    data = [{"op": "add", "path": "/fields/System.State", "value": new_state}]

    async with httpx.AsyncClient() as client:
        response = await client.patch(url, headers=headers, json=data, auth=("", AZURE_PAT))
        print(f"Azure update {work_item_id} → {new_state}: {response.status_code}")
        if response.status_code >= 400:
            print("Azure error:", response.text)
