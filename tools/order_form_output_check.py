import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from rapidfuzz import fuzz


# ==========================================================
# SESSION STATE INITIALIZATION
# ==========================================================

if "of_excel" not in st.session_state:
    st.session_state["of_excel"] = None

if "of_pdf" not in st.session_state:
    st.session_state["of_pdf"] = None

if "of_selected_fields" not in st.session_state:
    st.session_state["of_selected_fields"] = []

if "of_product_type" not in st.session_state:
    st.session_state["of_product_type"] = "----- SELECT -----"

if "of_result" not in st.session_state:
    st.session_state["of_result"] = None


# ==========================================================
# FIELD CONCEPTS
# ==========================================================

FIELD_CONCEPTS = {
    "ITEM CODE": [
        "item code",
        "itemcode",
        "item",
        "sku",
        "style number",
        "style no",
        "style"
    ],

    "ORDER NUMBER": [
        "order form",
        "order number",
        "order no",
        "order #",
        "order"
    ],

    "PRODUCT GENDER": [
        "product gender",
        "gender",
        "sex"
    ],

    "PRODUCT TYPE": [
        "product type",
        "product",
        "type"
    ],

    "COO": [
        "coo",
        "country of origin",
        "country origin",
        "made in",
        "origin"
    ],

    "ENGLISH COO": [
        "english coo",
        "coo english",
        "english country of origin",
        "english country"
    ],

    "FRENCH COO": [
        "french coo",
        "coo french",
        "french country of origin",
        "french country"
    ],

    "CARE": [
        "care",
        "care instruction",
        "care instructions",
        "washing instruction",
        "washing instructions",
        "wash instruction"
    ],

    "ENGLISH CARE": [
        "english care",
        "care english",
        "english instruction",
        "english instructions"
    ],

    "FRENCH CARE": [
        "french care",
        "care french",
        "french instruction",
        "french instructions"
    ],

    "CONTENT": [
        "content",
        "fiber content",
        "fabric content",
        "material",
        "composition"
    ],

    "FIT": [
        "fit",
        "product fit",
        "fit type"
    ],

    "SIZE": [
        "size",
        "size 1",
        "size1",
        "size modifier",
        "size label"
    ],

    "DESCRIPTION": [
        "description",
        "product description",
        "desc"
    ],

    "COLOR": [
        "color",
        "colour",
        "product color",
        "product colour"
    ],
}


# ==========================================================
# TEXT NORMALIZATION
# ==========================================================

def normalize_unicode(value):
    if value is None:
        return ""

    value = str(value)

    value = unicodedata.normalize("NFKC", value)

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u2022": " ",
        "\t": " ",
        "\r": " ",
        "\n": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def normalize_text(value):
    """
    Normalize text for comparison.

    Handles:
    - upper/lower case
    - punctuation
    - commas
    - periods
    - hyphens
    - slashes
    - brackets
    - extra spaces
    - line breaks
    """

    value = normalize_unicode(value)

    value = value.lower()

    value = re.sub(r"[^\w\s]", " ", value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def compact_text(value):
    """
    Removes spaces after normalization.

    Example:
        "MADE IN CHINA"
        "MADEINCHINA"

    become comparable.
    """

    value = normalize_text(value)

    return re.sub(r"\s+", "", value)


# ==========================================================
# EXCEL HELPERS
# ==========================================================

def read_excel_file(uploaded_file):

    if uploaded_file is None:
        return pd.DataFrame()

    uploaded_file.seek(0)

    try:

        excel = pd.ExcelFile(uploaded_file)

        for sheet in excel.sheet_names:

            uploaded_file.seek(0)

            df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet
            )

            if not df.empty:
                return df

        return pd.DataFrame()

    except Exception as exc:

        st.error(
            f"Unable to read Excel file: {exc}"
        )

        return pd.DataFrame()


def clean_dataframe(df):

    df = df.copy()

    df = df.dropna(
        axis=0,
        how="all"
    )

    df = df.dropna(
        axis=1,
        how="all"
    )

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    return df


# ==========================================================
# FIELD DETECTION
# ==========================================================

def score_column_against_concept(
    column_name,
    aliases
):

    column = normalize_text(
        column_name
    )

    best_score = 0

    for alias in aliases:

        alias_normalized = normalize_text(
            alias
        )

        if column == alias_normalized:

            best_score = max(
                best_score,
                100
            )

        elif alias_normalized in column:

            best_score = max(
                best_score,
                92
            )

        else:

            score = fuzz.token_set_ratio(
                column,
                alias_normalized
            )

            best_score = max(
                best_score,
                score
            )

    return best_score


