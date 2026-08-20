# TRU Blockchain White Paper

## Tokenized Real Utility
### A UTXO Proof-of-Work Architecture for Programmable Assets, Stateful Contracts, and Verifiable AI Evolution

**Version 2.0 — August 2026**

---

## Abstract

TRU — **Tokenized Real Utility** — is an independent Layer-1 blockchain designed to combine the ownership and settlement properties of a Bitcoin-style UTXO ledger with programmable state, native tokenization, and verifiable AI-assisted applications.

The TRU protocol is implemented in C++17 and operates its own Proof-of-Work blockchain, transaction model, UTXO set, mempool, peer-to-peer network, block validation, mining software, wallet stack, smart-contract interpreter, token system, AI-oracle subsystem, JSON-RPC interface, command-line tooling, and block explorer.

TRU's design centers on four ideas:

1. **Deterministic ownership and settlement** through a UTXO-based Proof-of-Work chain.
2. **Programmability without abandoning UTXOs**, using a gas-metered script engine with persistent contract state.
3. **Native programmable assets**, including FT, NFT, SFT, NCFT, and TRUSCRIPT inscriptions.
4. **AI as verifiable off-chain computation rather than nondeterministic consensus**, allowing AI responses and evolving token state to be cryptographically committed to the blockchain without requiring every validator to run or trust the same model.

The current implementation uses a 60-second target block interval and TRU's custom `SHA256d + 21E8` Proof-of-Work puzzle. The staged large-block profile supports a 64 MiB consensus block cap, a 56 MiB miner/template assembly budget, and an 80 MiB P2P payload cap. The large-block infrastructure is intentionally configurable, while recognizing that a configured maximum is not equivalent to benchmarked sustainable throughput.

TRU is an evolving independent network. Several advanced components are operational today, while generic external-data opcodes, portions of contract-token functionality, and cross-chain bridge paths remain incomplete. This paper distinguishes implemented functionality from future architecture.

---

# 1. Vision

Blockchain systems have historically tended to optimize around one dominant objective.

Bitcoin prioritizes conservative monetary settlement, independently verifiable ownership, and Proof-of-Work security. General-purpose account-based systems prioritize application programmability. High-throughput chains prioritize rapid execution and parallel processing. AI-oriented networks increasingly add inference, data, or agent functionality on top of distributed ledgers.

TRU takes a different approach.

The objective is to create a blockchain where:

- real and digital assets can be represented natively;
- ownership remains UTXO-based;
- transactions settle through Proof-of-Work;
- contracts can maintain deterministic persistent state;
- token behavior can evolve over time;
- AI systems can contribute computation and metadata;
- AI output can be cryptographically proven to have existed in a specific state;
- validators never need nondeterministic language-model output to agree on block validity.

This is the meaning of **Tokenized Real Utility**.

The chain is intended to act as a deterministic ownership, settlement, and provenance layer for applications whose useful state may extend beyond simple currency transfers.

---

# 2. Design Principles

TRU is built around the following protocol principles.

## 2.1 UTXO Ownership

Assets are controlled through discrete unspent transaction outputs rather than a single global account balance.

This provides:

- explicit spend dependencies;
- deterministic ownership transitions;
- natural double-spend boundaries;
- a transaction graph that can be inspected and validated;
- an architectural path toward parallel validation of independent UTXOs.

## 2.2 Proof-of-Work Settlement

TRU uses Nakamoto-style Proof-of-Work and cumulative chain work for fork choice.

No trusted coordinator determines the canonical chain.

## 2.3 Deterministic Consensus

Consensus-critical execution must produce the same result on every validating node.

Nondeterministic external services — including AI models and live web APIs — therefore do not directly decide whether a TRU block is valid.

## 2.4 Programmable State

TRU extends Bitcoin-style script execution with:

- persistent contract storage;
- gas accounting;
- deterministic chain-state reads;
- caller and contract context;
- modern cryptographic hashes;
- transaction-aware contract execution.

## 2.5 Native Assets

TRU does not treat all tokenization as an external overlay. The wallet and protocol stack contain dedicated support for multiple classes of assets and inscriptions.

## 2.6 Verifiable AI Rather Than AI Consensus

TRU separates AI computation from blockchain consensus.

The model may change. The provider may change. The generated output may be stored outside the blockchain.

What the blockchain preserves is a signed, timestamped, cryptographic commitment connecting the resulting state to TRU's immutable transaction history.

---

# 3. Protocol Overview

## 3.1 Current Chain Parameters

| Parameter | Current TRU Design |
|---|---|
| Chain | TrueChain |
| Native asset | TRU |
| Ledger model | UTXO |
| Consensus | Nakamoto Proof-of-Work |
| PoW puzzle | `SHA256d + 21E8` |
| Base unit | 1 TRU = 100,000,000 satoshis |
| Initial block subsidy | 50 TRU |
| Halving interval | 210,000 blocks |
| Target block interval | 60 seconds |
| Difficulty retarget interval | 60 blocks |
| Retarget adjustment clamp | 0.5× to 2× target movement per interval |
| Coinbase maturity | 100 blocks |
| Maximum monetary supply | 21,000,000 TRU |
| Address format | Base58Check P2PKH |
| Default RPC port | 8332 |
| Default P2P port | 8333 |
| Default explorer port | 8001 |

