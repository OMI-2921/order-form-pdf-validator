import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from rapidfuzz import fuzz
from difflib import SequenceMatcher


def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = unicodedata.normalize(
        "NFKC",
        text
    )

    text = text.lower()

    # -----------------------------------------------------
    # Normalize common PDF characters
    # -----------------------------------------------------

    text = text.replace("’", "'")
    text = text.replace("`", "'")
    text = text.replace("–", "-")
    text = text.replace("—", "-")

    # -----------------------------------------------------
    # PDF line breaks
    # -----------------------------------------------------

    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # The PDF may extract bullets as "n".
    # We DO NOT want that "n" to become real content.
    # -----------------------------------------------------

    text = re.sub(
        r"(^|\s)n(?=\s)",
        " ",
        text
    )

    # -----------------------------------------------------
    # Separators
    # -----------------------------------------------------

    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    text = re.sub(
        r"-+",
        " ",
        text
    )

    # -----------------------------------------------------
    # Remove remaining punctuation
    # -----------------------------------------------------

    text = re.sub(
        r"[^\w%#'\s]",
        " ",
        text
    )

    # -----------------------------------------------------
    # Apostrophe differences ignored
    # -----------------------------------------------------

    text = text.replace(
        "'",
        ""
    )

    # -----------------------------------------------------
    # Multiple spaces
    # -----------------------------------------------------

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def compact_text(text):

    return normalize_text(
        text
    ).replace(
        " ",
        ""
    )


def tokenize(text):

    value = normalize_text(
        text
    )

    if not value:
        return []

    return value.split()


# =========================================================
# FIELD TYPE DETECTION
#
# This is NOT deciding what to check.
# The user-selected field is always checked.
#
# This only helps us locate the correct variable
# information inside the PDF.
# =========================================================


def get_field_type(field_name):

    field = normalize_text(field_name)

    compact = (
        field
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )

    # RN / Registration Number — check early so it cannot
    # accidentally be classified as a general field.
    if (
        compact in {"rn", "rnno", "rnnumber"}
        or compact.startswith("rnno")
        or compact.startswith("rnnumber")
        or "registrationnumber" in compact
        or "companyrn" in compact
    ):
        return "RN"

    # Country of Origin
    if (
        "coo" in compact
        or "countryoforigin" in compact
        or "countryorigin" in compact
        or "madein" in compact
        or compact == "origin"
        or compact.endswith("origin")
    ):
        return "COO"

    # Fiber / Fabric / Content
    if (
        "fiber" in compact
        or "fibre" in compact
        or "fabric" in compact
        or "content" in compact
        or "composition" in compact
        or "fabrication" in compact
    ):
        return "CONTENT"

    # Care / Washing
    if (
        "care" in compact
        or "wash" in compact
        or "washing" in compact
        or "laundry" in compact
        or "instruction" in compact
    ):
        return "CARE"

    # Size — includes OSZ / size-line fields
    if (
        "size" in compact
        or compact.startswith("osz")
        or "sizeline" in compact
        or "alpha" in compact
        or "waist" in compact
        or "inseam" in compact
        or "fit" in compact
    ):
        return "SIZE"

    if "brand" in compact:
        return "BRAND"

    if "color" in compact or "colour" in compact:
        return "COLOR"

    if "gender" in compact:
        return "GENDER"

    if (
        "attribute" in compact
        or "technology" in compact
        or "feature" in compact
        or "description" in compact
    ):
        return "ATTRIBUTE"

    return "GENERAL"

# =========================================================
# FIELD LANGUAGE / REGION DETECTION
# =========================================================

def get_field_region(field_name):

    field = normalize_text(
        field_name
    )

    compact = field.replace(
        " ",
        ""
    )

    # English

    if (
        "_en" in str(field_name).lower()
        or compact.endswith("en")
        or "english" in compact
    ):

        return "EN"


    # French / Canada

    if (
        "_fr" in str(field_name).lower()
        or compact.endswith("fr")
        or "french" in compact
        or "canada" in compact
    ):

        return "FR"


    # Spanish

    if (
        "_sp" in str(field_name).lower()
        or compact.endswith("sp")
        or "spanish" in compact
        or "espanol" in compact
        or "span" in compact
    ):

        return "SP"


    return ""


# =========================================================
# LOAD EXCEL
# =========================================================