def detect_field_mapping(df):

    mapping = {}

    for concept, aliases in FIELD_CONCEPTS.items():

        best_column = None
        best_score = 0

        for column in df.columns:

            score = score_column_against_concept(
                column,
                aliases
            )

            if score > best_score:

                best_score = score
                best_column = column

        if (
            best_column is not None
            and best_score >= 65
        ):

            mapping[concept] = {
                "column": best_column,
                "score": best_score
            }

    return mapping


# ==========================================================
# PDF EXTRACTION
# ==========================================================

def extract_pdf_text(uploaded_pdf):

    if uploaded_pdf is None:
        return []

    uploaded_pdf.seek(0)

    pdf_bytes = uploaded_pdf.read()

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
            "text": normalize_unicode(text)
        })

    document.close()

    return pages


def combine_pdf_text(pages):

    return "\n".join(
        page["text"]
        for page in pages
    )


# ==========================================================
# EXCEL VALUE EXTRACTION
# ==========================================================

def get_column_values(
    df,
    column
):

    values = []

    if column not in df.columns:
        return values

    for value in df[column].tolist():

        if pd.isna(value):
            continue

        value = normalize_unicode(
            value
        ).strip()

        if not value:
            continue

        values.append(value)

    return values


def combine_values(values):

    return " ".join(
        str(value)
        for value in values
        if str(value).strip()
    )


# ==========================================================
# MATCHING
# ==========================================================

def direct_match(
    expected,
    artwork
):

    expected_normalized = normalize_text(
        expected
    )

    artwork_normalized = normalize_text(
        artwork
    )

    if not expected_normalized:
        return False

    if expected_normalized in artwork_normalized:
        return True

    expected_compact = compact_text(
        expected
    )

    artwork_compact = compact_text(
        artwork
    )

    if expected_compact in artwork_compact:
        return True

    return False


def fuzzy_match(
    expected,
    artwork,
    threshold=88
):

    expected_normalized = normalize_text(
        expected
    )

    artwork_normalized = normalize_text(
        artwork
    )

    if not expected_normalized:
        return False, 0

    score = fuzz.partial_ratio(
        expected_normalized,
        artwork_normalized
    )

    return (
        score >= threshold,
        score
    )


def find_best_context(
    expected,
    artwork,
    window=180
):

    expected_normalized = normalize_text(
        expected
    )

    if not expected_normalized:
        return ""

    artwork_normalized = normalize_text(
        artwork
    )

    index = artwork_normalized.find(
        expected_normalized
    )

    if index == -1:
        return ""

    start = max(
        0,
        index - window
    )

    end = min(
        len(artwork_normalized),
        index
        + len(expected_normalized)
        + window
    )

    return artwork_normalized[
        start:end
    ]


# ==========================================================
# SPECIAL FIELD LOGIC
# ==========================================================

def is_french_field(field_name):

    return (
        "FRENCH"
        in field_name.upper()
    )


def is_english_field(field_name):

    return (
        "ENGLISH"
        in field_name.upper()
    )


def clean_field_value(
    field_name,
    value
):

    value = normalize_unicode(
        value
    )

    if field_name in [
        "SIZE",
        "FIT",
        "COLOR"
    ]:

        value = re.sub(
            r"\s+",
            " ",
            value
        )

    return value.strip()


# ==========================================================
# BUILD VALIDATION ROWS
# ==========================================================

def build_validation_rows(
    df,
    selected_fields,
    field_mapping
):

    rows = []

    for field_name in selected_fields:

        if field_name not in field_mapping:

            rows.append({
                "field": field_name,
                "column": "Not detected",
                "expected": "",
                "status": "NOT FOUND",
                "confidence": 0,
                "reason":
                    "Matching column could not be detected."
            })

            continue

        column = field_mapping[
            field_name
        ]["column"]

        values = get_column_values(
            df,
            column
        )

        expected = combine_values(
            values
        )

        expected = clean_field_value(
            field_name,
            expected
        )

        rows.append({
            "field": field_name,
            "column": column,
            "expected": expected
        })

    return rows


# ==========================================================
# VALIDATE
# ==========================================================

def validate_rows(
    rows,
    artwork_text
):

    result_rows = []

    for row in rows:

        field = row["field"]
        expected = row["expected"]

        if not expected:

            result_rows.append({
                **row,
                "status": "SKIPPED",
                "confidence": 0,
                "reason":
                    "No usable value found in Order Form."
            })

            continue

        # --------------------------------------------------
        # DIRECT MATCH
        # --------------------------------------------------

        if direct_match(
            expected,
            artwork_text
        ):

            result_rows.append({
                **row,
                "status": "PASS",
                "confidence": 100,
                "reason":
                    "Order Form value found in output."
            })

            continue

        # --------------------------------------------------
        # FUZZY MATCH
        # --------------------------------------------------

        matched, score = fuzzy_match(
            expected,
            artwork_text
        )

        if matched:

            result_rows.append({
                **row,
                "status": "PASS",
                "confidence": round(
                    score,
                    1
                ),
                "reason":
                    "High similarity match found in output."
            })

        else:

            result_rows.append({
                **row,
                "status": "FAIL",
                "confidence": round(
                    score,
                    1
                ),
                "reason":
                    "Expected value was not found in output."
            })

    return result_rows


