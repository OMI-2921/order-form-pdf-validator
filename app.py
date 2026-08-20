import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from difflib import SequenceMatcher
from rapidfuzz import fuzz


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Order Form PDF Validator",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Validator")
st.caption(
    "Order Form is treated as the master reference. "
    "The PDF artwork is proofread against it."
)


# =========================================================
# FIELD CONCEPTS
# =========================================================
#
# These are used mainly for identifying the type/language
# of a field. The actual comparison is based on the CELL
# DATA itself.
#
# Example:
#
# French Care
# French Instruction
#
# are both understood as French care-related fields.
# =========================================================

FIELD_CONCEPTS = {

    "CARE": [
        "care",
        "instruction",
        "instructions",
        "washing",
        "wash",
        "laundry",
        "careinstruction",
        "careinstructions",
        "washinstruction",
        "washinginstruction",
        "laundryinstruction",
        "washcare",
        "carelabel"
    ],

    "CONTENT": [
        "content",
        "fabric",
        "fiber",
        "fibre",
        "material",
        "composition",
        "fabriccontent",
        "fibercontent",
        "fibrecontent",
        "materialcomposition",
        "fabrication"
    ],

    "COO": [
        "coo",
        "country",
        "origin",
        "madein",
        "countryoforigin",
        "countryorigin",
        "countryofmanufacture"
    ],

    "SIZE": [
        "size",
        "sizeline",
        "sizelines",
        "osz",
        "fit",
        "alpha",
        "alphasize",
        "waist",
        "inseam",
        "sizecode",
        "sizemodifier"
    ],

    "ATTRIBUTE": [
        "attribute",
        "attributes",
        "technology",
        "technologyanddesign",
        "technologyanddesignattributes",
        "design",
        "feature",
        "features",
        "description",
        "productdescription",
        "finish"
    ],

    "RN": [
        "rn",
        "registration",
        "registrationnumber",
        "companyrn"
    ],

    "BRAND": [
        "brand",
        "brandname",
        "logo"
    ],

    "STYLE": [
        "style",
        "stylenumber",
        "stylecode",
        "styleid"
    ],

    "COLOR": [
        "color",
        "colour",
        "colorname",
        "colourname"
    ],

    "GENDER": [
        "gender",
        "productgender"
    ]
}


# =========================================================
# FIELDS THAT SHOULD GENERALLY NOT BE CHECKED
# =========================================================

IGNORE_KEYWORDS = [

    "datetime",
    "date",
    "time",

    "quantity",
    "qty",

    "corporatecustomer",

    "vendorcompany",
    "vendor",

    "customerpo",

    "orderno",
    "ordernumber",
    "orderformnumber",

    "jobno",
    "jobnumber",

    "ticket",

    "userid",
    "username",

    "createdby",
    "modifiedby",

    "status",

    "internal",

    "database",
    "recordid",
    "systemid",

    "timestamp",

    "revision",

    "filelocation",
    "filepath"
]


# =========================================================
# HEADER NORMALIZATION
# =========================================================

def clean_header(value):

    if value is None:
        return ""

    text = str(value).strip().lower()

    return re.sub(
        r"[^a-z0-9]",
        "",
        text
    )


# =========================================================
# FIELD CLASSIFICATION
# =========================================================

def classify_field(header):

    if header is None:
        return "IGNORE"

    header_text = str(header).strip()

    if not header_text:
        return "IGNORE"

    compact = clean_header(
        header_text
    )

    # Internal fields first
    for keyword in IGNORE_KEYWORDS:

        keyword_clean = clean_header(
            keyword
        )

        if (
            keyword_clean
            and keyword_clean in compact
        ):
            return "IGNORE"

    # Artwork-related fields
    for concept, keywords in FIELD_CONCEPTS.items():

        for keyword in keywords:

            keyword_clean = clean_header(
                keyword
            )

            if (
                keyword_clean
                and keyword_clean in compact
            ):
                return "CHECK"

    return "REVIEW"


