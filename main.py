import asyncio, json, time
from typing import Optional
import paramiko, uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="SSH Manager")

class SSHSession:
    def __init__(self, sid):
        self.sid = sid
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self.connected = False
        self._stop = False

    def connect(self, host, port, username, password=None, pkey_str=None, width=80, height=24):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kw = dict(hostname=host, port=port, username=username,
                      timeout=15, allow_agent=False, look_for_keys=False)
            if pkey_str and pkey_str.strip():
                import io
                buf = io.StringIO(pkey_str.strip())
                for cls in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
                    try:
                        buf.seek(0); kw["pkey"] = cls.from_private_key(buf); break
                    except: continue
                if "pkey" not in kw:
                    return "error:Cannot parse private key"
            elif password:
                kw["password"] = password
            else:
                return "error:No auth method provided"
            self.client.connect(**kw)
            self.channel = self.client.invoke_shell(term="xterm-256color", width=width, height=height)
            self.channel.settimeout(0.1)
            self.connected = True
            return "ok"
        except paramiko.AuthenticationException:
            return "error:Authentication failed — wrong username or password"
        except paramiko.SSHException as e:
            return "error:SSH error: " + str(e)
        except TimeoutError:
            return "error:Connection timed out — check host/port and firewall"
        except ConnectionRefusedError:
            return "error:Connection refused — SSH not running on port " + str(port)
        except OSError as e:
            return "error:Network error: " + str(e)
        except Exception as e:
            return "error:" + type(e).__name__ + ": " + str(e)

    def resize(self, w, h):
        if self.channel and self.connected:
            try: self.channel.resize_pty(width=w, height=h)
            except: pass

    def disconnect(self):
        self._stop = True; self.connected = False
        try:
            if self.channel: self.channel.close()
            if self.client: self.client.close()
        except: pass

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
        params = json.loads(raw)
    except Exception as e:
        await websocket.send_text(json.dumps({"type":"error","data":str(e)}))
        await websocket.close(); return

    if params.get("action") != "connect":
        await websocket.close(); return

    session = SSHSession(session_id)
    host = params.get("host","")
    port = int(params.get("port", 22))
    username = params.get("username","")
    password = params.get("password","")
    pkey_str = params.get("private_key","")
    cols = int(params.get("cols", 80))
    rows = int(params.get("rows", 24))

    await websocket.send_text(json.dumps({"type":"status","data":f"Connecting to {host}…"}))
    result = await asyncio.get_event_loop().run_in_executor(
        None, session.connect, host, port, username, password, pkey_str, cols, rows)

    if not result.startswith("ok"):
        await websocket.send_text(json.dumps({"type":"error","data":result.replace("error:","",1)}))
        await websocket.close(); return

    await websocket.send_text(json.dumps({"type":"connected","data":f"Connected to {host}"}))

    def _read(ch):
        if ch is None or ch.closed: return None
        try:
            if ch.recv_ready(): return ch.recv(4096).decode("utf-8", errors="replace")
            if ch.exit_status_ready(): return None
            time.sleep(0.02); return ""
        except: return None

    async def reader():
        loop = asyncio.get_event_loop()
        while session.connected and not session._stop:
            try:
                data = await loop.run_in_executor(None, _read, session.channel)
                if data is None: break
                if data: await websocket.send_text(json.dumps({"type":"output","data":data}))
            except: break
        try: await websocket.send_text(json.dumps({"type":"disconnected","data":"Session closed"}))
        except: pass

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            t = msg.get("type")
            if t == "input" and session.channel and session.connected:
                session.channel.send(msg["data"])
            elif t == "resize":
                session.resize(int(msg.get("cols",80)), int(msg.get("rows",24)))
            elif t == "disconnect": break
    except (WebSocketDisconnect, Exception): pass
    finally:
        reader_task.cancel()
        session.disconnect()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