## 3.2 Staged Large-Block Profile

The current large-block infrastructure uses:

| Layer | Current Staged Limit |
|---|---:|
| Consensus block cap | **64 MiB** |
| Miner/template assembly budget | **56 MiB** |
| P2P framed payload cap | **80 MiB** |

These values are deliberately separate.

The miner/template budget is lower than the consensus cap so block construction leaves room for metadata and serialization overhead. The network payload cap is higher than the consensus cap so a block accepted by consensus is not rejected merely because the transport layer has a lower limit.

The limits are centralized and can be deliberately reconfigured as the network matures.

---

# 4. System Architecture

A TRU deployment consists of a cooperating set of components.

```text
                  +-------------------------+
                  | User / Developer Layer  |
                  | CLI | Qt | tru-cli | RPC|
                  +------------+------------+
                               |
             +-----------------+-----------------+
             |                                   |
      +------v------+                     +------v------+
      | CPU / GPU  |                     | Applications|
      |   Miners   |                     | / Services  |
      +------+-----+                     +------+------+
             |                                   |
             +-----------------+-----------------+
                               |
                     +---------v---------+
                     |      TRU Node     |
                     |   tru_advanced    |
                     +---------+---------+
                               |
      +------------------------+-------------------------+
      |                        |                         |
+-----v------+          +------v------+           +------v------+
| Blockchain |          |   Mempool   |           |  Script VM  |
| Validation |          | Admission / |           | + Contracts |
| / Reorg    |          | Conflicts   |           +------+------+
+-----+------+          +------+------+                  |
      |                        |                         |
      +------------------------+-------------------------+
                               |
              +----------------+----------------+
              |                                 |
       +------v------+                   +------v------+
       | UTXO/State  |                   | AI Oracle   |
       |  LevelDB    |                   | Providers   |
       +------+------+                   +------+------+
              |                                 |
              +----------------+----------------+
                               |
                         +-----v-----+
                         |    P2P    |
                         | Protobuf  |
                         +-----------+
```

The implementation includes:

- blockchain validation and reorganization;
- mempool admission and double-spend handling;
- UTXO management;
- script execution;
- persistent contract state;
- HD wallet functionality;
- CPU and GPU mining;
- P2P synchronization and relay;
- JSON-RPC;
- interactive terminal operation;
- standalone `tru-cli`;
- Qt GUI support;
- HTTP block explorer;
- token creation and transfer;
- AI-provider routing;
- Living Token evolution and blockchain anchoring.

---

# 5. Consensus

## 5.1 Nakamoto Proof-of-Work

TRU selects the valid branch containing the greatest cumulative Proof-of-Work.

Each indexed block contributes work to its parent branch. When a competing branch is discovered, TRU can identify the common ancestor and reorganize when the competing valid chain contains strictly more cumulative work.

This is a cumulative-work rule rather than a simple block-count rule.

## 5.2 SHA256d + 21E8

TRU's Proof-of-Work is based on double SHA-256 with the protocol's `21E8` modification applied consistently to mining and validation.

The same puzzle definition is shared by:

- node block validation;
- multithreaded CPU mining;
- OpenCL GPU mining.

A miner must produce a block hash satisfying the target encoded in the block header's compact `bits` field.

## 5.3 Contextual Block Validation

Before applying a block, the node verifies consensus conditions including:

- structural correctness;
- valid header serialization;
- valid Proof-of-Work;
- expected parent;
- correct height;
- timestamp constraints;
- Median Time Past;
- Merkle root;
- coinbase placement;
- subsidy and fee limits;
- referenced UTXO existence;
- no same-block double spends;
- coinbase maturity;
- script validity;
- transaction value bounds;
- expected difficulty;
- serialized block-size limit.

Only after contextual validation succeeds is chain state applied.

## 5.4 Difficulty Adjustment

The active TRU design targets a block every 60 seconds and recalculates difficulty every 60 blocks.

Difficulty adjustment operates in the compact-target domain used by the full 256-bit mining and validation target.

Adjustment magnitude is constrained so a single retarget cannot move the target more than the configured 0.5× to 2× range.

This prevents abrupt target collapse while allowing the network to adapt to changing mining power.

---

# 6. Transactions and the UTXO Model

TRU transactions follow a Bitcoin-derived structure.

Each input references:

```text
previous transaction ID
output index
unlocking script
```

Each output contains:

```text
amount
locking script
```

A transaction consumes existing UTXOs and creates new UTXOs.

## 6.1 Transaction Identity

A transaction ID is derived from the serialized transaction bytes using double SHA-256.

