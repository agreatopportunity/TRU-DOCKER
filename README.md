# TRU Blockchain — PUBLIC Docker README

This guide is for someone who wants to run a TRU node using Docker without building the source code.

It is written to be copy/paste friendly.

> **Important:** This guide runs a normal public peer node. You do **not** need an oracle address or token-evolution setup just to run a node and sync the blockchain.

---

# 1. What you need

You need:

- A Linux computer or server
- Docker installed
- Internet access
- About 5–10 minutes for the first setup
- For the GPU image: an NVIDIA GPU, NVIDIA driver, and NVIDIA Container Toolkit

Check Docker:

```bash
docker --version
```

If that prints a Docker version, continue.

For an NVIDIA GPU node, also check:

```bash
nvidia-smi
```

---

# 2. Choose CPU or NVIDIA GPU

## CPU node

Use:

```bash
CPU_IMAGE="ghcr.io/agreatopportunity/tru-node:latest"
```

## NVIDIA GPU node

Use:

```bash
GPU_IMAGE="ghcr.io/agreatopportunity/tru-node-gpu:latest"
```

A numbered release can be used instead of `latest` when one is published.

Example format:

```text
ghcr.io/agreatopportunity/tru-node:vX.Y.Z
```

Using a numbered version keeps you on that exact release until you choose to upgrade.

---

# 3. Make the TRU folder

Copy/paste:

```bash
mkdir -p ~/tru
cd ~/tru
```

Everything in this guide assumes this folder is:

```text
~/tru
```

---

# 4. Create `tru.conf`

Copy/paste this entire block:

```bash
cat > ~/tru/tru.conf << 'EOF'
[network]
rpcbind=0.0.0.0
rpcport=8332
p2pPort=8333
listen=1
rpcMaxConnections=32
addnode=137.184.68.43:8333

[default]
node.ip=127.0.0.1
node.port=8332

[chain]
chainName=TRUMain
networkType=mainnet
EOF
```

Check it:

```bash
cat ~/tru/tru.conf
```

### What these important settings mean

```ini
rpcbind=0.0.0.0
```

Allows RPC to listen inside the Docker container.

```ini
rpcport=8332
```

TRU RPC port.

```ini
p2pPort=8333
```

TRU peer-to-peer port.

```ini
listen=1
```

Allows the TRU node to listen for peers.

```ini
addnode=137.184.68.43:8333
```

Tells your node which public TRU peer/seed to contact when it starts.

You normally do **not** need to set `externalip` on a home computer.

---

# 5. Download the Docker image

## CPU

```bash
docker pull ghcr.io/agreatopportunity/tru-node:latest
```

## NVIDIA GPU

```bash
docker pull ghcr.io/agreatopportunity/tru-node-gpu:latest
```

You only need the image you plan to run.

---

# 6. First start — CPU node

Copy/paste:

```bash
docker run -it \
  --name tru \
  -w /app \
  -p 8333:8333 \
  -p 127.0.0.1:8332:8332 \
  -e TRU_ALLOW_NEW_SEED=1 \
  -e TRU_WALLET_SEED_PATH=/app/data/seed.dat \
  -v tru-data:/app/data \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  ghcr.io/agreatopportunity/tru-node:latest \
  --conf /app/tru.conf \
  --datadir /app/data/utxo \
  --cli
```

---

# 7. First start — NVIDIA GPU node

Copy/paste:

```bash
docker run -it \
  --gpus all \
  --name tru \
  -w /app \
  -p 8333:8333 \
  -p 127.0.0.1:8332:8332 \
  -e TRU_ALLOW_NEW_SEED=1 \
  -e TRU_WALLET_SEED_PATH=/app/data/seed.dat \
  -v tru-data:/app/data \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  ghcr.io/agreatopportunity/tru-node-gpu:latest \
  --conf /app/tru.conf \
  --datadir /app/data/utxo \
  --cli
```

If Docker says it cannot use `--gpus all`, your NVIDIA Container Toolkit is not installed/configured correctly.

---

# 8. VERY IMPORTANT — how to leave the window without stopping TRU

When you are attached to the TRU Docker console:

**Do not press `Ctrl+C` just because you want to close the terminal.**

To disconnect from the Docker console while leaving TRU running:

1. Press:

```text
Ctrl+P
```

2. Then press:

```text
Ctrl+Q
```

