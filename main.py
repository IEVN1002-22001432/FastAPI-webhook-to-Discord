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

GITHUB_TOKEN=os.getenv("GITHUB_TOKEN")
GITHUB_OWNER=os.getenv("GITHUB_OWNER")
GITHUB_REPO=os.getenv("GITHUB_REPO")

USER_MAP = {
    "80981@alumnos.utleon.edu.mx": "IEVN1002-22001432",
    "21000020@alumnos.utleon.edu.mx": "IEVN1002-21000020",
    "21002110@alumnos.utleon.edu.mx": "IEVN1002-21002110",
    "79028@alumnos.utleon.edu.mx": "IEVN1002-22001383",
    "21000456@alumnos.utleon.edu.mx": "IEVN1002-22000456"
}

# ---------------- Azure Boards ---------------- #

@app.post("/update")
async def update(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        print("❌ JSON parse error:", e)
        return {"status": "error", "details": "invalid json"}

    resource = body.get("resource", {})
    revision = resource.get("revision", {})
    fields = revision.get("fields", {})
    work_id = revision.get("id", "-")
    title = fields.get("System.Title", "Sin título")

    # --- ChangedBy ---
    changed_field = fields.get("System.ChangedBy")
    if isinstance(changed_field, dict):
        user = changed_field.get("displayName", "Desconocido")
    elif isinstance(changed_field, str):
        user = changed_field
    else:
        user = "Desconocido"

    # --- AssignedTo ---
    assigned_field = fields.get("System.AssignedTo")
    if isinstance(assigned_field, dict):
        assigned_to = assigned_field.get("uniqueName")
    elif isinstance(assigned_field, str):
        import re
        match = re.search(r"<(.+?)>", assigned_field)
        assigned_to = match.group(1) if match else assigned_field
    else:
        assigned_to = None

    print(f"🧱 UPDATE recibido → id={work_id}, title='{title}', assigned_to={assigned_to}, user={user}")

    # --- Discord notification ---
    discord_payload = {
        "content": f"**Actualización en Azure**\n"
                   f"**ID:** {work_id}\n"
                   f"**Trabajo:** {title}\n"
                   f"**Miembro:** {user}"
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
        print(f"📤 Discord webhook → {r.status_code}")

    # --- GitHub issue update ---
    print("🚀 Entrando a bloque de actualización GitHub")

    # ✅ Validar configuración
    print("🔧 GITHUB_OWNER:", GITHUB_OWNER)
    print("🔧 GITHUB_REPO:", GITHUB_REPO)
    print("🔧 TOKEN presente:", "✅" if GITHUB_TOKEN else "❌ vacío")

    if not all([GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO]):
        print("⚠️ Configuración GitHub incompleta. Abortando actualización.")
        return {"status": "error", "details": "GitHub config missing"}

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    try:
        async with httpx.AsyncClient() as client:
            search_url = (
                f"https://api.github.com/search/issues"
                f"?q=repo:{GITHUB_OWNER}/{GITHUB_REPO}+in:title+AB#{work_id}"
            )
            print(f"🔍 Buscando issue en GitHub → {search_url}")
            search = await client.get(search_url, headers=headers)

            print(f"🔎 GitHub search status: {search.status_code}")
            if search.status_code >= 400:
                print("❌ GitHub search error:", search.text)
                return {"status": "error", "details": f"GitHub search failed ({search.status_code})"}

            data = search.json()
            print(f"📦 Search JSON keys: {list(data.keys())}")
            total = data.get("total_count", 0)
            print(f"🔢 Issues encontrados: {total}")

            if total == 0:
                print("⚠️ No se encontró ningún issue con ese AB#ID.")
                return {"status": "ok", "details": "no matching issue"}

            issue_number = data["items"][0]["number"]
            issue_title = data["items"][0]["title"]
            print(f"🪣 Issue encontrado #{issue_number}: '{issue_title}'")

            # --- Si hay assigned_to ---
            if assigned_to:
                gh_user = USER_MAP.get(assigned_to)
                print(f"👤 Mapeo de usuario: {assigned_to} → {gh_user}")
                if gh_user:
                    update_data = {"assignees": [gh_user]}
                    patch_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}"
                    print(f"🛠️ Actualizando issue #{issue_number} con {update_data}")
                    patch = await client.patch(patch_url, headers=headers, json=update_data)
                    print(f"🐙 GitHub issue update → {patch.status_code}")
                    print("🔧 Response text:", patch.text[:300])
                else:
                    print(f"No hay mapeo en USER_MAP para {assigned_to}")
            else:
                print("No hay ningún usuario asignado en Azure (assigned_to es None)")

    except Exception as e:
        print(f"💥 Error actualizando GitHub: {type(e).__name__} - {e}")

    return {"status": "ok"}

@app.post("/create")
async def create(request: Request):
    print("🚀 Azure → /create endpoint llamado")

    try:
        body = await request.json()
        print("📩 Received Azure CREATE webhook body:", json.dumps(body, indent=2))
    except Exception as e:
        print("❌ JSON parse error:", e)
        raw = await request.body()
        print("📦 Raw body recibido:", raw[:500])
        return {"status": "error", "details": "invalid json"}

    resource = body.get("resource", {})
    fields = resource.get("fields", {})
    title = fields.get("System.Title", "Sin título")
    assigned_field = fields.get("System.AssignedTo")
    if isinstance(assigned_field, dict):
        assigned_to = assigned_field.get("uniqueName")
    elif isinstance(assigned_field, str):
    # Extrae el correo si existe entre < >
        import re
        match = re.search(r"<(.+?)>", assigned_field)
        assigned_to = match.group(1) if match else assigned_field
    else:
        assigned_to = None
    user = fields.get("System.ChangedBy", "Desconocido")
    work_id = resource.get("id", "—")

    print(f"🧱 Datos procesados → title={title}, assigned_to={assigned_to}, user={user}, id={work_id}")

    # ========== 🔔 Discord notification ==========
    discord_payload = {
        "content": f"**Nuevo trabajo en Azure**\n"
                   f"**ID:** {work_id}\n"
                   f"**Trabajo:** {title}\n"
                   f"**Miembro:** {user}"
    }

    try:
        async with httpx.AsyncClient() as client:
            discord_response = await client.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
            print("✅ Discord response:", discord_response.status_code, discord_response.text[:200])
    except Exception as e:
        print("❌ Error enviando a Discord:", e)

    # ========== 🧩 Crear issue en GitHub ==========
    github_issue = {
        "title": f"[AB#{work_id}] {title}",
        "body": f"Creado automáticamente desde Azure Boards por **{user}**.\n\n"
                f"🔗 [Ver en Azure Boards](https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_workitems/edit/{work_id})"
    }

    if assigned_to:
        gh_user = USER_MAP.get(assigned_to)
        if gh_user:
            github_issue["assignees"] = [gh_user]

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    github_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues"

    print(f"🐙 Creando issue en GitHub → {github_url}")
    print(f"🧾 Payload:", json.dumps(github_issue, indent=2))

    try:
        async with httpx.AsyncClient() as client:
            gh_resp = await client.post(github_url, headers=headers, json=github_issue, timeout=10)
            print("🐙 GitHub issue create:", gh_resp.status_code, gh_resp.text[:200])
    except Exception as e:
        print("❌ Error al crear issue en GitHub:", e)

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
        "content": f"**Trabajo eliminado en Azure**\n"
                   f"**ID:** {work_id}\n"
                   f"**Trabajo:** {title}\n"
                   f"**Miembro:** {user}\n"
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
                    f"**Nuevo commit**\n"
                    f"**Repositorio:** {repo_name}\n"
                    f"**Miembro:** {author}\n"
                    f"**Mensaje:** {message}\n"
                    f"[Link directo]({url})"
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