Incoming peer transactions are independently re-hashed rather than trusting a peer-provided ID.

## 6.2 Signatures

Standard transaction authorization uses ECDSA over secp256k1.

The live interpreter supports:

- `OP_CHECKSIG`;
- `OP_CHECKSIGVERIFY`;
- `OP_CHECKMULTISIG`;
- `OP_CHECKMULTISIGVERIFY`.

## 6.3 Relay Types

TRU recognizes transaction/output patterns including:

- P2PKH;
- P2SH;
- `OP_RETURN`;
- token data;
- inscriptions;
- allow-listed contract scripts.

---

# 7. Programmable UTXO Contracts

TRU extends a Bitcoin-style stack VM rather than replacing the UTXO ledger with a global account runtime.

This produces a hybrid model:

```text
UTXO ownership
      +
script execution
      +
persistent contract state
      +
gas metering
```

## 7.1 Persistent State

`OP_STORE` and `OP_LOAD` allow contract-scoped key/value state to persist across valid state transitions.

Persistent state makes possible applications that cannot be expressed through purely stateless Bitcoin-style locking scripts.

## 7.2 Execution Context

The script execution context can expose:

- current transaction;
- input index;
- current script;
- sighash context;
- sender/caller;
- contract address;
- gas counters;
- execution height;
- deterministic chain reference;
- persistent state;
- validation callbacks.

## 7.3 Gas

TRU uses gas as an execution resource meter.

Simple operations consume less gas while storage, hashing, and signature operations consume more.

The purpose of gas is primarily computational safety: execution must remain bounded and deterministic.

The presence of a gas meter should not be interpreted as a claim that every gas unit currently maps to a particular public-market fee schedule.

## 7.4 Custom Opcodes

| Opcode | Purpose | Current Status |
|---|---|---|
| `OP_BLOCKTIME` | Push current block time | Implemented |
| `OP_CHAINSTATECHECK` | Deterministic chain-state query | Implemented |
| `OP_HASHBLAKE2B` | BLAKE2b-256 | Implemented |
| `OP_SHA3` | SHA3-256 | Implemented |
| `OP_STORE` | Persistent state write | Implemented |
| `OP_LOAD` | Persistent state read | Implemented |
| `OP_CALLER` | Push sender address | Implemented |
| `OP_CONTRACT_ADDR` | Push contract address | Implemented |
| `OP_GAS` | Remaining gas | Implemented |
| `OP_HALT` | Stop execution | Implemented |
| `OP_REVERT` | Revert execution/state | Implemented |
| `OP_OUTPUTAMOUNT` | Current output amount | Implemented |
| `OP_MINT_TOKEN` | Contract-token minting | Implemented |
| `OP_TOKEN_BALANCE` | Contract-token balance | Partial |
| `OP_BURN_TOKEN` | Contract-token burning | Partial |
| `OP_EXTERNALDATA` | Generic off-chain data | Placeholder |
| `OP_DATAFEED` | Generic keyed feed | Placeholder |
| `OP_DELEGATECHECK` | Delegated signature | Stub |
| NOVO bridge opcodes | Wrapped-asset bridge path | Scaffold |
| BSTY bridge opcodes | Wrapped-asset bridge path | Scaffold |

## 7.5 Deterministic External Data Rule

A validator cannot safely call arbitrary web services while executing consensus.

Two nodes could receive:

- different prices;
- different API responses;
- different AI output;
- a timeout on one machine;
- a successful response on another.

TRU therefore does **not** treat the generic `OP_EXTERNALDATA` and `OP_DATAFEED` placeholders as production live-oracle consensus features.

External information must ultimately be committed, signed, or otherwise made deterministic before consensus relies on it.

---

# 8. Native Asset System

TRU supports multiple token classes as first-class wallet and transaction concepts.

## 8.1 Fungible Token — FT

FTs provide:

- configurable supply;
- configurable decimal precision;
- name and symbol;
- description;
- media/metadata references;
- UTXO-based ownership and transfer.

Typical uses include:

- utility credits;
- rewards;
- digital currencies;
- application-specific units.

## 8.2 Non-Fungible Token — NFT

NFTs represent unique assets with an issuance amount of one.

Potential uses include:

- digital collectibles;
- certificates;
- ownership records;
- unique real-world assets;
- art and media.

## 8.3 Sentient Fungible Token — SFT

SFTs combine fungibility with AI-oriented or evolving metadata.

Their purpose is broader than the conventional meaning of "semi-fungible token." Within TRU, **SFT refers to Sentient Fungible Token**.

SFTs can be used for:

- evolving limited-edition assets;
- AI-assisted digital objects;
- stateful membership or utility assets;
- agent-associated token states.

## 8.4 Neural Canvas Fungible Token — NCFT

NCFTs are designed around dynamic or AI-oriented digital media and metadata.

Potential applications include:

- evolving digital artwork;
- generative media;
- transferable AI-assisted experiences;
- dynamic digital twins or representations.

## 8.5 Token Ownership

Token creation and transfer use ordinary blockchain transactions funded by TRU UTXOs.

Token metadata and ownership information are persisted and indexed by the node/wallet stack.

---

# 9. TRUSCRIPT

TRUSCRIPT provides on-chain text/data inscription functionality.

An inscription can retain information including:

- inscription identity;
- ordering/index;
- satoshi association;
- timestamp;
- current ownership;
- transfer history.

TRUSCRIPT is integrated with wallet and RPC operations so inscriptions can be created, inspected, tracked, and transferred.

---

# 10. AI Architecture

## 10.1 The Consensus Problem with AI

Modern AI models are nondeterministic computational systems.

Even when given the same prompt:

```text
Model A may return response X
Model B may return response Y
The same model may return response Z later
```

If block validity depended on independently rerunning an LLM, honest validators could disagree.

TRU therefore treats AI as an **off-chain computation service whose result can be anchored into deterministic blockchain state**.

## 10.2 AI Request / Response Flow

```text
TRU AI request
      |
      v
AI Provider Registry
      |
      +-------------------------+
      |                         |
      v                         v
Local / Private              Cloud
AI providers                 AI providers
      |                         |
      +------------+------------+
                   |
                   v
              AI response
                   |
          +--------+--------+
          |                 |
          v                 v
Full response          SHA-256 digest
storage                    |
                           v
                     TRU anchor TX
                           |
                           v
                       Mempool
                           |
                           v
                     Mined block
```

The chain does not need to store an arbitrarily large AI response directly.

Instead, a compact on-chain record can commit to the response hash and related metadata.

## 10.3 Provider Independence

TRU's provider layer can route to configured systems including:

### Local / Private

- Nemotron;
- Ollama;
- Oobabooga;
- custom JSON or OpenAI-compatible endpoints.

### Cloud

- OpenAI;
- Anthropic / Claude;
- xAI / Grok;
- Google Gemini.

The AI provider can change without changing Proof-of-Work consensus.

## 10.4 AI Credentials

Provider credentials are local application secrets.

They are not intended to become part of blockchain state.

Oracle wallet credentials and AI API credentials are distinct secrets and must be protected separately.

---

# 11. Living Token Evolution

Living Token Evolution is now an implemented TRU subsystem rather than only a future concept.

Supported tokens can evolve off-chain metadata while preserving a verifiable sequence of state transitions.

## 11.1 Evolution Flow

```text
Token Epoch N
      |
      v
Load current metadata
      |
      v
Selected AI provider
      |
      v
Generate new state
      |
      v
Token Epoch N+1
      |
      +---------------------------+
      |                           |
      v                           v
Persist full state         Hash old + new state
                                  |
                                  v
                          Build anchor transaction
                                  |
                                  v
                               Sign
                                  |
                                  v
                              Mempool
                                  |
                                  v
                           Blockchain block
```

## 11.2 Evolution Commitment

A compact evolution commitment can include:

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

This creates an auditable chain:

```text
State A
  -> State B
      -> State C
          -> State D
```

without requiring every generated document, image, model context, or AI artifact to be stored directly in every blockchain block.

## 11.3 Why This Matters

A blockchain token can represent more than a static row of metadata.

A Living Token can become a persistent digital object whose state changes while its provenance remains cryptographically linked to the chain.

Potential applications include:

- AI agents;
- game characters;
- equipment digital twins;
- vehicle/service histories;
- supply-chain objects;
- evolving art;
- adaptive memberships;
- digital identity;
- machine-learning provenance;
- AI-generated content history.

---

# 12. Large-Block Scaling

TRU's current scaling direction emphasizes increasing base-layer capacity while preserving deterministic block validation.

## 12.1 Size-Aware Construction

A miner should never blindly copy an arbitrarily large mempool into a candidate block.

TRU's large-block construction path limits transaction selection before mining:

```text
Mempool
   |
   v
Transaction selection
   |
   v
Assembly-size accounting
   |
   v
Configured budget reached
   |
   +----> remaining TX stay in mempool
   |
   v
Candidate block
```

## 12.2 Three Coordinated Limits

Large blocks require more than changing a single consensus constant.

TRU coordinates:

1. consensus block cap;
2. mining/template assembly cap;
3. P2P message capacity.

This avoids the failure mode where a node accepts a large block locally but cannot relay it to peers.

## 12.3 Configurable Capacity

The current staged profile is 64 MiB.

A reusable block-size configuration utility can adjust the coordinated limits for future network upgrades.

Under the current P2P Frame V1, controlled configurations up to approximately 3 GiB can be represented while preserving relay headroom.

## 12.4 Why 4 GiB+ Requires More Work

The present P2P framing uses a 32-bit payload-length field.

A true 4 GiB payload cannot be represented safely in that field, especially after transport/serialization overhead.

