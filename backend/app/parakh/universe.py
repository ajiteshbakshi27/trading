"""
NSE universe: symbols, plain-English aliases (for the idea parser) and
sector themes (for event impact maps). Index symbols use Yahoo's tickers.

Survivorship note: this is *today's* list of large, liquid names. Any
backtest over it inherits survivorship bias, and the backtester says so.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# symbol -> (display name, sector, aliases)
STOCKS: Dict[str, tuple] = {
    "RELIANCE": ("Reliance Industries", "energy", ["reliance", "ril"]),
    "TCS": ("Tata Consultancy Services", "it", ["tcs", "tata consultancy"]),
    "INFY": ("Infosys", "it", ["infosys", "infy"]),
    "HCLTECH": ("HCL Technologies", "it", ["hcl", "hcl tech"]),
    "WIPRO": ("Wipro", "it", ["wipro"]),
    "TECHM": ("Tech Mahindra", "it", ["tech mahindra", "techm"]),
    "HDFCBANK": ("HDFC Bank", "bank_private", ["hdfc bank", "hdfcbank", "hdfc"]),
    "ICICIBANK": ("ICICI Bank", "bank_private", ["icici bank", "icici"]),
    "KOTAKBANK": ("Kotak Mahindra Bank", "bank_private", ["kotak", "kotak bank"]),
    "AXISBANK": ("Axis Bank", "bank_private", ["axis bank", "axis"]),
    "INDUSINDBK": ("IndusInd Bank", "bank_private", ["indusind"]),
    "SBIN": ("State Bank of India", "bank_psu", ["sbi", "state bank", "sbin"]),
    "BANKBARODA": ("Bank of Baroda", "bank_psu", ["bank of baroda", "bob"]),
    "PNB": ("Punjab National Bank", "bank_psu", ["pnb", "punjab national"]),
    "BAJFINANCE": ("Bajaj Finance", "nbfc", ["bajaj finance", "bajfinance"]),
    "BAJAJFINSV": ("Bajaj Finserv", "nbfc", ["bajaj finserv"]),
    "SHRIRAMFIN": ("Shriram Finance", "nbfc", ["shriram"]),
    "HINDUNILVR": ("Hindustan Unilever", "fmcg", ["hul", "hindustan unilever"]),
    "ITC": ("ITC", "fmcg", ["itc"]),
    "NESTLEIND": ("Nestle India", "fmcg", ["nestle"]),
    "BRITANNIA": ("Britannia", "fmcg", ["britannia"]),
    "DABUR": ("Dabur", "fmcg", ["dabur"]),
    "MARUTI": ("Maruti Suzuki", "auto", ["maruti", "maruti suzuki"]),
    "TATAMOTORS": ("Tata Motors", "auto", ["tata motors"]),
    "M&M": ("Mahindra & Mahindra", "auto", ["mahindra", "m&m", "m and m"]),
    "BAJAJ-AUTO": ("Bajaj Auto", "auto", ["bajaj auto"]),
    "EICHERMOT": ("Eicher Motors", "auto", ["eicher", "royal enfield"]),
    "ESCORTS": ("Escorts Kubota", "agri", ["escorts"]),
    "SUNPHARMA": ("Sun Pharma", "pharma", ["sun pharma", "sunpharma"]),
    "DRREDDY": ("Dr Reddy's", "pharma", ["dr reddy", "drreddy"]),
    "CIPLA": ("Cipla", "pharma", ["cipla"]),
    "LT": ("Larsen & Toubro", "infra", ["l&t", "larsen", "lt"]),
    "ULTRACEMCO": ("UltraTech Cement", "cement", ["ultratech"]),
    "ADANIPORTS": ("Adani Ports", "infra", ["adani ports"]),
    "ADANIENT": ("Adani Enterprises", "infra", ["adani enterprises", "adani ent"]),
    "NTPC": ("NTPC", "power", ["ntpc"]),
    "POWERGRID": ("Power Grid", "power", ["power grid", "powergrid"]),
    "TATAPOWER": ("Tata Power", "power", ["tata power"]),
    "ONGC": ("ONGC", "oil_upstream", ["ongc"]),
    "BPCL": ("BPCL", "oil_marketing", ["bpcl", "bharat petroleum"]),
    "IOC": ("Indian Oil", "oil_marketing", ["ioc", "indian oil"]),
    "ASIANPAINT": ("Asian Paints", "paints", ["asian paints", "asianpaint"]),
    "INDIGO": ("InterGlobe Aviation", "aviation", ["indigo", "interglobe"]),
    "TATASTEEL": ("Tata Steel", "metals", ["tata steel"]),
    "JSWSTEEL": ("JSW Steel", "metals", ["jsw steel", "jsw"]),
    "HINDALCO": ("Hindalco", "metals", ["hindalco"]),
    "HAL": ("Hindustan Aeronautics", "defence", ["hal", "hindustan aeronautics"]),
    "BEL": ("Bharat Electronics", "defence", ["bel", "bharat electronics"]),
    "DLF": ("DLF", "realty", ["dlf"]),
    "GODREJPROP": ("Godrej Properties", "realty", ["godrej properties"]),
    "BHARTIARTL": ("Bharti Airtel", "telecom", ["airtel", "bharti"]),
    "ZOMATO": ("Zomato (Eternal)", "consumer_tech", ["zomato", "eternal"]),
    "PAYTM": ("Paytm", "consumer_tech", ["paytm"]),
    "ANGELONE": ("Angel One", "capital_markets", ["angel one", "angel"]),
    "BSE": ("BSE Ltd", "capital_markets", ["bse ltd", "bse share"]),
    "CDSL": ("CDSL", "capital_markets", ["cdsl"]),
    "TITAN": ("Titan", "consumer", ["titan"]),
}

# index symbol -> (display name, yahoo ticker, aliases)
INDICES: Dict[str, tuple] = {
    "NIFTY": ("NIFTY 50", "^NSEI", ["nifty", "nifty 50", "nifty50"]),
    "BANKNIFTY": ("NIFTY Bank", "^NSEBANK", ["bank nifty", "banknifty", "nifty bank"]),
    "SENSEX": ("SENSEX", "^BSESN", ["sensex"]),
}


def is_index(symbol: str) -> bool:
    return symbol.upper() in INDICES


def yahoo_ticker(symbol: str) -> str:
    s = symbol.upper().strip()
    if s in INDICES:
        return INDICES[s][1]
    if s.endswith(".NS") or s.endswith(".BO") or s.startswith("^"):
        return s
    return f"{s}.NS"


def normalize(symbol: str) -> str:
    s = symbol.upper().strip()
    for suf in (".NS", ".BO"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def display_name(symbol: str) -> str:
    s = normalize(symbol)
    if s in STOCKS:
        return STOCKS[s][0]
    if s in INDICES:
        return INDICES[s][0]
    return s


def sector_of(symbol: str) -> Optional[str]:
    s = normalize(symbol)
    if s in STOCKS:
        return STOCKS[s][1]
    if s == "BANKNIFTY":
        return "bank_private"
    return None


def alias_table() -> List[tuple]:
    """(alias, symbol) pairs, longest alias first so 'bank nifty' beats 'nifty'."""
    pairs = []
    for sym, (_, _, aliases) in STOCKS.items():
        pairs += [(a, sym) for a in aliases]
        pairs.append((sym.lower(), sym))
    for sym, (_, _, aliases) in INDICES.items():
        pairs += [(a, sym) for a in aliases]
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def search(query: str, limit: int = 10) -> List[Dict[str, str]]:
    q = query.lower().strip()
    out = []
    for sym, (name, sector, aliases) in STOCKS.items():
        if q in sym.lower() or q in name.lower() or any(q in a for a in aliases):
            out.append({"symbol": sym, "name": name, "sector": sector, "kind": "stock"})
    for sym, (name, _, aliases) in INDICES.items():
        if q in sym.lower() or q in name.lower() or any(q in a for a in aliases):
            out.append({"symbol": sym, "name": name, "sector": "index", "kind": "index"})
    return out[:limit]