def load_excel(file):

    file.seek(0)

    df = pd.read_excel(
        file,
        header=0
    )

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    return df


# =========================================================
# LOAD PDF
# =========================================================

def load_pdf(file):

    file.seek(0)

    pdf_bytes = file.read()

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(
        document
    ):

        text = page.get_text(
            "text"
        )

        pages.append(
            {
                "page": page_number + 1,
                "text": text
            }
        )

    document.close()

    return pages


# =========================================================
# CLEAN PDF LINE
# =========================================================

def clean_pdf_line(line):

    if not line:
        return ""

    line = str(line).strip()

    # -----------------------------------------------------
    # Remove PDF bullet/keystroke "n"
    #
    # Examples:
    #
    # n US :
    # n CA :
    # n MX :
    #
    # becomes:
    #
    # US :
    # CA :
    # MX :
    # -----------------------------------------------------

    line = re.sub(
        r"^\s*n\s+(?=[A-Za-z])",
        "",
        line
    )

    return line.strip()


# =========================================================
# CREATE SMART PDF BLOCKS
# =========================================================

def create_pdf_blocks(page_text):

    if not page_text:
        return []

    raw_lines = page_text.splitlines()

    lines = []

    for raw_line in raw_lines:

        line = clean_pdf_line(
            raw_line
        )

        if not line:
            continue

        if len(line) > 1500:
            continue

        lines.append(
            line
        )


    if not lines:
        return []


    blocks = []


    # -----------------------------------------------------
    # INDIVIDUAL LINES
    #
    # Important because many variable fields are contained
    # inside one PDF line.
    # -----------------------------------------------------

    for line in lines:

        blocks.append(
            line
        )


    # -----------------------------------------------------
    # ADJACENT LINE BLOCKS
    #
    # Used for wrapped care/content text.
    # -----------------------------------------------------

    maximum = min(
        8,
        len(lines)
    )

    for size in range(
        2,
        maximum + 1
    ):

        for start in range(
            len(lines) - size + 1
        ):

            block = " ".join(
                lines[
                    start:start + size
                ]
            )

            if block:

                blocks.append(
                    block
                )


    # -----------------------------------------------------
    # Full page is deliberately NOT used as the primary
    # comparison block.
    #
    # This prevents unrelated static/regional information
    # from being mixed with variable data.
    # -----------------------------------------------------


    # -----------------------------------------------------
    # Remove duplicates
    # -----------------------------------------------------

    unique = []

    seen = set()

    for block in blocks:

        normalized = normalize_text(
            block
        )

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        unique.append(
            block
        )

    return unique


# =========================================================
# EXACT MATCH
# =========================================================


def exact_match(expected, actual):

    expected_normalized = normalize_text(expected)
    actual_normalized = normalize_text(actual)

    if not expected_normalized or not actual_normalized:
        return False

    expected_tokens = tokenize(expected)
    actual_tokens = tokenize(actual)

    if not expected_tokens:
        return False

    # -----------------------------------------------------
    # SHORT / SINGLE-TOKEN VALUES
    #
    # Examples:
    # 2, 4, 8, S, M, L, XL, XXL
    #
    # These MUST be standalone tokens. This prevents:
    # 2  -> matching RN# 55285
    # 8  -> matching 55285
    # M  -> matching MADE
    # -----------------------------------------------------
    if len(expected_tokens) == 1:
        expected_value = expected_tokens[0]

        if (
            expected_value.isdigit()
            or len(expected_value) <= 4
        ):
            return expected_value in actual_tokens

    # -----------------------------------------------------
    # NORMAL CASE-INSENSITIVE / SEPARATOR-TOLERANT MATCH
    # -----------------------------------------------------
    if expected_normalized in actual_normalized:
        return True

    # Space-independent match is only safe for meaningful
    # multi-character values.
    expected_compact = compact_text(expected)
    actual_compact = compact_text(actual)

    if (
        expected_compact
        and len(expected_compact) > 4
        and expected_compact in actual_compact
    ):
        return True

    return False


def get_match_key(value):

    normalized = normalize_text(value)

    if not normalized:
        return ""

    tokens = tokenize(value)

    if len(tokens) == 1:
        return f"TOKEN:{tokens[0]}"

    return f"TEXT:{normalized}"

# =========================================================
# EXPECTED VALUE SEARCH
# =========================================================