Future very-large-block operation therefore requires P2P Frame V2 or equivalent architecture, likely including:

- 64-bit length metadata;
- chunked or streamed blocks;
- bounded peer buffering;
- incremental decoding;
- incremental/disk-backed processing;
- explicit protocol-version negotiation.

## 12.5 Capacity Is Not Throughput

A 1 GiB configured block limit does **not** prove that the network can sustainably process 1 GiB blocks every minute.

Actual scalability depends on:

- signature verification;
- script execution;
- UTXO access;
- disk writes;
- LevelDB behavior;
- block assembly;
- network propagation;
- peer bandwidth;
- reorganization performance;
- memory pressure;
- hardware diversity.

TRU therefore treats benchmarked throughput and configured capacity as different measurements.

---

# 13. Path to Parallel Validation

The UTXO model creates a useful scaling property.

Consider:

```text
TX A spends UTXO A
TX B spends UTXO B
TX C spends UTXO C
```

If these transactions do not conflict, much of their validation can theoretically occur concurrently.

TRU's current implementation should not be described as a fully parallel execution engine comparable to architectures built around parallel execution from inception.

However, the protocol model provides a development path toward:

- parallel signature checking;
- independent script validation;
- UTXO conflict partitioning;
- deterministic batched state commitment.

Parallel validation is therefore a **scaling direction**, not a current throughput claim.

---

# 14. P2P Network

TRU nodes communicate over TCP using framed, checksummed Protobuf messages.

Message families include:

- `VERSION`;
- `VERACK`;
- `ADDR`;
- `INV`;
- `GETDATA`;
- `BLOCK`;
- `TX`;
- `PING`;
- `PONG`;
- `HEIGHT`;
- `GET_BLOCK`;
- `GET_HEIGHT`;
- `BLOCK_NOT_FOUND`.

Current network behavior includes:

- node handshake;
- peer tracking;
- transaction relay;
- block relay;
- height-based synchronization;
- stale-peer handling;
- per-IP controls;
- incoming transaction revalidation;
- payload checksum verification;
- large-write handling that retries partial TCP sends.

The public P2P service uses port `8333` by default.

---

# 15. Persistence and Storage

TRU uses LevelDB for UTXO and state persistence.

The storage layer includes:

- Snappy compression;
- caching;
- thread-safe access;
- batched writes;
- prefix iteration;
- compaction;
- repair;
- integrity verification;
- checksums on persisted values.

The persistent data model supports:

- UTXOs;
- coinbase maturity metadata;
- contract state;
- token metadata;
- token ownership;
- inscriptions;
- AI/evolution state where applicable.

---

# 16. Wallet and User Interfaces

TRU provides multiple ways to interact with the network.

## 16.1 HD Wallet

The wallet core supports hierarchical deterministic key generation and transaction signing.

Functionality includes:

- address creation;
- UTXO discovery;
- TRU balance;
- transaction creation;
- signing;
- token issuance;
- token transfer;
- TRUSCRIPT;
- contract creation;
- private-key import.

## 16.2 Interactive Node Interface

Running:

```bash
./tru_advanced --cli
```

opens the interactive node interface.

The current terminal interface contains a responsive menu system. It can switch between full and compact layouts with:

```text
M
```

or:

```text
m
```

The interface exposes operations for:

- wallets;
- addresses and private keys;
- TRU transfers;
- CPU/GPU mining;
- chain information;
- peers;
- block lookup;
- FT/NFT/SFT/NCFT;
- TRUSCRIPT;
- AI tokens;
- contracts;
- bridge scaffolding;
- mempool inspection;
- contract state;
- voting functionality;
- token minting;
- synchronization.

The interface also includes a live mining dashboard reporting information such as hashrate, height, blocks found, reward, difficulty, and activity.

## 16.3 Standalone `tru-cli`

`tru-cli` is a separate scriptable RPC client.

Examples:

```bash
./tru-cli getinfo
./tru-cli getbalance
./tru-cli getblockcount
./tru-cli getchaininfo
./tru-cli getpeerinfo
./tru-cli getrawmempool
```

The `raw` command can pass through arbitrary node RPC calls:

```bash
./tru-cli raw getblocktemplate
```

This separates interactive operator use from shell scripting and automation.

## 16.4 Qt GUI

TRU also contains Qt-based desktop wallet/interface functionality for graphical operation.

---

# 17. JSON-RPC and Developer Interface

The node exposes JSON-RPC over HTTP, normally at:

```text
127.0.0.1:8332/rpc
```

Representative method groups include:

## Chain

```text
getinfo
getchaininfo
getblockcount
getblock
getblockbyheight
getblocktemplate
submitblock
```

## Transactions

```text
sendrawtransaction
createrawtransaction
signrawtransactionwithkey
gettransaction
getrawtransaction
decoderawtransaction
gettxout
listtransactions
getrawmempool
```

## Wallet

```text
getbalance
getnewaddress
listaddresses
listunspent
```

## Tokens

