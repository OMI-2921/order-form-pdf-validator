import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from difflib import SequenceMatcher
from rapidfuzz import fuzz


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Order Form → PDF Proofreader",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Proofreader")
st.caption(
    "PDF artwork is the driver. The Order Form is used as the master reference."
)


# =========================================================
# SETTINGS
# =========================================================

# Very short PDF strings such as "0", "2", "S", "M"
# require much stronger matching.
SHORT_TEXT_MIN_LENGTH = 3

# Minimum confidence before we call something a
# proofreading mismatch.
MIN_MISMATCH_SCORE = 72

# Minimum percentage of PDF words that should be found
# in the Order Form reference.
MIN_SHARED_WORDS = 0.45


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):
    """
    Normalize text while preserving the actual words.

    Differences ignored:
    - uppercase/lowercase
    - line breaks
    - multiple spaces
    - comma
    - full stop
    - colon
    - semicolon
    - slash
    - hyphen formatting
    - apostrophe formatting
    """

    if text is None:
        return ""

    text = str(text)

    text = unicodedata.normalize(
        "NFKC",
        text
    )

    text = text.lower()

    text = text.replace("’", "'")
    text = text.replace("`", "'")

    # PDF line wrapping
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Treat punctuation/separators as spaces
    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    # Hyphen can be formatting
    text = re.sub(
        r"-+",
        " ",
        text
    )

    # Keep letters/numbers/%/#/apostrophe
    text = re.sub(
        r"[^\w%#'\s]",
        " ",
        text
    )

    # Apostrophe formatting should not cause failure
    text = text.replace(
        "'",
        ""
    )

    # Collapse whitespace
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def compact_text(text):
    return normalize_text(text).replace(
        " ",
        ""
    )


def tokenize(text):
    value = normalize_text(text)

    if not value:
        return []

    return value.split()


def is_empty(value):
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    return str(value).strip() == ""


# =========================================================
# EXCEL HEADER NORMALIZATION
# =========================================================

def clean_header(value):
    if value is None:
        return ""

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower()
    )


# =========================================================
# FIELDS THAT ARE GENERALLY NOT ARTWORK CONTENT
# =========================================================

IGNORE_HEADERS = [
    "date",
    "time",
    "datetime",
    "quantity",
    "qty",
    "jobno",
    "jobnumber",
    "orderno",
    "ordernumber",
    "customerpo",
    "ticket",
    "userid",
    "username",
    "createdby",
    "modifiedby",
    "timestamp",
    "recordid",
    "systemid",
    "filepath",
    "filelocation",
    "internal",
    "status"
]


def should_ignore_header(header):
    h = clean_header(header)

    if not h:
        return True

    for item in IGNORE_HEADERS:
        if item in h:
            return True

    return False


# =========================================================
# PDF TEXT EXTRACTION
# =========================================================

def extract_pdf_pages(pdf_file):

    pdf_file.seek(0)

    data = pdf_file.read()

    doc = fitz.open(
        stream=data,
        filetype="pdf"
    )

    pages = []

    for page_index, page in enumerate(
        doc
    ):

        # IMPORTANT:
        # Extract actual page text.
        #
        # We do not use PDF filename or metadata.
        #
        text = page.get_text(
            "text"
        )

        pages.append({
            "page_number": page_index + 1,
            "text": text
        })

    doc.close()

    return pages


# =========================================================
# PDF BLOCK EXTRACTION
# =========================================================
#
# We read the PDF first.
#
# A paragraph may be broken into:
#
# MACHINE WASH COLD WITH LIKE
# COLORS. CHLORINE BLEACH WHEN
# NEEDED.
#
# So we create:
#
# - individual lines
# - 2-line combinations
# - 3-line combinations
# - paragraphs
#
# This allows long artwork text to be compared.
# =========================================================