def search_exact_value(expected, pdf_blocks, used_block_keys=None):
    if used_block_keys is None:
        used_block_keys = set()

    expected_key = get_match_key(expected)

    for block in pdf_blocks:
        block_key = normalize_text(block)

        if not block_key or block_key in used_block_keys:
            continue

        if exact_match(expected, block):
            return {
                "status": "PASS",
                "pdf": block,
                "difference": "—",
                "score": 100,
                "match_key": expected_key,
                "block_key": block_key
            }

    return None

# =========================================================
# FIELD ANCHORS
#
# These help us locate the relevant variable value.
# They prevent static information from being treated as
# a mismatch.
# =========================================================

FIELD_ANCHORS = {

    "COO": [
        "made in",
        "hecho en",
        "fabrique en",
        "madein"
    ],

    "CONTENT": [
        "shell",
        "liner",
        "body",
        "fabric",
        "fiber",
        "fibre",
        "content",
        "composition",
        "exterior",
        "extérieur",
        "forro",
        "doublure"
    ],

    "CARE": [
        "machine wash",
        "wash",
        "lavar",
        "laver",
        "dry clean",
        "bleach",
        "blanchiment",
        "detergent",
        "detergente"
    ],

    "RN": [
        "rn",
        "ca"
    ],

    "SIZE": [
        "size"
    ],

    "COLOR": [
        "color",
        "colour"
    ],

    "BRAND": [
        "brand"
    ],

    "GENDER": [
        "girls",
        "boys",
        "women",
        "men",
        "unisex"
    ],

    "ATTRIBUTE": [
        "attribute",
        "technology",
        "feature"
    ],

    "GENERAL": []
}


# =========================================================
# CHECK IF BLOCK IS RELEVANT TO FIELD
# =========================================================

def is_relevant_block(
    block,
    field_type,
    field_name,
    expected
):

    normalized_block = normalize_text(
        block
    )

    if not normalized_block:
        return False


    # -----------------------------------------------------
    # Field-specific anchors
    # -----------------------------------------------------

    anchors = FIELD_ANCHORS.get(
        field_type,
        []
    )


    for anchor in anchors:

        anchor_norm = normalize_text(
            anchor
        )

        if (
            anchor_norm
            and
            anchor_norm in normalized_block
        ):

            return True


    # -----------------------------------------------------
    # Language-specific clues
    #
    # Only used when the selected field name explicitly
    # indicates a language.
    # -----------------------------------------------------

    region = get_field_region(
        field_name
    )


    if region == "EN":

        english_markers = [
            "made in",
            "machine wash",
            "shell",
            "liner",
            "polyester",
            "span dex",
            "bleach"
        ]

        for marker in english_markers:

            if normalize_text(marker) in normalized_block:

                return True


    if region == "FR":

        french_markers = [
            "laver",
            "machine",
            "extérieur",
            "doublure",
            "polyester",
            "élasthanne",
            "sans chlore"
        ]

        for marker in french_markers:

            if normalize_text(marker) in normalized_block:

                return True


    if region == "SP":

        spanish_markers = [
            "lavar",
            "máquina",
            "maquina",
            "cuerpo",
            "forro",
            "poliéster",
            "poliester",
            "cloro",
            "hecho en"
        ]

        for marker in spanish_markers:

            if normalize_text(marker) in normalized_block:

                return True


    return False


# =========================================================
# TOKEN OVERLAP
# =========================================================

def token_overlap(
    expected,
    actual
):

    expected_tokens = set(
        tokenize(expected)
    )

    actual_tokens = set(
        tokenize(actual)
    )

    if not expected_tokens:
        return 0

    common = (
        expected_tokens
        &
        actual_tokens
    )

    return (
        len(common)
        /
        len(expected_tokens)
    )


# =========================================================
# DIFFERENCE
# =========================================================