You should return to your normal Linux prompt.

Now you can close SSH or close the terminal window.

TRU keeps running.

---

# 9. Attach to TRU again

To go back into the running TRU console:

```bash
docker attach tru
```

To leave it again without stopping TRU:

```text
Ctrl+P
Ctrl+Q
```

---

# 10. Check whether TRU is running

```bash
docker ps
```

You should see:

```text
tru
```

To also show stopped containers:

```bash
docker ps -a
```

---

# 11. View logs without attaching

Last 100 log lines:

```bash
docker logs --tail 100 tru
```

Follow the log live:

```bash
docker logs -f tru
```

Press:

```text
Ctrl+C
```

to stop following the **log**.

That does **not** stop the TRU container when you are using `docker logs -f`.

Useful network/sync messages:

```bash
docker logs tru 2>&1 | \
grep -Ei 'peer|connected|sync|height|listening|accepted|block' | tail -100
```

---

# 12. Start a stopped TRU container

Start it in the background:

```bash
docker start tru
```

Then attach:

```bash
docker attach tru
```

Or start it and attach immediately:

```bash
docker start -ai tru
```

---

# 13. Stop TRU safely

The preferred method is:

1. Attach:

```bash
docker attach tru
```

2. Use TRU's normal **Exit** option in the CLI/menu.

This gives TRU time to save its wallet, peers, blockchain state, and close the database cleanly.

If you cannot use the menu, try:

```bash
docker stop -t 30 tru
```

Use this only as a last resort:

```bash
docker kill tru
```

`docker kill` immediately kills the process and does not allow a clean shutdown.

---

# 14. Restart TRU

Normal restart:

```bash
docker stop -t 30 tru
docker start tru
```

Then:

```bash
docker attach tru
```

If TRU has a normal Exit menu available, using that before restarting is preferred.

---

# 15. Check whether port 8333 is listening

On the host:

```bash
sudo ss -ltnp | grep 8333
```

Check the public seed:

```bash
nc -vz 137.184.68.43 8333
```

If you see:

```text
succeeded
```

the seed is reachable.

If you see:

```text
Connection refused
```

the remote node is not currently accepting connections on that port.

---

# 16. Home router / firewall information

TRU can make **outbound** connections without port forwarding.

So a normal home user can usually sync without changing the router.

For inbound peers, TCP port:

```text
8333
```

must be reachable.

If Ubuntu UFW is enabled:

```bash
sudo ufw allow 8333/tcp
```

Check UFW:

```bash
sudo ufw status
```

You do **not** need to expose RPC port `8332` to the Internet.

The Docker command in this guide deliberately publishes RPC only on:

```text
127.0.0.1:8332
```

That means RPC can be used by software on the same machine, but is not directly exposed to the public Internet.

---

# 17. Important wallet information

TRU's main wallet file is:

```text
/app/tru.dat
```

inside the container.

The blockchain data volume is:

```text
tru-data
```

mounted at:

```text
/app/data
```

These are **not the same thing**.

## Important rule

Stopping and starting the same container keeps `tru.dat`.

Removing the container can delete the wallet that exists in the container filesystem.

Therefore:

> **BACK UP THE WALLET BEFORE RUNNING `docker rm`.**

---

# 18. Back up the wallet

Create a backup folder:

```bash
mkdir -p ~/tru/backups
```

Back up the main wallet:

```bash
STAMP=$(date +%F-%H%M%S)
mkdir -p "$HOME/tru/backups/$STAMP"

docker cp \
  tru:/app/tru.dat \
  "$HOME/tru/backups/$STAMP/tru.dat"
```

TRU may also have additional wallet/seed state. Back up these if they exist:

```bash
docker cp tru:/app/wallet_seed.dat \
  "$HOME/tru/backups/$STAMP/wallet_seed.dat" 2>/dev/null || true

docker cp tru:/app/wallet_index.dat \
  "$HOME/tru/backups/$STAMP/wallet_index.dat" 2>/dev/null || true

docker cp tru:/app/data/seed.dat \
  "$HOME/tru/backups/$STAMP/seed.dat" 2>/dev/null || true
```

Also save the config:

```bash
cp ~/tru/tru.conf \
  "$HOME/tru/backups/$STAMP/tru.conf"
```

List the backup:

```bash
ls -lah "$HOME/tru/backups/$STAMP"
```