```text
issuetoken
sendtoken
gettokenutxo
gettokenmetadata
verifytokenbalance
```

## TRUSCRIPT

```text
inscribeTRUScript
transferTRUScript
getTRUScripts
getTRUScriptDetails
```

## Contracts

```text
createsmartcontract
createcontracttransaction
getcontracts
createmagiclock
unlockmagiclock
listmagiclocks
```

## Mining

```text
startmining
registerminer
unregisterminer
getminerstatus
getallminers
reportmineractivity
```

## AI

```text
configureAIProvider
getAIProviders
createAIToken
interactWithAIToken
getAIResponse
getAITokenState
trainAIToken
```

## Identity / Social

```text
createDID
createsocialpost
```

RPC is an application-control interface and is distinct from the public P2P port.

---

# 18. Explorer

TRU includes an HTTP block explorer capable of displaying and serving information for:

- blocks;
- transactions;
- addresses;
- tokens;
- contracts;
- miners;
- chain statistics.

Representative API paths include:

```text
/api/stats
/api/blocks
/api/addresses
/api/transactions
/api/tokens
/api/contracts
/api/miners
```

The explorer can operate alongside the node or as a dedicated explorer process depending on deployment.

---

# 19. Docker and Deployment

TRU can be packaged into container images for repeatable node and miner deployment.

Current image roles include:

```text
tru-node
tru-miner-cpu
tru-miner-gpu
```

Containerized nodes persist chain data through Docker volumes and load machine-specific configuration through `tru.conf`.

The reference operational network currently uses multiple hosts, including a public seed node, a GPU-capable peer, and a native development/explorer host.

Container releases can be published as immutable numbered tags while `latest` points to the newest build.

---

# 20. Economic Model

## 20.1 Native Asset

TRU is the chain's native unit.

The current monetary schedule includes:

```text
Initial subsidy: 50 TRU
Halving:         every 210,000 blocks
Maximum supply:  21,000,000 TRU
Precision:       8 decimal places
```

## 20.2 Miner Revenue

A valid coinbase may claim:

```text
block subsidy + eligible transaction fees
```

Coinbase outputs mature after 100 blocks.

## 20.3 Fees

Transactions, token issuance, AI anchor transactions, and other network operations can require spendable TRU UTXOs.

This whitepaper intentionally does not declare a permanent market-wide fee schedule where the current implementation does not establish one as a fixed protocol-economic rule.

Fee policy can evolve independently from the fundamental 21-million-TRU monetary schedule where consensus permits.

---

# 21. Security Model

## 21.1 Proof-of-Work

Chain security depends on distributed mining power and the cumulative-work fork-choice rule.

Like other Proof-of-Work networks, an early or low-hashrate network is materially less resistant to majority-hash attacks than a mature network with substantial independent mining.

Large transaction capacity does not itself create Proof-of-Work security.

## 21.2 Deterministic Validation

Consensus-critical functions are designed to be reproducible by validating nodes.

AI and generic external-service calls are kept outside block-validity decisions unless their data can be made deterministic through committed/signed mechanisms.

## 21.3 Smart-Contract Safety

Gas bounds execution.

Stateful operations should be tested against:

- invalid signatures;
- unauthorized writes;
- malformed scripts;
- rollback behavior;
- gas exhaustion;
- conflicting UTXOs;
- reorganization.

## 21.4 Key Security

Sensitive material includes:

- wallet private keys;
- `tru.dat`;
- seed files;
- wallet index/identity files;
- oracle WIF;
- AI API credentials.

These must not be committed to public source repositories.

## 21.5 RPC Security

The current RPC interface does not provide native HTTP authentication.

Therefore:

```text
8333 P2P -> intended for peer networking
8332 RPC -> keep private / loopback / authenticated proxy
```

## 21.6 Implementation Maturity

TRU is presently an independent single-implementation chain.

It has not received the years of public adversarial testing, independent implementations, security research, or economic attack exposure of mature major blockchains.

Production maturity will benefit from:

- independent code review;
- fuzzing;
- multi-node adversarial testnets;
- consensus test vectors;
- independent node implementation;
- reproducible builds;
- formal release processes;
- external security audit.

---

# 22. Current Implementation Status

## 22.1 Implemented

The current codebase implements:

- independent Layer-1 blockchain;
- Nakamoto Proof-of-Work;
- SHA256d + 21E8 mining/validation;
- cumulative-work fork choice;
- chain reorganization;
- 60-second target blocks;
- difficulty retargeting;
- UTXO persistence;
- mempool validation;
- P2P synchronization;
- single-signature ECDSA;
- multisignature ECDSA;
- stateful contracts;
- gas accounting;
- deterministic chain-state opcode;
- SHA3;
- BLAKE2b;
- FT;
- NFT;
- SFT;
- NCFT;
- TRUSCRIPT;
- AI provider registry;
- local and cloud AI routing;
- AI response anchoring;
- Living Token Evolution;
- blockchain evolution commitments;
- CPU mining;
- OpenCL GPU mining;
- HD wallet;
- interactive responsive CLI;
- full/compact `M/m` terminal menu;
- live mining dashboard;
- standalone `tru-cli`;
- JSON-RPC;
- HTTP explorer;
- Docker deployment;
- size-aware large-block construction;
- large-message P2P send handling.

