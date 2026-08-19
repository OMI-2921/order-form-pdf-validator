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

# These are the Order Form fields we will initially check.
# We can expand this list later as we test more files.

FIELD_MAPPING = {
    "Content": ["Content"],
    "English COO": ["EnglishCOO"],
    "English Care": ["EnglishCare"],

    # Size fields
    "Size Line 1": ["SizeLine1"],
    "Size Line 2": ["SizeLine2"],
    "Size Line 3": ["SizeLine3"],

    # OSZ fields
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
    Normalize text for comparison.

    Rules:
    - Case insensitive
    - Removes punctuation used as separators
    - Removes extra spaces
    - Keeps letters and numbers
    """

    if text is None:
        return ""

    text = str(text)

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Lowercase
    text = text.lower()

    # Replace common separators with spaces
    text = re.sub(r"[,.;:|/\\]+", " ", text)

    # Treat hyphen as a separator
    text = re.sub(r"[-]+", " ", text)

    # Remove unnecessary symbols while keeping
    # letters, numbers, %, # and spaces
    text = re.sub(r"[^\w%#\s]", " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def compare_values(expected, actual):
    """
    Compare Order Form data with PDF data.
    """

    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)

    if not expected_norm:
        return "SKIP", 100

    if not actual_norm:
        return "FAIL", 0

    # Exact normalized match
    if expected_norm == actual_norm:
        return "PASS", 100

    # Check whether the expected value appears inside
    # the PDF text. This is useful when the PDF combines
    # multiple fields into a sentence.
    if expected_norm in actual_norm:
        return "PASS", 100

    # Check reverse containment for longer PDF text
    if actual_norm in expected_norm:
        return "PASS", 100

    # Fuzzy comparison only for diagnostic purposes.
    # We do NOT automatically pass fuzzy spelling differences.
    score = fuzz.ratio(expected_norm, actual_norm)

    return "FAIL", score


# =========================================================
# READ PDF
# =========================================================

def extract_pdf_text(pdf_file):

    pdf_file.seek(0)

    pdf_bytes = pdf_file.read()

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text()

        pages.append({
            "page": page_number,
            "text": text
        })

    document.close()

    return pages


# =========================================================
# FIND VALUE IN PDF
# =========================================================

def find_best_pdf_match(expected, pdf_pages):

    expected_norm = normalize_text(expected)

    if not expected_norm:
        return "", 0

    best_text = ""
    best_score = 0

    for page in pdf_pages:

        page_text = page["text"]

        # First look at individual lines
        lines = page_text.splitlines()

        for line in lines:

            line = line.strip()

            if not line:
                continue

            line_norm = normalize_text(line)

            if not line_norm:
                continue

            # Exact normalized match
            if expected_norm == line_norm:
                return line, 100

            # Expected data contained within a PDF line
            if expected_norm in line_norm:
                return line, 100

            # Compare similarity
            score = fuzz.ratio(
                expected_norm,
                line_norm
            )

            if score > best_score:

                best_score = score
                best_text = line

    return best_text, best_score


# =========================================================
# CREATE COMPARISON REPORT
# =========================================================

def create_report(df, pdf_pages):

    results = []

    field_no = 1

    for report_field, excel_columns in FIELD_MAPPING.items():

        # Make sure required Excel columns exist
        available_columns = [
            column
            for column in excel_columns
            if column in df.columns
        ]

        if not available_columns:
            continue

        # Process every row in the Excel
        for row_index, row in df.iterrows():

            values = []

            for column in available_columns:

                value = row[column]

                if pd.notna(value):

                    value = str(value).strip()

                    if value:
                        values.append(value)

            # Nothing to compare
            if not values:
                continue

            # Combine multiple Excel cells
            expected = " ".join(values)

            # Find corresponding PDF text
            output, score = find_best_pdf_match(
                expected,
                pdf_pages
            )

            status, comparison_score = compare_values(
                expected,
                output
            )

            results.append({
                "FIELD NO": field_no,
                "FIELD": report_field,
                "ORDER FORM DATA": expected,
                "OUTPUT": output,
                "STATUS": status,
                "MATCH SCORE": round(comparison_score, 1)
            })

            field_no += 1

    return pd.DataFrame(results)


# =========================================================
# FILE UPLOAD AREA
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
# COMPARE
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

            pdf_pages = extract_pdf_text(
                pdf_file
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
            "Comparing Order Form data with PDF..."
        ):

            report = create_report(
                df,
                pdf_pages
            )


        # -------------------------------------------------
        # REPORT
        # -------------------------------------------------

        st.divider()

        st.subheader("📋 QC Comparison Report")


        if report.empty:

            st.warning(
                "No configured fields were found in the Excel file."
            )

            st.info(
                "The field mapping in the application needs "
                "to be updated for this Order Form."
            )

        else:

            # Summary
            pass_count = (
                report["STATUS"] == "PASS"
            ).sum()

            fail_count = (
                report["STATUS"] == "FAIL"
            ).sum()

            skip_count = (
                report["STATUS"] == "SKIP"
            ).sum()


            c1, c2, c3, c4 = st.columns(4)

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

            with c4:
                st.metric(
                    "SKIPPED",
                    skip_count
                )


            # -------------------------------------------------
            # COLOR STATUS
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
                    "✅ CONCLUSION: All checked fields passed."
                )

            else:

                st.error(
                    f"❌ CONCLUSION: {fail_count} "
                    f"field(s) require review."
                )


            # -------------------------------------------------
            # DOWNLOAD REPORT
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
        "Upload both the Order Form Excel and PDF Output "
        "to begin comparison."
    )