# =========================================================
# FIELD CONCEPT
# =========================================================

def get_field_concept(header):

    compact = clean_header(
        header
    )

    for concept, keywords in FIELD_CONCEPTS.items():

        for keyword in keywords:

            keyword_clean = clean_header(
                keyword
            )

            if (
                keyword_clean
                and keyword_clean in compact
            ):
                return concept

    return "UNKNOWN"


# =========================================================
# LANGUAGE DETECTION
# =========================================================

def get_field_language(header):

    compact = clean_header(
        header
    )

    if "french" in compact:
        return "FRENCH"

    if "francais" in compact:
        return "FRENCH"

    if "english" in compact:
        return "ENGLISH"

    if "anglais" in compact:
        return "ENGLISH"

    return "UNKNOWN"


# =========================================================
# TEXT NORMALIZATION
# =========================================================
#
# This is used for the actual proofreading comparison.
#
# Example:
#
# ORDER FORM:
# WARM WASH ONLY.
#
# PDF:
# Warm   Wash
# Only
#
# becomes:
#
# warm wash only
#
# =========================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = unicodedata.normalize(
        "NFKC",
        text
    )

    # Case insensitive
    text = text.lower()

    # Normalize apostrophes
    text = text.replace(
        "’",
        "'"
    )

    # PDF line breaks become spaces
    text = text.replace(
        "\n",
        " "
    )

    text = text.replace(
        "\r",
        " "
    )

    # Separators are not important
    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    # Hyphen handling
    text = re.sub(
        r"-+",
        " ",
        text
    )

    # Keep letters, numbers, %, # and spaces
    text = re.sub(
        r"[^\w%#\s']",
        " ",
        text
    )

    # Remove apostrophes for matching
    text = text.replace(
        "'",
        ""
    )

    # Collapse spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# TOKENIZATION
# =========================================================

def tokenize(text):

    normalized = normalize_text(
        text
    )

    if not normalized:
        return []

    return normalized.split()


# =========================================================
# COMPACT NORMALIZATION
# =========================================================

def compact_normalize(text):

    return normalize_text(
        text
    ).replace(
        " ",
        ""
    )


# =========================================================
# EMPTY VALUE
# =========================================================

def is_empty_value(value):

    if value is None:
        return True

    try:

        if pd.isna(value):
            return True

    except Exception:

        pass

    return str(
        value
    ).strip() == ""


# =========================================================
# SHORT VALUE
# =========================================================

def is_short_value(value):

    tokens = tokenize(
        value
    )

    if not tokens:
        return True

    normalized = normalize_text(
        value
    )

    # Single short values such as:
    #
    # S
    # M
    # L
    # XL
    # XXL
    #
    # should use exact token matching.

    if (
        len(tokens) == 1
        and len(normalized) <= 5
    ):
        return True

    return False


# =========================================================
# EXACT TOKEN SEARCH
# =========================================================

def exact_token_exists(
    expected,
    pdf_text
):

    expected_norm = normalize_text(
        expected
    )

    pdf_norm = normalize_text(
        pdf_text
    )

    if not expected_norm:
        return False

    pattern = (
        r"(?<![\w])"
        + re.escape(expected_norm)
        + r"(?![\w])"
    )

    return (
        re.search(
            pattern,
            pdf_norm
        )
        is not None
    )


# =========================================================
# EXACT NORMALIZED SEARCH
# =========================================================

def exact_normalized_exists(
    expected,
    pdf_text
):

    expected_norm = normalize_text(
        expected
    )

    pdf_norm = normalize_text(
        pdf_text
    )

    if not expected_norm:
        return False

    # Direct normalized match
    if expected_norm in pdf_norm:
        return True

    # Ignore all spaces
    expected_compact = compact_normalize(
        expected
    )

    pdf_compact = compact_normalize(
        pdf_text
    )

    if expected_compact in pdf_compact:
        return True

    return False