# ==========================================================
# DISPLAY RESULT
# ==========================================================

def display_results(
    result_rows
):

    if not result_rows:

        st.warning(
            "No fields were available for validation."
        )

        return

    # ======================================================
    # SUMMARY
    # ======================================================

    total = len(
        result_rows
    )

    passed = sum(
        row["status"] == "PASS"
        for row in result_rows
    )

    failed = sum(
        row["status"] == "FAIL"
        for row in result_rows
    )

    skipped = sum(
        row["status"] == "SKIPPED"
        for row in result_rows
    )

    not_found = sum(
        row["status"] == "NOT FOUND"
        for row in result_rows
    )

    st.markdown("---")

    st.subheader(
        "Validation Result"
    )

    # ======================================================
    # OVERALL RESULT
    # ======================================================

    if failed == 0 and not_found == 0:

        st.success(
            "PASS — All selected fields matched the output."
        )

    else:

        st.error(
            f"FAIL — {failed + not_found} "
            "selected field(s) require attention."
        )

    # ======================================================
    # SUMMARY METRICS
    # ======================================================

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Selected Fields",
            total
        )

    with c2:

        st.metric(
            "PASS",
            passed
        )

    with c3:

        st.metric(
            "FAIL",
            failed
        )

    with c4:

        st.metric(
            "Skipped",
            skipped + not_found
        )

    # ======================================================
    # RESULT TABLE
    # ======================================================

    display_data = []

    for row in result_rows:

        display_data.append({
            "Field": row["field"],
            "Order Form Column": row["column"],
            "Expected Value": row["expected"],
            "Result": row["status"],
            "Confidence": (
                f"{row['confidence']}%"
                if row["confidence"]
                else "-"
            ),
            "Details": row["reason"]
        })

    result_df = pd.DataFrame(
        display_data
    )

    # ======================================================
    # RESULT STYLING
    # ======================================================

    def style_status(
        value
    ):

        if value == "PASS":

            return (
                "background-color: #166534; "
                "color: white; "
                "font-weight: bold;"
            )

        if value == "FAIL":

            return (
                "background-color: #991b1b; "
                "color: white; "
                "font-weight: bold;"
            )

        return (
            "background-color: #475569; "
            "color: white; "
            "font-weight: bold;"
        )

    styled = result_df.style.map(
        style_status,
        subset=["Result"]
    )

    st.dataframe(
        styled,
        width="stretch",
        hide_index=True
    )

    # ======================================================
    # FAILURE DETAILS
    # ======================================================

    failures = [
        row
        for row in result_rows
        if row["status"] == "FAIL"
    ]

    if failures:

        st.markdown(
            "### ⚠️ Fields Requiring Attention"
        )

        for row in failures:

            with st.expander(
                f"❌ {row['field']}"
            ):

                st.write(
                    f"**Order Form Column:** "
                    f"{row['column']}"
                )

                st.write(
                    f"**Expected:** "
                    f"{row['expected']}"
                )

                st.write(
                    f"**Match Confidence:** "
                    f"{row['confidence']}%"
                )

                st.write(
                    f"**Reason:** "
                    f"{row['reason']}"
                )


# ==========================================================
# MAIN TOOL
# ==========================================================

