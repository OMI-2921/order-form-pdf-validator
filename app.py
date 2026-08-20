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

    /* =====================================================
       COMPLETE DARK BACKGROUND
       ===================================================== */

    html,
    body,
    [data-testid="stAppViewContainer"],
    [data-testid="stApp"],
    .stApp,
    .main {
        background-color: #0e1117 !important;
        color: #ffffff !important;
    }


    /* Main application container */

    [data-testid="stAppViewContainer"] {
        background-color: #0e1117 !important;
    }


    /* Header */

    [data-testid="stHeader"] {
        background-color: #0e1117 !important;
    }


    /* Main content */

    [data-testid="stMain"] {
        background-color: #0e1117 !important;
    }


    /* =====================================================
       ALL TEXT
       ===================================================== */

    .stApp,
    .stApp p,
    .stApp label,
    .stApp span,
    .stApp div {
        color: #ffffff;
    }


    /* =====================================================
       TITLE
       ===================================================== */

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


    /* =====================================================
       SECTION TITLES
       ===================================================== */

    .section-title {
        color: #ffffff !important;
        font-size: 20px;
        font-weight: 700;
        margin-top: 12px;
        margin-bottom: 10px;
    }


    /* =====================================================
       UPLOADER CONTAINER
       ===================================================== */

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


    /* Upload button */

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


    /* =====================================================
       SELECT BOX / MULTISELECT
       ===================================================== */

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


    /* Dropdown menu */

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


    /* Selected field pills */

    [data-baseweb="tag"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
    }


    [data-baseweb="tag"] span {
        color: #ffffff !important;
    }


    /* =====================================================
       COMPARE BUTTON
       ===================================================== */

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


    /* =====================================================
       DOWNLOAD BUTTON
       ===================================================== */

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


    /* =====================================================
       DATAFRAME
       ===================================================== */

    [data-testid="stDataFrame"] {

        border: 1px solid #374151 !important;

        border-radius: 10px !important;

    }


    /* =====================================================
       METRICS
       ===================================================== */

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


    /* =====================================================
       DIVIDER
       ===================================================== */

    hr {

        border-color: #30363d !important;

    }


    /* =====================================================
       INFO / CAPTION
       ===================================================== */

    .stCaption {

        color: #9ca3af !important;

    }


    /* =====================================================
       SUCCESS / WARNING / ERROR
       ===================================================== */

    [data-testid="stAlert"] {

        border-radius: 10px !important;

    }


    /* =====================================================
       SPINNER
       ===================================================== */

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

    # Case insensitive
    text = text.lower()

    # Normalize apostrophes
    text = text.replace("’", "'")
    text = text.replace("`", "'")

    # PDF line breaks
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Treat punctuation/separators as spaces
    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    # Hyphens should not create mismatch
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

    # Apostrophe differences should not cause failure
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
    # Combine adjacent lines
    #
    # Useful when artwork text wraps into paragraphs.
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

    # Normal normalized match
    if expected_normalized in actual_normalized:
        return True

    # Ignore spaces completely
    if compact_text(expected) in compact_text(actual):
        return True

    return False


# =========================================================
# FIND DIFFERENCE
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

    for block in pdf_blocks:

        if exact_match(
            expected,
            block
        ):

            return {
                "status": "PASS",
                "pdf": block,
                "difference": "—"
            }

    return None


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
        # Similarity calculations
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
        # Word overlap
        # -------------------------------------------------

        expected_set = set(
            expected_tokens
        )

        actual_set = set(
            actual_tokens
        )

        common = (
            expected_set
            &
            actual_set
        )

        if expected_set:

            common_ratio = (
                len(common)
                /
                len(expected_set)
            )

        else:

            common_ratio = 0


        # -------------------------------------------------
        # Combined similarity
        # -------------------------------------------------

        score = (
            ratio * 0.45
            +
            partial * 0.15
            +
            token_ratio * 0.20
            +
            common_ratio * 100 * 0.20
        )


        # -------------------------------------------------
        # Strict rules
        # -------------------------------------------------

        if len(expected_tokens) <= 2:

            acceptable = (
                ratio >= 88
                and
                common_ratio >= 0.50
            )

        elif len(expected_tokens) <= 5:

            acceptable = (
                score >= 78
                and
                common_ratio >= 0.50
            )

        else:

            acceptable = (
                score >= 70
                and
                common_ratio >= 0.40
            )


        if not acceptable:
            continue


        # -------------------------------------------------
        # Keep best match
        # -------------------------------------------------

        if (
            best is None
            or
            score > best["score"]
        ):

            best = {
                "status": "FAIL",
                "pdf": block,
                "difference": get_difference(
                    expected,
                    block
                ),
                "score": score
            }


    return best


# =========================================================
# CHECK FIELD
# =========================================================

def check_field(
    expected,
    pdf_blocks
):

    # -----------------------------------------------------
    # 1. Exact match
    # -----------------------------------------------------

    exact = search_exact_value(
        expected,
        pdf_blocks
    )

    if exact:

        return exact


    # -----------------------------------------------------
    # 2. Similar text / spelling mismatch
    # -----------------------------------------------------

    probable = search_probable_mismatch(
        expected,
        pdf_blocks
    )

    if probable:

        return probable


    # -----------------------------------------------------
    # 3. Not found
    #
    # IMPORTANT:
    # Selected fields are NEVER silently skipped.
    # -----------------------------------------------------

    return {
        "status": "NOT FOUND",
        "pdf": "Not found in PDF",
        "difference": "Selected field was not detected in the PDF."
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
    # etc.
    # -----------------------------------------------------

    for page_index, page in enumerate(
        pdf_pages
    ):

        excel_index = page_index


        # -------------------------------------------------
        # Corresponding Excel row doesn't exist
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
                        "STATUS": "NOT FOUND",
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
                        "STATUS": "NOT FOUND",
                        "DIFFERENCE": "Order Form field is blank."
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

    if value == "NOT FOUND":

        return (
            "background-color: #9e6a03;"
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

    except Exception:

        st.error(
            "Unable to read the Excel Order Form."
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

    except Exception:

        st.error(
            "Unable to read the PDF file."
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

        not_found_count = int(
            (
                report["STATUS"]
                == "NOT FOUND"
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
                "NOT FOUND",
                not_found_count
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

        elif not_found_count > 0:

            st.warning(
                f"⚠️ REVIEW — {not_found_count} "
                f"selected field(s) were not found in the PDF."
            )

        else:

            st.success(
                "✅ PASS — All selected fields matched the PDF artwork."
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
