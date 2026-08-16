# TRU Blockchain — Node

Run a node on the Tokenized Real Utility (TRU) blockchain. The published
Docker image carries everything it needs, so there is nothing to compile and
no dependencies to install beyond Docker itself.

---

## Quick start

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
node will find a seed peer and begin syncing on first launch.

You should see the menu appear, followed by peer connection and sync activity.

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

Your data volume is untouched by this — the new container picks up right where
the old one left off.

Version tags are published alongside `latest` if you prefer to pin:

```bash
docker pull ghcr.io/agreatopportunity/tru-node:v0.1.0
```

---

## Known limitations

**No background mode yet.** The node currently has no daemon mode, so it needs
a terminal attached. `docker run -d` will not work correctly, and `docker stop`
kills the process rather than shutting it down cleanly — which can leave a
stale database lock. Use the menu's Exit option to stop the node, and detach
with `Ctrl-P` `Ctrl-Q` rather than stopping the container. A `--daemon` mode is
planned.

**No GUI wallet in the image.** Containers have no display, so the Qt wallet is
not included. It is available as a native build from the source repository.

**Single seed peer.** New nodes currently bootstrap from one seed. If it is
unreachable, sync will not start. Additional seeds are planned.

---

## Troubleshooting

**`permission denied ... docker.sock`**
Your user is not in the `docker` group. Run `sudo usermod -aG docker $USER`
then `newgrp docker`, or log out and back in.

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

## What is in the image

Built from `ubuntu:24.04`, roughly 130 MB. Contains the headless node binary
and its runtime libraries — no compiler, no Qt, no GPU drivers. The node runs
as an unprivileged user inside the container, not as root.

Source and build files: [github.com/agreatopportunity/TRU-DOCKER](https://github.com/agreatopportunity/TRU-DOCKER)