Keep wallet backups private.

**Never upload wallet files, seed files, private keys, or `.env` files to GitHub or another public location.**

---

# 19. Removing the container

First make a wallet backup.

Then:

```bash
docker stop -t 30 tru 2>/dev/null || true
docker rm tru
```

This removes the container.

It does **not** remove the named blockchain volume:

```text
tru-data
```

---

# 20. DO NOT casually delete the blockchain volume

Show TRU volumes:

```bash
docker volume ls | grep tru
```

The public node volume is:

```text
tru-data
```

Deleting it deletes the Docker blockchain database:

```bash
docker volume rm tru-data
```

Do **not** run that command unless you intentionally want a completely fresh chain database.

Deleting a container and deleting a volume are two different things.

---

# 21. Re-create the container while keeping the blockchain

If the container was removed but the volume still exists, use the same run command again.

CPU example:

```bash
docker run -it \
  --name tru \
  -w /app \
  -p 8333:8333 \
  -p 127.0.0.1:8332:8332 \
  -v tru-data:/app/data \
  --mount type=bind,src="$HOME/tru/tru.conf",dst=/app/tru.conf,readonly \
  ghcr.io/agreatopportunity/tru-node:latest \
  --conf /app/tru.conf \
  --datadir /app/data/utxo \
  --cli
```

**Important:** a newly created container may create a new wallet. Restore your backed-up wallet/seed state before using that replacement container for funds.

For a careful wallet restore, stop the new container first:

```bash
docker stop -t 30 tru
```

Then copy your backed-up files into it:

```bash
docker cp ~/tru/backups/YOUR_BACKUP_FOLDER/tru.dat \
  tru:/app/tru.dat
```

If your backup contains these files, restore them too:

```bash
docker cp ~/tru/backups/YOUR_BACKUP_FOLDER/wallet_seed.dat \
  tru:/app/wallet_seed.dat
```

```bash
docker cp ~/tru/backups/YOUR_BACKUP_FOLDER/wallet_index.dat \
  tru:/app/wallet_index.dat
```

```bash
docker cp ~/tru/backups/YOUR_BACKUP_FOLDER/seed.dat \
  tru:/app/data/seed.dat
```

Then:

```bash
docker start -ai tru
```

---

# 22. Update to a newer TRU Docker image

First back up the wallet as shown above.

Then pull the new image.

CPU:

```bash
docker pull ghcr.io/agreatopportunity/tru-node:latest
```

GPU:

```bash
docker pull ghcr.io/agreatopportunity/tru-node-gpu:latest
```

See which image your current container uses:

```bash
docker inspect tru \
  --format='{{.Config.Image}}'
```

Because changing the image requires creating a new container, always back up the wallet/seed files before upgrading.

---

# 23. Check chain information

Attach:

```bash
docker attach tru
```

Use the TRU CLI/menu option for chain information.

Useful items to check:

- Current block height
- Best block hash
- Connected peers
- Sync status

When comparing two TRU nodes, the best block hash at the same height should match.

Detach afterward:

```text
Ctrl+P
Ctrl+Q
```

---

# 24. Check peers

You can use the TRU CLI/menu peer list.

Or check logs:

```bash
docker logs tru 2>&1 | \
grep -Ei 'peer|connected|handshake|addnode' | tail -100
```

---

# 25. CPU mining from the same host

If you also downloaded the standalone TRU CPU miner, it connects to the local node using:

```text
127.0.0.1:8332
```

Example:

```bash
./tru_miner_cpu \
  --node-ip 127.0.0.1 \
  --node-port 8332 \
  --mineraddr YOUR_TRU_ADDRESS \
  --threads 4
```

Replace:

```text
YOUR_TRU_ADDRESS
```

with your own TRU address.

---

# 26. GPU mining from the same host

Standalone GPU miner example:

```bash
./tru_miner \
  --node-ip 127.0.0.1 \
  --node-port 8332 \
  --mineraddr YOUR_TRU_ADDRESS
```

The standalone GPU miner does not require the CPU miner's `--threads` option.

---

# 27. Quick command cheat sheet

## Is TRU running?

```bash
docker ps
```

## Show stopped containers too

```bash
docker ps -a
```

## Attach

```bash
docker attach tru
```

## Detach without stopping

```text
Ctrl+P
Ctrl+Q
```

