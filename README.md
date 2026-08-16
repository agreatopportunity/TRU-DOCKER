# TRU Blockchain — Docker

Run a TRU node without installing a compiler, hunting down four
from-source libraries, or fighting a protobuf version mismatch. The image
carries its own dependencies, so it behaves the same on Ubuntu, Debian,
Fedora, macOS, or Windows/WSL2.

Three images are provided:

| Image | What it is | Needs a GPU? | Needs a terminal? |
|---|---|---|---|
| `tru-node` | Headless node — syncs blocks, serves peers | No | Only for `--cli` |
| `tru-miner-cpu` | CPU miner | No | Yes |
| `tru-miner-gpu` | OpenCL GPU miner | Yes (NVIDIA) | Yes |

Most people want **`tru-node`**. Start there.

---

## Quick start

```bash
git clone <your-repo-url> tru && cd tru

# 1. Create your config (see "Configuration" below)
cp tru.conf.example tru.conf

# 2. Build
docker build -t tru-node:latest .

# 3. Run
docker run -d --name tru-node \
    -p 8333:8333 \
    -v tru-data:/app/data \
    -v "$(pwd)/tru.conf:/app/tru.conf:ro" \
    tru-node:latest --cli
```

Watch it come up:

```bash
docker logs -f tru-node
```

You are looking for the P2P layer binding to 8333 and the sync thread
starting. Stop following with `Ctrl-C` — that leaves the container running.

---

## Configuration

`tru.conf` is mounted read-only into the container at `/app/tru.conf`. If you
do not mount one, the image seeds a default and prints a notice.

A working peer configuration:

```ini
[network]
# Bind for the JSON-RPC server. See "RPC inside Docker" before changing.
rpcbind=127.0.0.1
rpcport=8332

# P2P port. This is the one that matters for syncing.
p2pPort=8333
listen=1
rpcMaxConnections=32

# The address you advertise to other peers. Set this to your machine's
# PUBLIC IP if you are reachable from the internet; omit or leave as your
# LAN IP if you are behind NAT and only making outbound connections.
externalip=203.0.113.10

# Seed peers to connect to on startup. Comma-separated ip:port, NO SPACES.
addnode=137.184.68.43:8333
```

Three things the config parser will not forgive:

- **No spaces after commas** in `addnode`. The line is trimmed as a whole, not
  per entry, so ` 198.51.100.22:8333` keeps its leading space and fails.
- **No inline comments.** `p2pPort=8333 # main` parses the value as
  `8333 # main`. Put comments on their own lines.
- **IP addresses only** in `addnode` and `seeds`, not hostnames. The P2P layer
  does not resolve names.

`seeds=` works identically to `addnode=` and both accumulate into the same
peer list, so you can use either or both.

---

## Running modes

### Interactive menu

The node's `--cli` mode draws a full-screen menu — wallet operations, mining,
tokens, smart contracts, peer management. It reads from stdin, so it needs a
terminal:

```bash
docker run -it --name tru-node \
    -p 8333:8333 \
    -v tru-data:/app/data \
    -v "$(pwd)/tru.conf:/app/tru.conf:ro" \
    tru-node:latest --cli
```

Detach without stopping it: `Ctrl-P` then `Ctrl-Q`. Reattach with
`docker attach tru-node`.

### Background node

> **Current limitation.** The node does not yet have a true daemon mode.
> `--cli` with no terminal attached hits EOF on stdin and will not behave
> correctly. Until `--daemon` exists (see "Adding a --daemon mode"), run
> detached containers with `-it` in the compose file, which allocates a TTY
> the menu can sit on harmlessly.

Once `--daemon` is implemented, the intended usage is:

```bash
docker run -d --name tru-node --restart unless-stopped \
    -p 8333:8333 \
    -v tru-data:/app/data \
    -v "$(pwd)/tru.conf:/app/tru.conf:ro" \
    tru-node:latest --daemon
```

### With the block explorer

```bash
docker run -it --name tru-node \
    -p 8333:8333 -p 127.0.0.1:8332:8332 \
    -v tru-data:/app/data \
    -v "$(pwd)/tru.conf:/app/tru.conf:ro" \
    tru-node:latest --cli --enable-explorer
```

---

## Compose

```bash
docker compose up -d node                    # node only
docker compose --profile miner up -d         # + CPU miner
docker compose --profile gpu   up -d         # + GPU miner
docker compose logs -f node
docker compose down                          # stop, keep data
docker compose down -v                       # stop, DELETE chain data
```

Miner profiles are opt-in so a plain `docker compose up` never starts mining
by surprise.

---

## RPC inside Docker

This trips people up. Inside a container, `127.0.0.1` is the *container's*
loopback, not your machine's. So `rpcbind=127.0.0.1` plus `-p 8332:8332` gives
you a published port that nothing is listening on.

To reach RPC from the host:

1. Set `rpcbind=0.0.0.0` in `tru.conf` — safe here, because the container's
   network namespace is already isolated.
2. Publish to your host's loopback **only**:
   `-p 127.0.0.1:8332:8332`

