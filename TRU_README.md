# TRU — TrueChain

**TRU (TrueChain)** is a from-scratch, UTXO-based Proof-of-Work blockchain written in C++17. It pairs a Bitcoin-style transaction model with an extended script interpreter, a four-type token system, on-chain AI oracle responses, and a full node/wallet/explorer/miner stack — all built and maintained by a single developer.

This document describes the system as it actually behaves in the code, including which features are fully implemented and which remain placeholders.

---

## Table of Contents

1. [What TRU Is](#what-tru-is)
2. [Chain Parameters](#chain-parameters)
3. [Architecture](#architecture)
4. [Consensus](#consensus)
5. [Transactions & Scripting](#transactions--scripting)
6. [Tokens](#tokens)
7. [Smart Contracts & Opcodes](#smart-contracts--opcodes)
8. [AI Oracle](#ai-oracle)
9. [Networking (P2P)](#networking-p2p)
10. [Storage](#storage)
11. [Wallets](#wallets)
12. [Mining](#mining)
13. [RPC API](#rpc-api)
14. [Block Explorer](#block-explorer)
15. [Building & Running](#building--running)
16. [Implementation Status](#implementation-status)
17. [Security Notes](#security-notes)

---

## What TRU Is

TRU is a complete Layer-1 blockchain, not a library or a cosmetic fork. It implements the full stack from the wire protocol up:

- A **UTXO ledger** persisted in LevelDB with per-value integrity checksums.
- **Proof-of-Work** using a custom `SHA256d + 21E8` puzzle, mineable on CPU (multithreaded) or GPU (OpenCL).
- A **script interpreter** extending Bitcoin's opcode set with real single- and multi-signature verification, stateful contract opcodes, gas metering, modern hashing, deterministic chain-state reads, and cross-chain bridge primitives.
- A **token layer** supporting four token classes plus on-chain text inscriptions (TRUSCRIPT).
- An **AI oracle** that writes language-model responses onto the chain via `OP_RETURN`.
- A **peer-to-peer network** using length-prefixed, checksummed Protobuf messages.
- **Wallets** (HD/BIP32) exposed through a CLI and a Qt desktop GUI.
- A **JSON-RPC API** (~65 methods) and an **HTTP block explorer**.

The chain is named *TrueChain*; its native asset ticker is **TRU**.

---

## Chain Parameters

| Parameter | Value |
|---|---|
| Chain name | TrueChain |
| Ticker | TRU |
| Consensus | Proof-of-Work (SHA256d + 21E8 injection) |
| Base unit | 1 TRU = 100,000,000 satoshis |
| Block subsidy | 50 TRU initial |
| Halving interval | 210,000 blocks |
| Target block time | 60 seconds |
| Difficulty retarget | Every 480 blocks (~8 hours) |
| Coinbase maturity | 100 blocks |
| Max block size | 10 MiB |
| Max money | 21,000,000 TRU |
| Address format | Base58Check P2PKH, version byte `0x00` |
| Default RPC port | 8332 |
| Default P2P port | 8333 |
| Default explorer port | 8001 |

---

## Architecture

TRU runs as one cooperating node process, plus standalone miner binaries and an optional explorer binary.

```
                      +-------------------+
                      |   CLI / Qt GUI    |
                      +---------+---------+
                                |
  +-----------+   +-------------v-------------+   +----------------+
  |  Miners   |-->|          Node             |<--|   RPC clients  |
  | CPU / GPU |   |                           |   +----------------+
  +-----------+   |  Blockchain  <-> Mempool  |
                  |      |            |        |   +----------------+
                  |   UTXO Set     Script VM  |<--|  Block Explorer |
                  |      |            |        |   +----------------+
                  |  LevelDB      AI Oracle   |
                  +------------+--------------+
                               |
                          +----v----+
                          |  P2P    |  <-- Protobuf over TCP
                          +---------+
```

Key modules:

- **`blockchain`** — block validation, chain state, reorg, difficulty, subsidy, UTXO application.
- **`mempool`** — transaction admission, conflict/double-spend handling, relay policy.
- **`script_interpreter`** — the stack VM that executes scriptSig + scriptPubKey.
- **`utxo`** — the UTXO set and transaction application/rollback against LevelDB.
- **`tx`** — transaction structures, serialization, signing, sighash.
- **`p2p` / `peer_connection` / `message_handler`** — the networking layer.
- **`wallet`** — HD key management, balance, transaction construction, token issuance.
- **`rpc_server`** — the JSON-RPC surface.
- **`ai_oracle_service` / `ai_providers`** — pluggable AI backends and on-chain response writing.

---

## Consensus

TRU is Nakamoto Proof-of-Work; the chain with the greatest cumulative work wins.

**Proof-of-Work.** The 80-byte block header is double-SHA256'd, then the constant `0x21E8` is added into the final 4 bytes (big-endian). The result must be ≤ the target encoded by the header's compact `bits`. The identical puzzle definition is shared by the CPU miner, the GPU (OpenCL) kernel, and the node's verifier, so all three agree bit-for-bit.

**Block validation.** Every block — mined locally, received over P2P, or submitted via RPC — passes the full contextual check *before* it is applied. Validation runs once, up front, before any state locks are taken:

- Structural checks (non-empty, valid hashes, correct sizes).
- Header hash matches the block hash and satisfies PoW.
- Previous block exists and height is exactly parent + 1.
- Timestamp is not more than 2 hours in the future and is greater than the median time past (MTP) of the last 11 blocks.
- Merkle root matches the transactions.
- Coinbase is the first (and only) coinbase transaction and pays no more than subsidy + fees.
- Every non-coinbase input references an existing, unspent UTXO; no double-spends within the block; scripts verify; coinbase inputs respect the 100-block maturity rule.
- Output values are individually bounded by `MAX_MONEY` and their sum cannot exceed inputs (checked, overflow-safe).
- The header's `bits` matches the difficulty expected from the parent chain, on **every** block.

**Difficulty retargeting.** Every 480 blocks the target is recomputed from the interval's actual time span against the desired span (480 × 60 s), in 128-bit arithmetic to avoid truncation, and clamped to a 4× move per retarget. Expected difficulty is a pure function of the parent chain, so all honest nodes derive the same value.

**Fork choice.** Each block index entry carries cumulative `chainWork` (parent work + this block's work), populated as blocks are added. On a competing block at or below the tip, the node traces to the common ancestor, sums the competing chain's work, and reorganizes only if the challenger has strictly more work.

**Transaction identity.** A transaction's txid is the double-SHA256 of its serialized bytes. Transactions received over the network are re-hashed on arrival; a peer-supplied id that disagrees with the computed hash causes the transaction to be dropped.

---

## Transactions & Scripting

TRU transactions follow the Bitcoin model: inputs (each referencing a prior output by txid+vout, with an unlocking `scriptSig`) and outputs (each an amount plus a locking `scriptPubKey`).

- **Signatures** are ECDSA over secp256k1 (via OpenSSL), with a `SIGHASH_ALL`-style sighash. Standard spends use compressed public keys and P2PKH scripts (`OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG`).
- **Script verification** runs `scriptSig` then `scriptPubKey` on a shared stack; the script succeeds if the final stack top is truthy.
- Both single-signature (`OP_CHECKSIG`, `OP_CHECKSIGVERIFY`) and **multi-signature** (`OP_CHECKMULTISIG`, `OP_CHECKMULTISIGVERIFY`) checks perform real ECDSA verification against the input sighash.

Standard output types recognized by relay policy: **P2PKH**, **P2SH**, **OP_RETURN** (data / token / inscription), and any script matching the allow-listed contract patterns in `allowed_scripts.json`.

---

## Tokens

TRU issues tokens as transactions carrying `OP_RETURN` metadata plus an ownership script. Four token classes are supported, each with a dedicated wallet issuance function.

| Type | Name | Divisible | Supply | Typical use |
|---|---|---|---|---|
| **FT** | Fungible Token | Yes (decimals) | Any | Currencies, rewards, utility tokens |
| **NFT** | Non-Fungible Token | No | Exactly 1 | Collectibles, art, unique assets |
| **SFT** | Sentient Fungible Token | Yes | > 1 | Limited editions / evolving assets with AI-oriented metadata |
| **NCFT** | Neural Canvas Fungible Token | Fungible | Any | AI-generated / evolving digital media |

In addition, **TRUSCRIPT** inscriptions store arbitrary text on-chain (ordinal-style), with an inscription index, sat number, timestamp, and current-owner tracking that updates on transfer.

**Issuance flow** (shared by all types):

1. Resolve the sender address and find a spendable UTXO for the fee.
2. Assemble metadata (name, symbol, description, image URL, type-specific fields).
3. Encode an `ExtendedTokenData` structure and build the `OP_RETURN` scriptPubKey.
4. Construct the transaction: fee input, token output, change output (minus a 10,000-satoshi fee).
5. Sign, attach metadata, and either add to the local mempool or broadcast via RPC.

**Issuance functions:** `issueExtendedFT`, `issueExtendedNFT`, `issueExtendedSFT`, `issueExtendedNCFT`, plus `inscribeTRUScript` and `transferTRUScript`.

```cpp
// Fungible token
wallet.issueExtendedFT("FT001", 1000000, "Fungible Coin", "FCO",
                       "A digital currency", "https://example.com/fco.png", 8);

// Non-fungible token
wallet.issueExtendedNFT("NFT001", "Rare Gem", "A unique jewel",
                        "https://example.com/gem.png", "Alice", "https://alice.art");

// Sentient fungible token
wallet.issueExtendedSFT("SFT002", 50, "Special Edition", "SED",
                        "Limited series", "https://example.com/sed.png", 0);

// Neural canvas fungible token
wallet.issueExtendedNCFT("NCFT002", 200, "AI Art Token",
                         "Evolving artwork", "https://example.com/aiart.png");
```

Validation enforces per-type rules: FT/SFT amounts must be non-zero, NFT amount must be exactly 1, token IDs must be present, and owner addresses must be valid. Metadata is stored under a `tokenMetadata:<txid>` key with a double-SHA256 integrity checksum, and ownership is tracked in LevelDB and updated on transfer.

---

## Smart Contracts & Opcodes

TRU's interpreter keeps the Bitcoin scripting foundation and layers custom "New Age" opcodes on top, giving UTXO scripts access to signatures, persistent state, gas metering, modern hashing, deterministic chain-state, and cross-chain bridge primitives.

### Standard opcodes (implemented)

Constants (`OP_0`–`OP_16`, `OP_1NEGATE`); data pushes (`OP_PUSHDATA1/2/4`); flow control (`OP_IF`, `OP_NOTIF`, `OP_ELSE`, `OP_ENDIF`, `OP_VERIFY`, `OP_RETURN`); stack ops (`OP_DUP`, `OP_DROP`, `OP_OVER`, `OP_SWAP`, `OP_NIP`, `OP_2DUP`, `OP_TOALTSTACK`/`OP_FROMALTSTACK`, etc.); splice (`OP_SIZE`, `OP_LEFT`); arithmetic/logic (`OP_ADD`, `OP_SUB`, `OP_MUL`, `OP_DIV`, `OP_MOD`, `OP_EQUAL`, `OP_EQUALVERIFY`, `OP_BOOLAND/OR`); crypto (`OP_RIPEMD160`, `OP_SHA1`, `OP_SHA256`, `OP_HASH160`, `OP_HASH256`); time locks (`OP_CHECKLOCKTIMEVERIFY`).

### Signature opcodes (implemented)

| Opcode | Hex | Function |
|---|---|---|
| `OP_CHECKSIG` | 0xac | Real ECDSA verification against the input sighash |
| `OP_CHECKSIGVERIFY` | 0xad | As above; aborts the script on an invalid signature |
| `OP_CHECKMULTISIG` | 0xae | Real M-of-N verification (ordered subset of N pubkeys) |
| `OP_CHECKMULTISIGVERIFY` | 0xaf | As above; aborts the script on failure |

Multisig follows the standard stack layout `<m> <sig_1..sig_m>` unlocking `<n> <pub_1..pub_n>`, matches signatures against public keys in order without reuse, enforces bounds (n ≤ 20, m ≤ n), and includes the historical extra-element pop for convention compatibility. In explicit simulation mode (no transaction context) signature checks accept, for offline script testing.

### Custom opcodes

| Opcode | Hex | Function | Status |
|---|---|---|---|
| `OP_BLOCKTIME` | 0xf0 | Push current block time | Implemented |
| `OP_EXTERNALDATA` | 0xf1 | Push external/off-chain data | **Placeholder** (see note) |
| `OP_DATAFEED` | 0xf2 | Push a keyed data-feed value | **Placeholder** (see note) |
| `OP_DELEGATECHECK` | 0xf3 | Verify a delegate/trusted signature | **Stub** (returns false) |
| `OP_CHAINSTATECHECK` | 0xf4 | Read a deterministic chain-state value | Implemented |
| `OP_HASHBLAKE2B` | 0xf5 | BLAKE2b-256 of top item (libsodium) | Implemented |
| `OP_SHA3` | 0xf6 | SHA3-256 of top item (OpenSSL) | Implemented |
| `OP_STORE` | 0xf7 | Write key/value to contract state | Implemented |
| `OP_LOAD` | 0xf8 | Read value from contract state | Implemented |
| `OP_CALLER` | 0xf9 | Push sender address | Implemented |
| `OP_CONTRACT_ADDR` | 0xfa | Push contract address | Implemented |
| `OP_GAS` | 0xfb | Push remaining gas | Implemented |
| `OP_HALT` | 0xfc | Halt execution | Implemented |
| `OP_REVERT` | 0xfd | Revert transaction + state | Implemented |
| `OP_OUTPUTAMOUNT` | 0xfe | Push current output amount | Implemented |
| `OP_MINT_TOKEN` | 0xe0 | Mint tokens against sent value | Implemented |
| `OP_TOKEN_BALANCE` | 0xe1 | Query token balance | Partial |
| `OP_BURN_TOKEN` | 0xe2 | Burn tokens | Partial |
| NOVO bridge | 0xb3–0xb6 | wNOVO deposit/redeem/verify | Bridge scaffold |
| BSTY bridge | 0xb7–0xba | wBSTY deposit/redeem/verify | Bridge scaffold |

**`OP_CHAINSTATECHECK`** reads real, deterministic on-chain state — values that are identical on every node at a given height, evaluated relative to the block being validated (not the live tip). Supported keys:

- `block_height` — the height at which the script executes
- `total_supply` / `total_issued` — cumulative issued TRU (a pure function of height)
- `block_reward` / `subsidy` — the subsidy at that height

If no chain context is available (e.g. mempool simulation) or the key is unsupported, the opcode fails closed rather than returning fabricated data.

### Execution model

- **Gas.** Every operation charges gas against a per-execution limit (default 1,000,000). Costs scale with complexity — simple ops are cheap; `OP_STORE`, hashing, and signature checks cost more. Overflow of the gas counter is guarded.
- **State.** `OP_STORE`/`OP_LOAD` read and write a key/value map scoped to the contract address, persisted through the storage layer.
- **Context.** `ScriptExecutionContext` carries the transaction, input index, scriptPubKey, sighash, sender, gas counters, execution height, a chain reference (for deterministic state), and callback hooks. A simulation mode (`tx == nullptr`) is available for testing scripts without a live transaction.

### Contract types (wallet/CLI)

The wallet can build several contract templates: time locks (`OP_CHECKLOCKTIMEVERIFY`), hash locks (`OP_HASH160` preimage reveal), oracle locks, stateful contracts, multisig, custom compiled scripts, and **MagicLock** — a signature-grinding construct that binds a spend to a target prefix.

---

## AI Oracle

TRU includes a configurable AI oracle that answers on-chain requests and writes the model's response back to the chain.

- A request is an `OP_DATAFEED`-tagged output carrying an `AI_REQUEST:<id>` prefix; the oracle scans the mempool for these.
- The oracle routes the request to a configured provider, then writes the response as an `OP_RETURN` transaction funded by an oracle key.
- **Providers:** Oobabooga (local text-gen, the default and functional), plus interface implementations for OpenAI, Ollama, Grok (x.AI), Gemini, and a generic custom endpoint. The non-default providers' HTTP transports are scaffolds and return an explicit "not implemented" error rather than failing silently.
- Providers are configured per user and selected through a registry; requests and responses can be tied to AI-enabled tokens.

This lets tokens and contracts reference model output that is permanently recorded on-chain.

---

## Networking (P2P)

Nodes communicate over TCP using Protobuf messages wrapped in a framed envelope: a 4-byte type, a 4-byte length, a 32-byte SHA-256 payload checksum, and the payload. Messages exceeding 32 MiB are rejected, and the checksum is verified before parsing.

**Message types:** `VERSION`/`VERACK` handshake, `ADDR`, `INV`, `GETDATA`, `BLOCK`, `TX`, `PING`/`PONG`, `HEIGHT`, `GET_BLOCK`, `GET_HEIGHT`, `BLOCK_NOT_FOUND`.

**Behavior:**
- Non-blocking accept loop with clean shutdown signaling via a self-pipe.
- Peer connections run their own read loop, send periodic pings, and time out stale links.
- Height gossip drives synchronization; blocks are requested by height or hash and validated on arrival.
- Peer management limits connections per IP (Sybil resistance) and tracks activity; an IP blacklist facility (`SybilProtection`) is available.
- Incoming transactions are re-hashed and revalidated locally rather than trusted.

---

## Storage

State is persisted in **LevelDB** through a thread-safe wrapper (`LevelDBStorage`):

- Snappy compression, a 100 MB LRU block cache, and reference-counted DB handles per path.
- Every stored value carries an integrity checksum; contract and UTXO values use double-SHA256, and reads verify before returning.
- A legacy single-SHA256 checksum format is auto-detected and transparently migrated on read.
- Batched writes, prefix iteration, compaction, repair, and a full-database verification pass are supported.

UTXOs are stored as `utxo:<txid>:<vout>` → `height=<H>|<amount>|<scriptHex>[|cb=1]`, capturing the creation height and coinbase flag needed for maturity enforcement.

---

## Wallets

TRU ships two wallet front-ends over one HD wallet core.

**Core (HD/BIP32):**
- Seed-derived keys via libwally, BIP44-style path (purpose/coin/account/change/index).
- Address generation (Base58Check P2PKH), balance calculation, UTXO discovery.
- Transaction construction and signing, local-chain or RPC modes.
- Token issuance/transfer, TRUSCRIPT inscription, smart-contract creation, MagicLock create/unlock.
- Import of external private keys (PEM or 32-byte hex).

**CLI wallet** — a rich terminal interface (colorized tables, QR display, menus) for wallet management, sending, mining, tokens, TRUSCRIPT, contracts, and mempool/chain inspection.

**Qt GUI wallet** — a tabbed desktop app (Wallet, Send, Tokens, TRUScript, Transactions, Smart Contracts, Settings) with an animated background, theming, auto-refresh, and live block-height display.

---

## Mining

Two miner implementations share the node's `SHA256d + 21E8` definition:

- **CPU miner** — multithreaded nonce search, tunable thread count.
- **GPU miner** — an OpenCL kernel (`tru_gpu_miner`) implementing the full double-SHA256 + 21E8 injection on-device, with auto-tuning of work sizes.

Miners obtain work via the `getblocktemplate` RPC, search for a valid nonce, and submit via `submitblock`. They report hashrate through `reportmineractivity` and register/unregister with the node. Mining can also be driven directly from the CLI/GUI wallet against the local chain.

---

## RPC API

The node exposes a JSON-RPC endpoint at `http://<bindIP>:<port>/rpc` (default `127.0.0.1:8332`). Requests are JSON with `method`, `params`, and optional `id`; responses carry a `result` or an `error`.

```bash
curl -X POST http://127.0.0.1:8332/rpc \
  -H "Content-Type: application/json" \
  -d '{"method":"getchaininfo","params":{},"id":1}'
```

**Selected methods** (~65 total):

*Chain & blocks:* `getchaininfo`, `getblockcount`, `getblock`, `getblockbyheight`, `getblocktemplate`, `submitblock`.

*Transactions:* `sendrawtransaction`, `createrawtransaction`, `signrawtransactionwithkey`, `gettransaction`, `getrawtransaction`, `decoderawtransaction`, `gettxout`, `listtransactions`, `getrawmempool`, `getmempooltransactions`.

*Addresses & UTXOs:* `getnewaddress`, `listaddresses`, `listunspent`, `getaddresstransactions`.

*Tokens & inscriptions:* `issuetoken`, `sendtoken`, `gettokenutxo`, `gettokenmetadata`, `verifytokenbalance`, `inscribeTRUScript`, `transferTRUScript`, `getTRUScripts`, `getTRUScriptDetails`.

*Contracts & MagicLock:* `createsmartcontract`, `createcontracttransaction`, `getcontracts`, `createmagiclock`, `unlockmagiclock`, `listmagiclocks`.

*Mining:* `startmining`, `registerminer`, `unregisterminer`, `getminerstatus`, `getallminers`, `reportmineractivity`.

*AI:* `configureAIProvider`, `getAIProviders`, `createAIToken`, `interactWithAIToken`, `getAIResponse`, `getAITokenState`, `trainAIToken`.

*Identity/social:* `createDID`, `createsocialpost`.

*Peers:* `getpeerinfo`.

> **Note:** The RPC server currently performs no authentication. Bind it to localhost or place it behind an authenticated reverse proxy for any non-local deployment.

---

## Block Explorer

An HTTP explorer (default port 8001) serves JSON endpoints backed by the chain and a static web front-end:

`/api/stats`, `/api/blocks`, `/block/<hash>`, `/api/addresses`, `/api/transactions`, `/api/address/<addr>`, `/api/transaction/<txid>`, `/api/tokens`, `/api/contracts`, `/api/miners`.

Error responses are emitted as properly escaped JSON. The explorer can run inside the node (`--enable-explorer`) or as the standalone `explorer_main` binary against an existing data directory.

---

## Building & Running

**Dependencies:** a C++17 compiler, OpenSSL, libsodium, LevelDB, Protobuf, libwally (BIP32), libcurl, nlohmann/json, cxxopts, httplib, OpenCL (for GPU mining), and Qt (for the GUI, gated behind `BUILD_WITH_QT`).

**Run the node (CLI):**

```bash
./tru_advanced --datadir data/utxo --cli \
               --rpcport 8332 --enable-explorer --explorer-port 8001
```

Useful flags: `--gui`, `--no-p2p`, `--no-seeds`, `--peers ip:port,...`, `--conf tru.conf`, `--rpcbind <ip>`.

**Mine:**

```bash
./tru_miner       --address <YOUR_ADDR>   # CPU
./tru_gpu_miner   --address <YOUR_ADDR>   # GPU (OpenCL)
```

**Explorer only:**

```bash
./blockexplorer data/utxo 8001
```

Configuration (seeds, addnode, external IP, oracle key) is read from `tru.conf`.

---

## Implementation Status

TRU is a working chain. The following remain honest placeholders or partial implementations:

- **Oracle-style opcodes** — `OP_EXTERNALDATA` and `OP_DATAFEED` return sample/dummy data. These are intentionally *not* wired to live feeds: a deterministic VM cannot consume non-deterministic external data without every node agreeing on identical bytes, which requires a committed/signed-oracle design (the data included and validated inside the transaction or block), not an opcode stub.
- **`OP_DELEGATECHECK`** — stubbed (returns false); needs delegate-signature logic.
- **Token opcodes** — `OP_MINT_TOKEN` is implemented; `OP_TOKEN_BALANCE` and `OP_BURN_TOKEN` are partial.
- **Cross-chain bridges** — the NOVO and BSTY bridge opcodes are scaffolding for wNOVO/wBSTY, not a live bridge.

Everything else described above — consensus, PoW, UTXO handling, standard scripting, single- and multi-signature verification, deterministic `OP_CHAINSTATECHECK`, tokens, state opcodes, gas, hashing opcodes, P2P, storage, wallets, mining, RPC, and the explorer — is implemented and functioning.

---

## Security Notes

TRU is an independent, single-implementation chain that has not undergone third-party audit or sustained adversarial testing. If you deploy it beyond a controlled/demo environment, be aware:

- **RPC has no authentication.** Keep it on localhost or behind an authenticated proxy.
- **Wallet key material** is stored on disk; protect the data directory with appropriate file permissions.
- **Consensus is enforced by one codebase.** A production network benefits from an independent reimplementation to catch divergence, plus a test suite and a public testnet run against hostile peers.
- **New consensus features** — such as multisig verification — should be exercised on a private testnet (e.g. build and spend a 2-of-3, and confirm that under-signed and wrong-key spends fail) before real value depends on them.

Contributions, testing, and review are welcome — this is a living project.

---

*TRU (TrueChain) — a UTXO Proof-of-Work blockchain with extended scripting, multisig, tokens, and on-chain AI.*
