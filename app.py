import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from rapidfuzz import fuzz
from difflib import SequenceMatcher


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="PDF Proofreader",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# DARK UI
# =========================================================

st.markdown(
    """
    <style>

    html,
    body,
    [data-testid="stAppViewContainer"],
    [data-testid="stApp"],
    .stApp,
    .main {
        background-color: #0e1117 !important;
        color: #ffffff !important;
    }

    [data-testid="stAppViewContainer"] {
        background-color: #0e1117 !important;
    }

    [data-testid="stHeader"] {
        background-color: #0e1117 !important;
    }

    [data-testid="stMain"] {
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
        transition: all 0.2s ease-in-out;
    }

    div.stButton > button:hover {
        background-color: #1976D2 !important;
        color: #ffffff !important;
        border: 2px solid #000000 !important;
    }

    div.stButton > button:active {
        background-color: #1565C0 !important;
        color: #ffffff !important;
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


# =========================================================
# TITLE
# =========================================================

st.markdown(
    '<div class="main-title">🔍 PDF Proofreader</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Compare selected Order Form fields against PDF artwork.'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = unicodedata.normalize(
        "NFKC",
        text
    )

    text = text.lower()

    # Normalize apostrophes
    text = text.replace("’", "'")
    text = text.replace("`", "'")

    # PDF line breaks
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Treat separators as spaces
    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    # Hyphens become spaces
    text = re.sub(
        r"-+",
        " ",
        text
    )

    # Remove remaining punctuation
    text = re.sub(
        r"[^\w%#'\s]",
        " ",
        text
    )

    # Apostrophe differences ignored
    text = text.replace(
        "'",
        ""
    )

    # Multiple spaces
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
# CREATE PDF TEXT BLOCKS
# =========================================================

def create_pdf_blocks(page_text):

    if not page_text:
        return []

    raw_lines = page_text.splitlines()

    lines = []

    for line in raw_lines:

        line = line.strip()

        if not line:
            continue

        if len(line) > 1000:
            continue

        lines.append(line)

    if not lines:
        return []

    blocks = []

    # -----------------------------------------------------
    # Individual lines
    # -----------------------------------------------------

    for line in lines:

        blocks.append(line)


    # -----------------------------------------------------
    # Adjacent line combinations
    # -----------------------------------------------------

    maximum = min(
        15,
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

            blocks.append(block)


    # -----------------------------------------------------
    # Full page
    # -----------------------------------------------------

    full_page = " ".join(
        lines
    )

    if full_page:
        blocks.append(full_page)


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

def exact_match(
    expected,
    actual
):

    expected_normalized = normalize_text(
        expected
    )

    actual_normalized = normalize_text(
        actual
    )

    if not expected_normalized:
        return False

    if not actual_normalized:
        return False

    # -----------------------------------------------------
    # Exact normalized text
    #
    # This is deliberately NOT a simple "expected in actual"
    # check.
    #
    # Example:
    #
    # Expected:
    # CHLORINE BLEACH
    #
    # Actual:
    # ONLY NON CHLORINE BLEACH
    #
    # This must NOT become PASS.
    # -----------------------------------------------------

    if expected_normalized == actual_normalized:
        return True

    # -----------------------------------------------------
    # Ignore spaces completely ONLY when the actual block
    # has the same content.
    # -----------------------------------------------------

    if compact_text(expected) == compact_text(actual):
        return True

    return False


# =========================================================
# SEQUENCE INFORMATION
# =========================================================

def sequence_analysis(
    expected_tokens,
    actual_tokens
):

    if not expected_tokens or not actual_tokens:
        return {
            "common_tokens": [],
            "longest_run": [],
            "common_count": 0,
            "coverage": 0
        }

    matcher = SequenceMatcher(
        None,
        expected_tokens,
        actual_tokens
    )

    matching_blocks = matcher.get_matching_blocks()

    common_tokens = []

    longest_run = []

    for block in matching_blocks:

        if block.size <= 0:
            continue

        current = expected_tokens[
            block.a:block.a + block.size
        ]

        common_tokens.extend(
            current
        )

        if len(current) > len(longest_run):

            longest_run = current

    common_count = len(
        set(expected_tokens)
        &
        set(actual_tokens)
    )

    coverage = (
        common_count
        /
        len(set(expected_tokens))
    )

    return {
        "common_tokens": common_tokens,
        "longest_run": longest_run,
        "common_count": common_count,
        "coverage": coverage
    }


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

    if not expected_tokens or not actual_tokens:

        return "Content differs."


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

            if expected_part and actual_part:

                differences.append(
                    f"{expected_part} → {actual_part}"
                )

        elif tag == "delete":

            differences.append(
                f"Missing: {expected_part}"
            )

        elif tag == "insert":

            differences.append(
                f"Extra: {actual_part}"
            )

    if not differences:

        return "Content differs."

    return "; ".join(
        differences[:10]
    )


# =========================================================
# EXACT SEARCH
# =========================================================

def search_exact_value(
    expected,
    pdf_blocks
):

    expected_tokens = tokenize(
        expected
    )

    for block in pdf_blocks:

        actual_tokens = tokenize(
            block
        )

        if not actual_tokens:
            continue

        # -------------------------------------------------
        # Exact block match
        # -------------------------------------------------

        if exact_match(
            expected,
            block
        ):

            return {
                "status": "PASS",
                "pdf": block,
                "difference": "—"
            }

        # -------------------------------------------------
        # If expected is a multi-word field and appears as
        # an exact sequence inside a PDF block, only accept
        # PASS when the surrounding text is clearly just
        # formatting/wrapping.
        #
        # Otherwise it is handled as a possible mismatch.
        # -------------------------------------------------

        if len(expected_tokens) >= 3:

            expected_norm = normalize_text(
                expected
            )

            actual_norm = normalize_text(
                block
            )

            # Exact sequence at block level
            if (
                expected_norm in actual_norm
                and
                len(actual_tokens)
                <= len(expected_tokens) + 2
            ):

                # Check that the extra words aren't meaningful
                # inserted content.

                if fuzz.ratio(
                    expected_norm,
                    actual_norm
                ) >= 92:

                    return {
                        "status": "PASS",
                        "pdf": block,
                        "difference": "—"
                    }

    return None


# =========================================================
# FIND STRONG COMMON SEQUENCE
# =========================================================

def find_strong_sequence(
    expected_tokens,
    actual_tokens
):

    if not expected_tokens or not actual_tokens:
        return None

    matcher = SequenceMatcher(
        None,
        expected_tokens,
        actual_tokens
    )

    blocks = matcher.get_matching_blocks()

    best = None

    for block in blocks:

        if block.size <= 0:
            continue

        matched = expected_tokens[
            block.a:block.a + block.size
        ]

        if not matched:
            continue

        if (
            best is None
            or
            len(matched)
            >
            len(best)
        ):

            best = matched

    return best


# =========================================================
# PROBABLE MISMATCH SEARCH
# =========================================================

def search_probable_mismatch(
    expected,
    pdf_blocks
):

    expected_normalized = normalize_text(
        expected
    )

    expected_tokens = tokenize(
        expected
    )

    if not expected_tokens:
        return None


    best = None


    for block in pdf_blocks:

        actual_normalized = normalize_text(
            block
        )

        if not actual_normalized:
            continue

        actual_tokens = tokenize(
            block
        )

        if not actual_tokens:
            continue


        # -------------------------------------------------
        # Sequence analysis
        # -------------------------------------------------

        analysis = sequence_analysis(
            expected_tokens,
            actual_tokens
        )

        coverage = analysis[
            "coverage"
        ]

        longest_run = analysis[
            "longest_run"
        ]

        common_count = analysis[
            "common_count"
        ]


        # -------------------------------------------------
        # Similarity
        # -------------------------------------------------

        ratio = fuzz.ratio(
            expected_normalized,
            actual_normalized
        )

        partial = fuzz.partial_ratio(
            expected_normalized,
            actual_normalized
        )

        token_ratio = fuzz.token_set_ratio(
            expected_normalized,
            actual_normalized
        )


        # -------------------------------------------------
        # Longest contiguous sequence ratio
        # -------------------------------------------------

        if expected_tokens:

            sequence_ratio = (
                len(longest_run)
                /
                len(expected_tokens)
            )

        else:

            sequence_ratio = 0


        # -------------------------------------------------
        # Combined score
        # -------------------------------------------------

        score = (
            ratio * 0.35
            +
            partial * 0.10
            +
            token_ratio * 0.20
            +
            coverage * 100 * 0.20
            +
            sequence_ratio * 100 * 0.15
        )


        # =================================================
        # RULE 1
        #
        # Two or more common consecutive words are a
        # strong indication that this is the same artwork
        # field with a changed value.
        #
        # Example:
        #
        # MADE IN CHINA
        # MADE IN VIETNAM
        #
        # Common sequence:
        # MADE IN
        #
        # Therefore FAIL.
        # =================================================

        strong_sequence = (
            len(longest_run) >= 2
        )


        # =================================================
        # RULE 2
        #
        # Long fields such as care instructions.
        #
        # If a large portion of the expected text appears
        # in the same sequence, but the content differs,
        # report FAIL.
        # =================================================

        long_field_match = (
            len(expected_tokens) >= 6
            and
            (
                coverage >= 0.45
                or
                sequence_ratio >= 0.35
            )
            and
            score >= 55
        )


        # =================================================
        # RULE 3
        #
        # Short fields.
        #
        # For a two-word value, at least one meaningful
        # neighboring word must match.
        # =================================================

        short_field_match = False

        if len(expected_tokens) <= 2:

            short_field_match = (
                strong_sequence
                and
                coverage >= 0.50
            )


        # =================================================
        # RULE 4
        #
        # Medium fields.
        # =================================================

        medium_field_match = False

        if 3 <= len(expected_tokens) <= 5:

            medium_field_match = (
                (
                    strong_sequence
                    and
                    coverage >= 0.40
                )
                or
                (
                    coverage >= 0.60
                    and
                    score >= 65
                )
            )


        # =================================================
        # DECISION
        # =================================================

        probable_mismatch = (
            short_field_match
            or
            medium_field_match
            or
            long_field_match
        )


        if not probable_mismatch:
            continue


        # -------------------------------------------------
        # Avoid accepting a completely unrelated block.
        # -------------------------------------------------

        if common_count <= 0:
            continue


        # -------------------------------------------------
        # Create result
        # -------------------------------------------------

        result = {
            "status": "FAIL",
            "pdf": block,
            "difference": get_difference(
                expected,
                block
            ),
            "score": score,
            "coverage": coverage,
            "sequence": len(longest_run)
        }


        # -------------------------------------------------
        # Keep strongest candidate
        # -------------------------------------------------

        if (
            best is None
            or
            result["score"]
            >
            best["score"]
        ):

            best = result


    return best


# =========================================================
# CHECK FIELD
# =========================================================

def check_field(
    expected,
    pdf_blocks
):

    expected = str(
        expected
    ).strip()

    if not expected:

        return {
            "status": "SKIP",
            "pdf": "Blank Order Form value",
            "difference": "Order Form value is blank."
        }


    # =====================================================
    # 1. EXACT MATCH
    # =====================================================

    exact = search_exact_value(
        expected,
        pdf_blocks
    )

    if exact:

        return exact


    # =====================================================
    # 2. PROBABLE MISMATCH
    # =====================================================

    probable = search_probable_mismatch(
        expected,
        pdf_blocks
    )

    if probable:

        return probable


    # =====================================================
    # 3. COMPLETELY ABSENT
    #
    # IMPORTANT:
    #
    # If there is no meaningful evidence that this field
    # exists in the PDF, IGNORE it.
    #
    # This is different from an error.
    # =====================================================

    return {
        "status": "SKIP",
        "pdf": "Not detected in PDF",
        "difference": (
            "Order Form data is not present in the PDF. "
            "Comparison ignored."
        )
    }


# =========================================================
# BUILD REPORT
# =========================================================

def build_report(
    df,
    pdf_pages,
    selected_fields
):

    results = []

    field_no = 1


    # -----------------------------------------------------
    # PDF PAGE → EXCEL ROW
    #
    # Excel row 2 = PDF page 1
    # Excel row 3 = PDF page 2
    # Excel row 4 = PDF page 3
    # -----------------------------------------------------

    for page_index, page in enumerate(
        pdf_pages
    ):

        excel_index = page_index


        # -------------------------------------------------
        # No corresponding Excel row
        # -------------------------------------------------

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
                        "STATUS": "SKIP",
                        "DIFFERENCE": "No corresponding Excel row."
                    }
                )

                field_no += 1

            continue


        row = df.iloc[
            excel_index
        ]


        # -------------------------------------------------
        # Extract PDF blocks
        # -------------------------------------------------

        pdf_blocks = create_pdf_blocks(
            page["text"]
        )


        # -------------------------------------------------
        # CHECK EVERY SELECTED FIELD
        # -------------------------------------------------

        for field in selected_fields:

            value = row[field]


            if pd.isna(value):

                value = ""

            else:

                value = str(
                    value
                ).strip()


            # -------------------------------------------------
            # Blank Order Form value
            # -------------------------------------------------

            if not value:

                results.append(
                    {
                        "FIELD NO": field_no,
                        "PDF PAGE": page["page"],
                        "EXCEL ROW": excel_index + 2,
                        "FIELD": field,
                        "ORDER FORM DATA": "",
                        "PDF OUTPUT": "Blank Order Form value",
                        "STATUS": "SKIP",
                        "DIFFERENCE": "Order Form field is blank. Ignored."
                    }
                )

                field_no += 1

                continue


            # -------------------------------------------------
            # Perform check
            # -------------------------------------------------

            result = check_field(
                value,
                pdf_blocks
            )


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


    return pd.DataFrame(
        results
    )


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

    if value == "SKIP":

        return (
            "background-color: #6b7280;"
            "color: white;"
            "font-weight: bold;"
        )

    return ""


# =========================================================
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
        key="excel_upload"
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
        key="pdf_upload"
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
        '<div class="section-title">Select Fields to Validate</div>',
        unsafe_allow_html=True
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
# COMPARE BUTTON
# =========================================================

if (
    excel_file
    and pdf_file
    and selected_fields
):

    st.markdown(
        "<br>",
        unsafe_allow_html=True
    )

    if st.button(
        "🔍  COMPARE & PROOFREAD",
        use_container_width=True
    ):

        with st.spinner(
            "Checking PDF artwork..."
        ):

            report = build_report(
                df,
                pdf_pages,
                selected_fields
            )


        # =================================================
        # REPORT
        # =================================================

        st.divider()

        st.markdown(
            '<div class="section-title">QC Report</div>',
            unsafe_allow_html=True
        )


        # =================================================
        # COUNTS
        # =================================================

        pass_count = int(
            (
                report["STATUS"]
                == "PASS"
            ).sum()
        )

        fail_count = int(
            (
                report["STATUS"]
                == "FAIL"
            ).sum()
        )

        skip_count = int(
            (
                report["STATUS"]
                == "SKIP"
            ).sum()
        )


        # =================================================
        # SUMMARY
        # =================================================

        col1, col2, col3 = st.columns(
            3
        )


        with col1:

            st.metric(
                "PASS",
                pass_count
            )


        with col2:

            st.metric(
                "FAIL",
                fail_count
            )


        with col3:

            st.metric(
                "IGNORED",
                skip_count
            )


        # =================================================
        # REPORT TABLE
        # =================================================

        styled_report = (
            report
            .style
            .map(
                style_status,
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


        if fail_count > 0:

            st.error(
                f"❌ FAIL — {fail_count} mismatch(es) detected."
            )

        else:

            st.success(
                "✅ PASS — All detected artwork fields matched. "
                f"{skip_count} field(s) were not present in the PDF "
                "and were ignored."
            )


        # =================================================
        # DOWNLOAD REPORT
        # =================================================

        csv_data = (
            report
            .to_csv(
                index=False
            )
            .encode(
                "utf-8-sig"
            )
        )


        st.download_button(
            label="⬇️ Download QC Report",
            data=csv_data,
            file_name="PDF_Proofreading_QC_Report.csv",
            mime="text/csv",
            use_container_width=True
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

elif not selected_fields:

    st.caption(
        "Select the fields you want to validate."
    )
