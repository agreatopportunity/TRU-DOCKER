#!/usr/bin/env python3
"""
TRU blockchain — patch 7 (CLI status notice)
============================================
Apply AFTER patches 1-6. Touches only main.cpp (cosmetic/UX; no consensus).

PROBLEM
  When token/contract creation fails (e.g. immature-coinbase spend rejected) or
  succeeds, the message is written into the scrolling output region and the very
  next menu redraw paints over it before the user can read it.

FIX
  Add a persistent "status notice" line that is repainted every menu cycle,
  pinned just below the [Chain Info] panel using the same fixed-cursor +
  save/restore technique printChainInfo already uses. Whatever is placed in the
  notice stays visible above the menu until it is replaced -- it cannot be
  clobbered by the menu redraw. Token success and token-error paths set it.

  A small helper `setStatusNotice(text, colorCode)` stores the message; the menu
  loop paints it right after displayMenu(). Row 18 sits just under the 5-line
  Chain Info block (which starts at row 12).

SAFETY MODEL: dated backup main.cpp.<date>.p7.bak, exact-match, aborts if any
anchor is missing, --dry-run / --revert supported.

  python3 apply_tru_fixes_7.py
  python3 apply_tru_fixes_7.py --dry-run
  python3 apply_tru_fixes_7.py --revert
"""

import os, sys, datetime, glob, shutil

DRY    = "--dry-run" in sys.argv
REVERT = "--revert" in sys.argv
TODAY  = datetime.date.today().isoformat()
SUFFIX = "p7"

PATCHES = {}

PATCHES["main.cpp"] = [

# --- 1: global notice state + helper + painter, placed next to g_running -----
(
"""std::atomic<bool> g_running(true);

std::atomic<bool> g_shuttingDown{false};""",
"""std::atomic<bool> g_running(true);

std::atomic<bool> g_shuttingDown{false};

// ---- Persistent CLI status notice (patch 7) --------------------------------
// A sticky message painted below the [Chain Info] panel every menu cycle so it
// is not clobbered by the menu redraw. Set it from anywhere via setStatusNotice.
static std::mutex g_statusNoticeMutex;
static std::string g_statusNotice;      // message text ("" = nothing to show)
static int         g_statusNoticeColor = 33;  // ANSI color code (33=yellow)

void setStatusNotice(const std::string& text, int colorCode = 33) {
    std::lock_guard<std::mutex> lk(g_statusNoticeMutex);
    g_statusNotice = text;
    g_statusNoticeColor = colorCode;
}

// Paints the notice at a fixed position under the Chain Info block (row 18),
// saving/restoring the cursor so it never disturbs menu or input. Wraps long
// messages are avoided by keeping them short; the terminal will clip if needed.
void paintStatusNotice() {
    std::string text; int color;
    {
        std::lock_guard<std::mutex> lk(g_statusNoticeMutex);
        text = g_statusNotice; color = g_statusNoticeColor;
    }
    fmt::print(\"\\033[s\");          // save cursor
    fmt::print(\"\\033[18;1H\");      // row 18, col 1 (just below Chain Info)
    fmt::print(\"\\033[K\");          // clear the line
    if (!text.empty()) {
        fmt::print(\"{}\\n\", colorText(text, color));
        fmt::print(\"\\033[K\");      // clear a possible second line
    }
    fmt::print(\"\\033[u\");          // restore cursor
}"""
),

# --- 2: paint the notice every menu cycle, right after displayMenu -----------
(
"""        displayMenu(rows, coutMutex);
        
        // Move cursor for user input""",
"""        displayMenu(rows, coutMutex);
        paintStatusNotice();  // patch 7: sticky status line under Chain Info
        
        // Move cursor for user input"""
),

# --- 3: token creation success -> set a sticky notice (in addition to banner)
(
"""                    txid = wallet.issueExtendedFT(tokenID, supply, name, symbol, desc, img, decimals, additionalMeta);
                    for (const auto& [key, value] : additionalMeta) tokenDetails[key] = value;
                    displayTokenCreationSuccess(\"FT\", txid, tokenDetails, coutMutex);""",
"""                    txid = wallet.issueExtendedFT(tokenID, supply, name, symbol, desc, img, decimals, additionalMeta);
                    for (const auto& [key, value] : additionalMeta) tokenDetails[key] = value;
                    displayTokenCreationSuccess(\"FT\", txid, tokenDetails, coutMutex);
                    setStatusNotice(\"Token submitted (tx \" + txid.substr(0, 12) +
                                    \"...). PENDING until mined. Keep a miner running.\", 32);"""
),

# --- 4: token creation failure -> sticky red notice that survives the redraw -
(
"""            } catch (const std::exception& e) {
                displayOutputProgressive(outputBuffer, \"[CLI] Failed to issue token: \" + std::string(e.what()), currentRow, rows, coutMutex, 31, true); // Red
            }""",
"""            } catch (const std::exception& e) {
                displayOutputProgressive(outputBuffer, \"[CLI] Failed to issue token: \" + std::string(e.what()), currentRow, rows, coutMutex, 31, true); // Red
                // patch 7: also pin the failure as a sticky notice so it isn't
                // covered by the menu redraw (e.g. immature-coinbase rejection).
                setStatusNotice(\"Token FAILED: \" + std::string(e.what()) +
                                \"  (see node log for details)\", 31);
            }"""
),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
def dated_backup(path):
    base = f"{path}.{TODAY}.{SUFFIX}.bak"
    cand, n = base, 1
    while os.path.exists(cand):
        cand = f"{base}-{n}"; n += 1
    shutil.copy2(path, cand)
    return cand

def revert():
    n = 0
    for fname in PATCHES:
        baks = sorted(glob.glob(f"{fname}.*.{SUFFIX}.bak*"))
        if not baks:
            print(f"  (no p7 backup) {fname}"); continue
        shutil.copy2(baks[-1], fname)
        print(f"  reverted {fname}  <=  {baks[-1]}"); n += 1
    print(f"\nReverted {n} file(s).")

def apply():
    total = 0
    for fname, edits in PATCHES.items():
        if not edits: continue
        if not os.path.exists(fname):
            print(f"!! SKIP {fname}: not found"); continue
        with open(fname, "r", encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
        staged, applied, failed = text, 0, False
        for edit in edits:
            anchor, repl = edit[0], edit[1]
            if anchor not in staged:
                print(f"!! ABORT {fname}: anchor not found (no changes written):")
                print("   " + anchor.strip().splitlines()[0][:80])
                failed = True; break
            staged = staged.replace(anchor, repl, 1); applied += 1
        if failed: continue
        if staged == text:
            print(f"== {fname}: already up to date"); continue
        if DRY:
            print(f"[dry-run] {fname}: {applied} edit(s) would apply"); total += applied; continue
        bak = dated_backup(fname)
        with open(fname, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(staged)
        print(f"OK {fname}: {applied} edit(s) applied   (backup: {bak})"); total += applied
    print(f"\n{'[dry-run] ' if DRY else ''}Total edits: {total}")
    if not DRY and not REVERT:
        print("Rebuild. Token results now pin a sticky line under [Chain Info].")

if __name__ == "__main__":
    print(f"TRU patcher 7 (CLI status notice) — {TODAY}" +
          ("  [DRY RUN]" if DRY else "  [REVERT]" if REVERT else ""))
    print("-" * 60)
    revert() if REVERT else apply()
