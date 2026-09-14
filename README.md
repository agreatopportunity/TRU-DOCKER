# TRU Blockchain — PUBLIC Docker README

This guide is for someone who wants to run a TRU node using Docker without
building the source code. It is written to be copy/paste friendly.

> **This guide runs a normal public peer node.** You do not need an oracle
> address or token-evolution setup just to run a node and sync the blockchain.

## Read this before you start

TRU v2.0 wallets are **encrypted**. You will choose a passphrase during setup
and type it every time the node starts.

- Choose that passphrase now and store it in a password manager.
- **There is no recovery if you lose it.** Not by us, not by anyone.
- Your wallet is three files on your own computer, plus that passphrase.
  Nothing else recovers your coins — not the chain data, not the container,
  not this repository.

Because the node asks for a passphrase interactively, it **cannot restart by
itself** after a reboot. That is deliberate. You start it by hand.

---

# 1. What you need

- A Linux computer or server
- Docker installed
- Internet access
- About 10 minutes for the first setup
- For the GPU image: an NVIDIA GPU, driver, and NVIDIA Container Toolkit

Check Docker:

```bash
docker --version
```

For an NVIDIA GPU node, also check:

```bash
nvidia-smi
```

---

# 2. Choose CPU or NVIDIA GPU

Pick one and set it for the rest of this guide.

**CPU node:**

```bash
TRU_IMAGE="ghcr.io/agreatopportunity/tru-node:v2.0.7"
```

**NVIDIA GPU node:**

```bash
TRU_IMAGE="ghcr.io/agreatopportunity/tru-node-gpu:v2.0.7"
```

Use a numbered version rather than `latest`. A pinned tag keeps you on that
exact release until you choose to upgrade, so an image change can never
surprise a running node.

Download it:

```bash
docker pull "$TRU_IMAGE"
```

---

# 3. Make the TRU folders

```bash
mkdir -p ~/tru/wallet
chmod 700 ~/tru/wallet
cd ~/tru
```

Everything in this guide assumes:

```text
~/tru          config and backups
~/tru/wallet   your encrypted wallet — the only irreplaceable part
```

---

# 4. Create `tru.conf`

```bash
cat > ~/tru/tru.conf << 'EOF'
[network]
rpcbind=127.0.0.1
rpcAllowRemote=0
rpcport=21832
p2pPort=21833
listen=1
addnode=137.184.68.43:21833
automaticReorg=1

[default]
node.ip=127.0.0.1
node.port=21832

[chain]
chainName=TRUMain
networkType=mainnet
EOF
```

Check it:

```bash
cat ~/tru/tru.conf
```

### What these settings mean

| Setting | Meaning |
| --- | --- |
| `rpcbind=127.0.0.1` | Lets RPC listen **inside** the container. The `docker run` command below publishes it only to your own machine. |
| `rpcport=21832` | TRU JSON-RPC port. |
| `p2pPort=21833` | TRU peer-to-peer port. |
| `listen=1` | Accept incoming peer connections. |
| `addnode=137.184.68.43:21833` | A public seed node to contact at startup. Without a peer, a new node sits at genesis forever. |
| `automaticReorg=1` | Lets the node follow the heaviest valid chain. Leave this on. |

### Optional — only for publicly reachable nodes

Skip both of these if you are on a home connection behind NAT. Outbound sync
works either way.

```bash
echo "externalip=YOUR.PUBLIC.IP.HERE" >> ~/tru/tru.conf
sudo ufw allow 21833/tcp
```

---

# 5. Create your wallet — once, ever

**Skip this step entirely if `~/tru/wallet/` already contains your wallet
files.** Running it again creates a *different* wallet, and the old one
becomes unreachable.

```bash
docker rm -f tru-bootstrap 2>/dev/null || true

docker run -it \
  --name tru-bootstrap \
  -w /app \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  "$TRU_IMAGE" \
  --conf /app/tru.conf \
  --bootstrap-encrypted-wallet
```

Enter your chosen passphrase when prompted. The container writes three files
and exits.

Copy them out to your computer:

```bash
docker cp tru-bootstrap:/app/wallet_seed.dat.enc "$HOME/tru/wallet/"
docker cp tru-bootstrap:/app/tru.dat.enc        "$HOME/tru/wallet/"
docker cp tru-bootstrap:/app/tru.dat.public     "$HOME/tru/wallet/"
```

Verify you got all three and that no unencrypted copy leaked out:

```bash
ls -la ~/tru/wallet/

test ! -e ~/tru/wallet/wallet_seed.dat && echo "PLAINTEXT_SEED_ABSENT=PASS"
test ! -e ~/tru/wallet/tru.dat         && echo "PLAINTEXT_WALLET_ABSENT=PASS"
```

