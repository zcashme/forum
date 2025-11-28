import subprocess
import os
import sys
import argparse
import re
# <-- Removed datetime import

# --- CONFIGURATION ---
# Path to the zcash-devtool repository folder
DEVTOOL_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "zcash-devtool")
# ---------------------

def run_command(command, capture_output=False):
    """
    Runs a subprocess command from within the DEVTOOL_PATH.
    """
    print("-" * 70)
    print(f"Running: {' '.join(command)}")
    print(f"In directory: {DEVTOOL_PATH}")
    print("-" * 70)
    
    if not os.path.exists(DEVTOOL_PATH):
        print(f"Error: zcash-devtool path not found at: {DEVTOOL_PATH}", file=sys.stderr)
        print("Please make sure the 'zcash-devtool' folder is in the same directory as this script.", file=sys.stderr)
        sys.exit(1)
    
    try:
        if capture_output:
            # Used for list-tx where we want to capture the text
            result = subprocess.run(
                command,
                cwd=DEVTOOL_PATH,  # Run from the devtool directory
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True
            )
            return result.stdout
        else:
            # Used for init, sync, enhance
            with subprocess.Popen(
                command,
                cwd=DEVTOOL_PATH,  # Run from the devtool directory
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, 
                text=True,
                encoding='utf-8',
                bufsize=1
            ) as proc:
                if proc.stdout:
                    for line in proc.stdout:
                        print(line, end='') 
                proc.wait() 
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, command)
        
        print("\n" + "-" * 70)
        print("Command finished successfully.")
        print("-" * 70 + "\n")
        return None

    except subprocess.CalledProcessError as e:
        print(f"\n" + "=" * 70, file=sys.stderr)
        print(f"ERROR: Command failed with exit code {e.returncode}", file=sys.stderr)
        print(f"Failed Command: {' '.join(e.cmd)}", file=sys.stderr)
        if hasattr(e, 'stdout') and e.stdout:
            print("\n--- Output ---", file=sys.stderr)
            print(e.stdout, file=sys.stderr)
        if hasattr(e, 'stderr') and e.stderr:
            print("\n--- Error Output ---", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(1) # Exit the script on failure
    except FileNotFoundError:
        print(f"Error: 'cargo' command not found. Is Rust installed and in your PATH?", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Automate zcash-devtool to read a view key and export transactions."
    )
    parser.add_argument(
        "--key", 
        required=True, 
        help="The Unified Full Viewing Key (ufvk) or Sapling Extended Full Viewing Key (zxviews...)."
    )
    parser.add_argument(
        "--birthday", 
        required=True, 
        type=int, 
        help="The wallet birthday height (e.g., 3000000)."
    )
    parser.add_argument(
        "--wallet-dir", 
        required=True, 
        help="Path to the wallet folder (e.g., ./wallets/my-sapling-wallet)."
    )
    parser.add_argument(
        "--name", 
        required=True, 
        help="A name for the wallet account (e.g., MySaplingWallet)."
    )
    parser.add_argument(
        "--output-prefix", 
        required=True, 
        help="The prefix for the output file (e.g., './exports/sapling_export' will create './exports/sapling_export.txt')."
    )
    parser.add_argument(
        "--server", 
        default="zecrocks", 
        help="The lightwalletd server to use (default: zecrocks)."
    )
    
    args = parser.parse_args()

    # --- FIX: Convert all paths to ABSOLUTE paths ---
    args.wallet_dir = os.path.abspath(args.wallet_dir)
    args.output_prefix = os.path.abspath(args.output_prefix)
    # ------------------------------------------------
    
    # --- Automatically create directories ---
    wallet_parent_dir = os.path.dirname(args.wallet_dir)
    if wallet_parent_dir:
        os.makedirs(wallet_parent_dir, exist_ok=True)
        
    output_parent_dir = os.path.dirname(args.output_prefix)
    if output_parent_dir:
        os.makedirs(output_parent_dir, exist_ok=True)

    cargo_base = ["cargo", "run", "--release", "--"]

    # --- Step 1: Initialize Wallet (if it doesn't exist) ---
    if not os.path.exists(args.wallet_dir):
        print(f"Wallet folder '{args.wallet_dir}' not found. Creating it...")
        init_cmd = cargo_base + [
            "wallet", "-w", args.wallet_dir,
            "init-fvk",
            "--name", args.name,
            "--fvk", args.key,
            "--birthday", str(args.birthday),
            "-s", args.server,
            "--disable-tor"
        ]
        run_command(init_cmd)
    else:
        print(f"Wallet folder '{args.wallet_dir}' already exists. Skipping initialization.")

    # --- Step 2: Sync Wallet ---
    print("Syncing wallet...")
    sync_cmd = cargo_base + [
        "wallet", "-w", args.wallet_dir,
        "sync",
        "-s", args.server
    ]
    run_command(sync_cmd)

    # --- Step 3: Enhance Transactions (to get memos) ---
    print("Enhancing transactions to decrypt memos...")
    enhance_cmd = cargo_base + [
        "wallet", "-w", args.wallet_dir,
        "enhance",
        "-s", args.server,
        "--disable-tor"
    ]
    run_command(enhance_cmd)

    # --- Step 4: Export TXT File ---
    
    # --- MODIFICATION: Removed timestamp ---
    txt_filename = f"{args.output_prefix}.txt"
    # -------------------------------------
    
    print(f"Exporting transaction list to '{txt_filename}'...")
    list_tx_txt_cmd = cargo_base + [
        "wallet", "-w", args.wallet_dir,
        "list-tx"
    ]
    
    txt_output = run_command(list_tx_txt_cmd, capture_output=True)
    try:
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(txt_output)
        print(f"Successfully saved '{txt_filename}'")
    except Exception as e:
        print(f"Error writing to {txt_filename}: {e}", file=sys.stderr)
        sys.exit(1)

        
    print("\n" + "=" * 70)
    print("Automation complete!")
    print(f"Output file created:\n- {txt_filename}")
    print("=" * 70)

if __name__ == "__main__":
    main()