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

TRU includes a configurable, provider-agnostic AI oracle that routes AI requests to local or cloud language-model providers and anchors the resulting response back onto the TRU blockchain.

The AI subsystem is intentionally separate from Proof-of-Work consensus. Nodes do **not** need access to an AI provider to validate the chain. AI computation occurs off-chain; the resulting oracle transaction is validated using normal TRU transaction and script rules.

### AI request and response flow

A request is represented by an `OP_DATAFEED`-tagged transaction carrying an `AI_REQUEST:<id>` identifier. The oracle monitors pending requests, resolves the provider configured for the requesting user, sends the prompt to that provider, stores the response, and anchors a cryptographic commitment to the response in an `OP_RETURN` transaction funded by the oracle wallet.

```text
TRU AI request
      |
      v
ConfigurableAIOracle
      |
      v
AIProviderRegistry
      |
      +----------------------+----------------------+----------------------+
      |                      |                      |
      v                      v                      v
 Local providers         Cloud providers       Custom provider
      |                      |                      |
 Oobabooga                OpenAI               Arbitrary JSON API
 Nemotron                 Anthropic / Claude
 Ollama                   xAI / Grok
                          Google Gemini
      |                      |                      |
      +----------------------+----------------------+
                             |
                             v
                      Provider response
                             |
                             v
                     Canonical AI text
                             |
                 +-----------+-----------+
                 |                       |
                 v                       v
          Contract storage          SHA-256 digest
                                         |
                                         v
                                 OP_RETURN anchor
                                         |
                                         v
                                   TRU blockchain
````

### Supported AI providers

| Provider               | Type           |        Status | Default interface                               | Authentication                          |
| ---------------------- | -------------- | ------------: | ----------------------------------------------- | --------------------------------------- |
| **Oobabooga**          | Local          | ✅ Implemented | OpenAI-compatible `/v1/chat/completions`        | Optional `OOBABOOGA_API_KEY`            |
| **Nemotron**           | Local          | ✅ Implemented | `http://127.0.0.1:5050/v1/chat/completions`     | Optional/recommended `NEMOTRON_API_KEY` |
| **Ollama**             | Local          | ✅ Implemented | Ollama `/api/chat`                              | None by default                         |
| **OpenAI**             | Cloud          | ✅ Implemented | Chat Completions-compatible HTTPS transport     | `OPENAI_API_KEY`                        |
| **Anthropic / Claude** | Cloud          | ✅ Implemented | Anthropic Messages API                          | `ANTHROPIC_API_KEY`                     |
| **xAI / Grok**         | Cloud          | ✅ Implemented | xAI Chat Completions-compatible HTTPS transport | `XAI_API_KEY`                           |
| **Google Gemini**      | Cloud          | ✅ Implemented | Gemini `generateContent` REST API               | `GEMINI_API_KEY`                        |
| **Custom**             | Local or Cloud | ✅ Implemented | User-defined JSON HTTP endpoint                 | `CUSTOM_AI_API_KEY` when required       |

Provider selection is handled by `AIProviderRegistry`. The oracle can therefore change providers without changing TRU consensus or the on-chain response format.

### Provider credentials and `.env`

AI-provider secrets should be supplied through environment variables. They should **not** be committed to Git and should not be stored in blockchain contract storage.

Create a project-local environment file:

```bash
cd ~/NEW_TRU
nano .env
```

Example:

```text
# Cloud AI providers
OPENAI_API_KEY=
XAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Local/private AI providers
NEMOTRON_API_KEY=
OOBABOOGA_API_KEY=

# Generic custom provider
CUSTOM_AI_API_KEY=
```

Only populate the providers you actually use.

Protect the file:

```bash
chmod 600 ~/NEW_TRU/.env
```

Add the following to `.gitignore`:

```gitignore
# Local secrets / API credentials
.env
.env.*
!.env.example
```

An optional `.env.example` may be committed with empty values:

```text
OPENAI_API_KEY=
XAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
NEMOTRON_API_KEY=
OOBABOOGA_API_KEY=
CUSTOM_AI_API_KEY=
```

### Loading `.env` before starting TRU

The TRU C++ process does **not** automatically parse `.env` files. Load the file into the process environment before launching the node:

```bash
cd ~/NEW_TRU

set -a
source .env
set +a
```

Then start TRU from that same shell.

The variables can also be exported individually:

```bash
export OPENAI_API_KEY="..."
export XAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GEMINI_API_KEY="..."
export NEMOTRON_API_KEY="..."
export OOBABOOGA_API_KEY="..."
export CUSTOM_AI_API_KEY="..."
```

