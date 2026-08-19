import streamlit as st
import pandas as pd
import fitz
import re
import unicodedata
from rapidfuzz import fuzz


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Order Form → PDF Validator",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Validator")
st.caption(
    "Smart comparison of Flat File Order Form data against PDF artwork."
)


# =========================================================
# SMART FIELD CONCEPTS
# =========================================================
#
# The application does NOT require one exact field name.
#
# Example:
#
# French Care
# French Instruction
# French Washing Instruction
# Care French
#
# can all be recognized as CARE-related fields.
#
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
        "washingcare",
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
# INTERNAL / NON-ARTWORK FIELDS
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

def clean_header(header):

    if header is None:
        return ""

    text = str(header).strip().lower()

    return re.sub(
        r"[^a-z0-9]",
        "",
        text
    )


# =========================================================
# SMART FIELD CLASSIFICATION
# =========================================================

def classify_field(header):

    if header is None:
        return "IGNORE"

    original = str(header).strip()

    if not original:
        return "IGNORE"

    compact = clean_header(original)

    # -----------------------------------------------------
    # Internal fields take priority
    # -----------------------------------------------------

    for keyword in IGNORE_KEYWORDS:

        keyword_clean = clean_header(keyword)

        if keyword_clean and keyword_clean in compact:
            return "IGNORE"

    # -----------------------------------------------------
    # Artwork-related concepts
    # -----------------------------------------------------

    for concept, keywords in FIELD_CONCEPTS.items():

        for keyword in keywords:

            keyword_clean = clean_header(keyword)

            if keyword_clean and keyword_clean in compact:
                return "CHECK"

    # -----------------------------------------------------
    # Language-aware care detection
    # -----------------------------------------------------

    if (
        "english" in compact
        or "french" in compact
        or "canada" in compact
    ):

        care_words = FIELD_CONCEPTS["CARE"]

        for keyword in care_words:

            if clean_header(keyword) in compact:
                return "CHECK"

    # -----------------------------------------------------
    # Unknown field
    # -----------------------------------------------------

    return "REVIEW"


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    # Unicode normalization
    text = unicodedata.normalize(
        "NFKC",
        text
    )

    # Case insensitive
    text = text.lower()

    # PDF line breaks become spaces
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Common separators become spaces
    text = re.sub(
        r"[,.;:|/\\]+",
        " ",
        text
    )

    # Hyphenated formatting
    text = re.sub(
        r"-+",
        " ",
        text
    )

    # Keep letters, numbers, % and #
    text = re.sub(
        r"[^\w%#\s]",
        " ",
        text
    )

    # Collapse multiple spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def compact_normalize(text):

    return normalize_text(
        text
    ).replace(
        " ",
        ""
    )


# =========================================================
# CHECK WHETHER VALUE IS EMPTY
# =========================================================

def is_empty_value(value):

    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    return str(value).strip() == ""


# =========================================================
# SHORT VALUE DETECTION
# =========================================================

def is_short_value(value):

    normalized = normalize_text(
        value
    )

    if not normalized:
        return True

    words = normalized.split()

    # Short values such as:
    #
    # 0
    # 2
    # 4
    # XXL
    # M
    # S
    #
    # should not be fuzzy matched against random
    # numbers elsewhere on the page.

    if len(words) == 1 and len(normalized) <= 5:
        return True

    return False


# =========================================================
# SHORT VALUE SEARCH
# =========================================================