def extract_pdf_blocks(page_text):

    if not page_text:
        return []

    raw_lines = page_text.splitlines()

    lines = []

    for line in raw_lines:

        line = line.strip()

        if not line:
            continue

        # Ignore extremely long technical strings.
        # These are often production/metadata-like text
        # rather than artwork content.
        if len(line) > 500:
            continue

        lines.append(line)

    if not lines:
        return []

    blocks = []

    # Individual lines
    for line in lines:

        blocks.append({
            "text": line,
            "type": "line"
        })

    # Consecutive line combinations
    for size in [
        2,
        3,
        4,
        5,
        6,
        8,
        10,
        12,
        15
    ]:

        if len(lines) < size:
            continue

        for start in range(
            len(lines) - size + 1
        ):

            block = " ".join(
                lines[
                    start:start + size
                ]
            )

            blocks.append({
                "text": block,
                "type": f"{size}-line"
            })

    # Paragraph-like groups
    paragraph_text = " ".join(lines)

    sentence_parts = re.split(
        r"(?<=[.!?])\s+",
        paragraph_text
    )

    for sentence in sentence_parts:

        sentence = sentence.strip()

        if sentence:

            blocks.append({
                "text": sentence,
                "type": "sentence"
            })

    # Remove duplicate normalized blocks
    unique = []

    seen = set()

    for block in blocks:

        normalized = normalize_text(
            block["text"]
        )

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)

        unique.append(block)

    return unique


# =========================================================
# BUILD EXCEL REFERENCE
# =========================================================
#
# IMPORTANT:
#
# Each PDF page is compared against ONE corresponding
# Excel row.
#
# PDF page 1 -> Excel row 2
# PDF page 2 -> Excel row 3
# PDF page 3 -> Excel row 4
# etc.
#
# The first Excel row is the header.
# =========================================================

def build_row_reference(row, columns):

    references = []

    for column in columns:

        if should_ignore_header(column):
            continue

        value = row[column]

        if is_empty(value):
            continue

        value = str(value).strip()

        if not value:
            continue

        references.append({
            "field": str(column),
            "value": value,
            "normalized": normalize_text(value)
        })

    return references


# =========================================================
# EXACT MATCH
# =========================================================

def exact_match(
    pdf_text,
    excel_value
):

    pdf_normalized = normalize_text(
        pdf_text
    )

    excel_normalized = normalize_text(
        excel_value
    )

    if not pdf_normalized:
        return False

    if not excel_normalized:
        return False

    # Exact phrase
    if excel_normalized in pdf_normalized:
        return True

    # Ignore all spaces
    pdf_compact = compact_text(
        pdf_text
    )

    excel_compact = compact_text(
        excel_value
    )

    if excel_compact in pdf_compact:
        return True

    return False


# =========================================================
# PDF TEXT -> EXCEL REFERENCE COMPARISON
# =========================================================