To verify that a variable exists without printing the secret:

```bash
test -n "$OPENAI_API_KEY" && echo "OPENAI_API_KEY loaded"
test -n "$GEMINI_API_KEY" && echo "GEMINI_API_KEY loaded"
test -n "$NEMOTRON_API_KEY" && echo "NEMOTRON_API_KEY loaded"
```

Do not use `echo $OPENAI_API_KEY` or similar commands in shared terminals, logs, screenshots, or shell transcripts.

For Docker-based launches, the same file can be supplied with Docker's environment-file mechanism:

```bash
docker run --env-file ~/NEW_TRU/.env ...
```

### Provider authentication

#### OpenAI

Credential:

```text
OPENAI_API_KEY
```

TRU sends the key using Bearer authentication:

```text
Authorization: Bearer <OPENAI_API_KEY>
```

#### xAI / Grok

Credential:

```text
XAI_API_KEY
```

TRU sends the key using Bearer authentication:

```text
Authorization: Bearer <XAI_API_KEY>
```

#### Anthropic / Claude

Credential:

```text
ANTHROPIC_API_KEY
```

TRU uses Anthropic's native Messages API authentication:

```text
x-api-key: <ANTHROPIC_API_KEY>
anthropic-version: 2023-06-01
```

#### Google Gemini

Credential:

```text
GEMINI_API_KEY
```

TRU uses the Gemini REST API and sends the key in the Google API-key header:

```text
x-goog-api-key: <GEMINI_API_KEY>
```

The default Gemini model is:

```text
gemini-3.6-flash
```

The default API base is:

```text
https://generativelanguage.googleapis.com/v1beta/models
```

TRU converts its common message format into Gemini's native request format:

```text
system    -> systemInstruction
user      -> contents[].role = "user"
assistant -> contents[].role = "model"
```

Gemini responses are normalized from:

```text
candidates[0].content.parts[].text
```

into the same internal text representation used by the other providers.

#### Nemotron

The built-in Nemotron provider targets the local OpenAI-compatible harness:

```text
http://127.0.0.1:5050/v1/chat/completions
```

Credential:

```text
NEMOTRON_API_KEY
```

Example Nemotron server `.env`:

```text
NEMOTRON_API_KEY=replace_with_a_long_random_secret
```

TRU should receive the same key:

```bash
export NEMOTRON_API_KEY="replace_with_a_long_random_secret"
```

When a key is present, TRU sends:

```text
Authorization: Bearer <NEMOTRON_API_KEY>
```

The Nemotron harness can also permit genuinely local loopback traffic without a key when its trusted-local setting is enabled. Using the key is still recommended because the same configuration remains protected if the service is later exposed through a LAN interface, reverse proxy, tunnel, or remote host.

The Nemotron `/v1/chat/completions` endpoint routes requests through the full local harness rather than directly calling only the underlying model. Depending on the harness configuration, a TRU request can therefore use the local model together with RAG, tools, validation, orchestration, memory, and other Nemotron pipeline features.

#### Oobabooga

Oobabooga is a local OpenAI-compatible provider.

Credential, when the local server requires one:

```text
OOBABOOGA_API_KEY
```

When set, TRU sends:

```text
Authorization: Bearer <OOBABOOGA_API_KEY>
```

If the local Oobabooga endpoint does not require authentication, the variable may be left unset.

#### Ollama

The default Ollama provider uses the local `/api/chat` endpoint and does not require an API key in the default local configuration.

#### Custom provider

Credential:

```text
CUSTOM_AI_API_KEY
```

The Custom provider supports a user-defined endpoint and configurable authorization header/prefix. This allows TRU to communicate with another private or commercial JSON API without adding another provider class.

### API-key persistence policy

Provider configuration may contain values such as provider name, model, endpoint, or request options. API keys are treated differently.

TRU removes `api_key` from provider configuration before that configuration is written to persistent contract storage. Secrets therefore remain process-local and should be restored from environment variables after a restart.

This prevents cloud and private-service API credentials from becoming part of persistent blockchain/application state.

### Oracle wallet credentials

AI-provider credentials and the blockchain oracle signing key are separate classes of secrets.

The oracle wallet currently loads its blockchain address and WIF from `tru.conf`:

```ini
[default]
oracle.address=<TRU_ORACLE_ADDRESS>
oracle.wif=<TRU_ORACLE_PRIVATE_WIF>
```