You should see exactly these three files:

```text
wallet_seed.dat.enc
tru.dat.enc
tru.dat.public
```

Read your public address:

```bash
python3 -c "import json,os; \
j=json.load(open(os.path.expanduser('~/tru/wallet/tru.dat.public'))); \
print('PUBLIC_WALLET_ADDRESS =', j['addresses'][j['currentIndex']])"
```

Clean up the bootstrap container:

```bash
docker rm tru-bootstrap
```

## Back up your wallet now

Do this before you start the node, not later.

```bash
tar czf ~/tru-wallet-backup-$(date +%F).tgz -C ~/tru wallet
ls -la ~/tru-wallet-backup-*.tgz
```

**Copy that file to another machine or offline storage.** A backup that only
exists on the same computer is not a backup.

---

# 6. Start the node

## CPU

```bash
docker rm -f tru 2>/dev/null || true

docker run -it \
  --name tru \
  -w /app \
  -p 21833:21833 \
  -p 127.0.0.1:21832:21832 \
  -v tru-data:/app/data \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  --mount "type=bind,src=$HOME/tru/wallet/wallet_seed.dat.enc,dst=/app/wallet_seed.dat.enc" \
  --mount "type=bind,src=$HOME/tru/wallet/tru.dat.enc,dst=/app/tru.dat.enc" \
  --mount "type=bind,src=$HOME/tru/wallet/tru.dat.public,dst=/app/tru.dat.public" \
  "$TRU_IMAGE" \
  --conf /app/tru.conf \
  --datadir /app/data/utxo \
  --cli
```

## NVIDIA GPU

Identical, with `--gpus all` added:

```bash
docker rm -f tru 2>/dev/null || true

docker run -it \
  --gpus all \
  --name tru \
  -w /app \
  -p 21833:21833 \
  -p 127.0.0.1:21832:21832 \
  -v tru-data:/app/data \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  --mount "type=bind,src=$HOME/tru/wallet/wallet_seed.dat.enc,dst=/app/wallet_seed.dat.enc" \
  --mount "type=bind,src=$HOME/tru/wallet/tru.dat.enc,dst=/app/tru.dat.enc" \
  --mount "type=bind,src=$HOME/tru/wallet/tru.dat.public,dst=/app/tru.dat.public" \
  "$TRU_IMAGE" \
  --conf /app/tru.conf \
  --datadir /app/data/utxo \
  --cli
```

If Docker rejects `--gpus all`, your NVIDIA Container Toolkit is not
installed or configured correctly.

Enter your passphrase when prompted.

## Optional — run the block explorer too

Add one port mapping and two flags:

```text
  -p 127.0.0.1:8001:8001 \
  ...
  --enable-explorer \
  --explorer-port 8001
```

Then browse to `http://127.0.0.1:8001`. Like RPC, the explorer is published
to your own machine only.

---

# 7. VERY IMPORTANT — leaving the window without stopping TRU

While attached to the TRU console:

**Do not press `Ctrl+C` just to close the terminal. That stops the node.**

To disconnect and leave TRU running, press:

```text
Ctrl+P
```

then:

```text
Ctrl+Q
```

You return to your normal prompt. You can now close SSH or the terminal.
TRU keeps running.

Reattach later:

```bash
docker attach tru
```

---

# 8. Check that it is working

```bash
docker ps
docker logs --tail 50 tru
```

The node ships with a command-line client. Use it without attaching:

```bash
docker exec tru /app/tru-cli getinfo
docker exec tru /app/tru-cli getconnectioncount
docker exec tru /app/tru-cli getblockcount
docker exec tru /app/tru-cli getchaininfo
docker exec tru /app/tru-cli getpeerinfo
```

Within a minute or two you should see at least one peer and a block height
that climbs. If the peer count stays at 0, confirm outbound 21833 is not
blocked and that `addnode` is in your config.

Useful log filter:

```bash
docker logs tru 2>&1 | \
  grep -Ei 'peer|connected|sync|height|listening|accepted|block' | tail -100
```

Follow the log live (`Ctrl+C` stops *following*, not the node):

```bash
docker logs -f tru
```

---

# 9. Start, stop, restart

## Start a stopped container

The node needs your passphrase, so start it attached:

```bash
docker start -ai tru
```

Then detach with `Ctrl+P`, `Ctrl+Q`.

## Stop safely

Preferred — attach and use TRU's own **Exit** menu option:

```bash
docker attach tru
```

That lets TRU close its database cleanly. If you cannot reach the menu:

```bash
docker stop -t 30 tru
```

Last resort only:

```bash
docker kill tru
```

`docker kill` gives no chance for a clean shutdown and can leave a stale
database lock that must be cleared before the next start.