# =========================================================
# SPLIT PDF INTO TEXT BLOCKS
# =========================================================
#
# Important:
#
# We do NOT compare the Order Form against the entire PDF
# page as one giant string for proofreading.
#
# Instead we create candidate text blocks.
#
# This prevents unrelated content from becoming the
# "OUTPUT".
# =========================================================

def create_pdf_blocks(pdf_text):

    if not pdf_text:
        return []

    raw_lines = pdf_text.splitlines()

    lines = []

    for line in raw_lines:

        line = line.strip()

        if line:
            lines.append(
                line
            )

    if not lines:
        return []

    blocks = []

    # -----------------------------------------------------
    # Individual lines
    # -----------------------------------------------------

    for line in lines:

        blocks.append(
            line
        )

    # -----------------------------------------------------
    # Adjacent line combinations
    #
    # This handles artwork text such as:
    #
    # MACHINE WASH COLD WITH LIKE
    # COLORS. CHLORINE BLEACH WHEN
    # NEEDED. TUMBLE DRY LOW.
    # -----------------------------------------------------

    for window_size in [
        2,
        3,
        4,
        5,
        6,
        8,
        10,
        12,
        15,
        20
    ]:

        if len(lines) < window_size:
            continue

        for start in range(
            0,
            len(lines) - window_size + 1
        ):

            block = " ".join(
                lines[
                    start:start + window_size
                ]
            )

            blocks.append(
                block
            )

    # -----------------------------------------------------
    # Sentence-like blocks
    # -----------------------------------------------------

    full_text = " ".join(
        lines
    )

    sentence_parts = re.split(
        r"(?<=[.!?])\s+",
        full_text
    )

    for part in sentence_parts:

        part = part.strip()

        if part:
            blocks.append(
                part
            )

    # Remove duplicates
    unique_blocks = []

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

        unique_blocks.append(
            block
        )

    return unique_blocks


# =========================================================
# LANGUAGE HEURISTICS
# =========================================================

FRENCH_WORDS = {
    "avec",
    "couleurs",
    "similaires",
    "utilisez",
    "seulement",
    "sans",
    "chlore",
    "nécessaire",
    "sechage",
    "séchage",
    "culbutage",
    "température",
    "repassage",
    "doux",
    "laver",
    "machine",
    "froide"
}

ENGLISH_WORDS = {
    "wash",
    "machine",
    "cold",
    "colors",
    "colour",
    "similar",
    "bleach",
    "chlorine",
    "needed",
    "tumble",
    "dry",
    "low",
    "iron",
    "warm",
    "only",
    "do",
    "not"
}


def language_score(
    text,
    language
):

    if language == "UNKNOWN":
        return 0

    tokens = set(
        tokenize(text)
    )

    if not tokens:
        return 0

    if language == "FRENCH":

        return len(
            tokens.intersection(
                FRENCH_WORDS
            )
        )

    if language == "ENGLISH":

        return len(
            tokens.intersection(
                ENGLISH_WORDS
            )
        )

    return 0


# =========================================================
# SHARED TOKEN SCORE
# =========================================================
#
# Used to prevent unrelated text from being selected.
# =========================================================

def shared_token_ratio(
    expected,
    candidate
):

    expected_tokens = tokenize(
        expected
    )

    candidate_tokens = tokenize(
        candidate
    )

    if not expected_tokens:
        return 0

    expected_set = set(
        expected_tokens
    )

    candidate_set = set(
        candidate_tokens
    )

    shared = (
        expected_set
        .intersection(
            candidate_set
        )
    )

    return (
        len(shared)
        /
        len(expected_set)
    )


# =========================================================
# GET BEST PROOFREADING CANDIDATE
# =========================================================
#
# This is deliberately conservative.
#
# We don't want:
#
# French Care
# ↓
# random English Care
#
# to appear as the output.
#
# A candidate must have strong textual relationship with
# the Order Form cell before we show it.
# =========================================================

