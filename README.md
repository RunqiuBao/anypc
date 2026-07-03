# "All you need to turn a remote server into an accessible desktop."

# Declaration of Purpose
- Once deployed this repo, a remote server that is accessible through SSH, can become a convenient desktop PC for neural network inference.
  - If needed, install ngrok and start the ssh server on boot in the remote.
  - Open a VNC server on boot in the remote.
  - Setup a WebSocket server instance for receiving remote observations (image + text prompt) and send through IPC to another inference process.

## Remote inference protocol
The gateway speaks the same WebSocket protocol as
[openpi remote inference](https://github.com/Physical-Intelligence/openpi/blob/main/docs/remote_inference.md):
a raw WebSocket carrying [msgpack](https://msgpack.org/) frames with numpy-array
support. On connect the server sends one metadata frame; thereafter each client
message is a packed observation dict and each reply is a packed result dict.

Any openpi client can talk to it directly. The openpi client is vendored under
`anypc.openpi_client` (Apache-2.0, from Physical Intelligence's openpi), so no
openpi install is needed — `from openpi_client import ...` works too if you have
openpi installed separately:

```python
from anypc.openpi_client import image_tools, websocket_client_policy

client = websocket_client_policy.WebsocketClientPolicy(host="<server>", port=8000)
print(client.get_server_metadata())            # the metadata frame sent on connect
image = image_tools.convert_to_uint8(          # resize+pad to the model's input
    image_tools.resize_with_pad(raw_image, 224, 224)
)
result = client.infer({"prompt": "...", "observation/image": image})
```

- `anypc-server` — start the gateway (WebSocket front door + ZeroMQ relay).
- `anypc-example-worker` — a stub ZeroMQ backend; replace `run_inference` with a real model.
- `anypc.openpi_client` — vendored openpi websocket client + msgpack-numpy + image helpers.
- Health check: HTTP `GET /healthz` returns `200 OK`.

# Deployment

Everything runs as systemd *user* services under the deploying user:

| Service | What it runs | Installed |
|---|---|---|
| `anypc-vnc` | TigerVNC desktop on display `:1` (localhost only) | always |
| `anypc-server` | WebSocket inference gateway on port 8000 | always |
| `ngrok-ssh` | ngrok TCP tunnel exposing local SSH (port 22) | only with `WITH_NGROK=1` |

## Server side: fresh machine (one-time)

```bash
sudo make install WITH_NGROK=1      # from the cloned repo; omit WITH_NGROK to skip ngrok
ngrok config add-authtoken <token>  # once per machine (skip if not using ngrok)
sudo loginctl enable-linger $USER   # let user services run without a login session
systemctl --user enable anypc-vnc anypc-server ngrok-ssh   # auto-start at boot
```

`make install` copies the repo to `/opt/anypc`, installs dependencies, places
the unit files in `~/.config/systemd/user/`, and hooks the `anypc` shell
helper into `~/.bashrc`.

### Day-to-day control

The `anypc` helper controls the two anypc services — it does **not** touch the
tunnel:

```bash
anypc launch            # start anypc-vnc + anypc-server
anypc {stop|restart|status|logs}
```

The ngrok tunnel is managed directly with systemctl:

```bash
systemctl --user status ngrok-ssh     # is the tunnel up?
systemctl --user restart ngrok-ssh
journalctl --user -u ngrok-ssh -f     # live logs
systemctl --user stop ngrok-ssh       # careful: if you are SSH'd in via the tunnel, this cuts you off
systemctl --user disable ngrok-ssh    # stop auto-starting at boot (independent of start/stop)
```

### Changing service configuration

The unit files in `systemd/` are the source of truth (for ngrok, the
`ExecStart` line carries the region and reserved address). After editing one,
propagate it and restart:

```bash
cp systemd/<unit>.service /opt/anypc/systemd/
cp systemd/<unit>.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart <unit>
```

ngrok's own settings (authtoken, etc.) live in `~/.config/ngrok/ngrok.yml`,
outside this repo. With a reserved TCP address the forwarding address is fixed
across restarts and reboots, so SSH access is simply:

```bash
ssh -p <reserved-port> <user>@<reserved-host>   # e.g. 1.tcp.jp.ngrok.io
```

## Client side:
- ssh to the server by
```bash
ssh -p <reserved-port> <user>@<reserved-host>   # e.g. 1.tcp.jp.ngrok.io, get from ngrok TCP addresses.
```
- start the vnc viewer by:
```
vnchome() {
    local port=5901
    local port2=5902
    local host="home"

    # Start tunnel in background (skip if already running)
    if ! pgrep -f "ssh -fN -L ${port2}:localhost:${port} ${host}" > /dev/null; then
        ssh -fN -L ${port2}:localhost:${port} ${host} || return 1
    fi

    # Launch viewer (blocks until you close it)
    vncviewer localhost:${port2}

    # Kill the tunnel when viewer exits
    pkill -f "ssh -fN -L ${port2}:localhost:${port} ${host}"
}
```