def compare_pdf_block_to_excel(
    pdf_block,
    excel_references
):

    pdf_norm = normalize_text(
        pdf_block
    )

    if not pdf_norm:
        return None

    pdf_tokens = tokenize(
        pdf_block
    )

    if not pdf_tokens:
        return None

    best = None

    for ref in excel_references:

        expected = ref["value"]

        expected_norm = ref["normalized"]

        if not expected_norm:
            continue

        # -------------------------------------------------
        # EXACT MATCH
        # -------------------------------------------------

        if exact_match(
            pdf_block,
            expected
        ):

            return {
                "field": ref["field"],
                "reference": expected,
                "score": 100,
                "match_type": "EXACT",
                "status": "PASS",
                "difference": "—"
            }

        # -------------------------------------------------
        # Short values need strict matching
        # -------------------------------------------------

        expected_tokens = tokenize(
            expected
        )

        if len(expected_tokens) == 1:

            # Avoid matching "2" inside a larger number.
            if len(expected_norm) <= SHORT_TEXT_MIN_LENGTH:

                if expected_norm.isdigit():

                    pattern = (
                        r"(?<!\d)"
                        + re.escape(expected_norm)
                        + r"(?!\d)"
                    )

                    if re.search(
                        pattern,
                        pdf_norm
                    ):

                        return {
                            "field": ref["field"],
                            "reference": expected,
                            "score": 100,
                            "match_type": "EXACT",
                            "status": "PASS",
                            "difference": "—"
                        }

                    # Don't fuzzy match tiny numbers.
                    continue

                # Short text such as S, M, L, XL
                # also should not fuzzy match randomly.
                if len(expected_norm) <= 2:
                    if expected_norm == pdf_norm:
                        return {
                            "field": ref["field"],
                            "reference": expected,
                            "score": 100,
                            "match_type": "EXACT",
                            "status": "PASS",
                            "difference": "—"
                        }

                    continue

        # -------------------------------------------------
        # Similarity
        # -------------------------------------------------

        ratio = fuzz.ratio(
            pdf_norm,
            expected_norm
        )

        partial = fuzz.partial_ratio(
            pdf_norm,
            expected_norm
        )

        token_set = fuzz.token_set_ratio(
            pdf_norm,
            expected_norm
        )

        # -------------------------------------------------
        # Shared word ratio
        # -------------------------------------------------

        expected_set = set(
            expected_tokens
        )

        pdf_set = set(
            pdf_tokens
        )

        shared = (
            expected_set.intersection(
                pdf_set
            )
        )

        if expected_set:

            shared_ratio = (
                len(shared)
                /
                len(expected_set)
            )

        else:

            shared_ratio = 0

        # -------------------------------------------------
        # Candidate score
        # -------------------------------------------------

        score = (
            ratio * 0.45
            +
            partial * 0.15
            +
            token_set * 0.20
            +
            shared_ratio * 100 * 0.20
        )

        # -------------------------------------------------
        # Don't match tiny PDF blocks against huge fields
        # -------------------------------------------------

        if len(pdf_tokens) == 1 and len(expected_tokens) > 5:
            continue

        # -------------------------------------------------
        # Candidate acceptance
        # -------------------------------------------------

        if len(expected_tokens) <= 2:

            acceptable = (
                ratio >= 88
                and
                shared_ratio >= 0.5
            )

        elif len(expected_tokens) <= 5:

            acceptable = (
                score >= 76
                and
                shared_ratio >= 0.50
            )

        else:

            acceptable = (
                score >= MIN_MISMATCH_SCORE
                and
                shared_ratio >= MIN_SHARED_WORDS
            )

        if not acceptable:
            continue

        # -------------------------------------------------
        # Keep best candidate
        # -------------------------------------------------

        if best is None or score > best["score"]:

            best = {
                "field": ref["field"],
                "reference": expected,
                "score": score,
                "match_type": "PROBABLE",
                "status": "FAIL",
                "difference": create_difference(
                    expected,
                    pdf_block
                )
            }

    return best


# =========================================================
# DIFFERENCE DETECTOR
# =========================================================

def create_difference(
    reference,
    pdf_text
):

    ref_tokens = tokenize(
        reference
    )

    pdf_tokens = tokenize(
        pdf_text
    )

    matcher = SequenceMatcher(
        None,
        ref_tokens,
        pdf_tokens
    )

    differences = []

    for tag, a1, a2, b1, b2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        ref_part = " ".join(
            ref_tokens[a1:a2]
        )

        pdf_part = " ".join(
            pdf_tokens[b1:b2]
        )

        if tag == "replace":

            differences.append(
                f"{ref_part} → {pdf_part}"
            )

        elif tag == "delete":

            differences.append(
                f"Missing: {ref_part}"
            )

        elif tag == "insert":

            differences.append(
                f"Extra: {pdf_part}"
            )

    if not differences:

        return (
            "Text differs from Order Form reference."
        )

    return "; ".join(
        differences[:10]
    )


# =========================================================
# FIND PDF BLOCKS THAT HAVE A REFERENCE
# =========================================================
#
# THIS IS THE IMPORTANT PART.
#
# We start from PDF blocks.
#
# We do NOT loop through every Excel field and ask:
#
# "Where is this field in PDF?"
#
# Instead:
#
# PDF text
#    ↓
# Find corresponding Order Form data
#    ↓
# Compare
#
# =========================================================