def find_proofreading_candidate(
    expected,
    pdf_text,
    language="UNKNOWN"
):

    expected_norm = normalize_text(
        expected
    )

    if not expected_norm:
        return None

    blocks = create_pdf_blocks(
        pdf_text
    )

    if not blocks:
        return None

    expected_tokens = tokenize(
        expected
    )

    expected_length = len(
        expected_tokens
    )

    best_candidate = None
    best_rank = -1

    for block in blocks:

        block_norm = normalize_text(
            block
        )

        if not block_norm:
            continue

        block_tokens = tokenize(
            block
        )

        if not block_tokens:
            continue

        # -------------------------------------------------
        # Exact normalized match
        # -------------------------------------------------

        if (
            expected_norm
            in block_norm
        ):

            return {
                "text": block,
                "similarity": 100,
                "shared": 1.0
            }

        # -------------------------------------------------
        # Similarity
        # -------------------------------------------------

        ratio = fuzz.ratio(
            expected_norm,
            block_norm
        )

        token_ratio = fuzz.token_set_ratio(
            expected_norm,
            block_norm
        )

        shared_ratio = shared_token_ratio(
            expected,
            block
        )

        # -------------------------------------------------
        # Length difference
        #
        # We don't want a tiny piece of text to become
        # the match for a huge paragraph.
        # -------------------------------------------------

        length_ratio = (
            min(
                len(expected_norm),
                len(block_norm)
            )
            /
            max(
                len(expected_norm),
                len(block_norm)
            )
        )

        # -------------------------------------------------
        # Language
        # -------------------------------------------------

        lang_score = language_score(
            block,
            language
        )

        # -------------------------------------------------
        # Combined ranking
        # -------------------------------------------------

        rank = (
            ratio * 0.45
            +
            token_ratio * 0.20
            +
            shared_ratio * 100 * 0.25
            +
            length_ratio * 100 * 0.10
        )

        # Language boost
        if language != "UNKNOWN":

            if lang_score > 0:

                rank += min(
                    lang_score * 2,
                    10
                )

            else:

                # Strong penalty when the field language
                # clearly doesn't resemble the candidate.
                if expected_length >= 4:
                    rank -= 12

        # -------------------------------------------------
        # Minimum requirements
        #
        # Short strings need much stronger evidence.
        # -------------------------------------------------

        if expected_length <= 2:

            acceptable = (
                ratio >= 90
                and
                shared_ratio >= 0.5
            )

        elif expected_length <= 5:

            acceptable = (
                ratio >= 75
                and
                shared_ratio >= 0.50
            )

        else:

            acceptable = (
                (
                    ratio >= 72
                    and
                    shared_ratio >= 0.45
                )
                or
                (
                    token_ratio >= 80
                    and
                    shared_ratio >= 0.55
                )
            )

        if not acceptable:
            continue

        if rank > best_rank:

            best_rank = rank

            best_candidate = {
                "text": block,
                "similarity": ratio,
                "shared": shared_ratio
            }

    return best_candidate


# =========================================================
# CHARACTER / WORD DIFFERENCE
# =========================================================

def make_difference(
    expected,
    actual
):

    expected_norm = normalize_text(
        expected
    )

    actual_norm = normalize_text(
        actual
    )

    if not expected_norm:
        return "Reference data is empty."

    if not actual_norm:
        return "Reference data was not found in the PDF."

    expected_words = expected_norm.split()
    actual_words = actual_norm.split()

    matcher = SequenceMatcher(
        None,
        expected_words,
        actual_words
    )

    differences = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        expected_part = " ".join(
            expected_words[i1:i2]
        )

        actual_part = " ".join(
            actual_words[j1:j2]
        )

        if tag == "replace":

            differences.append(
                f"'{expected_part}' → '{actual_part}'"
            )

        elif tag == "delete":

            differences.append(
                f"Missing '{expected_part}'"
            )

        elif tag == "insert":

            differences.append(
                f"Extra '{actual_part}'"
            )

    if not differences:

        # Character-level fallback
        ratio = fuzz.ratio(
            expected_norm,
            actual_norm
        )

        if ratio < 100:

            return (
                f"Text differs from reference "
                f"({expected_norm} → {actual_norm})"
            )

        return "Formatting difference only."

    # Don't make the report enormous
    return "; ".join(
        differences[:8]
    )


