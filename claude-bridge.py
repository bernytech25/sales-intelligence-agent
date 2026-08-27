import os, sys, json, httpx

URL = os.environ.get("MCP_REMOTE_URL", "https://sales-intelligence-mcp-439702316082.us-central1.run.app/mcp")
TOKEN = os.environ["MCP_AUTH_TOKEN"]

client = httpx.Client(timeout=60.0, headers={
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
})

# El servidor MCP remoto exige un mcp-session-id en cada request DESPUES del
# 'initialize' (protocolo Streamable HTTP con estado de sesion). Lo capturamos
# de la respuesta del primer request y lo reenviamos en todos los siguientes.
session_id = None

for line in sys.stdin:
    if not line.strip():
        continue

    # Intentamos leer el id del request ANTES de hacer nada, para poder
    # devolverlo correctamente si algo falla mas adelante. Los mensajes
    # tipo "notification" (ej. notifications/initialized) no tienen id;
    # a esos el protocolo dice que no hay que responderles nada.
    request_id = None
    is_notification = True
    try:
        parsed_request = json.loads(line)
        if "id" in parsed_request:
            request_id = parsed_request["id"]
            is_notification = False
    except json.JSONDecodeError:
        pass  # dejamos que falle mas abajo con un error prolijo

    try:
        headers = {}
        if session_id:
            headers["mcp-session-id"] = session_id

        r = client.post(URL, content=line.strip(), headers=headers)

        if not session_id and "mcp-session-id" in r.headers:
            session_id = r.headers["mcp-session-id"]

        # Las notificaciones no esperan respuesta (el server responde 202
        # sin cuerpo) -- no imprimimos nada en ese caso.
        if is_notification and not r.text.strip():
            continue

        for response_line in r.text.strip().split('\n'):
            if response_line.startswith('data: '):
                json_data = response_line[6:]  # Quitar "data: "
                print(json_data, flush=True)
            elif response_line.startswith('event: '):
                continue  # Ignorar lineas de evento
            elif response_line.strip():
                print(response_line, flush=True)

    except Exception as e:
        # Solo emitimos un error JSON-RPC si el request original tenia id
        # (si era una notificacion, no corresponde responder nada, ni con
        # error -- eso es lo que generaba el "id": null invalido).
        if not is_notification:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)},
            }), flush=True)