def analyze_pdf_page(
    page_text,
    excel_references
):

    blocks = extract_pdf_blocks(
        page_text
    )

    if not blocks:
        return []

    results = []

    # -----------------------------------------------------
    # We primarily use longer/meaningful blocks.
    #
    # Individual tiny lines can create duplicate results.
    # -----------------------------------------------------

    meaningful_blocks = []

    for block in blocks:

        text = block["text"]

        normalized = normalize_text(
            text
        )

        tokens = tokenize(
            text
        )

        if not normalized:
            continue

        # Ignore tiny noise
        if len(normalized) < 3:
            continue

        # Ignore extremely long technical strings
        if len(normalized) > 1200:
            continue

        # Ignore pure numbers unless they are meaningful
        if (
            normalized.isdigit()
            and len(normalized) <= 2
        ):
            continue

        meaningful_blocks.append(
            block
        )

    # -----------------------------------------------------
    # Compare blocks
    # -----------------------------------------------------

    matched_blocks = []

    for block in meaningful_blocks:

        result = compare_pdf_block_to_excel(
            block["text"],
            excel_references
        )

        if result is None:
            continue

        result["pdf_text"] = block["text"]

        matched_blocks.append(
            result
        )

    # -----------------------------------------------------
    # Remove duplicate results.
    #
    # Example:
    #
    # MACHINE WASH COLD
    #
    # MACHINE WASH COLD WITH LIKE
    #
    # MACHINE WASH COLD WITH LIKE COLORS
    #
    # We don't want 3 separate FAILs for one sentence.
    # -----------------------------------------------------

    final = []

    used_keys = set()

    # Prefer exact matches first
    matched_blocks.sort(
        key=lambda x: (
            x["status"] != "PASS",
            -len(x["reference"])
        )
    )

    for result in matched_blocks:

        key = (
            result["field"],
            normalize_text(
                result["reference"]
            )
        )

        if key in used_keys:
            continue

        used_keys.add(key)

        final.append(
            result
        )

    return final


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
        str(c).strip()
        for c in df.columns
    ]

    return df


# =========================================================
# CREATE FINAL REPORT
# =========================================================

def create_report(
    df,
    pdf_pages
):

    report = []

    # -----------------------------------------------------
    # PDF page N corresponds to Excel row N+1
    #
    # Excel header = row 1
    # Excel row 2 = PDF page 1
    # Excel row 3 = PDF page 2
    # etc.
    # -----------------------------------------------------

    for page_index, page in enumerate(
        pdf_pages
    ):

        excel_index = page_index

        # No corresponding Excel row
        if excel_index >= len(df):

            report.append({
                "FIELD NO": len(report) + 1,
                "EXCEL ROW": "",
                "PDF PAGE": page["page_number"],
                "FIELD": "PDF PAGE",
                "ORDER FORM DATA": "Not available",
                "PDF OUTPUT": page["text"][:500],
                "STATUS": "FAIL",
                "DIFFERENCE": "No corresponding Order Form row."
            })

            continue

        row = df.iloc[
            excel_index
        ]

        references = build_row_reference(
            row,
            df.columns
        )

        page_results = analyze_pdf_page(
            page["text"],
            references
        )

        # -------------------------------------------------
        # If no relevant Order Form match was found on
        # the PDF page, don't invent failures.
        # -------------------------------------------------

        for result in page_results:

            report.append({
                "FIELD NO": len(report) + 1,

                "EXCEL ROW":
                    excel_index + 2,

                "PDF PAGE":
                    page["page_number"],

                "FIELD":
                    result["field"],

                "ORDER FORM DATA":
                    result["reference"],

                "PDF OUTPUT":
                    result["pdf_text"],

                "STATUS":
                    result["status"],

                "DIFFERENCE":
                    result["difference"]
            })

    return pd.DataFrame(
        report
    )


# =========================================================
# STATUS COLOR
# =========================================================

def status_style(value):

    if value == "PASS":

        return (
            "background-color:#90EE90;"
            "color:black;"
            "font-weight:bold;"
        )

    if value == "FAIL":

        return (
            "background-color:#FF7F7F;"
            "color:black;"
            "font-weight:bold;"
        )

    return ""