# =========================================================
# COMPARE ONE CELL
# =========================================================

def compare_cell(
    expected,
    pdf_text,
    field_name
):

    expected = str(
        expected
    ).strip()

    if not expected:

        return {
            "output": "",
            "status": "SKIP",
            "difference": "No Order Form data."
        }

    language = get_field_language(
        field_name
    )

    # =====================================================
    # STEP 1 — EXACT NORMALIZED SEARCH
    # =====================================================

    if exact_normalized_exists(
        expected,
        pdf_text
    ):

        # Find a readable block containing it
        blocks = create_pdf_blocks(
            pdf_text
        )

        output = expected

        for block in blocks:

            if (
                normalize_text(expected)
                in normalize_text(block)
            ):

                output = block
                break

        return {
            "output": output,
            "status": "PASS",
            "difference": "—"
        }


    # =====================================================
    # STEP 2 — PROOFREADING CANDIDATE
    # =====================================================

    candidate = find_proofreading_candidate(
        expected,
        pdf_text,
        language
    )


    # =====================================================
    # STEP 3 — NO RELIABLE MATCH
    # =====================================================

    if candidate is None:

        return {
            "output": "Not found in corresponding PDF page",
            "status": "FAIL",
            "difference": "Reference data not found."
        }


    actual = candidate["text"]

    difference = make_difference(
        expected,
        actual
    )

    return {
        "output": actual,
        "status": "FAIL",
        "difference": difference
    }


# =========================================================
# READ EXCEL
# =========================================================

def read_order_form(
    excel_file
):

    excel_file.seek(0)

    df = pd.read_excel(
        excel_file,
        header=0
    )

    # Clean column names
    cleaned_columns = []

    for column in df.columns:

        column_text = str(
            column
        ).strip()

        cleaned_columns.append(
            column_text
        )

    df.columns = cleaned_columns

    return df


# =========================================================
# EXTRACT PDF PAGES
# =========================================================

def extract_pdf_pages(
    pdf_file
):

    pdf_file.seek(0)

    pdf_bytes = pdf_file.read()

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(
        document,
        start=1
    ):

        text = page.get_text(
            "text"
        )

        pages.append({
            "page": page_number,
            "text": text
        })

    document.close()

    return pages


# =========================================================
# ANALYZE EXCEL HEADERS
# =========================================================

def analyze_headers(
    df
):

    results = []

    for column in df.columns:

        classification = classify_field(
            column
        )

        concept = get_field_concept(
            column
        )

        language = get_field_language(
            column
        )

        non_empty = (
            df[column]
            .dropna()
        )

        if len(non_empty) > 0:

            sample = str(
                non_empty.iloc[0]
            )

        else:

            sample = ""

        results.append({

            "FIELD": column,

            "CLASSIFICATION":
                classification,

            "CONCEPT":
                concept,

            "LANGUAGE":
                language,

            "SAMPLE DATA":
                sample
        })

    return pd.DataFrame(
        results
    )


# =========================================================
# CREATE QC REPORT
# =========================================================

