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
    page_title="Order Form → PDF Proofreader",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Proofreader")

st.write(
    "Upload your Order Form and PDF artwork, select the fields "
    "you want to validate, and the tool will proofread the PDF "
    "against the selected Order Form data."
)


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):
    """
    Normalizes text for comparison.

    These differences are ignored:
    - Uppercase/lowercase
    - Multiple spaces
    - Line breaks
    - Commas
    - Full stops
    - Colons
    - Semicolons
    - Slashes
    - Hyphens
    - Apostrophe formatting
    """

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

    # Separators should not cause failure
    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    # Treat hyphen as separator
    text = re.sub(
        r"-+",
        " ",
        text
    )

    # Remove remaining unusual punctuation
    text = re.sub(
        r"[^\w%#'\s]",
        " ",
        text
    )

    # Apostrophe formatting shouldn't matter
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
    return normalize_text(text).replace(
        " ",
        ""
    )


def tokenize(text):
    value = normalize_text(text)

    if not value:
        return []

    return value.split()


# =========================================================
# EXCEL LOADING
# =========================================================

def load_excel(uploaded_file):

    uploaded_file.seek(0)

    df = pd.read_excel(
        uploaded_file,
        header=0
    )

    # Clean column names
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    return df


# =========================================================
# PDF EXTRACTION
# =========================================================

def extract_pdf_pages(uploaded_file):

    uploaded_file.seek(0)

    pdf_bytes = uploaded_file.read()

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(
        document
    ):

        # Only actual page text.
        # We intentionally don't use filename,
        # PDF metadata, etc.
        text = page.get_text(
            "text"
        )

        pages.append({
            "page_number": page_number + 1,
            "text": text
        })

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

        # Ignore very long technical strings
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
    # Combine consecutive lines.
    #
    # This is important for care instructions such as:
    #
    # MACHINE WASH COLD WITH LIKE
    # COLORS. CHLORINE BLEACH WHEN
    # NEEDED.
    #
    # -----------------------------------------------------

    max_group = min(
        15,
        len(lines)
    )

    for group_size in range(
        2,
        max_group + 1
    ):

        for start in range(
            0,
            len(lines) - group_size + 1
        ):

            block = " ".join(
                lines[
                    start:start + group_size
                ]
            )

            blocks.append(block)


    # -----------------------------------------------------
    # Full page text
    # -----------------------------------------------------

    full_text = " ".join(lines)

    if full_text:
        blocks.append(full_text)


    # -----------------------------------------------------
    # Remove duplicates
    # -----------------------------------------------------

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

        seen.add(normalized)

        unique_blocks.append(block)

    return unique_blocks


# =========================================================
# EXACT MATCH
# =========================================================

def exact_match(
    pdf_text,
    order_form_text
):

    pdf_normalized = normalize_text(
        pdf_text
    )

    order_normalized = normalize_text(
        order_form_text
    )

    if not pdf_normalized:
        return False

    if not order_normalized:
        return False


    # -----------------------------------------------------
    # Normalized phrase
    # -----------------------------------------------------

    if order_normalized in pdf_normalized:
        return True


    # -----------------------------------------------------
    # Ignore spaces completely
    # -----------------------------------------------------

    pdf_compact = compact_text(
        pdf_text
    )

    order_compact = compact_text(
        order_form_text
    )

    if order_compact in pdf_compact:
        return True

    return False


# =========================================================
# FIND DIFFERENCES
# =========================================================

def get_difference(
    order_form_text,
    pdf_text
):

    order_tokens = tokenize(
        order_form_text
    )

    pdf_tokens = tokenize(
        pdf_text
    )

    matcher = SequenceMatcher(
        None,
        order_tokens,
        pdf_tokens
    )

    differences = []

    for tag, a1, a2, b1, b2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        order_part = " ".join(
            order_tokens[a1:a2]
        )

        pdf_part = " ".join(
            pdf_tokens[b1:b2]
        )

        if tag == "replace":

            differences.append(
                f"{order_part} → {pdf_part}"
            )

        elif tag == "delete":

            differences.append(
                f"Missing: {order_part}"
            )

        elif tag == "insert":

            differences.append(
                f"Extra: {pdf_part}"
            )

    if not differences:

        return "Text differs from Order Form."

    return "; ".join(
        differences[:10]
    )