The WIF controls the oracle wallet and is used to sign the transaction that anchors the AI response onto TRU. Protect any `tru.conf` containing a WIF:

```bash
chmod 600 ~/NEW_TRU/tru.conf
```

Do not commit a production `tru.conf` containing `oracle.wif` to Git.

Recommended separation:

```text
tru.conf
├── node / network configuration
├── oracle.address
└── oracle.wif

.env / process environment
├── OPENAI_API_KEY
├── XAI_API_KEY
├── ANTHROPIC_API_KEY
├── GEMINI_API_KEY
├── NEMOTRON_API_KEY
├── OOBABOOGA_API_KEY
└── CUSTOM_AI_API_KEY
```

### On-chain response anchoring

The complete AI response is retained by the oracle storage layer. The blockchain transaction stores a compact anchor rather than placing an arbitrarily large model response directly on-chain.

The response anchor contains information including:

```text
AI_RESP_V1
request ID
provider
SHA-256 digest
short response preview
```

The digest cryptographically commits the stored response to the blockchain record.

This separates:

```text
AI computation
      |
      v
response storage
      |
      v
SHA-256 commitment
      |
      v
TRU transaction
      |
      v
blockchain confirmation
```

The underlying AI provider can therefore change without changing TRU consensus.

### Provider independence

TRU can operate with:

* fully local/open-source AI,
* locally hosted private AI,
* commercial cloud AI,
* OpenAI-compatible custom servers,
* native provider APIs,
* or a mixture of providers selected per user or application.

No single AI company, hosted API, or language model is required for the TRU blockchain to function.

---

# Living Token Evolution

TRU supports **AI-assisted Living Token Evolution**, allowing supported tokens to update their off-chain metadata over time while preserving a verifiable history of each evolution.

Instead of replacing the original token or rewriting its history, each evolution creates a new persisted epoch and links it to the previous metadata state.

A compact cryptographic commitment to that evolution is then submitted to the TRU blockchain through a normal transaction.

## What Token Evolution Does

A Living Token evolution can use an AI provider to generate a new version of the token's metadata based on its current state.

The evolution system:

```text
Existing Token
      │
      ▼
Load Latest Persisted State
      │
      ▼
AI Provider
      │
      ▼
Generate New Metadata
      │
      ▼
Epoch N → Epoch N+1
      │
      ▼
Hash Previous + New Metadata
      │
      ▼
Persist Evolution Record
      │
      ▼
Queue Blockchain Anchor
      │
      ▼
Oracle Signs Transaction
      │
      ▼
TRU Mempool
      │
      ▼
Next Mined Block
      │
      ▼
On-Chain Evolution Commitment
```

The complete AI-generated metadata does **not** need to be stored directly on-chain.

Instead, TRU places a compact evolution commitment into an `OP_RETURN` transaction containing information such as:

```text
TRU_EVOLVE_V1
tokenID
tokenType
epoch
provider
trigger
previous_metadata_hash
new_metadata_hash
```

This provides an auditable connection between the previous and new token states without unnecessarily putting the full AI response into the blockchain.

---

## Supported Evolution Providers

Evolution can be performed using configured AI providers.

For example:

```text
nemotron
openai
anthropic
grok
gemini
ollama
oobabooga
custom
```

Provider availability depends on how the node was configured and which API keys or local AI services are available.

Example using the local Nemotron provider:

```bash
./tru_evolve_token \
  --token-id f0e6d042 \
  --provider nemotron \
  --db /path/to/data/utxo
```

---

# Normal Evolution Workflow

For a normal TRU installation, there are two parts involved:

1. `tru_evolve_token` creates and persists the new evolution state.
2. `tru_advanced` detects the queued evolution and creates the on-chain anchor transaction.

Because `tru_evolve_token` accesses the LevelDB database directly, **do not run it while `tru_advanced` has the same database open.**

The normal workflow is therefore:

```text
Stop node
   ↓
Run token evolution
   ↓
Verify latest state
   ↓
Restart node
   ↓
Oracle submits anchor transaction
   ↓
Miner confirms transaction
```

---

# Step 1 — Stop the Node

If `tru_advanced` is currently running, shut it down normally.

Verify that it has stopped:

```bash
pgrep -af tru_advanced
```

There should be no running `tru_advanced` process using the database.

---

# Step 2 — Load the AI Environment

If using providers configured through `.env`:

```bash
cd ~/NEW_TRU

set -a
source .env
set +a
```

For a local Nemotron service, for example:

```bash
echo "$NEMOTRON_ENDPOINT"
```

Typical configuration:

```text
http://127.0.0.1:5051/v1/chat/completions
```

---

# Step 3 — Check the Current Token State

Before evolving the token, inspect its latest persisted evolution:

```bash
cd ~/NEW_TRU

./build-native/bin/tru_evolve_token \
  --token-id f0e6d042 \
  --db /NEW_TRU/build-native/bin/data/utxo \
  --show-latest
```

This displays the most recently persisted epoch.

For example:

```text
Token: f0e6d042
Epoch: 1
Provider: nemotron
...
```

---

# Step 4 — Evolve the Token

Run:

```bash
./build-native/bin/tru_evolve_token \
  --token-id f0e6d042 \
  --provider nemotron \
  --db /NEW_TRU/build-native/bin/data/utxo
```

A successful evolution should advance the token exactly one epoch:

```text
Epoch 1 → Epoch 2
```

The evolution engine preserves the previous metadata hash and produces a new metadata hash.

The new state is persisted before the blockchain anchor is submitted.

---

# Step 5 — Verify the New Evolution

While the node is still stopped:

```bash
./build-native/bin/tru_evolve_token \
  --token-id f0e6d042 \
  --db /NEW_TRU/build-native/bin/data/utxo \
  --show-latest
```

The new epoch should now be shown as the latest persisted state.

---

# Step 6 — Restart the TRU Node

Start `tru_advanced` again:

```bash
cd ~/NEW_TRU/build-native/bin

./tru_advanced \
  --datadir /NEW_TRU/build-native/bin/data/utxo \
  --cli \
  --rpcport 8332
```

The AI Oracle service monitors the persisted evolution queue.

When it finds the new evolution, it creates and signs a TRU transaction containing the evolution commitment.

---

# Step 7 — Watch the Evolution Anchor

From another terminal:

```bash
cd ~/NEW_TRU/build-native/bin

tail -f Tru_debug.log | \
grep --line-buffered -iE \
'TokenEvolutionAnchor|anchor_queue|signTransaction'
```

A successful submission looks similar to:

```text
[TokenEvolutionAnchor] Submitted token=f0e6d042 epoch=2 txid=<TXID>
```

You may also see:

```text
[TokenEvolutionAnchor] Anchored token=f0e6d042 epoch=2 txid=<TXID>
```

### Important

In the current implementation, this means the anchor transaction was successfully created/submitted and associated with the evolution record.

**Blockchain confirmation occurs when a miner includes that transaction in a block.**

---

# Step 8 — Check the Mempool

The TRU JSON-RPC interface can be used to see whether the evolution transaction is waiting to be mined.

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  --data '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"getrawmempool",
    "params":{}
  }' \
  http://127.0.0.1:8332/rpc | python3 -m json.tool
```

Example:

```json
{
    "id": 1,
    "jsonrpc": "2.0",
    "result": [
        "0af06ae9f80d399a8ac41ddeb00ad3a86949498c5adc05bf553a438d2e9d3a6e"
    ]
}
```

This means:

```text
0af06ae9...d3a6e
```

is currently in the TRU mempool waiting for inclusion in a block.

For an evolution transaction, the flow is now:

```text
Evolution complete       ✅
Evolution persisted      ✅
Anchor transaction built ✅
Transaction signed       ✅
Transaction in mempool   ✅
Blockchain confirmation  ⏳
```

---

# Step 9 — Mine the Anchor

A miner can now mine the next TRU block.

For example:

```bash
cd ~/NEW_TRU/build-native/bin

./tru_miner_cpu \
  --node-ip 127.0.0.1 \
  --node-port 8332 \
  --mineraddr YOUR_TRU_ADDRESS \
  --threads 4
```

The built-in CPU/GPU mining options may also be used.

Once the transaction is included in a block, the anchor leaves the mempool.

---

# Step 10 — Verify Confirmation

Run `getrawmempool` again:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  --data '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"getrawmempool",
    "params":{}
  }' \
  http://127.0.0.1:8332/rpc | python3 -m json.tool
```

If no other transactions are waiting, the response will be:

```json
{
    "id": 1,
    "jsonrpc": "2.0",
    "result": []
}
```

If the evolution transaction was previously present and disappears immediately after a successful block is mined, it has progressed out of the mempool and into block processing.

---

# How a Normal User Would Use Evolution

The commands above expose the complete low-level workflow for operators and developers.

