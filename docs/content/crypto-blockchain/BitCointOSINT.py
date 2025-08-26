# Bitcoin_DarkWeb_OSINT
# Analysis of Bitcoin transactions on the Dark Web

import argparse
import requests
import networkx as nx

# ======================
# CONFIGURATION
# ======================
WEBHOSE_ACCESS_TOKEN = "INSERT_YOUR_API_KEY_HERE"

BLACKLIST = [
    "4a6kzlzytb4ksafk.onion",
    "blockchainbdgpzk.onion"
]

WEBHOSE_BASE_URL = "http://webhose.io"
WEBHOSE_DARKWEB_URL = f"/darkFilter?token={WEBHOSE_ACCESS_TOKEN}&format=json&q="

BLOCK_EXPLORER_URL = "https://blockexplorer.com/api/addrs/"

# ======================
# ARGUMENT PARSER
# ======================
parser = argparse.ArgumentParser(
    description='Collect and visualize Bitcoin transactions and related hidden services.'
)
parser.add_argument(
    "--graph",
    help="Output filename of the graph file. Default: bitcoingraph.gexf",
    nargs='?',  # Makes the value optional
    const="bitcoingraph.gexf",  # If provided without value, use default
    default="bitcoingraph.gexf"
)
parser.add_argument(
    "--address",
    help="A bitcoin address to begin the search on.",
    required=True
)
parser.add_argument(
    "--webhose-token",
    help="Your Webhose.io API token (overrides default in script)."
)

args = parser.parse_args()

bitcoin_address = args.address
graph_file = args.graph
if args.webhose_token:
    WEBHOSE_ACCESS_TOKEN = args.webhose_token
    WEBHOSE_DARKWEB_URL = f"/darkFilter?token={WEBHOSE_ACCESS_TOKEN}&format=json&q="

# ======================
# FUNCTIONS
# ======================

def get_all_transactions(bitcoin_address):
    """Retrieve all Bitcoin transactions for a Bitcoin address."""
    transactions = []
    from_number = 0
    to_number = 50

    while True:
        url = f"{BLOCK_EXPLORER_URL}{bitcoin_address}/txs?from={from_number}&to={to_number}"
        response = requests.get(url)
        try:
            results = response.json()
        except Exception:
            print(f"[!] Error retrieving Bitcoin transactions for {bitcoin_address}.")
            break

        if results.get('totalItems', 0) == 0:
            print(f"[*] No transactions for {bitcoin_address}")
            break

        transactions.extend(results.get('items', []))

        if len(transactions) >= results.get('totalItems', 0):
            break

        from_number += 50
        to_number += 50

    print(f"[*] Retrieved {len(transactions)} bitcoin transactions.")
    return transactions


def get_unique_bitcoin_addresses(transaction_list):
    """Return all unique Bitcoin addresses from a transaction list."""
    bitcoin_addresses = []

    for transaction in transaction_list:
        # Check sender
        sender = transaction['vin'][0].get('addr')
        if sender and sender not in bitcoin_addresses:
            bitcoin_addresses.append(sender)

        # Check all recipients
        for receiving_side in transaction.get('vout', []):
            script_pub_key = receiving_side.get('scriptPubKey', {})
            if "addresses" in script_pub_key:
                for address in script_pub_key['addresses']:
                    if address not in bitcoin_addresses:
                        bitcoin_addresses.append(address)

    print(f"[*] Identified {len(bitcoin_addresses)} unique bitcoin addresses.")
    return bitcoin_addresses


def search_webhose(bitcoin_addresses):
    """Search Webhose.io for each Bitcoin address and map to hidden services."""
    bitcoin_to_hidden_services = {}
    count = 1

    for btc_address in bitcoin_addresses:
        print(f"[*] Searching {count} of {len(bitcoin_addresses)} bitcoin addresses.")

        search_url = WEBHOSE_BASE_URL + WEBHOSE_DARKWEB_URL + btc_address
        response = requests.get(search_url)
        result = response.json()

        while result.get('totalResults', 0) > 0:
            for search_result in result.get('darkposts', []):
                bitcoin_to_hidden_services.setdefault(btc_address, [])
                site = search_result.get('source', {}).get('site')
                if site and site not in bitcoin_to_hidden_services[btc_address]:
                    bitcoin_to_hidden_services[btc_address].append(site)

            if result['totalResults'] <= 10:
                break

            query = btc_address
            for hs in bitcoin_to_hidden_services[btc_address]:
                query += f" -site:{hs}"
            for hs in BLACKLIST:
                query += f" -site:{hs}"

            search_url = WEBHOSE_BASE_URL + WEBHOSE_DARKWEB_URL + query
            response = requests.get(search_url)
            result = response.json()

        if btc_address in bitcoin_to_hidden_services:
            print(f"[*] Discovered {len(bitcoin_to_hidden_services[btc_address])} hidden services connected to {btc_address}")

        count += 1

    return bitcoin_to_hidden_services


def build_graph(source_bitcoin_address, transaction_list, hidden_services):
    """Build a GEXF graph of transactions and hidden services."""
    graph = nx.DiGraph()

    for transaction in transaction_list:
        sender = transaction['vin'][0].get('addr')
        if not sender:
            continue

        if sender == source_bitcoin_address:
            graph.add_node(sender, type="Target Bitcoin Address")
        else:
            graph.add_node(sender, type="Bitcoin Address")

        for receiving_side in transaction.get('vout', []):
            script_pub_key = receiving_side.get('scriptPubKey', {})
            if "addresses" in script_pub_key:
                for address in script_pub_key['addresses']:
                    if address == source_bitcoin_address:
                        graph.add_node(address, type="Target Bitcoin Wallet")
                    else:
                        graph.add_node(address, type="Bitcoin Wallet")
                    graph.add_edge(sender, address)

    for btc_address, services in hidden_services.items():
        for service in services:
            if service not in BLACKLIST:
                graph.add_node(service, type="Hidden Service")
                graph.add_edge(btc_address, service)

    nx.write_gexf(graph, graph_file)
    print(f"[*] Graph saved to {graph_file}")


# ======================
# MAIN EXECUTION
# ======================
print(f"[*] Retrieving all transactions from the blockchain for {bitcoin_address}")
transaction_list = get_all_transactions(bitcoin_address)

if transaction_list:
    bitcoin_addresses = get_unique_bitcoin_addresses(transaction_list)
    hidden_services = search_webhose(bitcoin_addresses)
    build_graph(bitcoin_address, transaction_list, hidden_services)
    print("[*] Done! Open the graph file in Gephi or similar for visualization.")
else:
    print("[!] No transactions found.")