# =========================================================
# SEARCH PDF FOR SELECTED FIELD
# =========================================================

def find_best_pdf_match(
    order_value,
    pdf_blocks
):

    order_normalized = normalize_text(
        order_value
    )

    if not order_normalized:
        return None

    order_tokens = tokenize(
        order_value
    )

    if not order_tokens:
        return None


    # =====================================================
    # FIRST: EXACT MATCH
    # =====================================================

    for block in pdf_blocks:

        if exact_match(
            block,
            order_value
        ):

            return {
                "pdf_text": block,
                "score": 100,
                "status": "PASS",
                "difference": "—",
                "match_type": "EXACT"
            }


    # =====================================================
    # SECOND: PROOFREADING MATCH
    # =====================================================
    #
    # If exact text isn't found, look for a very similar
    # PDF block.
    #
    # This is where:
    #
    # ONLY → ONLI
    #
    # can be detected.
    #
    # =====================================================

    best_match = None

    for block in pdf_blocks:

        pdf_normalized = normalize_text(
            block
        )

        if not pdf_normalized:
            continue

        pdf_tokens = tokenize(
            block
        )

        if not pdf_tokens:
            continue


        # -------------------------------------------------
        # Don't compare extremely tiny values against
        # random PDF text.
        # -------------------------------------------------

        if len(order_tokens) == 1:

            order_word = order_tokens[0]

            if len(order_word) <= 2:
                continue


        # -------------------------------------------------
        # Similarity calculations
        # -------------------------------------------------

        ratio = fuzz.ratio(
            order_normalized,
            pdf_normalized
        )

        partial = fuzz.partial_ratio(
            order_normalized,
            pdf_normalized
        )

        token_ratio = fuzz.token_set_ratio(
            order_normalized,
            pdf_normalized
        )


        # -------------------------------------------------
        # Word overlap
        # -------------------------------------------------

        order_set = set(
            order_tokens
        )

        pdf_set = set(
            pdf_tokens
        )

        common_words = (
            order_set.intersection(
                pdf_set
            )
        )

        if order_set:

            common_ratio = (
                len(common_words)
                /
                len(order_set)
            )

        else:

            common_ratio = 0


        # -------------------------------------------------
        # Combined score
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
        # Acceptance rules
        # -------------------------------------------------

        if len(order_tokens) <= 2:

            acceptable = (
                ratio >= 88
                and
                common_ratio >= 0.50
            )

        elif len(order_tokens) <= 5:

            acceptable = (
                score >= 78
                and
                common_ratio >= 0.50
            )

        else:

            acceptable = (
                score >= 72
                and
                common_ratio >= 0.45
            )


        if not acceptable:
            continue


        # -------------------------------------------------
        # Keep strongest candidate
        # -------------------------------------------------

        if (
            best_match is None
            or
            score > best_match["score"]
        ):

            best_match = {
                "pdf_text": block,
                "score": score,
                "status": "FAIL",
                "difference": get_difference(
                    order_value,
                    block
                ),
                "match_type": "PROBABLE"
            }


    return best_match


# =========================================================
# BUILD REPORT
# =========================================================