Then `curl http://127.0.0.1:8332/rpc` works from the host and nothing else can
reach it.

> **The RPC layer has no authentication.** Per `README_API.md`, there is no
> username, password, or token check on any method — including wallet and
> mining operations. Never publish 8332 to `0.0.0.0`, never put it behind a
> public hostname, and never expose it through a tunnel without an
> authenticating proxy in front. Publishing 8333 is fine and expected;
> publishing 8332 is not.

---

## Ports

| Port | Purpose | Publish publicly? |
|---|---|---|
| 8333 | P2P — block and transaction sync | **Yes** — this is how peers reach you |
| 8332 | JSON-RPC — node control, wallet, mining | **No** — loopback only |

Host firewall, if you want inbound peers:

```bash
sudo ufw allow 8333/tcp
```

Do not open 8332.

---

## Being reachable by other peers

Publishing 8333 lets peers connect *if they can route to your machine*. Two
common reasons they cannot:

**Behind NAT.** You need a port forward on your router: external TCP 8333 to
your machine's LAN IP. Then set `externalip` to your public IP.

**Behind CGNAT.** Common on Starlink, cellular, and some cable providers. Your
"public" IP is shared at the carrier level and no port forward will work.
Check your router's WAN address — anything in `100.64.0.0/10` is CGNAT. There
is no fix on your end; run your public node on a VPS instead and let your home
node connect outbound to it.

Outbound connections always work, CGNAT or not. So a node behind CGNAT can
still sync fully — it just cannot accept incoming peers.

---

## Data and persistence

Chain data, the UTXO set, wallet files, and peer lists live in `/app/data`,
backed by a named Docker volume. It survives `docker rm` and image rebuilds.

```bash
docker volume ls                             # find it
docker volume inspect tru-data               # where it lives on disk
docker run --rm -v tru-data:/data -v "$(pwd)":/backup ubuntu \
    tar czf /backup/tru-data-backup.tar.gz /data    # back it up
```

`docker compose down -v` deletes it. So does `docker volume rm tru-data`.
Neither is reversible.

### If the node will not start with a lock error

```
FATAL ERROR: [LevelDBStorage] Unable to open/create database:
IO error: lock data/utxo/LOCK: Resource temporarily unavailable
```

LevelDB permits a single writer. Either another container is using the same
volume, or a previous container was killed and left a stale lock. The
entrypoint clears stale locks automatically on start, so this almost always
means **two containers are sharing one volume** — check with `docker ps` and
give each its own.

---

## GPU mining

The GPU image is the least portable of the three. It needs:

- an NVIDIA GPU
- the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) on the host
- `--gpus all` at run time

```bash
docker build -f Dockerfile.gpu -t tru-miner-gpu:latest .
docker run -it --gpus all --name tru-miner-gpu \
    -v tru-gpu-data:/app/data \
    -v "$(pwd)/tru.conf:/app/tru.conf:ro" \
    tru-miner-gpu:latest
```

Verify the GPU is visible inside the container:

```bash
docker run --rm --gpus all tru-miner-gpu:latest nvidia-smi
```

If `clGetPlatformIDs` finds no platforms, the ICD registration is the usual
culprit — check `/etc/OpenCL/vendors/nvidia.icd` exists in the image and that
`NVIDIA_DRIVER_CAPABILITIES` includes `compute`.