A normal user does **not need to manually inspect LevelDB, calculate metadata hashes, construct `OP_RETURN` scripts, sign anchor transactions, or manage the evolution queue.**

Conceptually, the user's workflow is simply:

```text
Choose Token
     ↓
Choose AI Provider
     ↓
Evolve Token
     ↓
Review New State
     ↓
TRU automatically queues blockchain proof
     ↓
Node submits anchor transaction
     ↓
Network miner confirms it
```

A future wallet/UI can therefore expose evolution as something as simple as:

```text
Token:       My Living Token
Epoch:       4
AI Provider: Nemotron

[ Evolve Token ]
```

with an evolution history such as:

```text
Epoch 0  Original
Epoch 1  Nemotron     Confirmed
Epoch 2  Nemotron     Confirmed
Epoch 3  Gemini       Confirmed
Epoch 4  Nemotron     Pending Confirmation
```

The underlying cryptographic and blockchain operations remain handled by TRU.

---

# Evolution State vs. Blockchain Anchor

These are intentionally separate concepts.

**Evolution State**

Contains the complete living-token evolution information and AI-generated metadata.

Persisted locally under evolution records such as:

```text
TOKEN_EVOLUTION/latest:<tokenID>
TOKEN_EVOLUTION/epoch:<tokenID>:<epoch>
```

**Blockchain Anchor**

Contains only the compact information needed to cryptographically prove the evolution.

The blockchain therefore acts as an immutable timestamped proof of:

```text
Token X
changed from metadata hash A
to metadata hash B
at epoch N
using provider Y
```

without requiring the blockchain to store the entire AI-generated document.

---

# Oracle Funding

The evolution oracle must have a spendable TRU UTXO because each evolution anchor is a normal signed blockchain transaction.

Configuration example:

```ini
[default]
oracle.address=<TRU_ADDRESS>
oracle.wallet=tru.dat
node.ip=127.0.0.1
node.port=8332
```

The configured address must belong to `tru.dat`.

Coinbase mining rewards must reach maturity before they can be spent by the oracle.

If the oracle cannot find a usable UTXO, the log may show:

```text
[TokenEvolutionAnchor] No UTXO large enough for fee
```

The evolution state itself remains persisted; the anchor stays queued and can be retried after the oracle is funded.

---

# Failure Safety

Living Token Evolution is designed so a failure in the blockchain-anchor stage does **not erase the completed AI evolution**.

For example:

```text
AI succeeds
↓
Epoch 4 persisted
↓
Node cannot currently pay anchor fee
↓
Anchor remains queued
↓
Oracle later receives TRU
↓
Anchor retried
↓
Transaction confirmed
```

Likewise, an AI-provider failure does not advance the persisted epoch.

This prevents an unsuccessful evolution attempt from corrupting or skipping the token's evolution history.

---

## Quick Reference

```bash
# STOP tru_advanced first.

# Show latest state
./build-native/bin/tru_evolve_token \
  --token-id f0e6d042 \
  --db /NEW_TRU/build-native/bin/data/utxo \
  --show-latest

# Evolve
./build-native/bin/tru_evolve_token \
  --token-id f0e6d042 \
  --provider nemotron \
  --db /NEW_TRU/build-native/bin/data/utxo

# Restart node
cd ~/NEW_TRU/build-native/bin

./tru_advanced \
  --datadir /NEW_TRU/build-native/bin/data/utxo \
  --cli \
  --rpcport 8332

# Watch anchor
tail -f Tru_debug.log | \
grep --line-buffered -iE 'TokenEvolutionAnchor|anchor_queue|signTransaction'

# Check mempool
curl -sS \
  -H 'Content-Type: application/json' \
  --data '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"getrawmempool",
    "params":{}
  }' \
  http://127.0.0.1:8332/rpc | python3 -m json.tool
```

Your current result containing:

```text
0af06ae9f80d399a8ac41ddeb00ad3a86949498c5adc05bf553a438d2e9d3a6e
```

is exactly the state you'd expect **between anchor submission and the next mined block**. In other words, for your current test, the next meaningful action is to mine a block and verify that transaction leaves the mempool.

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
## Mining with stand alone

```
./tru_miner --node-ip 127.0.0.1 --node-port 8332 --mineraddr 1CaVjWwXheAm74AKLa3KbyLEWAB5L6s49t

./tru_miner_cpu --node-ip 127.0.0.1 --node-port 8332 --mineraddr 1CaVjWwXheAm74AKLa3KbyLEWAB5L6s49t --threads 4

```
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