def build_report(
    df,
    pdf_pages,
    selected_fields
):

    report_rows = []

    field_number = 1


    # =====================================================
    # PDF PAGE → EXCEL ROW
    # =====================================================
    #
    # Excel row 2 → PDF page 1
    # Excel row 3 → PDF page 2
    # Excel row 4 → PDF page 3
    #
    # =====================================================

    for page_index, page in enumerate(
        pdf_pages
    ):

        excel_row_index = page_index


        # -------------------------------------------------
        # If PDF has more pages than Excel rows
        # -------------------------------------------------

        if (
            excel_row_index
            >= len(df)
        ):

            report_rows.append({

                "FIELD NO":
                    field_number,

                "EXCEL ROW":
                    "N/A",

                "PDF PAGE":
                    page["page_number"],

                "FIELD":
                    "PDF PAGE",

                "ORDER FORM DATA":
                    "No corresponding Excel row",

                "PDF OUTPUT":
                    page["text"][:500],

                "STATUS":
                    "FAIL",

                "DIFFERENCE":
                    "PDF page has no corresponding Order Form row."
            })

            field_number += 1

            continue


        # -------------------------------------------------
        # Current Order Form row
        # -------------------------------------------------

        row = df.iloc[
            excel_row_index
        ]


        # -------------------------------------------------
        # PDF blocks
        # -------------------------------------------------

        pdf_blocks = create_pdf_blocks(
            page["text"]
        )


        # -------------------------------------------------
        # Check ONLY selected fields
        # -------------------------------------------------

        for field in selected_fields:

            if field not in df.columns:
                continue

            value = row[field]

            if pd.isna(value):
                continue

            value = str(value).strip()

            if not value:
                continue


            # -------------------------------------------------
            # Search PDF for this selected field
            # -------------------------------------------------

            match = find_best_pdf_match(
                value,
                pdf_blocks
            )


            # -------------------------------------------------
            # IMPORTANT:
            #
            # If there is NO sufficiently reliable match,
            # do NOT create a FAIL.
            #
            # This prevents:
            #
            # French Care
            # French COO
            # etc.
            #
            # from being reported when they aren't actually
            # present in the artwork.
            # -------------------------------------------------

            if match is None:

                continue


            # -------------------------------------------------
            # Add report
            # -------------------------------------------------

            report_rows.append({

                "FIELD NO":
                    field_number,

                "EXCEL ROW":
                    excel_row_index + 2,

                "PDF PAGE":
                    page["page_number"],

                "FIELD":
                    field,

                "ORDER FORM DATA":
                    value,

                "PDF OUTPUT":
                    match["pdf_text"],

                "STATUS":
                    match["status"],

                "DIFFERENCE":
                    match["difference"]
            })

            field_number += 1


    return pd.DataFrame(
        report_rows
    )


# =========================================================
# STATUS COLOR
# =========================================================

def highlight_status(value):

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

    return ""


# =========================================================
# APP UI
# =========================================================

st.divider()

left_column, right_column = st.columns(
    2
)


# =========================================================
# ORDER FORM UPLOAD
# =========================================================

with left_column:

    st.subheader(
        "📊 1. Upload Order Form"
    )

    excel_file = st.file_uploader(
        "Upload Excel file",
        type=[
            "xlsx",
            "xls"
        ],
        key="order_form"
    )


# =========================================================
# PDF UPLOAD
# =========================================================

with right_column:

    st.subheader(
        "📄 2. Upload PDF Output"
    )

    pdf_file = st.file_uploader(
        "Upload PDF artwork",
        type=[
            "pdf"
        ],
        key="pdf_output"
    )


# =========================================================
# AFTER EXCEL UPLOAD
# =========================================================

df = None

if excel_file:

    try:

        df = load_excel(
            excel_file
        )

    except Exception as error:

        st.error(
            f"Could not read Excel file: {error}"
        )

        st.stop()


    st.divider()

    st.subheader(
        "🎯 3. Select Fields to Validate"
    )

    st.write(
        "Select only the fields that should appear "
        "in your PDF artwork. The tool will ignore all "
        "other Excel columns."
    )


    # -----------------------------------------------------
    # Show detected fields
    # -----------------------------------------------------

    available_fields = [
        str(column)
        for column in df.columns
    ]


    # -----------------------------------------------------
    # Multiselect
    # -----------------------------------------------------

    selected_fields = st.multiselect(

        "Fields to compare",

        options=available_fields,

        default=[],

        help=(
            "Only the fields selected here will be "
            "checked against the PDF."
        )
    )


    # -----------------------------------------------------
    # Select all button
    # -----------------------------------------------------

    if selected_fields:

        st.success(
            f"{len(selected_fields)} field(s) selected."
        )

    else:

        st.warning(
            "Please select at least one field."
        )


    # -----------------------------------------------------
    # Excel preview
    # -----------------------------------------------------

    with st.expander(
        "👀 Preview Order Form"
    ):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# PDF INFORMATION