def get_difference(
    expected,
    actual
):

    expected_tokens = tokenize(
        expected
    )

    actual_tokens = tokenize(
        actual
    )

    if not expected_tokens:
        return "Content differs."

    if not actual_tokens:
        return "Expected value is missing from PDF."

    matcher = SequenceMatcher(
        None,
        expected_tokens,
        actual_tokens
    )

    differences = []

    for tag, a1, a2, b1, b2 in matcher.get_opcodes():

        if tag == "equal":
            continue


        expected_part = " ".join(
            expected_tokens[a1:a2]
        )

        actual_part = " ".join(
            actual_tokens[b1:b2]
        )


        if tag == "replace":

            differences.append(
                f"{expected_part} → {actual_part}"
            )


        elif tag == "delete":

            differences.append(
                f"Missing: {expected_part}"
            )


        elif tag == "insert":

            # IMPORTANT:
            #
            # Extra static PDF content should NOT become
            # a failure automatically.
            #
            # Therefore inserted words are only shown when
            # they occur inside a relevant candidate.

            differences.append(
                f"Extra: {actual_part}"
            )


    if not differences:

        return "Content differs."

    return "; ".join(
        differences[:8]
    )


# =========================================================
# FIND PROBABLE VARIABLE MISMATCH
#
# This is the most important new function.
#
# We DO NOT compare the Order Form value against the
# entire PDF.
#
# We only consider PDF blocks relevant to the selected
# variable field.
# =========================================================


def search_probable_mismatch(
    expected,
    pdf_blocks,
    field_name,
    used_block_keys=None
):
    if used_block_keys is None:
        used_block_keys = set()

    expected_normalized = normalize_text(expected)
    expected_tokens = tokenize(expected)

    if not expected_tokens:
        return None

    field_type = get_field_type(field_name)

    # Never fuzzy-match short single-token values.
    if len(expected_tokens) == 1:
        short_value = expected_tokens[0]
        if short_value.isdigit() or len(short_value) <= 4:
            return None

    candidates = []

    for block in pdf_blocks:
        block_key = normalize_text(block)

        if not block_key or block_key in used_block_keys:
            continue

        if is_relevant_block(
            block,
            field_type,
            field_name,
            expected
        ):
            candidates.append(block)

    if not candidates:
        return None

    best = None

    for block in candidates:
        actual_normalized = normalize_text(block)
        actual_tokens = tokenize(block)

        if not actual_tokens:
            continue

        ratio = fuzz.ratio(expected_normalized, actual_normalized)
        partial = fuzz.partial_ratio(expected_normalized, actual_normalized)
        token_ratio = fuzz.token_set_ratio(
            expected_normalized,
            actual_normalized
        )
        overlap = token_overlap(expected, block)

        score = (
            ratio * 0.35
            + partial * 0.20
            + token_ratio * 0.25
            + overlap * 100 * 0.20
        )

        expected_word_count = len(expected_tokens)

        # Strong country-of-origin comparison.
        if field_type == "COO":
            expected_has_made_in = "made in" in expected_normalized
            actual_has_made_in = "made in" in actual_normalized

            if expected_has_made_in and actual_has_made_in:
                expected_country = re.sub(
                    r"^.*?made in\s+",
                    "",
                    expected_normalized
                ).strip()

                actual_country = re.sub(
                    r"^.*?made in\s+",
                    "",
                    actual_normalized
                ).strip()

                if expected_country and actual_country:
                    country_similarity = fuzz.ratio(
                        expected_country,
                        actual_country
                    )

                    if country_similarity < 95:
                        return {
                            "status": "FAIL",
                            "pdf": block,
                            "difference": get_difference(expected, block),
                            "score": score,
                            "match_key": get_match_key(expected),
                            "block_key": normalize_text(block)
                        }

        if expected_word_count <= 2:
            acceptable = score >= 80 and overlap >= 0.50
        elif expected_word_count <= 5:
            acceptable = score >= 70 and overlap >= 0.40
        else:
            acceptable = score >= 65 and overlap >= 0.30

        if not acceptable:
            continue

        if best is None or score > best["score"]:
            best = {
                "status": "FAIL",
                "pdf": block,
                "difference": get_difference(expected, block),
                "score": score,
                "match_key": get_match_key(expected),
                "block_key": normalize_text(block)
            }

    return best

# =========================================================
# CHECK ONE VARIABLE FIELD
# =========================================================


def check_field(
    expected,
    pdf_blocks,
    field_name,
    used_block_keys=None
):
    if used_block_keys is None:
        used_block_keys = set()

    if expected is None or str(expected).strip() == "":
        return {
            "status": "SKIP",
            "pdf": "—",
            "difference": "No variable data in Order Form.",
            "match_key": "",
            "block_key": ""
        }

    expected = str(expected).strip()

    exact = search_exact_value(
        expected,
        pdf_blocks,
        used_block_keys
    )

    if exact:
        return exact

    probable = search_probable_mismatch(
        expected,
        pdf_blocks,
        field_name,
        used_block_keys
    )

    if probable:
        return probable

    return {
        "status": "NOT FOUND",
        "pdf": "Not found in relevant PDF area",
        "difference": "Selected variable value was not detected.",
        "match_key": "",
        "block_key": ""
    }