## Restart

```bash
docker stop -t 30 tru
docker start -ai tru
```

## Why there is no automatic restart

The encrypted wallet must be unlocked interactively. If you add
`--restart=always`, after a reboot Docker starts the container, TRU prompts
for a passphrase nobody types, and it waits forever. `docker ps` reports
**Up** while the node serves nothing. Start it by hand instead.

---

# 10. Your wallet and your chain are two different things

```text
~/tru/wallet/          your keys        IRREPLACEABLE
tru-data (volume)      the blockchain   re-downloadable
```

Because the wallet lives in `~/tru/wallet/` on your own machine and is only
*mounted* into the container, `docker rm tru` **cannot** delete it. That is
the main reason this guide mounts it from the host.

The chain volume can always be resynced from the network. Your wallet cannot.

## Backing up

```bash
tar czf ~/tru-wallet-backup-$(date +%F).tgz -C ~/tru wallet
```

Copy the result off the machine. Do this after first creating the wallet and
any time you are about to change something significant.

## Restoring

Put the three files back and start the node normally:

```bash
mkdir -p ~/tru/wallet && chmod 700 ~/tru/wallet
tar xzf ~/tru-wallet-backup-YYYY-MM-DD.tgz -C ~/tru
ls -la ~/tru/wallet/
```

There is no copying into the container and no separate restore procedure.
The files plus your passphrase are the whole wallet.

> **Never upload wallet files, seed files, private keys, or `.env` files to
> GitHub or anywhere public.**

---

# 11. Recreating the container while keeping everything

Safe, because both the wallet and chain live outside the container:

```bash
docker stop -t 30 tru
docker rm tru
# then re-run the exact same docker run command from section 6
```

Your wallet and blockchain are untouched.

---

# 12. Updating to a newer image

```bash
docker pull ghcr.io/agreatopportunity/tru-node:vX.Y.Z
```

Check which image the current container uses:

```bash
docker inspect tru --format='{{.Config.Image}}'
```

Then stop, remove, and re-run section 6 with the new tag. Do **not** run the
bootstrap step again — that would create a new wallet.

---

# 13. Ports and firewall

```text
21833   P2P        may be public
21832   JSON-RPC   127.0.0.1 only
8001    Explorer   127.0.0.1 only, when enabled
```

Check what is listening on the host:

```bash
sudo ss -ltnp | grep -E '21832|21833|8001'
```

Test the public seed:

```bash
nc -vz 137.184.68.43 21833
```

`succeeded` means reachable. `Connection refused` means that node is not
accepting connections right now; yours will keep retrying.

TRU makes **outbound** connections without port forwarding, so a home user
can usually sync without touching the router. Port forwarding and
`externalip` are only needed if you want others to connect *to* you.

If UFW is enabled and you want inbound peers:

```bash
sudo ufw allow 21833/tcp
sudo ufw status
```

## Never publish RPC

The commands in this guide map RPC to `127.0.0.1:21832` on purpose.

**The RPC endpoint has no authentication.** Anything that can reach it can
use your wallet. Never map it to `0.0.0.0` or forward 21832 through a router.

---

# 14. Mining from the same host

Miners talk to your node over RPC on port **21832**. They do not need the
chain database.

CPU:

```bash
./tru_miner_cpu \
  --node-ip 127.0.0.1 \
  --node-port 21832 \
  --mineraddr YOUR_TRU_ADDRESS \
  --threads 4
```

GPU:

```bash
./tru_miner \
  --node-ip 127.0.0.1 \
  --node-port 21832 \
  --mineraddr YOUR_TRU_ADDRESS
```

Replace `YOUR_TRU_ADDRESS` with the address printed in section 5. **If you
leave the default placeholder address in place, every reward you mine goes
somewhere you cannot spend it.**

---

# 15. Quick command cheat sheet

```bash
docker ps                                   # is TRU running?
docker ps -a                                # include stopped
docker attach tru                           # attach to console
# Ctrl+P then Ctrl+Q                        # detach, leave running
docker start -ai tru                        # start and attach
docker stop -t 30 tru                       # graceful stop
docker logs --tail 100 tru                  # recent logs
docker logs -f tru                          # follow logs
docker exec tru /app/tru-cli getinfo        # node status
docker inspect tru --format='{{.Config.Image}}'
docker volume ls | grep tru
sudo ss -ltnp | grep -E '21832|21833'
nc -vz 137.184.68.43 21833
```

---

# 16. Common problems

### `Conflict. The container name "/tru" is already in use`

It already exists. Start it instead:

```bash
docker ps -a | grep tru
docker start -ai tru
```

### `port is already allocated`

Something else holds 21832 or 21833:

```bash
sudo ss -ltnp | grep -E '21832|21833'
docker ps
```

### Docker created directories instead of using my wallet files

Bind mounts create an empty **directory** when the source path does not
exist. If `ls -la ~/tru/wallet/` shows directories rather than three files,
remove the container, fix the paths, and start again. A node that starts
without its wallet files will create a throwaway wallet.

### The node shows `Up` but nothing works

It is almost certainly waiting at the passphrase prompt. Attach and look:

```bash
docker attach tru
```

### `Connection refused` to the seed

That node is not accepting connections at that moment. Yours retries
automatically. Check again with `nc -vz 137.184.68.43 21833`.

### Docker cannot use `--gpus all`

```bash
nvidia-smi
```

If the GPU works on the host but not in Docker, install and configure the
NVIDIA Container Toolkit.

### Node stops when I close my terminal

You pressed `Ctrl+C` instead of detaching. Use `Ctrl+P` then `Ctrl+Q`.

---

# 17. Security rules

1. Never expose RPC port `21832` to the Internet. It has no authentication.
2. Never upload `tru.dat.enc`, `wallet_seed.dat.enc`, or `tru.dat.public`
   anywhere public.
3. Never upload private keys, WIFs, or `.env` files.
4. Keep `~/tru/wallet/` at mode `700`.
5. Back up `~/tru/wallet/` **off this machine**, and store the passphrase
   separately.
6. Do not delete `tru-data` unless you intend to resync from scratch.
7. Pin a version tag rather than `latest` on anything you care about.

---

# 18. Clean uninstall

Remove the container, keep the chain and wallet:

```bash
docker stop -t 30 tru 2>/dev/null || true
docker rm tru
```

Remove the downloaded image:

```bash
docker image rm ghcr.io/agreatopportunity/tru-node:v2.0.7
```

### Deleting chain data

Resyncable, but it takes time:

```bash
docker volume rm tru-data
```

### Deleting your wallet

**This is permanent and unrecoverable.** Only do this if the wallet is
retired and backed up elsewhere:

```bash
rm -rf ~/tru/wallet
```

---

# 19. The three things to remember

**1. Leave the console without stopping TRU**

```text
Ctrl+P  then  Ctrl+Q
```

**2. Your wallet is three files plus a passphrase**

```text
~/tru/wallet/wallet_seed.dat.enc
~/tru/wallet/tru.dat.enc
~/tru/wallet/tru.dat.public
```

Back them up off this machine. Lose the passphrase and they are worthless.

**3. Never expose RPC 21832 publicly**

P2P `21833` may be public. RPC `21832` must not be.

---

# Quick start for experienced Docker users

```bash
TRU_IMAGE="ghcr.io/agreatopportunity/tru-node:v2.0.7"
mkdir -p ~/tru/wallet && chmod 700 ~/tru/wallet

cat > ~/tru/tru.conf << 'EOF'
[network]
rpcbind=127.0.0.1
rpcport=21832
p2pPort=21833
listen=1
rpcMaxConnections=32
addnode=137.184.68.43:21833
automaticReorg=1

[default]
node.ip=127.0.0.1
node.port=21832

[chain]
chainName=TRUMain
networkType=mainnet
EOF

docker pull "$TRU_IMAGE"

# once, ever — creates the encrypted wallet
docker run -it --name tru-bootstrap -w /app \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  "$TRU_IMAGE" --conf /app/tru.conf --bootstrap-encrypted-wallet

for f in wallet_seed.dat.enc tru.dat.enc tru.dat.public; do
  docker cp "tru-bootstrap:/app/$f" "$HOME/tru/wallet/$f"
done
docker rm tru-bootstrap
tar czf ~/tru-wallet-backup-$(date +%F).tgz -C ~/tru wallet   # copy this off-box

# every start
docker run -it --name tru -w /app \
  -p 21833:21833 -p 127.0.0.1:21832:21832 \
  -v tru-data:/app/data \
  --mount "type=bind,src=$HOME/tru/tru.conf,dst=/app/tru.conf,readonly" \
  --mount "type=bind,src=$HOME/tru/wallet/wallet_seed.dat.enc,dst=/app/wallet_seed.dat.enc" \
  --mount "type=bind,src=$HOME/tru/wallet/tru.dat.enc,dst=/app/tru.dat.enc" \
  --mount "type=bind,src=$HOME/tru/wallet/tru.dat.public,dst=/app/tru.dat.public" \
  "$TRU_IMAGE" --conf /app/tru.conf --datadir /app/data/utxo --cli
```

Detach with `Ctrl+P`, `Ctrl+Q`. Reattach with `docker attach tru`.

---

**TRU Blockchain — PUBLIC Docker README**