# =========================================================

pdf_pages = None

if pdf_file:

    try:

        pdf_pages = extract_pdf_pages(
            pdf_file
        )

    except Exception as error:

        st.error(
            f"Could not read PDF: {error}"
        )

        st.stop()


    st.divider()

    st.subheader(
        "📄 PDF Information"
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        st.metric(
            "PDF Pages",
            len(pdf_pages)
        )

    with col2:

        st.metric(
            "Excel Rows",
            len(df) if df is not None else 0
        )


# =========================================================
# MAPPING INFORMATION
# =========================================================

if df is not None and pdf_pages is not None:

    st.info(
        "📌 Page mapping: "
        "Excel Row 2 → PDF Page 1 | "
        "Excel Row 3 → PDF Page 2 | "
        "Excel Row 4 → PDF Page 3 | "
        "and so on."
    )


# =========================================================
# COMPARE BUTTON
# =========================================================

if (
    df is not None
    and pdf_file is not None
    and selected_fields
):

    st.divider()

    if st.button(
        "🔍 COMPARE / PROOFREAD PDF",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Reading PDF artwork and checking selected fields..."
        ):

            report = build_report(
                df,
                pdf_pages,
                selected_fields
            )


        st.divider()

        st.subheader(
            "📋 QC / Proofreading Report"
        )


        # =================================================
        # NO RESULTS
        # =================================================

        if report.empty:

            st.warning(
                "No selected field could be confidently "
                "found in the PDF artwork."
            )

            st.info(
                "This does not automatically mean the artwork "
                "is incorrect. It means the selected Order Form "
                "data was not confidently detected in the PDF."
            )


        else:

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


            # =================================================
            # SUMMARY
            # =================================================

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


            # =================================================
            # REPORT TABLE
            # =================================================

            styled_report = (
                report
                .style
                .map(
                    highlight_status,
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
                    "All detected selected-field matches "
                    "passed proofreading."
                )

            else:

                st.error(
                    f"❌ CONCLUSION: "
                    f"{fail_count} mismatch(es) detected."
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

                "⬇️ Download QC Report",

                data=csv_data,

                file_name=(
                    "Order_Form_PDF_QC_Report.csv"
                ),

                mime="text/csv",

                use_container_width=True
            )


# =========================================================
# INSTRUCTIONS
# =========================================================

if not excel_file or not pdf_file:

    st.divider()

    st.subheader(
        "How to use"
    )

    st.markdown(
        """
### 1️⃣ Upload your Order Form
Upload the Excel file. The first row is treated as the field/header row.

### 2️⃣ Select the fields
Choose only the fields that are expected to appear on your artwork.

For example:

- COO
- Content
- English Care
- Brand
- Size
- RN

You do **not** need to select fields such as French Care or French COO if they are not present on that artwork.

### 3️⃣ Upload your PDF
The application supports multiple-page PDFs.

### 4️⃣ Click Compare / Proofread
The application uses:

**Excel Row 2 → PDF Page 1**

**Excel Row 3 → PDF Page 2**

**Excel Row 4 → PDF Page 3**

and so on.

### 5️⃣ Review the QC report
🟢 **PASS** = PDF matches the selected Order Form data.

🔴 **FAIL** = PDF contains a probable spelling/content difference.

The report shows the Order Form reference, the actual PDF text and the detected difference.
"""
    )
