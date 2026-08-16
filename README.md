# TRU Blockchain — Node

Run a node on the Tokenized Real Utility (TRU) blockchain. The published
Docker images carry everything they need, so there is nothing to compile and
no dependencies to install beyond Docker itself.

---

## Which image do I want?

| Image | Use when |
|---|---|
| **`tru-node`** | Default choice. Runs anywhere, no GPU needed. Full menu, CPU mining works. |
| **`tru-node-gpu`** | You have an **NVIDIA** GPU and want GPU mining. Everything else is identical. |

Both are the same node with the same interactive menu, built from the same
source. The only difference is that `tru-node-gpu` is compiled with OpenCL, so
the GPU mining options do something. If you are not going to mine on a GPU,
take `tru-node` — it has fewer moving parts.

The GPU image is NVIDIA only. AMD and Intel GPUs use a different OpenCL driver
setup and are not supported by this image.

---

## Quick start — CPU (`tru-node`)

**1. Install Docker**

Ubuntu / Debian:

```bash
sudo apt update && sudo apt install -y docker.io
sudo usermod -aG docker $USER
newgrp docker
```

macOS or Windows: install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

**2. Run the node**

```bash
docker run -it -p 8333:8333 -v tru-data:/app/data \
    ghcr.io/agreatopportunity/tru-node:latest --cli
```

That is the whole thing. The image ships with a working default config, so the
node will find a seed peer and begin syncing on first launch. You should see
the menu appear, followed by peer connection and sync activity.

---

## Quick start — GPU (`tru-node-gpu`)

Everything above, plus the NVIDIA Container Toolkit on the host. Having the
NVIDIA driver alone is not enough — the toolkit is what lets Docker pass the
GPU into a container.

**1. Confirm your driver works**

```bash
nvidia-smi
```

Your GPUs should be listed. If not, install the NVIDIA driver first.