def short_value_exists(
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

    # Exact token matching.
    #
    # "2" matches "2"
    #
    # but does NOT match:
    #
    # "7606601"
    # "2026"
    # "12"
    #

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
# COMPLETE TEXT SEARCH
# =========================================================

def complete_text_exists(
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

    # -----------------------------------------------------
    # Normal comparison
    # -----------------------------------------------------

    if expected_norm in pdf_norm:
        return True

    # -----------------------------------------------------
    # Compact comparison
    #
    # Handles additional spaces/line wrapping.
    # -----------------------------------------------------

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
# FIND SIMILAR PDF TEXT
# =========================================================

def find_similar_text(
    expected,
    pdf_text
):

    expected_norm = normalize_text(
        expected
    )

    lines = [
        line.strip()
        for line in pdf_text.splitlines()
        if line.strip()
    ]

    if not lines:
        return "", 0

    best_text = ""
    best_score = 0

    # Combine multiple PDF lines.
    #
    # This is important for:
    #
    # MACHINE WASH COLD WITH LIKE
    # COLORS. CHLORINE BLEACH WHEN
    # NEEDED. TUMBLE DRY LOW.
    #
    # The system can analyze the entire paragraph
    # instead of just one line.

    for start in range(
        len(lines)
    ):

        max_window = min(
            12,
            len(lines) - start
        )

        for window in range(
            1,
            max_window + 1
        ):

            block = " ".join(
                lines[
                    start:start + window
                ]
            )

            block_norm = normalize_text(
                block
            )

            if not block_norm:
                continue

            score = fuzz.ratio(
                expected_norm,
                block_norm
            )

            if score > best_score:

                best_score = score
                best_text = block

    return (
        best_text,
        best_score
    )


# =========================================================
# COMPARE ONE FIELD
# =========================================================

def compare_field(
    expected,
    pdf_text
):

    expected = str(
        expected
    ).strip()

    if not expected:

        return (
            "",
            "SKIP",
            "No Order Form data."
        )

    # -----------------------------------------------------
    # SHORT VALUES
    # -----------------------------------------------------

    if is_short_value(
        expected
    ):

        if short_value_exists(
            expected,
            pdf_text
        ):

            return (
                expected,
                "PASS",
                "Exact value found. "
                "Case and formatting differences ignored."
            )

        return (
            "",
            "FAIL",
            "Expected value not found on the corresponding PDF page."
        )

    # -----------------------------------------------------
    # COMPLETE LONG TEXT
    # -----------------------------------------------------

    if complete_text_exists(
        expected,
        pdf_text
    ):

        return (
            get_readable_pdf_text(
                expected,
                pdf_text
            ),
            "PASS",
            "Complete data found. "
            "Case, spacing, punctuation and PDF line wrapping ignored."
        )

    # -----------------------------------------------------
    # SIMILARITY ANALYSIS
    #
    # Used only to explain a FAIL.
    #
    # It NEVER converts a fuzzy match into PASS.
    # -----------------------------------------------------

    similar_text, score = find_similar_text(
        expected,
        pdf_text
    )

    if similar_text:

        if score >= 80:

            return (
                similar_text,
                "FAIL",
                "Possible spelling difference or minor text difference."
            )

        return (
            similar_text,
            "FAIL",
            "Data mismatch."
        )

    return (
        "",
        "FAIL",
        "Expected data not found on the corresponding PDF page."
    )


# =========================================================
# GET READABLE PDF TEXT
# =========================================================

def get_readable_pdf_text(
    expected,
    pdf_text
):

    lines = [
        line.strip()
        for line in pdf_text.splitlines()
        if line.strip()
    ]

    if not lines:
        return ""

    expected_norm = normalize_text(
        expected
    )

    # -----------------------------------------------------
    # If the complete content is contained in one
    # page, return the page's readable text.
    #
    # This is useful for long care instructions because
    # the user can see the complete paragraph rather than
    # only the first wrapped line.
    # -----------------------------------------------------

    page_text = " ".join(
        lines
    )

    page_norm = normalize_text(
        page_text
    )

    if expected_norm in page_norm:

        return page_text

    return page_text


# =========================================================
# READ EXCEL
# =========================================================

def read_order_form(
    excel_file
):

    excel_file.seek(0)

    # Row 1 of the Flat File is treated as the header.
    df = pd.read_excel(
        excel_file,
        header=0
    )

    return df


# =========================================================
# ANALYZE ALL HEADERS
# =========================================================

def analyze_headers(
    df
):

    fields = []

    for column in df.columns:

        classification = classify_field(
            column
        )

        non_empty = (
            df[column]
            .dropna()
        )

        if len(non_empty) > 0:

            sample_data = str(
                non_empty.iloc[0]
            )

        else:

            sample_data = ""

        fields.append({

            "FIELD": column,

            "CLASSIFICATION": classification,

            "SAMPLE DATA": sample_data
        })

    return pd.DataFrame(
        fields
    )


# =========================================================
# BUILD COMPARISON REPORT
# =========================================================

def create_report(
    df,
    pdf_pages,
    selected_fields
):

    results = []

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # Excel row 2 → PDF page 1
    # Excel row 3 → PDF page 2
    # Excel row 4 → PDF page 3
    #
    # pandas row index 0 = Excel row 2
    # -----------------------------------------------------

    for excel_index, row in df.iterrows():

        pdf_page_number = (
            excel_index + 1
        )

        # -------------------------------------------------
        # No corresponding PDF page
        # -------------------------------------------------

        if (
            pdf_page_number
            > len(pdf_pages)
        ):

            results.append({

                "EXCEL ROW":
                    excel_index + 2,

                "PDF PAGE":
                    pdf_page_number,

                "FIELD":
                    "PAGE CHECK",

                "ORDER FORM DATA":
                    "",

                "OUTPUT":
                    "",

                "STATUS":
                    "FAIL",

                "COMMENTS":
                    "No corresponding PDF page found."
            })

            continue

        pdf_text = pdf_pages[
            pdf_page_number - 1
        ]["text"]

        # -------------------------------------------------
        # Compare each selected artwork field
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

            output, status, comments = (
                compare_field(
                    value,
                    pdf_text
                )
            )

            results.append({

                "EXCEL ROW":
                    excel_index + 2,

                "PDF PAGE":
                    pdf_page_number,

                "FIELD":
                    field,

                "ORDER FORM DATA":
                    value,

                "OUTPUT":
                    output,

                "STATUS":
                    status,

                "COMMENTS":
                    comments
            })

    return pd.DataFrame(
        results
    )


# =========================================================
# STATUS COLORS
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
# FILE UPLOAD AREA
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

    # -----------------------------------------------------
    # READ EXCEL
    # -----------------------------------------------------

    try:

        df = read_order_form(
            excel_file
        )

    except Exception as error:

        st.error(
            f"Unable to read the Excel file: {error}"
        )

        st.stop()


    # -----------------------------------------------------
    # READ PDF
    # -----------------------------------------------------

    try:

        pdf_pages = extract_pdf_pages(
            pdf_file
        )

    except Exception as error:

        st.error(
            f"Unable to read the PDF file: {error}"
        )

        st.stop()


    # -----------------------------------------------------
    # FILE INFORMATION
    # -----------------------------------------------------

    st.divider()

    st.subheader(
        "📌 File Information"
    )

    col1, col2, col3 = st.columns(
        3
    )

    with col1:

        st.metric(
            "Excel Data Rows",
            len(df)
        )

    with col2:

        st.metric(
            "PDF Pages",
            len(pdf_pages)
        )

    with col3:

        difference = (
            len(df)
            - len(pdf_pages)
        )

        st.metric(
            "Row / Page Difference",
            difference
        )


    # -----------------------------------------------------
    # ROW / PAGE WARNING
    # -----------------------------------------------------

    if len(df) != len(pdf_pages):

        st.warning(
            "⚠️ The number of Excel data rows and PDF pages "
            "does not match. The application will still "
            "compare available Row → Page pairs, but please "
            "verify the PDF/page structure."
        )

    else:

        st.success(
            "✅ Excel data rows and PDF pages match."
        )


    # =====================================================
    # SMART FIELD ANALYSIS
    # =====================================================

    st.divider()

    st.subheader(
        "🧠 Smart Field Analysis"
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


    # -----------------------------------------------------
    # DETECTED FIELDS
    # -----------------------------------------------------

    st.write(
        f"**Artwork-related fields automatically detected: "
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
            "No artwork-related fields were automatically detected."
        )


    # -----------------------------------------------------
    # FIELD ANALYSIS TABLE
    # -----------------------------------------------------

    with st.expander(
        "🔎 View complete field analysis"
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
                "These fields could not be confidently "
                "classified. Select any that should be "
                "checked against the artwork."
            )

            additional_fields = st.multiselect(
                "Additional fields to check:",
                review_fields
            )

            for field in additional_fields:

                if field not in check_fields:

                    check_fields.append(
                        field
                    )


    # =====================================================
    # EXCLUDED FIELDS
    # =====================================================

    with st.expander(
        "🚫 Fields currently excluded"
    ):

        if ignore_fields:

            st.write(
                ignore_fields
            )

        else:

            st.write(
                "No fields automatically excluded."
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
                "No fields have been selected for comparison."
            )

            st.stop()


        with st.spinner(
            "Analyzing Order Form data against "
            "the corresponding PDF pages..."
        ):

            report = create_report(
                df,
                pdf_pages,
                check_fields
            )


        # =================================================
        # QC REPORT
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
                report[
                    "STATUS"
                ] == "PASS"
            ).sum()

            fail_count = (
                report[
                    "STATUS"
                ] == "FAIL"
            ).sum()

            skip_count = (
                report[
                    "STATUS"
                ] == "SKIP"
            ).sum()


            # -------------------------------------------------
            # SUMMARY
            # -------------------------------------------------

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


            # -------------------------------------------------
            # COLORED REPORT
            # -------------------------------------------------

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


            # -------------------------------------------------
            # CONCLUSION
            # -------------------------------------------------

            st.divider()

            if fail_count == 0:

                st.success(
                    "✅ CONCLUSION: "
                    "All checked artwork fields passed."
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
        "Upload both the Order Form Excel and "
        "PDF Output to begin comparison."
    )