def main():

    # ======================================================
    # TITLE
    # ======================================================

    st.markdown(
        """
        <h1 style="margin-bottom:0;">
            Order Form → Output Check
        </h1>

        <p style="color:#94a3b8;">
            Validate selected Order Form data against
            the final PDF artwork.
        </p>
        """,
        unsafe_allow_html=True
    )

    # ======================================================
    # NEW START
    # ======================================================

    top_left, top_right = st.columns(
        [6, 1]
    )

    with top_right:

        if st.button(
            "↻ NEW START",
            key="of_new_start"
        ):

            st.session_state[
                "of_excel"
            ] = None

            st.session_state[
                "of_pdf"
            ] = None

            st.session_state[
                "of_selected_fields"
            ] = []

            st.session_state[
                "of_product_type"
            ] = "----- SELECT -----"

            st.session_state[
                "of_result"
            ] = None

            st.rerun()

    # ======================================================
    # PRODUCT TYPE
    # ======================================================

    st.markdown(
        "### 1. Select Product Type"
    )

    product_types = [
        "----- SELECT -----",
        "STANDARD",
        "PFL"
    ]

    current_product_type = (
        st.session_state.get(
            "of_product_type",
            "----- SELECT -----"
        )
    )

    if current_product_type not in product_types:

        current_product_type = (
            "----- SELECT -----"
        )

    product_type = st.selectbox(
        "Product Type",
        product_types,
        index=product_types.index(
            current_product_type
        ),
        key="of_product_type"
    )

    if product_type == "----- SELECT -----":

        st.info(
            "Select the product type before starting validation."
        )

    # ======================================================
    # UPLOADS
    # ======================================================

    st.markdown(
        "### 2. Upload Files"
    )

    upload_col1, upload_col2 = st.columns(
        2
    )

    with upload_col1:

        excel_file = st.file_uploader(
            "📊 Upload Order Form",
            type=["xlsx", "xls"],
            key="of_excel_upload"
        )

    with upload_col2:

        pdf_file = st.file_uploader(
            "📄 Upload Output PDF",
            type=["pdf"],
            key="of_pdf_upload"
        )

    if excel_file is None or pdf_file is None:

        st.info(
            "Upload both the Order Form Excel and "
            "Output PDF to continue."
        )

        return

    # ======================================================
    # READ EXCEL
    # ======================================================

    df = read_excel_file(
        excel_file
    )

    if df.empty:

        st.error(
            "The Order Form Excel appears to be empty."
        )

        return

    df = clean_dataframe(
        df
    )

    # ======================================================
    # DETECT FIELD MAPPING
    # ======================================================

    field_mapping = detect_field_mapping(
        df
    )

    st.markdown(
        "### 3. Select Fields to Validate"
    )

    available_concepts = []

    for concept in FIELD_CONCEPTS:

        if concept in field_mapping:

            available_concepts.append(
                concept
            )

    if not available_concepts:

        st.error(
            "No supported fields could be detected "
            "in the Order Form."
        )

        st.write(
            "Detected Excel columns:"
        )

        st.write(
            list(df.columns)
        )

        return

    # ======================================================
    # DEFAULT FIELDS
    # ======================================================

    default_fields = [
        field
        for field in available_concepts
        if field not in [
            "FRENCH CARE",
            "FRENCH COO"
        ]
    ]

    selected_fields = st.multiselect(
        "Select the Order Form fields you want to compare",
        options=available_concepts,
        default=default_fields,
        key="of_selected_fields"
    )

    # ======================================================
    # FIELD MAPPING PREVIEW
    # ======================================================

    with st.expander(
        "🔎 View detected Order Form field mapping"
    ):

        mapping_rows = []

        for concept in available_concepts:

            info = field_mapping[
                concept
            ]

            mapping_rows.append({
                "Tool Field": concept,
                "Excel Column": info["column"],
                "Detection Confidence":
                    f"{info['score']}%"
            })

        mapping_df = pd.DataFrame(
            mapping_rows
        )

        st.dataframe(
            mapping_df,
            width="stretch",
            hide_index=True
        )

    # ======================================================
    # PRODUCT TYPE RULES
    # ======================================================

    if product_type == "PFL":

        st.info(
            "PFL mode is enabled. Panel-based output artwork "
            "can contain variable data continuing across panels."
        )

    elif product_type == "STANDARD":

        st.info(
            "Standard mode is enabled."
        )

    # ======================================================
    # VALIDATION BUTTON
    # ======================================================

    st.markdown(
        "### 4. Run Validation"
    )

    if not selected_fields:

        st.warning(
            "Select at least one field before running validation."
        )

        return

    compare = st.button(
        "🔍  COMPARE ORDER FORM WITH OUTPUT",
        key="of_compare",
        type="primary",
        width="stretch"
    )

    if not compare:
        return

    # ======================================================
    # EXTRACT PDF
    # ======================================================

    with st.spinner(
        "Reading and analyzing the output PDF..."
    ):

        pdf_pages = extract_pdf_text(
            pdf_file
        )

        artwork_text = combine_pdf_text(
            pdf_pages
        )

    if not artwork_text.strip():

        st.error(
            "No readable text was found in the PDF."
        )

        return

    # ======================================================
    # BUILD EXPECTED VALUES
    # ======================================================

    validation_rows = build_validation_rows(
        df,
        selected_fields,
        field_mapping
    )

    # ======================================================
    # VALIDATE
    # ======================================================

    with st.spinner(
        "Comparing Order Form data with output..."
    ):

        result_rows = validate_rows(
            validation_rows,
            artwork_text
        )

    # ======================================================
    # SAVE RESULT
    # ======================================================

    st.session_state[
        "of_result"
    ] = result_rows

    # ======================================================
    # DISPLAY RESULTS
    # ======================================================

    display_results(
        result_rows
    )

    # ======================================================
    # PDF INFORMATION
    # ======================================================

    st.markdown("---")

    st.caption(
        f"Output PDF analyzed: "
        f"{len(pdf_pages)} page(s)"
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    main()
