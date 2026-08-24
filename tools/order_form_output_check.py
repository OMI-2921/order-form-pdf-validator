import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from rapidfuzz import fuzz


# ==========================================================
# SESSION STATE
# ==========================================================

if "of_product_type" not in st.session_state:
    st.session_state["of_product_type"] = "----- SELECT -----"

if "of_selected_excel_fields" not in st.session_state:
    st.session_state["of_selected_excel_fields"] = []

if "of_result" not in st.session_state:
    st.session_state["of_result"] = None


# ==========================================================
# PAGE HELPERS
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
    value = normalize_unicode(value)

    value = value.lower()

    value = re.sub(
        r"[^\w\s]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def compact_text(value):
    return re.sub(
        r"\s+",
        "",
        normalize_text(value)
    )


# ==========================================================
# EXCEL
# ==========================================================

def read_excel_file(uploaded_file):

    if uploaded_file is None:
        return pd.DataFrame()

    try:

        uploaded_file.seek(0)

        excel = pd.ExcelFile(
            uploaded_file
        )

        for sheet_name in excel.sheet_names:

            uploaded_file.seek(0)

            df = pd.read_excel(
                uploaded_file,
                sheet_name=sheet_name
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
# PDF
# ==========================================================

def extract_pdf_text(uploaded_pdf):

    if uploaded_pdf is None:
        return ""

    try:

        uploaded_pdf.seek(0)

        pdf_bytes = uploaded_pdf.read()

        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        pages = []

        for page in document:

            text = page.get_text(
                "text"
            )

            pages.append(
                normalize_unicode(text)
            )

        document.close()

        return "\n".join(pages)

    except Exception as exc:

        st.error(
            f"Unable to read PDF: {exc}"
        )

        return ""


# ==========================================================
# VALUES
# ==========================================================

def get_column_values(
    df,
    column
):

    if column not in df.columns:
        return []

    values = []

    for value in df[column].tolist():

        if pd.isna(value):
            continue

        value = normalize_unicode(
            value
        ).strip()

        if value:
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


# ==========================================================
# VALIDATION
# ==========================================================

def validate_field(
    field_name,
    expected,
    artwork_text
):

    if not expected:

        return {
            "field": field_name,
            "expected": "",
            "status": "SKIPPED",
            "confidence": 0,
            "details": "No usable value found."
        }

    if direct_match(
        expected,
        artwork_text
    ):

        return {
            "field": field_name,
            "expected": expected,
            "status": "PASS",
            "confidence": 100,
            "details": "Value found in output."
        }

    matched, score = fuzzy_match(
        expected,
        artwork_text
    )

    if matched:

        return {
            "field": field_name,
            "expected": expected,
            "status": "PASS",
            "confidence": round(
                score,
                1
            ),
            "details": "High similarity match found."
        }

    return {
        "field": field_name,
        "expected": expected,
        "status": "FAIL",
        "confidence": round(
            score,
            1
        ),
        "details": "Expected value was not found."
    }


# ==========================================================
# RESULTS
# ==========================================================

def display_results(
    results
):

    if not results:

        st.warning(
            "No validation results available."
        )

        return

    passed = sum(
        r["status"] == "PASS"
        for r in results
    )

    failed = sum(
        r["status"] == "FAIL"
        for r in results
    )

    skipped = sum(
        r["status"] == "SKIPPED"
        for r in results
    )

    st.markdown("---")

    st.subheader(
        "Validation Result"
    )

    if failed == 0:

        st.success(
            "PASS — All selected fields matched the output."
        )

    else:

        st.error(
            f"FAIL — {failed} selected field(s) "
            "did not match the output."
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Selected Fields",
            len(results)
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

    display_rows = []

    for result in results:

        display_rows.append({
            "Field": result["field"],
            "Expected Value": result["expected"],
            "Result": result["status"],
            "Confidence": (
                f'{result["confidence"]}%'
                if result["confidence"]
                else "-"
            ),
            "Details": result["details"]
        })

    results_df = pd.DataFrame(
        display_rows
    )

    def status_style(value):

        if value == "PASS":

            return (
                "background-color:#166534;"
                "color:white;"
                "font-weight:bold;"
            )

        if value == "FAIL":

            return (
                "background-color:#991b1b;"
                "color:white;"
                "font-weight:bold;"
            )

        return (
            "background-color:#475569;"
            "color:white;"
            "font-weight:bold;"
        )

    styled = results_df.style.map(
        status_style,
        subset=["Result"]
    )

    st.dataframe(
        styled,
        width="stretch",
        hide_index=True
    )

    failures = [
        result
        for result in results
        if result["status"] == "FAIL"
    ]

    if failures:

        st.markdown(
            "### ⚠️ Fields Requiring Attention"
        )

        for result in failures:

            with st.expander(
                f'❌ {result["field"]}'
            ):

                st.write(
                    f'**Expected Value:** '
                    f'{result["expected"]}'
                )

                st.write(
                    f'**Confidence:** '
                    f'{result["confidence"]}%'
                )

                st.write(
                    f'**Details:** '
                    f'{result["details"]}'
                )


# ==========================================================
# MAIN
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
            Select specific fields from the uploaded Order Form
            and validate them against the final PDF artwork.
        </p>
        """,
        unsafe_allow_html=True
    )

    # ======================================================
    # NEW START
    # ======================================================

    _, top_right = st.columns(
        [6, 1]
    )

    with top_right:

        if st.button(
            "↻ NEW START",
            key="of_new_start"
        ):

            st.session_state[
                "of_selected_excel_fields"
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
            "Select the product type before continuing."
        )

    # ======================================================
    # UPLOAD FILES
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

    if excel_file is None:

        st.info(
            "Upload the Order Form Excel to select fields."
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
            "The uploaded Excel is empty or could not be read."
        )

        return

    df = clean_dataframe(
        df
    )

    # ======================================================
    # SHOW ACTUAL EXCEL FIELDS
    # ======================================================

    st.markdown(
        "### 3. Select Fields from Excel"
    )

    excel_fields = [
        str(column).strip()
        for column in df.columns
        if str(column).strip()
    ]

    if not excel_fields:

        st.error(
            "No fields were found in the Excel."
        )

        return

    selected_excel_fields = st.multiselect(
        "Select ONLY the Excel fields you want to validate",
        options=excel_fields,
        default=[],
        key="of_selected_excel_fields"
    )

    # ======================================================
    # FIELD PREVIEW
    # ======================================================

    if selected_excel_fields:

        st.markdown(
            "#### Selected Fields"
        )

        preview_rows = []

        for column in selected_excel_fields:

            values = get_column_values(
                df,
                column
            )

            preview_rows.append({
                "Excel Field": column,
                "Values Found": len(values),
                "Preview": " | ".join(values[:3])
            })

        preview_df = pd.DataFrame(
            preview_rows
        )

        st.dataframe(
            preview_df,
            width="stretch",
            hide_index=True
        )

    else:

        st.info(
            "No fields selected. Choose the Excel fields "
            "you want the validator to check."
        )

        return

    # ======================================================
    # PFL / STANDARD
    # ======================================================

    if product_type == "PFL":

        st.info(
            "PFL mode selected."
        )

    elif product_type == "STANDARD":

        st.info(
            "Standard mode selected."
        )

    # ======================================================
    # PDF REQUIRED
    # ======================================================

    if pdf_file is None:

        st.info(
            "Now upload the Output PDF to continue."
        )

        return

    # ======================================================
    # COMPARE
    # ======================================================

    st.markdown(
        "### 4. Run Validation"
    )

    compare = st.button(
        "🔍  COMPARE ORDER FORM WITH OUTPUT",
        key="of_compare",
        type="primary",
        width="stretch"
    )

    if not compare:
        return

    # ======================================================
    # READ PDF
    # ======================================================

    with st.spinner(
        "Reading output PDF..."
    ):

        artwork_text = extract_pdf_text(
            pdf_file
        )

    if not artwork_text.strip():

        st.error(
            "No readable text was found in the PDF."
        )

        return

    # ======================================================
    # VALIDATE SELECTED EXCEL FIELDS
    # ======================================================

    with st.spinner(
        "Comparing selected Excel fields with output..."
    ):

        results = []

        for column in selected_excel_fields:

            values = get_column_values(
                df,
                column
            )

            expected = combine_values(
                values
            )

            result = validate_field(
                column,
                expected,
                artwork_text
            )

            results.append(
                result
            )

    # ======================================================
    # SAVE / DISPLAY
    # ======================================================

    st.session_state[
        "of_result"
    ] = results

    display_results(
        results
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    main()