# =========================================================
# UI
# =========================================================

left, right = st.columns(
    2
)

with left:

    st.subheader(
        "📊 Order Form"
    )

    excel_file = st.file_uploader(
        "Upload Excel Order Form",
        type=[
            "xlsx",
            "xls"
        ],
        key="excel"
    )

with right:

    st.subheader(
        "📄 PDF Output"
    )

    pdf_file = st.file_uploader(
        "Upload PDF Artwork",
        type=[
            "pdf"
        ],
        key="pdf"
    )


# =========================================================
# START
# =========================================================

if excel_file and pdf_file:

    # -----------------------------------------------------
    # Read Excel
    # -----------------------------------------------------

    try:

        df = load_excel(
            excel_file
        )

    except Exception as error:

        st.error(
            f"Unable to read Excel: {error}"
        )

        st.stop()


    # -----------------------------------------------------
    # Read PDF
    # -----------------------------------------------------

    try:

        pdf_pages = extract_pdf_pages(
            pdf_file
        )

    except Exception as error:

        st.error(
            f"Unable to read PDF: {error}"
        )

        st.stop()


    # -----------------------------------------------------
    # File information
    # -----------------------------------------------------

    st.divider()

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
            "Excel Fields",
            len(df.columns)
        )


    # -----------------------------------------------------
    # Mapping explanation
    # -----------------------------------------------------

    st.info(
        "📌 Comparison mapping: "
        "Excel Row 2 → PDF Page 1, "
        "Excel Row 3 → PDF Page 2, "
        "Excel Row 4 → PDF Page 3, and so on."
    )


    # -----------------------------------------------------
    # Preview Excel
    # -----------------------------------------------------

    with st.expander(
        "📊 View Order Form"
    ):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


    # -----------------------------------------------------
    # Compare
    # -----------------------------------------------------

    st.divider()

    if st.button(
        "🔍 START PDF PROOFREADING",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Reading PDF artwork and comparing it against the Order Form..."
        ):

            report = create_report(
                df,
                pdf_pages
            )


        st.divider()

        st.subheader(
            "📋 Proofreading Report"
        )


        # -------------------------------------------------
        # No matches
        # -------------------------------------------------

        if report.empty:

            st.warning(
                "No PDF artwork text could be matched "
                "against the corresponding Order Form rows."
            )

            st.info(
                "This does NOT automatically mean the artwork "
                "is wrong. It means the PDF text could not be "
                "confidently associated with Order Form data."
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


            # -------------------------------------------------
            # Summary
            # -------------------------------------------------

            c1, c2, c3 = st.columns(
                3
            )

            with c1:

                st.metric(
                    "CHECKED",
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


            # -------------------------------------------------
            # Styled report
            # -------------------------------------------------

            styled = (
                report
                .style
                .map(
                    status_style,
                    subset=[
                        "STATUS"
                    ]
                )
            )

            st.dataframe(
                styled,
                use_container_width=True,
                hide_index=True
            )


            # -------------------------------------------------
            # Conclusion
            # -------------------------------------------------

            st.divider()

            if fail_count == 0:

                st.success(
                    "✅ CONCLUSION: "
                    "No proofreading mismatches were detected "
                    "among the PDF text that could be associated "
                    "with the Order Form."
                )

            else:

                st.error(
                    f"❌ CONCLUSION: "
                    f"{fail_count} proofreading mismatch(es) detected."
                )


            # -------------------------------------------------
            # Download
            # -------------------------------------------------

            csv = (
                report
                .to_csv(
                    index=False
                )
                .encode(
                    "utf-8-sig"
                )
            )

            st.download_button(
                "⬇️ Download QC Report",
                data=csv,
                file_name="Order_Form_PDF_Proofreading_Report.csv",
                mime="text/csv",
                use_container_width=True
            )

else:

    st.info(
        "Upload both the Excel Order Form and PDF Artwork."
    )