def create_report(
    df,
    pdf_pages,
    selected_fields
):

    results = []

    # -----------------------------------------------------
    # Mapping:
    #
    # Excel Row 2 → PDF Page 1
    # Excel Row 3 → PDF Page 2
    # Excel Row 4 → PDF Page 3
    # etc.
    # -----------------------------------------------------

    for excel_index, row in df.iterrows():

        pdf_page_number = (
            excel_index + 1
        )

        excel_row_number = (
            excel_index + 2
        )

        # -------------------------------------------------
        # Missing corresponding PDF page
        # -------------------------------------------------

        if (
            pdf_page_number
            > len(pdf_pages)
        ):

            results.append({

                "FIELD NO":
                    len(results) + 1,

                "EXCEL ROW":
                    excel_row_number,

                "PDF PAGE":
                    pdf_page_number,

                "FIELD":
                    "PAGE CHECK",

                "ORDER FORM DATA":
                    "",

                "OUTPUT":
                    "PDF page not available",

                "STATUS":
                    "FAIL",

                "DIFFERENCE":
                    "Corresponding PDF page was not found."
            })

            continue

        pdf_text = pdf_pages[
            pdf_page_number - 1
        ]["text"]


        # -------------------------------------------------
        # Check every selected cell
        # -------------------------------------------------

        for field in selected_fields:

            value = row[field]

            if is_empty_value(
                value
            ):
                continue

            value = str(
                value
            ).strip()

            result = compare_cell(
                value,
                pdf_text,
                field
            )

            results.append({

                "FIELD NO":
                    len(results) + 1,

                "EXCEL ROW":
                    excel_row_number,

                "PDF PAGE":
                    pdf_page_number,

                "FIELD":
                    field,

                "ORDER FORM DATA":
                    value,

                "OUTPUT":
                    result["output"],

                "STATUS":
                    result["status"],

                "DIFFERENCE":
                    result["difference"]
            })

    return pd.DataFrame(
        results
    )


# =========================================================
# COLOR STATUS
# =========================================================

def color_status(
    value
):

    if value == "PASS":

        return (
            "background-color: #90EE90;"
            "color: black;"
            "font-weight: bold;"
        )

    if value == "FAIL":

        return (
            "background-color: #FF7F7F;"
            "color: black;"
            "font-weight: bold;"
        )

    if value == "SKIP":

        return (
            "background-color: #D3D3D3;"
            "color: black;"
            "font-weight: bold;"
        )

    return ""


# =========================================================
# UPLOAD SECTION
# =========================================================

left, right = st.columns(
    2
)


with left:

    st.subheader(
        "📊 Order Form"
    )

    excel_file = st.file_uploader(
        "Upload Flat File Excel",
        type=[
            "xlsx",
            "xls"
        ]
    )


with right:

    st.subheader(
        "📄 PDF Output"
    )

    pdf_file = st.file_uploader(
        "Upload PDF Output",
        type=[
            "pdf"
        ]
    )


# =========================================================
# MAIN APPLICATION
# =========================================================