**AMD or Intel GPUs** need a different base image (`rocm/dev-ubuntu-22.04` or
Intel's compute runtime) and `--device /dev/dri --group-add video` instead of
`--gpus`. Not provided here; the `Dockerfile.gpu` is a reasonable starting
point to adapt.

---

## The Qt wallet GUI

**Not in these images, by design.**

A container has no display. Running a Qt GUI from one means mounting the X11
socket and forwarding `DISPLAY` — workable on Linux, awkward on macOS (needs
XQuartz), and painful on Windows. For a wallet that users are meant to install
and open, that is the wrong distribution channel.

The GUI wallet is shipped as a **native build** instead. Build it directly:

```bash
cmake -B build -DBUILD_WITH_QT=ON -DUSE_OPENCL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)" --target tru_advanced
./build/bin/tru_advanced --gui
```

If you want the GUI in Docker anyway, on Linux:

```bash
xhost +local:docker
docker run -it \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v tru-data:/app/data \
    tru-gui:latest --gui
```

That requires an image built with `-DBUILD_WITH_QT=ON` and the Qt5 runtime
libraries installed in the runtime stage — roughly 300 MB of extra image for a
window. Not recommended for general distribution.

---

## The keccak library

Three of the four non-repo dependencies build from source in the Dockerfile:
`crc32c`, `ethash`, and `libwally-core`. The fourth, **keccak**, does not — the
upstream source was not identified on the build host, only the compiled
`libkeccak.a`.

The archive is vendored in at `docker/vendor/libkeccak.a` and copied into the
image. To populate it before your first build:

```bash
mkdir -p docker/vendor/keccak-include
cp /usr/local/lib/libkeccak.a docker/vendor/

# Find and copy the headers the build needs
grep -rn "keccak" src/*.h src/*.cpp | grep include
cp -r /usr/local/include/<keccak-headers> docker/vendor/keccak-include/
```

This works, but it is the one part of the build that is not reproducible from
source. If you identify the upstream project, replace the `COPY` in the
Dockerfile with a proper `git clone` + build block like the other three, and
delete the vendor directory. Everything else in this image builds from
scratch.

---

## Why protobuf is regenerated in the image

The Dockerfile runs `protoc --cpp_out=src -I src src/message.proto` during the
build rather than using committed `.pb.h` / `.pb.cc` files, and `.dockerignore`
excludes them from the build context entirely.

This is deliberate. Generated protobuf code contains a version guard that
fails the build if the generating `protoc` does not match the linked
`libprotobuf`:

```
#error This file was generated by an older version of protoc which is
#error incompatible with your Protocol Buffer headers.
```

Regenerating inside the image guarantees both come from the same Ubuntu
package set. It also means a `protoc` on your `PATH` from conda, homebrew, or
`/usr/local` cannot poison the build.

---

## Building images for distribution

Build once on a capable machine, ship the result. A 512 MB VPS cannot compile
this — `g++` needs 1–2 GB for the larger translation units — but it runs the
finished node comfortably.

**Push to a registry:**

```bash
docker tag tru-node:latest ghcr.io/<user>/tru-node:latest
docker push ghcr.io/<user>/tru-node:latest
```

**Or transfer directly over SSH, no registry needed:**

```bash
docker save tru-node:latest | gzip | \
    ssh user@remote-host 'gunzip | docker load'
```

**Multi-architecture** (x86_64 + ARM, for Raspberry Pi and Apple Silicon):

```bash
docker buildx create --use --name tru-builder
docker buildx build --platform linux/amd64,linux/arm64 \
    -t ghcr.io/<user>/tru-node:latest --push .
```

ARM builds are slow under emulation. A native ARM builder is much faster if
you have one.

---

## Adding a `--daemon` mode

The single change that would most improve this setup. `main.cpp` currently
branches on `guiMode` and `cliMode`; both expect a human. A third branch that
starts P2P, RPC, and sync and then blocks would make the container behave
properly under `docker run -d`, `restart: unless-stopped`, and systemd.

Sketch, alongside the existing `else if (cliMode)` block:

```cpp
} else if (daemonMode) {
    std::atomic<bool> syncRunning{true};
    std::thread syncThread([&chain, &node, &syncRunning]() {
        try {
            chain->syncWithPeers(*node, syncRunning, nullptr);
        } catch (const std::exception& e) {
            Logger::log("[main] ERROR: Sync failed: " + std::string(e.what()));
        }
    });

    Logger::log("[main] Daemon mode: running until signal.");
    while (g_running) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    // reuse the same shutdown sequence as the GUI/CLI paths
    syncRunning = false;
    chain->stop();
    g_rpcServer.stop();
    node->stop();
    if (syncThread.joinable()) syncThread.join();
    chain->saveChainState();
    savePeers(node->getKnownPeers(), dbPath + "/peers.dat");
    Logger::shutdown();
    return 0;
}
```

With a `SIGTERM` handler setting `g_running = false`, `docker stop` would then
shut the node down cleanly instead of killing it after the 10-second timeout —
which is also what leaves stale LevelDB locks behind.

Once that exists: change `CMD` to `["--daemon"]`, and drop `stdin_open` and
`tty` from the compose file.

---

## Troubleshooting

**`Cannot open config file: tru.conf`**
`ConfigReader` opens the file by relative path, so the working directory must
be `/app`. The entrypoint handles this; if you override `--entrypoint`, `cd
/app` first.

**Container exits immediately**
Check `docker logs tru-node`. Most often a config parse error or the LevelDB
lock. If it exits with no output at all, `--cli` was started without a TTY.

**No peers connecting**
Confirm your seeds parsed — the node logs `[P2PNode] Added addnode: ip:port`
for each one at startup. If those lines are missing, `tru.conf` was not found
or the format is wrong. If they appear but nothing connects, test reachability
from the host: `nc -vz <seed-ip> 8333`.

**`ldd` shows missing libraries**
Should not happen in the container. If you see it, the runtime stage is
missing a `COPY --from=deps` line for a library added since this image was
written.

**Build fails on the keccak COPY**
`docker/vendor/libkeccak.a` is not populated. See "The keccak library".

**Build runs out of memory**
Use a machine with at least 4 GB, or add swap. `docker build` inherits the
host's memory; there is no way around the compiler's requirements.

---

## Image contents

Built from `ubuntu:24.04`. Runtime image installs from apt:
`libprotobuf32t64`, `libleveldb1d`, `libssl3t64`, `libcurl4t64`, `libfmt9`,
`libjsoncpp25`, `libsodium23`, `libqrencode4`, `libsnappy1v5`.

Built from source in the deps stage: `crc32c` (shared), `ethash` (static),
`libwally-core` (shared). Vendored: `keccak` (static).

Static archives are linked into the binary and do not appear in the runtime
image. The node runs as an unprivileged `tru` user, not root.