# =========================================================
# PFL PANEL SUPPORT
# =========================================================

def get_pfl_panel_blocks(page_text):
    """
    PFL mode treats panel-numbered artwork as a continuous stream.
    Panel labels such as 1, 2, 3 or PANEL 1 / PANEL 2 are removed
    from the comparison content. The extracted lines are then grouped
    into larger blocks so text split at a panel boundary can be found.
    """
    if not page_text:
        return []

    raw_lines = page_text.splitlines()
    cleaned = []

    panel_pattern = re.compile(
        r"^\s*(?:panel\s*)?(\d{1,3})\s*$",
        re.IGNORECASE
    )

    for raw in raw_lines:
        line = clean_pdf_line(raw)
        if not line:
            continue
        if len(line) > 1500:
            continue

        # Ignore standalone panel sequence numbers.
        if panel_pattern.match(line):
            continue

        # Ignore common textual panel labels.
        if re.match(r"^\s*panel\s*[-#:]?\s*\d{1,3}\s*$", line, re.IGNORECASE):
            continue

        cleaned.append(line)

    if not cleaned:
        return []

    blocks = list(cleaned)

    # Larger windows are the important part for PFL because a value
    # may begin near the end of one panel and continue into the next.
    maximum = min(24, len(cleaned))

    for size in range(2, maximum + 1):
        for start in range(len(cleaned) - size + 1):
            block = " ".join(cleaned[start:start + size])
            if block:
                blocks.append(block)

    unique = []
    seen = set()

    for block in blocks:
        normalized = normalize_text(block)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(block)

    return unique


def get_comparison_blocks(page_text, product_type):
    if product_type == "PFL":
        return get_pfl_panel_blocks(page_text)
    return create_pdf_blocks(page_text)


# =========================================================
# BUILD REPORT
#
# PAGE 1 → EXCEL ROW 2
# PAGE 2 → EXCEL ROW 3
# PAGE 3 → EXCEL ROW 4
# =========================================================


def build_report(
    df,
    pdf_pages,
    selected_fields,
    product_type
):
    results = []
    field_no = 1

    for page_index, page in enumerate(pdf_pages):
        excel_index = page_index

        if excel_index >= len(df):
            for field in selected_fields:
                results.append(
                    {
                        "FIELD NO": field_no,
                        "PDF PAGE": page["page"],
                        "EXCEL ROW": "N/A",
                        "FIELD": field,
                        "ORDER FORM DATA": "No Excel row",
                        "PDF OUTPUT": "No corresponding Order Form row",
                        "STATUS": "NOT FOUND",
                        "DIFFERENCE": "No corresponding Excel row."
                    }
                )
                field_no += 1
            continue

        row = df.iloc[excel_index]

        pdf_blocks = get_comparison_blocks(
            page["text"],
            product_type
        )

        # A matched PDF block can only be used once on a page.
        used_block_keys = set()

        for field in selected_fields:
            value = row[field]

            if pd.isna(value):
                value = ""
            else:
                value = str(value).strip()

            if not value:
                results.append(
                    {
                        "FIELD NO": field_no,
                        "PDF PAGE": page["page"],
                        "EXCEL ROW": excel_index + 2,
                        "FIELD": field,
                        "ORDER FORM DATA": "",
                        "PDF OUTPUT": "—",
                        "STATUS": "SKIP",
                        "DIFFERENCE": (
                            "Blank Order Form value — "
                            "PDF content ignored."
                        )
                    }
                )
                field_no += 1
                continue

            result = check_field(
                value,
                pdf_blocks,
                field,
                used_block_keys
            )

            # Lock the exact PDF candidate after it has been
            # assigned to this field.
            if result["status"] in ["PASS", "FAIL"]:
                block_key = result.get("block_key", "")
                if block_key:
                    used_block_keys.add(block_key)

            results.append(
                {
                    "FIELD NO": field_no,
                    "PDF PAGE": page["page"],
                    "EXCEL ROW": excel_index + 2,
                    "FIELD": field,
                    "ORDER FORM DATA": value,
                    "PDF OUTPUT": result["pdf"],
                    "STATUS": result["status"],
                    "DIFFERENCE": result["difference"]
                }
            )

            field_no += 1

    return pd.DataFrame(results)

