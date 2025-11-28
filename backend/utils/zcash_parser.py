def parse_list_tx_text(text: str):
    """
    Extremely simplified parser: we only care about:
      - txid (line with hex, not indented)
      - output lines & memos
      - mined height/time if present
    """
    txs = []
    current_tx = None
    current_output = None

    lines = text.splitlines()
    for line in lines:
        raw = line.rstrip("\n")

        if not raw.strip():
            continue
        if raw.strip().startswith("Transactions:"):
            continue

        # txid: hex, not starting with space
        if not raw.startswith(" ") and all(c in "0123456789abcdefABCDEF" for c in raw.strip()) and len(raw.strip()) >= 32:
            if current_tx:
                txs.append(current_tx)
            current_tx = {
                "txid": raw.strip(),
                "outputs": [],
                "mined_time": None,
            }
            current_output = None
            continue

        if current_tx is None:
            continue

        stripped = raw.strip()

        if stripped.startswith("Mined:"):
            # "Mined: 309972 ... (timestamp)"
            rest = stripped[len("Mined:"):].strip()
            parts = rest.split(" ", 1)
            if len(parts) > 1:
                current_tx["mined_time"] = parts[1].strip("() ")
        elif stripped.startswith("Output "):
            current_output = {"raw_header": stripped}
            # try to pull index
            tokens = stripped.split()
            if len(tokens) >= 2 and tokens[1].isdigit():
                current_output["index"] = int(tokens[1])
            current_tx["outputs"].append(current_output)
        elif stripped.startswith("Memo:") and current_output is not None:
            memo = stripped[len("Memo:"):].strip()
            if "Memo::Text(" in memo:
                start = memo.find("Memo::Text(") + len("Memo::Text(")
                if memo[start:].startswith('"'):
                    start += 1
                end = memo.rfind('")')
                if end == -1:
                    end = len(memo)
                memo = memo[start:end]
            current_output["memo"] = memo

        # NEW: try to pick up amount for the current output
        elif current_output is not None and "ZEC" in stripped:
            # look for something like "0.00005000 ZEC"
            m = re.search(r"([0-9]+\.[0-9]+)\s+ZEC", stripped)
            if m:
                zec_amount = float(m.group(1))
                current_output["amount_zats"] = int(round(zec_amount * 1e8))

    if current_tx:
        txs.append(current_tx)
    return txs