## 22.2 Partial / Scaffolded

The following should not yet be described as complete production capabilities:

- `OP_EXTERNALDATA`;
- `OP_DATAFEED`;
- `OP_DELEGATECHECK`;
- `OP_TOKEN_BALANCE`;
- `OP_BURN_TOKEN`;
- NOVO bridge;
- BSTY bridge.

---

# 23. Applications

TRU's architecture is designed to support applications where blockchain ownership and external evolving state intersect.

## 23.1 Real-World Asset Records

A token can represent:

- equipment;
- property interests;
- certificates;
- service rights;
- memberships;
- warranties;
- tracked physical assets.

Blockchain history can record ownership or state commitments while larger documents remain off-chain.

## 23.2 AI Agents

A token or contract can provide an identity anchor for an AI agent.

Evolution epochs can establish a verifiable state timeline even if the underlying model changes.

## 23.3 Digital Twins

Machines, vehicles, equipment, or facilities can be represented by evolving digital objects whose historical state hashes are anchored to TRU.

## 23.4 Dynamic Media

NCFT/Living Token architecture can represent art or media that changes over time while retaining verifiable provenance.

## 23.5 Gaming

Game items and characters can maintain ownership and evolution history separate from a single game server.

## 23.6 Supply Chain

Asset states, inspections, document hashes, events, and ownership transitions can be tied together using token ownership, contract state, and signed external commitments.

## 23.7 AI Provenance

Generated text, analysis, media, or machine decisions can be stored externally while a cryptographic digest is committed to TRU.

The blockchain then proves that a specific digest was associated with a particular transaction and time in chain history.

---

# 24. Scaling Roadmap

TRU's current large-block work establishes capacity controls, not the end state of network scaling.

Priority scaling areas include:

## Phase A — Measurement

- transaction-generation benchmark tools;
- mempool admission measurements;
- transfer TPS;
- token TPS;
- contract TPS;
- block validation timing;
- state-commit timing;
- propagation timing.

## Phase B — Parallel Validation

- independent transaction classification;
- parallel signature verification;
- parallel script execution where UTXOs do not conflict;
- deterministic result commitment.

## Phase C — Mempool and Block Assembly

- indexed conflicts;
- dependency-aware ordering;
- fee/priority policies;
- bounded resource use;
- high-volume template construction.

## Phase D — P2P Frame V2

- streamed/chunked block transport;
- 64-bit total-length representation;
- bounded buffers;
- incremental block verification;
- backpressure;
- protocol negotiation.

## Phase E — Storage

- large-state profiling;
- cache tuning;
- snapshot/recovery research;
- faster initial sync;
- pruning strategies where appropriate.

## Phase F — Adversarial Scale Testing

- multi-node WAN testing;
- malformed block floods;
- transaction spam;
- deep reorganization testing;
- network partition/recovery;
- heterogeneous hardware.

The target is not merely to configure large blocks. The objective is to demonstrate sustainable, reproducible throughput under real network conditions.

---

# 25. AI Roadmap

The next stages of TRU's AI architecture can focus on strengthening verifiability rather than embedding nondeterministic inference into consensus.

Potential directions include:

- multiple independent oracle operators;
- signed AI attestations;
- oracle reputation;
- quorum responses;
- deterministic canonicalization;
- model/version provenance;
- trusted execution environments;
- proof-of-inference research;
- zkML or other verifiable-computation systems where practical;
- decentralized storage for full AI artifacts;
- stronger linkage between token evolution and signed real-world events.

The principle remains:

> **Consensus proves the commitment; AI produces the computation.**

---

# 26. Governance and Protocol Change

TRU does not currently need to claim a fixed on-chain governance structure that the implementation does not enforce.

Protocol changes should instead be treated according to their technical effect.

Examples:

### Non-consensus application change

A CLI display improvement may require only a software update.

### Consensus expansion

Increasing maximum accepted block size allows new blocks that older nodes may reject.

All network nodes should upgrade before miners produce blocks exceeding the previous limit.

### Consensus restriction

Reducing a block-size limit can make previously valid large history invalid during revalidation if historical blocks exceed the new rule.

### Fundamental consensus change

Changing Proof-of-Work, difficulty interpretation, transaction validity, or historical state rules may require coordinated activation or a fresh chain depending on the change.

A formal TRU Improvement Proposal process can be introduced when the network and contributor base are sufficiently developed. This paper does not invent voting percentages or treasury allocations that are not presently enforced by the protocol.

---

# 27. Comparison of Design Philosophy

