"""
Category tagger — Phase 1 (rule-based, no AI needed yet)
Assigns a spending category to each transaction using keyword matching.
Phase 2 will replace/augment this with Claude AI.
"""

import re
import pandas as pd

# ---------------------------------------------------------------------------
# Rules: (category, subcategory, keywords/patterns)
# Order matters — first match wins.
# ---------------------------------------------------------------------------
RULES = [
    # Payments / transfers
    ("Income",       "Payment received",  [r"payment\s*-\s*thank you", r"e-?transfer", r"payroll", r"salary", r"deposit"]),
    ("Transfer",     "Refund / return",   [r"refund", r"return", r"chargeback"]),

    # Travel
    ("Travel",       "Flights",           [r"air can", r"expedia", r"airbnb", r"klm", r"thai airw", r"flight"]),
    ("Travel",       "Airport",           [r"airport", r"don mueang", r"suvarnabhumi", r"yyz", r"pearson"]),
    ("Travel",       "Ride sharing",      [r"uber.*trip", r"grab", r"bolt", r"lyft", r"taxi"]),
    ("Travel",       "Transit",           [r"presto", r"ttc", r"go train", r"mrt", r"bts", r"transit"]),
    ("Travel",       "Accommodation",     [r"hotel", r"marriott", r"hilton", r"airbnb"]),
    ("Travel",       "Route stop",        [r"onroute"]),

    # Food & Drink
    ("Food & Drink", "Groceries",         [r"tops\b", r"big c", r"makro", r"loblaws", r"sobeys", r"metro\b", r"no frills", r"walmart"]),
    ("Food & Drink", "Restaurants",       [r"sansotei", r"kinton ramen", r"pho ", r"kaka japanese", r"big way hot pot",
                                           r"elvis suki", r"panda express", r"gigli", r"nuru nuru", r"home ekkamai",
                                           r"mjtx?\b", r"mjt-", r"tst-", r"sq \*"]),
    ("Food & Drink", "Fast food",         [r"mcdonald", r"kfc", r"subway\b", r"burger king", r"tim horton"]),
    ("Food & Drink", "Coffee",            [r"starbucks", r"sbux", r"tim horton", r"balzac", r"crave coffee",
                                           r"cafe\b", r"caffe\b", r"coffee", r"chagee"]),
    ("Food & Drink", "Bubble tea",        [r"gotcha", r"chatime", r"tiger sugar", r"bubble tea"]),
    ("Food & Drink", "Delivery",          [r"ubereats", r"uber.*eats", r"doordash", r"skip.*dishes", r"foodpanda"]),
    ("Food & Drink", "Convenience store", [r"7[- ]?11", r"seven eleven", r"circle k", r"family mart", r"coca cola"]),
    ("Food & Drink", "Bar / alcohol",     [r"lcbo", r"wine", r"beer", r"brewery", r"brewers", r"rwco", r"liquor",
                                           r"tokyo smoke"]),

    # Shopping
    ("Shopping",     "Department store",  [r"winners", r"marshalls", r"dollarama", r"dollar tree"]),
    ("Shopping",     "Fashion",           [r"victoria.*secret", r"h&m", r"zara", r"uniqlo", r"tricolour outlet"]),
    ("Shopping",     "Electronics",       [r"primetech", r"apple", r"best buy", r"it city", r"jib\b"]),
    ("Shopping",     "Optical",           [r"optic", r"optical", r"eyewear", r"lenscrafters", r"clearly"]),
    ("Shopping",     "Books",             [r"bookstore", r"chapters", r"indigo", r"amazon.*book"]),
    ("Shopping",     "General",           [r"amazon", r"amz_", r"shopee", r"lazada"]),

    # Health & Fitness
    ("Health",       "Pharmacy",          [r"shoppers drug", r"rexall", r"boots\b", r"watsons", r"pharmacy"]),
    ("Health",       "Gym / fitness",     [r"la fitness", r"goodlife", r"fitness", r"gym"]),
    ("Health",       "Salon / spa",       [r"salon", r"salonedivita", r"spa\b", r"nail", r"beauty"]),

    # Subscriptions / Digital
    ("Subscriptions", "Streaming",        [r"youtube", r"netflix", r"spotify", r"disney", r"apple.*tv", r"hulu"]),
    ("Subscriptions", "Ride membership",  [r"uberone", r"uber.*memb"]),
    ("Subscriptions", "Software / SaaS",  [r"google\b", r"microsoft", r"adobe", r"dropbox", r"notion"]),

    # Entertainment
    ("Entertainment", "Bars / nightlife", [r"warehouse", r"yonge street warehouse", r"bar\b", r"pub\b", r"club\b"]),
    ("Entertainment", "General",          [r"cinema", r"netflix", r"ticketmaster"]),

    # Services
    ("Services",     "Cibo / airport",    [r"cibo express"]),
]

_COMPILED = [
    (cat, sub, [re.compile(kw, re.IGNORECASE) for kw in keywords])
    for cat, sub, keywords in RULES
]


def tag(description: str) -> tuple[str, str]:
    """Return (category, subcategory) for a transaction description."""
    for cat, sub, patterns in _COMPILED:
        if any(p.search(description) for p in patterns):
            return cat, sub
    return "Other", "Uncategorized"


def tag_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'category' and 'subcategory' columns to a parsed DataFrame."""
    df = df.copy()
    tags = df["description"].apply(tag)
    df["category"]    = tags.apply(lambda t: t[0])
    df["subcategory"] = tags.apply(lambda t: t[1])
    return df