# =========================================================
# STATUS COLORS
# =========================================================

def style_status(value):

    if value == "PASS":

        return (
            "background-color: #238636;"
            "color: white;"
            "font-weight: bold;"
        )


    if value == "FAIL":

        return (
            "background-color: #da3633;"
            "color: white;"
            "font-weight: bold;"
        )


    if value == "NOT FOUND":

        return (
            "background-color: #9e6a03;"
            "color: white;"
            "font-weight: bold;"
        )


    if value == "SKIP":

        return (
            "background-color: #555555;"
            "color: white;"
            "font-weight: bold;"
        )


    return ""


# =========================================================


def main():
    """Order Form to Output Check tool."""

    st.markdown(
        """
        <style>

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stApp"],
        .stApp,
        .main,
        [data-testid="stMain"] {
            background-color: #0e1117 !important;
            color: #ffffff !important;
        }

        [data-testid="stHeader"] {
            background-color: #0e1117 !important;
        }

        .stApp,
        .stApp p,
        .stApp label,
        .stApp span,
        .stApp div {
            color: #ffffff;
        }

        .main-title {
            color: #ffffff !important;
            font-size: 34px;
            font-weight: 700;
            margin-top: 5px;
            margin-bottom: 4px;
        }

        .sub-title {
            color: #b8c0cc !important;
            font-size: 15px;
            margin-bottom: 30px;
        }

        .section-title {
            color: #ffffff !important;
            font-size: 20px;
            font-weight: 700;
            margin-top: 12px;
            margin-bottom: 10px;
        }

        [data-testid="stFileUploader"] {
            background-color: #161b22 !important;
            border: 1px solid #4b5563 !important;
            border-radius: 12px !important;
            padding: 8px !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            background-color: #161b22 !important;
            border: 1px solid #4b5563 !important;
            border-radius: 10px !important;
        }

        [data-testid="stFileUploaderDropzoneInstructions"] {
            color: #ffffff !important;
        }

        [data-testid="stFileUploaderDropzoneInstructions"] span {
            color: #ffffff !important;
        }

        [data-testid="stFileUploader"] button {
            background-color: #111827 !important;
            color: #ffffff !important;
            border: 1px solid #6b7280 !important;
            border-radius: 8px !important;
        }

        [data-testid="stFileUploader"] button:hover {
            background-color: #1f2937 !important;
            color: #ffffff !important;
        }

        [data-baseweb="select"] > div {
            background-color: #161b22 !important;
            color: #ffffff !important;
            border: 1px solid #4b5563 !important;
            border-radius: 10px !important;
        }

        [data-baseweb="select"] input {
            color: #ffffff !important;
        }

        [data-baseweb="select"] span {
            color: #ffffff !important;
        }

        [data-baseweb="popover"] {
            background-color: #161b22 !important;
        }

        [role="option"] {
            background-color: #161b22 !important;
            color: #ffffff !important;
        }

        [role="option"]:hover {
            background-color: #263241 !important;
        }

        [data-baseweb="tag"] {
            background-color: #2563eb !important;
            color: #ffffff !important;
        }

        [data-baseweb="tag"] span {
            color: #ffffff !important;
        }

        div.stButton > button {
            background-color: #2196F3 !important;
            color: #ffffff !important;
            border: 2px solid #000000 !important;
            border-radius: 12px !important;
            font-size: 18px !important;
            font-weight: 700 !important;
            height: 54px !important;
            width: 100% !important;
            box-shadow: none !important;
        }

        div.stButton > button:hover {
            background-color: #1976D2 !important;
            color: #ffffff !important;
            border: 2px solid #000000 !important;
        }

        div.stDownloadButton > button {
            background-color: #1f2937 !important;
            color: #ffffff !important;
            border: 1px solid #6b7280 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }

        div.stDownloadButton > button:hover {
            background-color: #374151 !important;
            color: #ffffff !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid #374151 !important;
            border-radius: 10px !important;
        }

        [data-testid="stMetric"] {
            background-color: #161b22 !important;
            border: 1px solid #374151 !important;
            border-radius: 10px !important;
            padding: 12px !important;
        }

        [data-testid="stMetricLabel"] {
            color: #b8c0cc !important;
        }

        [data-testid="stMetricValue"] {
            color: #ffffff !important;
        }

        hr {
            border-color: #30363d !important;
        }

        .stCaption {
            color: #9ca3af !important;
        }

        [data-testid="stAlert"] {
            border-radius: 10px !important;
        }

        [data-testid="stSpinner"] {
            color: #ffffff !important;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="main-title">🔍 Order Form to Output Check</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Compare selected variable Order Form fields against PDF artwork.</div>', unsafe_allow_html=True)

    # =========================================================
    # TOOL CONTROLS
    # =========================================================

    if "of_reset_id" not in st.session_state:
        st.session_state["of_reset_id"] = 0

    if "report" not in st.session_state:
        st.session_state["report"] = None

    if st.button("🆕 NEW START", key="of_new_start", width="stretch"):
        st.session_state["of_reset_id"] += 1
        st.session_state["report"] = None
        st.rerun()

    product_type = st.selectbox(
        "Select Product Type",
        options=["----- SELECT -----", "PFL", "HTL", "Other"],
        index=0,
        key="of_product_type"
    )

    if product_type == "----- SELECT -----":
        st.info("Please select a Product Type before starting the comparison.")

    # UPLOAD AREA
    # =========================================================

    left_column, right_column = st.columns(
        2
    )


    # =========================================================
    # ORDER FORM
    # =========================================================

    with left_column:

        st.markdown(
            '<div class="section-title">📊 Order Form</div>',
            unsafe_allow_html=True
        )

        excel_file = st.file_uploader(
            "Upload Excel Order Form",
            type=[
                "xlsx",
                "xls"
            ],
            key=f"excel_upload_{st.session_state['of_reset_id']}"
        )


    # =========================================================
    # PDF
    # =========================================================

    with right_column:

        st.markdown(
            '<div class="section-title">📄 PDF Output</div>',
            unsafe_allow_html=True
        )

        pdf_file = st.file_uploader(
            "Upload PDF Artwork",
            type=[
                "pdf"
            ],
            key=f"pdf_upload_{st.session_state['of_reset_id']}"
        )


    # =========================================================
    # LOAD EXCEL
    # =========================================================

    df = None

    if excel_file:

        try:

            df = load_excel(
                excel_file
            )

        except Exception as error:

            st.error(
                f"Unable to read the Excel Order Form: {error}"
            )

            st.stop()


        # =====================================================
        # FIELD SELECTION
        # =====================================================

        st.markdown(
            '<div class="section-title">'
            'Select Variable Fields to Validate'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(
            "Only the fields selected below are treated as "
            "variable artwork data. Other PDF content is ignored."
        )


        selected_fields = st.multiselect(
            "Select the fields from your Order Form",
            options=[
                str(column)
                for column in df.columns
            ],
            default=[],
            label_visibility="collapsed"
        )


    else:

        selected_fields = []


    # =========================================================
    # LOAD PDF
    # =========================================================

    pdf_pages = None

    if pdf_file:

        try:

            pdf_pages = load_pdf(
                pdf_file
            )

        except Exception as error:

            st.error(
                f"Unable to read the PDF file: {error}"
            )

            st.stop()


    # =========================================================
    # FILE INFORMATION
    # =========================================================

    if (
        excel_file
        and
        pdf_file
    ):

        st.divider()

        st.markdown(
            '<div class="section-title">'
            '📌 File Information'
            '</div>',
            unsafe_allow_html=True
        )


        info1, info2, info3 = st.columns(
            3
        )


        with info1:

            st.metric(
                "Excel Data Rows",
                len(df)
            )


        with info2:

            st.metric(
                "PDF Pages",
                len(pdf_pages)
            )


        with info3:

            difference = (
                len(df)
                -
                len(pdf_pages)
            )

            st.metric(
                "Row / Page Difference",
                difference
            )


        if len(df) == len(pdf_pages):

            st.success(
                "✅ Excel rows and PDF pages match."
            )

        else:

            st.warning(
                "⚠️ Excel rows and PDF pages do not have the "
                "same count. Matching will use Page 1 → Excel "
                "Row 2, Page 2 → Excel Row 3, etc."
            )


    # =========================================================
    # COMPARE BUTTON
    # =========================================================

    if (
        excel_file
        and
        pdf_file
        and
        selected_fields
        and
        product_type != "----- SELECT -----"
    ):

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(
            "🔍  COMPARE & PROOFREAD",
            width="stretch",
            key="compare_button"
        ):

            with st.spinner(
                "Checking selected variable artwork data..."
            ):

                st.session_state["report"] = build_report(
                    df,
                    pdf_pages,
                    selected_fields,
                    product_type
                )

                st.session_state["report_product_type"] = product_type


    # =========================================================
    # SAVED REPORT
    #
    # Stored in session state so the report remains visible after
    # normal Streamlit reruns until NEW START is selected.
    # =========================================================

    report = st.session_state.get("report")

    if report is not None:

        st.divider()

        st.markdown(
            '<div class="section-title">QC Report</div>',
            unsafe_allow_html=True
        )

        report_product_type = st.session_state.get(
            "report_product_type",
            product_type
        )

        st.caption(
            f"Comparison mode: {report_product_type}"
        )

        # =================================================
        # COUNTS
        # =================================================

        pass_count = int(
            (report["STATUS"] == "PASS").sum()
        )

        fail_count = int(
            (report["STATUS"] == "FAIL").sum()
        )

        not_found_count = int(
            (report["STATUS"] == "NOT FOUND").sum()
        )

        skip_count = int(
            (report["STATUS"] == "SKIP").sum()
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("PASS", pass_count)

        with col2:
            st.metric("FAIL", fail_count)

        with col3:
            st.metric("NOT FOUND", not_found_count)

        with col4:
            st.metric("IGNORED", skip_count)

        # =================================================
        # REPORT TABLE
        # =================================================

        styled_report = (
            report
            .style
            .map(
                style_status,
                subset=["STATUS"]
            )
        )

        st.dataframe(
            styled_report,
            width="stretch",
            hide_index=True
        )

        # =================================================
        # CONCLUSION
        # =================================================

        st.divider()

        if fail_count > 0:
            st.error(
                f"❌ FAIL — {fail_count} variable-data mismatch(es) detected."
            )

        elif not_found_count > 0:
            st.warning(
                f"⚠️ REVIEW — {not_found_count} selected variable "
                f"field(s) could not be located."
            )

        else:
            st.success(
                "✅ PASS — All selected variable fields matched the PDF artwork."
            )

        # =================================================
        # LOGIC EXPLANATION
        # =================================================

        with st.expander("ℹ️ How this validation works"):
            st.write(
                """
                **Variable-data validation**

                Only the fields selected from the Order Form are treated as
                variable artwork data.

                **Static PDF content is ignored.**

                PDF bullets/keystrokes such as `n`, regional prefixes,
                addresses, phone numbers and other unselected static artwork
                content do not create failures.

                **Page mapping**

                PDF Page 1 → Excel Row 2

                PDF Page 2 → Excel Row 3

                PDF Page 3 → Excel Row 4

                and so on.

                **PFL mode**

                Panel-numbered artwork is treated as a continuous stream so
                selected variable data can continue from one panel into the
                next panel.

                **Mismatch detection**

                If the selected Order Form value is present in the PDF → PASS.

                If the expected value is absent but a relevant alternative
                value is detected → FAIL.

                If an Order Form field is blank, that field is not required
                and is ignored.
                """
            )

        # =================================================
        # DOWNLOAD REPORT
        # =================================================

        csv_data = (
            report
            .to_csv(index=False)
            .encode("utf-8-sig")
        )

        st.download_button(
            label="⬇️ Download QC Report",
            data=csv_data,
            file_name="PDF_Proofreading_QC_Report.csv",
            mime="text/csv",
            width="stretch",
            key="download_qc_report"
        )


    # =========================================================
    # INITIAL INSTRUCTIONS
    # =========================================================

    if not excel_file:

        st.caption(
            "Upload an Order Form to begin."
        )


    elif not pdf_file:

        st.caption(
            "Upload the PDF artwork to continue."
        )


    elif product_type == "----- SELECT -----":

        st.caption(
            "Select the Product Type to continue."
        )


    elif not selected_fields:

        st.caption(
            "Select the variable fields you want to validate."
        )


if __name__ == "__main__":
    main()