if excel_file and pdf_file:

    # =====================================================
    # READ EXCEL
    # =====================================================

    try:

        df = read_order_form(
            excel_file
        )

    except Exception as error:

        st.error(
            f"Unable to read Excel file: {error}"
        )

        st.stop()


    # =====================================================
    # READ PDF
    # =====================================================

    try:

        pdf_pages = extract_pdf_pages(
            pdf_file
        )

    except Exception as error:

        st.error(
            f"Unable to read PDF file: {error}"
        )

        st.stop()


    # =====================================================
    # FILE INFORMATION
    # =====================================================

    st.divider()

    st.subheader(
        "📌 File Information"
    )

    c1, c2, c3 = st.columns(
        3
    )

    with c1:

        st.metric(
            "Excel Data Rows",
            len(df)
        )

    with c2:

        st.metric(
            "PDF Pages",
            len(pdf_pages)
        )

    with c3:

        st.metric(
            "Fields",
            len(df.columns)
        )


    if len(df) != len(pdf_pages):

        st.warning(
            "⚠️ Excel data rows and PDF pages do not "
            "have the same count. The application will "
            "still compare the available Row → Page pairs."
        )

    else:

        st.success(
            "✅ Excel rows and PDF pages are aligned."
        )


    # =====================================================
    # SMART FIELD ANALYSIS
    # =====================================================

    st.divider()

    st.subheader(
        "🧠 Smart Field Mapping"
    )

    field_analysis = analyze_headers(
        df
    )


    check_fields = (
        field_analysis[
            field_analysis[
                "CLASSIFICATION"
            ] == "CHECK"
        ]["FIELD"]
        .tolist()
    )


    review_fields = (
        field_analysis[
            field_analysis[
                "CLASSIFICATION"
            ] == "REVIEW"
        ]["FIELD"]
        .tolist()
    )


    ignore_fields = (
        field_analysis[
            field_analysis[
                "CLASSIFICATION"
            ] == "IGNORE"
        ]["FIELD"]
        .tolist()
    )


    st.write(
        f"**Automatically detected artwork fields: "
        f"{len(check_fields)}**"
    )


    if check_fields:

        st.success(
            ", ".join(
                check_fields
            )
        )

    else:

        st.warning(
            "No artwork fields were automatically detected."
        )


    # =====================================================
    # FIELD ANALYSIS
    # =====================================================

    with st.expander(
        "🔎 View field mapping"
    ):

        st.dataframe(
            field_analysis,
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # UNKNOWN FIELDS
    # =====================================================

    if review_fields:

        st.divider()

        with st.expander(
            "⚠️ Fields requiring review"
        ):

            st.write(
                "These fields were not confidently identified. "
                "Select them if they should be proofread."
            )

            additional_fields = st.multiselect(
                "Additional fields:",
                review_fields
            )

            for field in additional_fields:

                if field not in check_fields:

                    check_fields.append(
                        field
                    )


    # =====================================================
    # IGNORED FIELDS
    # =====================================================

    with st.expander(
        "🚫 Ignored fields"
    ):

        if ignore_fields:

            st.write(
                ignore_fields
            )

        else:

            st.write(
                "No fields automatically ignored."
            )


    # =====================================================
    # COMPARE BUTTON
    # =====================================================

    st.divider()

    if st.button(
        "🔍 COMPARE FILES",
        type="primary",
        use_container_width=True
    ):

        if not check_fields:

            st.error(
                "No fields selected for comparison."
            )

            st.stop()


        with st.spinner(
            "Proofreading PDF against the Order Form..."
        ):

            report = create_report(
                df,
                pdf_pages,
                check_fields
            )


        # =================================================
        # REPORT
        # =================================================

        st.divider()

        st.subheader(
            "📋 QC Comparison Report"
        )


        if report.empty:

            st.warning(
                "No data was available for comparison."
            )

        else:

            pass_count = (
                report["STATUS"]
                .eq("PASS")
                .sum()
            )

            fail_count = (
                report["STATUS"]
                .eq("FAIL")
                .sum()
            )


            # =================================================
            # SUMMARY
            # =================================================

            c1, c2, c3 = st.columns(
                3
            )

            with c1:

                st.metric(
                    "TOTAL CHECKED",
                    len(report)
                )

            with c2:

                st.metric(
                    "PASS",
                    pass_count
                )

            with c3:

                st.metric(
                    "FAIL",
                    fail_count
                )


            # =================================================
            # STYLED REPORT
            # =================================================

            styled_report = (
                report
                .style
                .map(
                    color_status,
                    subset=[
                        "STATUS"
                    ]
                )
            )


            st.dataframe(
                styled_report,
                use_container_width=True,
                hide_index=True
            )


            # =================================================
            # CONCLUSION
            # =================================================

            st.divider()

            if fail_count == 0:

                st.success(
                    "✅ CONCLUSION: "
                    "All checked Order Form data was found "
                    "correctly in the corresponding PDF artwork."
                )

            else:

                st.error(
                    f"❌ CONCLUSION: "
                    f"{fail_count} mismatch(es) found. "
                    f"Please review the red FAIL rows."
                )


            # =================================================
            # DOWNLOAD CSV
            # =================================================

            csv_data = (
                report
                .to_csv(
                    index=False
                )
                .encode(
                    "utf-8"
                )
            )


            st.download_button(
                "⬇️ Download QC Report",
                data=csv_data,
                file_name=(
                    "Order_Form_PDF_QC_Report.csv"
                ),
                mime="text/csv",
                use_container_width=True
            )


else:

    st.info(
        "Upload both the Order Form Excel and PDF Output "
        "to begin proofreading."
    )
