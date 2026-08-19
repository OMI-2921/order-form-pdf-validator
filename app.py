import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from rapidfuzz import fuzz


# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="Order Form → PDF Validator",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Validator")
st.caption(
    "Compare relevant Order Form data against the PDF artwork output."
)


# =========================================================
# FIELD CONFIGURATION
# =========================================================

FIELD_MAPPING = {
    "Content": ["Content"],
    "English COO": ["EnglishCOO"],
    "English Care": ["EnglishCare"],

    "Size Line 1": ["SizeLine1"],
    "Size Line 2": ["SizeLine2"],
    "Size Line 3": ["SizeLine3"],

    "OSZ1": ["OSZ1"],
    "OSZ2": ["OSZ2"],
    "OSZ3": ["OSZ3"],
    "OSZ4": ["OSZ4"],
    "OSZ5": ["OSZ5"],
    "OSZ6": ["OSZ6"],
    "OSZ7": ["OSZ7"],
    "OSZ8": ["OSZ8"],
    "OSZ9": ["OSZ9"],
    "OSZ10": ["OSZ10"],
    "OSZ11": ["OSZ11"],
    "OSZ12": ["OSZ12"],
    "OSZ13": ["OSZ13"],
    "OSZ14": ["OSZ14"],
    "OSZ15": ["OSZ15"],
}


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):
    """
    Normalization used for comparison.

    - Case insensitive
    - Handles PDF line breaks
    - Handles extra spaces
    - Treats common punctuation as separators
    - Keeps % and # because they can be meaningful artwork data
    """

    if text is None:
        return ""

    text = str(text)

    text = unicodedata.normalize("NFKC", text)

    # Lowercase
    text = text.lower()

    # PDF line breaks become spaces
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Common separators become spaces
    text = re.sub(r"[,.;:|/\\]+", " ", text)
    text = re.sub(r"[-]+", " ", text)

    # Keep letters, numbers, %, # and spaces
    text = re.sub(r"[^\w%#\s]", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_for_exact_match(text):
    """
    Strong normalization used for exact comparison.
    """

    value = normalize_text(text)

    # Remove spaces for a second-level comparison.
    # This helps when artwork formatting introduces
    # unexpected spaces around punctuation.
    return value.replace(" ", "")


# =========================================================
# PDF TEXT EXTRACTION
# =========================================================

def extract_pdf_text(pdf_file):

    pdf_file.seek(0)

    pdf_bytes = pdf_file.read()

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages = []
    full_text_parts = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text()

        pages.append({
            "page": page_number,
            "text": text
        })

        full_text_parts.append(text)

    document.close()

    # Combine every page.
    # This is important for long text and text wrapped
    # across multiple PDF lines.
    full_text = "\n".join(full_text_parts)

    return pages, full_text


# =========================================================
# SHORT VALUE CHECK
# =========================================================

def is_short_value(value):
    """
    Identifies values where fuzzy matching is dangerous.

    Examples:
    0
    2
    4
    XXL
    M
    S
    """

    normalized = normalize_text(value)

    if not normalized:
        return True

    words = normalized.split()

    if len(words) == 1 and len(normalized) <= 5:
        return True

    return False


# =========================================================
# TOKEN-BASED SEARCH FOR SHORT VALUES
# =========================================================

def short_value_exists(expected, pdf_text):

    expected_norm = normalize_text(expected)

    if not expected_norm:
        return False

    pdf_norm = normalize_text(pdf_text)

    # Exact token matching for short values.
    #
    # Example:
    # expected = "2"
    #
    # This matches:
    # "2"
    #
    # But does NOT match:
    # "7606601"
    # "2026"
    # etc.

    pattern = r"(?<![\w])" + re.escape(expected_norm) + r"(?![\w])"

    return re.search(pattern, pdf_norm) is not None


# =========================================================
# FIND RELEVANT PDF OUTPUT
# =========================================================

def find_pdf_output(expected, pdf_pages, full_pdf_text):

    expected_norm = normalize_text(expected)

    if not expected_norm:
        return "", "SKIP"

    # -----------------------------------------------------
    # SHORT VALUES
    # -----------------------------------------------------

    if is_short_value(expected):

        if short_value_exists(expected, full_pdf_text):

            # Find a readable occurrence from PDF lines
            for page in pdf_pages:

                for line in page["text"].splitlines():

                    line_clean = line.strip()

                    if not line_clean:
                        continue

                    if short_value_exists(
                        expected,
                        line_clean
                    ):
                        return line_clean, "FOUND"

            return expected, "FOUND"

        return "", "NOT_FOUND"

    # -----------------------------------------------------
    # LONG VALUES
    # -----------------------------------------------------

    full_norm = normalize_text(full_pdf_text)

    expected_exact = normalize_for_exact_match(expected)
    full_exact = normalize_for_exact_match(full_pdf_text)

    # Exact complete-content match.
    #
    # This is the important change for care instructions:
    # PDF line wrapping does not matter.
    if expected_norm in full_norm:

        return extract_context(
            expected_norm,
            pdf_pages
        ), "FOUND"

    # Second comparison after removing spaces.
    if expected_exact in full_exact:

        return extract_context(
            expected_norm,
            pdf_pages
        ), "FOUND"

    return find_similar_pdf_text(
        expected,
        pdf_pages
    )


# =========================================================
# EXTRACT READABLE PDF CONTEXT
# =========================================================

def extract_context(expected_norm, pdf_pages):

    """
    Finds the relevant PDF lines surrounding the expected
    content so the report remains readable.

    It does NOT use only the first matching line for the
    comparison.
    """

    matching_lines = []

    for page in pdf_pages:

        lines = [
            line.strip()
            for line in page["text"].splitlines()
            if line.strip()
        ]

        page_text_norm = normalize_text(
            " ".join(lines)
        )

        if expected_norm in page_text_norm:

            # Return the complete page text.
            # This allows long care paragraphs to be visible
            # instead of returning only the first wrapped line.
            return " ".join(lines)

    return ""


# =========================================================
# SIMILARITY DIAGNOSTIC
# =========================================================

def find_similar_pdf_text(expected, pdf_pages):

    """
    Used only to provide a useful FAIL explanation.

    It does NOT turn a fuzzy match into PASS.
    """

    expected_norm = normalize_text(expected)

    best_text = ""
    best_score = 0

    for page in pdf_pages:

        lines = [
            line.strip()
            for line in page["text"].splitlines()
            if line.strip()
        ]

        # Compare small groups of lines together.
        # This helps with paragraph wrapping.
        for i in range(len(lines)):

            for window_size in range(1, 8):

                end = i + window_size

                if end > len(lines):
                    break

                block = " ".join(
                    lines[i:end]
                )

                block_norm = normalize_text(block)

                if not block_norm:
                    continue

                score = fuzz.ratio(
                    expected_norm,
                    block_norm
                )

                if score > best_score:

                    best_score = score
                    best_text = block

    return best_text, "SIMILAR"


# =========================================================
# COMPARE ONE FIELD
# =========================================================

def compare_field(expected, pdf_pages, full_pdf_text):

    expected = str(expected).strip()

    if not expected:
        return "", "SKIP", "No Order Form data to check."

    output, result_type = find_pdf_output(
        expected,
        pdf_pages,
        full_pdf_text
    )

    # -----------------------------------------------------
    # FOUND
    # -----------------------------------------------------

    if result_type == "FOUND":

        return (
            output,
            "PASS",
            "Complete data found in PDF. "
            "Case, spacing and artwork line wrapping ignored."
        )

    # -----------------------------------------------------
    # NOT FOUND
    # -----------------------------------------------------

    if result_type == "NOT_FOUND":

        return (
            "",
            "FAIL",
            "Expected data not found in PDF output."
        )

    # -----------------------------------------------------
    # SIMILAR
    # -----------------------------------------------------

    if result_type == "SIMILAR":

        if output:

            # Determine whether this looks like a spelling
            # difference or a larger data difference.
            expected_norm = normalize_text(expected)
            output_norm = normalize_text(output)

            score = fuzz.ratio(
                expected_norm,
                output_norm
            )

            if score >= 80:

                return (
                    output,
                    "FAIL",
                    "Possible spelling difference or "
                    "minor text difference."
                )

            return (
                output,
                "FAIL",
                "Data mismatch."
            )

        return (
            "",
            "FAIL",
            "Expected data not found in PDF output."
        )

    return (
        output,
        "FAIL",
        "Unable to validate the expected data."
    )


# =========================================================
# CREATE REPORT
# =========================================================

def create_report(
    df,
    pdf_pages,
    full_pdf_text
):

    results = []

    field_no = 1

    for report_field, excel_columns in FIELD_MAPPING.items():

        available_columns = [
            column
            for column in excel_columns
            if column in df.columns
        ]

        if not available_columns:
            continue

        for row_index, row in df.iterrows():

            values = []

            for column in available_columns:

                value = row[column]

                if pd.notna(value):

                    value = str(value).strip()

                    if value:
                        values.append(value)

            if not values:
                continue

            # Combine multiple Excel cells.
            #
            # Example:
            # Cell 1 = 100% COTTON
            # Cell 2 = EXCLUSIVE OF TRIM
            #
            # Combined expected value:
            # 100% COTTON EXCLUSIVE OF TRIM
            expected = " ".join(values)

            output, status, comments = compare_field(
                expected,
                pdf_pages,
                full_pdf_text
            )

            results.append({
                "FIELD NO": field_no,
                "FIELD": report_field,
                "ORDER FORM DATA": expected,
                "OUTPUT": output,
                "STATUS": status,
                "COMMENTS": comments
            })

            field_no += 1

    return pd.DataFrame(results)


# =========================================================
# FILE UPLOAD
# =========================================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("📊 Order Form")

    excel_file = st.file_uploader(
        "Upload Excel Order Form",
        type=["xlsx", "xls"],
        key="excel"
    )

with col2:

    st.subheader("📄 PDF Output")

    pdf_file = st.file_uploader(
        "Upload PDF Output",
        type=["pdf"],
        key="pdf"
    )


# =========================================================
# COMPARE BUTTON
# =========================================================

if excel_file and pdf_file:

    st.divider()

    if st.button(
        "🔍 COMPARE FILES",
        type="primary",
        use_container_width=True
    ):

        # -------------------------------------------------
        # READ EXCEL
        # -------------------------------------------------

        try:

            excel_file.seek(0)

            df = pd.read_excel(
                excel_file,
                header=0
            )

        except Exception as e:

            st.error(
                f"Unable to read the Excel file: {e}"
            )

            st.stop()


        # -------------------------------------------------
        # READ PDF
        # -------------------------------------------------

        try:

            pdf_pages, full_pdf_text = (
                extract_pdf_text(pdf_file)
            )

        except Exception as e:

            st.error(
                f"Unable to read the PDF file: {e}"
            )

            st.stop()


        # -------------------------------------------------
        # CREATE REPORT
        # -------------------------------------------------

        with st.spinner(
            "Analyzing Order Form and PDF..."
        ):

            report = create_report(
                df,
                pdf_pages,
                full_pdf_text
            )


        # -------------------------------------------------
        # QC REPORT
        # -------------------------------------------------

        st.divider()

        st.subheader("📋 QC Comparison Report")

        if report.empty:

            st.warning(
                "No configured fields were found "
                "in the Order Form."
            )

        else:

            pass_count = (
                report["STATUS"] == "PASS"
            ).sum()

            fail_count = (
                report["STATUS"] == "FAIL"
            ).sum()

            skip_count = (
                report["STATUS"] == "SKIP"
            ).sum()


            # -------------------------------------------------
            # SUMMARY
            # -------------------------------------------------

            c1, c2, c3 = st.columns(3)

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


            # -------------------------------------------------
            # STATUS COLORING
            # -------------------------------------------------

            def highlight_status(value):

                if value == "PASS":

                    return (
                        "background-color: #90EE90; "
                        "color: black; "
                        "font-weight: bold;"
                    )

                if value == "FAIL":

                    return (
                        "background-color: #FF7F7F; "
                        "color: black; "
                        "font-weight: bold;"
                    )

                if value == "SKIP":

                    return (
                        "background-color: #D3D3D3; "
                        "color: black; "
                        "font-weight: bold;"
                    )

                return ""


            styled_report = (
                report
                .style
                .map(
                    highlight_status,
                    subset=["STATUS"]
                )
            )


            st.dataframe(
                styled_report,
                use_container_width=True,
                hide_index=True
            )


            # -------------------------------------------------
            # CONCLUSION
            # -------------------------------------------------

            st.divider()

            if fail_count == 0:

                st.success(
                    "✅ CONCLUSION: "
                    "All checked fields passed."
                )

            else:

                st.error(
                    f"❌ CONCLUSION: "
                    f"{fail_count} field(s) "
                    f"require review."
                )


            # -------------------------------------------------
            # DOWNLOAD CSV
            # -------------------------------------------------

            csv_data = report.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "⬇️ Download QC Report",
                data=csv_data,
                file_name="Order_Form_PDF_QC_Report.csv",
                mime="text/csv",
                use_container_width=True
            )

else:

    st.info(
        "Upload both the Order Form Excel and "
        "PDF Output to begin comparison."
    )