## Start

```bash
docker start tru
```

## Start and attach

```bash
docker start -ai tru
```

## Stop

```bash
docker stop -t 30 tru
```

## Last 100 logs

```bash
docker logs --tail 100 tru
```

## Follow logs

```bash
docker logs -f tru
```

## Inspect image version

```bash
docker inspect tru --format='{{.Config.Image}}'
```

## Show TRU Docker volume

```bash
docker volume ls | grep tru
```

## Check local P2P port

```bash
sudo ss -ltnp | grep 8333
```

## Test seed

```bash
nc -vz 137.184.68.43 8333
```

---

# 28. Common problems

## `Conflict. The container name "/tru" is already in use`

The container already exists.

Check:

```bash
docker ps -a | grep tru
```

Start it:

```bash
docker start -ai tru
```

Do **not** remove it unless you have backed up the wallet.

---

## `port is already allocated` or `Address already in use`

Something else is already using port 8333 or 8332.

Check:

```bash
sudo ss -ltnp | grep -E '8332|8333'
```

Also check Docker:

```bash
docker ps
```

---

## `Connection refused` to `137.184.68.43:8333`

The seed is not accepting a connection at that moment.

Your node may retry automatically.

Check again:

```bash
nc -vz 137.184.68.43 8333
```

---

## GPU error about `--gpus all`

Check:

```bash
nvidia-smi
```

If NVIDIA works on the host but Docker cannot use the GPU, install/configure the NVIDIA Container Toolkit.

---

## Node stops when I close my terminal

When attached to Docker, detach properly first:

```text
Ctrl+P
Ctrl+Q
```

Then close the terminal.

---

# 29. Security rules

1. Never expose RPC port `8332` directly to the public Internet.
2. Never upload `tru.dat` publicly.
3. Never upload wallet seed files publicly.
4. Never upload private keys.
5. Never upload `.env` files containing API keys.
6. Back up the wallet before removing or replacing a container.
7. Do not delete `tru-data` unless you intentionally want to erase the Docker blockchain database.

---

# 30. Clean uninstall

If you want to remove the container but keep blockchain data:

```bash
docker stop -t 30 tru 2>/dev/null || true
docker rm tru
```

The named volume remains.

To also remove the downloaded CPU image:

```bash
docker image rm ghcr.io/agreatopportunity/tru-node:latest
```

GPU:

```bash
docker image rm ghcr.io/agreatopportunity/tru-node-gpu:latest
```

### Permanent chain-data deletion

Only if you truly want to erase the Docker blockchain database:

```bash
docker volume rm tru-data
```

This does **not** magically back up your wallet. Back up wallet/seed files first.

---

# 31. The three things to remember

If you remember nothing else, remember these:

### 1. Leave the console without stopping TRU

```text
Ctrl+P
Ctrl+Q
```

### 2. Back up your wallet before removing a container

```text
/app/tru.dat
```

### 3. Never expose RPC 8332 publicly

The Docker commands in this guide expose RPC only to:

```text
127.0.0.1:8332
```

P2P uses:

```text
8333
```

---

# TRU PUBLIC Docker Quick Start

For an experienced Docker user, the short version is:

```bash
mkdir -p ~/tru

cat > ~/tru/tru.conf << 'EOF'
[network]
rpcbind=0.0.0.0
rpcport=8332
p2pPort=8333
listen=1
rpcMaxConnections=32
addnode=137.184.68.43:8333

[default]
node.ip=127.0.0.1
node.port=8332

[chain]
chainName=TRUMain
networkType=mainnet
EOF

docker pull ghcr.io/agreatopportunity/tru-node-gpu:latest

docker run -it \
  --gpus all \
  --name tru \
  -w /app \
  -p 8333:8333 \
  -p 127.0.0.1:8332:8332 \
  -v tru-data:/app/data \
  --mount type=bind,src="$HOME/tru/tru.conf",dst=/app/tru.conf,readonly \
  ghcr.io/agreatopportunity/tru-node-gpu:latest \
  --conf /app/tru.conf \
  --datadir /app/data/utxo \
  --cli
```

Detach without stopping:

```text
Ctrl+P
Ctrl+Q
```

Reattach:

```bash
docker attach tru
```

Check logs:

```bash
docker logs --tail 100 tru
```

---

**TRU Blockchain — PUBLIC Docker README**