TRU is not intended to be a direct clone of BTC, BSV, Ethereum, or Solana.

Its architecture occupies a different design space.

```text
Bitcoin-style concepts
    UTXO
    PoW
    explicit ownership
             |
             v
          TRU L1
             |
      +------+------+
      |             |
      v             v
Stateful         Native
contracts        assets
      |             |
      +------+------+
             |
             v
       AI commitments
             |
             v
      Living Tokens /
      evolving state
```

TRU's differentiating thesis is the combination of:

- UTXO settlement;
- Proof-of-Work;
- persistent contract state;
- native specialized tokens;
- AI provider abstraction;
- cryptographic AI provenance;
- evolving asset state.

The ultimate competitiveness of that architecture depends not only on features, but also on:

- network effect;
- security;
- independent miners;
- node diversity;
- sustained throughput;
- developer tooling;
- applications;
- economic activity.

---

# 28. Conclusion

TRU began from a Bitcoin-style UTXO foundation but has evolved into a broader programmable blockchain architecture.

Its present system combines:

```text
UTXO ownership
+
Nakamoto Proof-of-Work
+
stateful smart contracts
+
native FT / NFT / SFT / NCFT assets
+
TRUSCRIPT
+
AI provider abstraction
+
on-chain AI commitments
+
Living Token Evolution
+
CPU/GPU mining
+
large-block infrastructure
+
wallet / CLI / RPC / explorer tooling
```

The core architectural principle is deliberate:

**The blockchain remains deterministic even when the applications using it are intelligent, dynamic, and externally connected.**

AI systems can change. Models can improve. Data can live outside the chain. Applications can evolve.

TRU's role is to preserve the cryptographic ownership, state transitions, provenance, and settlement history connecting those systems over time.

That is the foundation of **Tokenized Real Utility**.

---

# Appendix A — Current Technical Summary

| Feature | Current State |
|---|---|
| UTXO ledger | Implemented |
| Nakamoto PoW | Implemented |
| PoW puzzle | SHA256d + 21E8 |
| Target block interval | 60 seconds |
| Difficulty interval | 60 blocks |
| Current staged block cap | 64 MiB |
| Current assembly budget | 56 MiB |
| Current P2P payload cap | 80 MiB |
| Configurable current Frame V1 block sizing | Up to 3 GiB with coordinated limits |
| 4 GiB+ | Requires P2P Frame V2 / streaming architecture |
| ECDSA secp256k1 | Implemented |
| Multisig | Implemented |
| Persistent contract state | Implemented |
| Gas metering | Implemented |
| FT | Implemented |
| NFT | Implemented |
| SFT | Implemented |
| NCFT | Implemented |
| TRUSCRIPT | Implemented |
| AI providers | Implemented |
| AI anchoring | Implemented |
| Living Token Evolution | Implemented |
| CPU miner | Implemented |
| OpenCL GPU miner | Implemented |
| HD wallet | Implemented |
| Interactive CLI | Implemented |
| `tru-cli` | Implemented |
| Qt GUI | Implemented |
| JSON-RPC | Implemented |
| Explorer | Implemented |
| Docker deployment | Implemented |
| Generic external-data opcode | Placeholder |
| Delegate opcode | Stub |
| Cross-chain bridges | Scaffold |
| Independent consensus implementation | Not yet |
| Third-party security audit | Not yet |
| Fully parallel validation engine | Future scaling work |
| P2P Frame V2 | Future scaling work |

---

# Appendix B — Network Interfaces

Default ports:

```text
8332  JSON-RPC
8333  P2P
8001  Explorer
```

Recommended exposure:

```text
P2P 8333: public when operating a reachable peer
RPC 8332: private / loopback / authenticated proxy
Explorer 8001: expose according to deployment requirements
```

---

# Appendix C — Representative AI Providers

```text
Local / Private
  Nemotron
  Ollama
  Oobabooga
  Custom endpoints

Cloud
  OpenAI
  Anthropic / Claude
  xAI / Grok
  Google Gemini
```

Provider availability depends on node/application configuration.

---

# Appendix D — Legal and Risk Notice

This white paper is technical and informational documentation.

It is not financial advice, an investment recommendation, a promise of future value, or an offer to buy or sell any security or financial instrument.

TRU is an evolving software project and independent blockchain. Software defects, cryptographic failures, implementation errors, network attacks, consensus failures, regulatory changes, market conditions, loss of private keys, and other risks can result in loss of access or value.

Statements describing roadmap items, potential applications, scaling directions, or future protocol work are goals and architectural directions, not guarantees.

Users, developers, miners, and operators should independently evaluate the software and applicable legal requirements before relying on the network for material value.

---

# Project

**TRU — Tokenized Real Utility**

Website: `https://tokenizedrealutility.com`

Source repository / public community links should be added to this document only when the final public endpoints are selected.

---

*TRU — UTXO ownership. Proof-of-Work settlement. Stateful contracts. Native assets. Verifiable AI evolution.*