**2. Install the NVIDIA Container Toolkit**

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Full instructions: [NVIDIA Container Toolkit install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

**3. Verify Docker can see the GPU**

```bash
docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

Your GPUs should appear again, this time from inside a container. Do not move
on until this works — if it fails here, the node will start but find no OpenCL
devices.

**4. Run the node**

```bash
docker run -it --gpus all -p 8333:8333 -v tru-data:/app/data \
    ghcr.io/agreatopportunity/tru-node-gpu:latest --cli
```

Then pick the GPU mining option from the menu. Watch `nvidia-smi` in another
terminal to confirm the GPU is actually being used.

---

## Running both at once

You can, but two things will collide:

- **Port 8333.** Only one container can bind it. Give the second a different
  host port: `-p 8334:8333`.
- **The data volume.** The database allows a single writer, so each container
  needs its own: `-v tru-gpu-data:/app/data`.

Most people should just run one.

---

## Using the menu

`--cli` opens an interactive menu covering wallet creation, sending funds,
mining, tokens, TRU scripts, smart contracts, and peer management. Navigate by
entering the number or letter shown.

To leave the container running while you do something else, press
`Ctrl-P` then `Ctrl-Q`. Come back with:

```bash
docker attach tru-node
```

To stop the node, choose the Exit option from the menu. That lets it save
chain state and wallet files cleanly, which `docker stop` currently does not.

---

## Keeping your data

Everything the node writes — chain data, UTXO set, wallet files, peer list —
lives in a Docker volume called `tru-data`. It survives container restarts,
removals, and image updates.

```bash
docker volume inspect tru-data       # see where it lives on disk
```

Back it up before doing anything risky:

```bash
docker run --rm -v tru-data:/data -v "$(pwd)":/backup ubuntu \
    tar czf /backup/tru-backup.tar.gz /data
```

> **Your wallet lives in this volume.** `docker volume rm tru-data` and
> `docker compose down -v` both delete it permanently. If you have funds on
> this node, back up first.

---

## Custom configuration

The defaults work for syncing. Mount your own `tru.conf` if you want to change
ports, add peers, or advertise a public address.

```bash
git clone https://github.com/agreatopportunity/TRU-DOCKER.git
cd TRU-DOCKER
cp tru.conf.example tru.conf
# edit tru.conf
```

Then mount it:

```bash
docker run -it -p 8333:8333 \
    -v tru-data:/app/data \
    -v "$(pwd)/tru.conf:/app/tru.conf:ro" \
    ghcr.io/agreatopportunity/tru-node:latest --cli
```

On Windows PowerShell, use `${PWD}` instead of `$(pwd)`.

Or use Compose, which handles the mounts for you:

```bash
docker compose up -d node
docker compose logs -f node
docker compose down          # stop, keep data
```

### Config format

```ini
[network]
rpcbind=127.0.0.1
rpcport=8332
p2pPort=8333
listen=1
rpcMaxConnections=32

# Your public IP, if other peers should be able to reach you.
# Leave commented out if you are behind a home router or CGNAT.
#externalip=203.0.113.10

# Peers to connect to on startup. Comma-separated ip:port.
addnode=137.184.68.43:8333
```

Three parser rules that will silently break things:

- **No spaces after commas** in `addnode`. Write `1.2.3.4:8333,5.6.7.8:8333`,
  not `1.2.3.4:8333, 5.6.7.8:8333`.
- **No inline comments.** `p2pPort=8333 # main` is read as the literal value
  `8333 # main`. Put comments on their own line.
- **IP addresses only**, not hostnames. The peer layer does not resolve DNS.

`seeds=` behaves identically to `addnode=`; both add to the same peer list.

---

## Ports

| Port | Purpose | Expose to the internet? |
|---|---|---|
| 8333 | Peer-to-peer sync | Yes — this is how other nodes reach you |
| 8332 | JSON-RPC | **No** |

> **The RPC interface has no authentication.** Any method — including wallet
> and mining operations — can be called by anyone who can reach port 8332. Do
> not publish it, do not put it behind a public hostname, and do not tunnel it
> without an authenticating proxy in front. Port 8333 is safe and meant to be
> public.

If you want inbound peers, open 8333 on your firewall:

```bash
sudo ufw allow 8333/tcp
```

---

## Accepting inbound peers

Your node syncs fine without this — outbound connections always work. Accepting
inbound peers is optional and helps the network.

To be reachable you need three things: port 8333 published (`-p 8333:8333`),
your firewall allowing it, and a route from the internet to your machine. That
last one is where it usually breaks:

**Home router.** Forward external TCP 8333 to your machine's LAN address, then
set `externalip` to your public IP (find it with `curl -4 ifconfig.me`).

**CGNAT.** Common on Starlink, cellular, and some cable providers — your public
IP is shared at the carrier level and port forwarding cannot work. Check your
router's WAN address; anything starting `100.64.` through `100.127.` is CGNAT.
There is no workaround at home. Your node still syncs normally; it just cannot
accept incoming connections.

---

## Updating

```bash
docker pull ghcr.io/agreatopportunity/tru-node:latest
docker rm -f tru-node
docker run -it -p 8333:8333 -v tru-data:/app/data \
    ghcr.io/agreatopportunity/tru-node:latest --cli
```

Same for the GPU image, substituting `tru-node-gpu` and adding `--gpus all`.

Your data volume is untouched by this — the new container picks up right where
the old one left off.

Version tags are published alongside `latest` if you prefer to pin:

```bash
docker pull ghcr.io/agreatopportunity/tru-node:v0.1.1
```

---

## Known limitations

**No background mode yet.** The node currently has no daemon mode, so it needs
a terminal attached. `docker run -d` will not work correctly, and `docker stop`
kills the process rather than shutting it down cleanly — which can leave a
stale database lock. Use the menu's Exit option to stop the node, and detach
with `Ctrl-P` `Ctrl-Q` rather than stopping the container. A `--daemon` mode is
planned.

**No GUI wallet in either image.** Containers have no display, so the Qt wallet
is not included. It is available as a native build from the source repository.

**GPU image is NVIDIA only.** AMD and Intel GPUs need a different OpenCL ICD
setup. `tru-node-gpu` will start on those systems but find no OpenCL devices.

**Single seed peer.** New nodes currently bootstrap from one seed. If it is
unreachable, sync will not start. Additional seeds are planned.

---

## Troubleshooting

**`permission denied ... docker.sock`**
Your user is not in the `docker` group. Run `sudo usermod -aG docker $USER`
then `newgrp docker`, or log out and back in.

**`failed to discover GPU vendor from CDI: no known GPU vendor found`**
The NVIDIA Container Toolkit is not installed, or Docker was not restarted after
configuring it. See the GPU quick start above. Having `nvidia-smi` work on the
host is not sufficient on its own.

**GPU mining finds no devices**
Check the toolkit is passing the driver through:

```bash
docker run --rm --gpus all ghcr.io/agreatopportunity/tru-node-gpu:latest \
    bash -c "ls /usr/lib/x86_64-linux-gnu/ | grep nvidia-opencl"
```

`libnvidia-opencl.so.1` should be listed. If it is missing, the container is
not receiving the driver — confirm you passed `--gpus all`.

**Container exits immediately**
Run without `-d` to see the output. Most often this means `--cli` was started
without a terminal — make sure you passed `-it`.

**`Unable to open/create database: IO error: lock data/utxo/LOCK`**
Two containers are sharing one data volume, and the database only permits one
writer. Check `docker ps` and stop the other one, or give each its own volume.

**No peers connecting**
At startup the node logs a line like `[P2PNode] Added addnode: 1.2.3.4:8333`
for each configured peer. If those lines are missing, your `tru.conf` was not
found or the format is wrong. If they appear but nothing connects, check the
seed is reachable: `nc -vz 137.184.68.43 8333`.

**Menu appears but nothing syncs**
Give it a minute — the initial peer handshake and header download take time on
a fresh node. Check the peer list from the menu to confirm a connection was
established.

---

## What is in the images

Both are built from `ubuntu:24.04` and are roughly 130 MB. They contain the
node binary and its runtime libraries — no compiler, no Qt, no bundled GPU
drivers. The node runs as an unprivileged user inside the container, not as
root.

`tru-node-gpu` additionally carries the OpenCL ICD loader. The NVIDIA OpenCL
driver itself is injected from your host at run time by the container toolkit,
which is why the image stays small and does not pin a CUDA version.

Source and build files: [github.com/agreatopportunity/TRU-DOCKER](https://github.com/agreatopportunity/TRU-DOCKER)
