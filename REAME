# Declaration of Purpose
- Once deployed this repo, a remote server that is accessible through SSH, can become a convenient desktop PC for neural network inference.
  - Open a VNC viewer.
  - Setup a fastAPI server instance for receving remote image, text prompt and send through IPC to another inference process.


# Installation on Remote Server
- `git clone git@github.com:RunqiuBao/anypc.git`
- `cd anypc && sudo make install`
- `anypc launch`


# Open Vncviewer on Client
- `ssh -L 5902:localhost:5901 <server-ip>`
- in another terminal `vncviewer localhost::5902`

