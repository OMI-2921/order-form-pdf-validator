import streamlit as st
import pandas as pd
import fitz
import re

st.set_page_config(
    page_title="Order Form PDF Validator",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Validator")
st.write(
    "Upload the Order Form Excel and PDF output. "
    "The tool will extract the information for validation."
)

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------

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

# ---------------------------------------------------------
# FILE STATUS
# ---------------------------------------------------------

if excel_file:
    st.success(f"Excel uploaded: {excel_file.name}")

if pdf_file:
    st.success(f"PDF uploaded: {pdf_file.name}")

# ---------------------------------------------------------
# COMPARE BUTTON
# ---------------------------------------------------------

if excel_file and pdf_file:

    st.divider()

    if st.button("🔍 Compare Files", type="primary"):

        # -----------------------------
        # READ EXCEL
        # -----------------------------

        try:
            excel_file.seek(0)

            df = pd.read_excel(
                excel_file,
                header=0
            )

            st.success("Excel file read successfully.")

            st.subheader("📊 Order Form Data")

            st.write(
                f"Rows found: {len(df)} | "
                f"Columns found: {len(df.columns)}"
            )

            st.dataframe(
                df,
                use_container_width=True
            )

        except Exception as e:

            st.error(
                f"Could not read the Excel file: {e}"
            )

        # -----------------------------
        # READ PDF
        # -----------------------------

        try:

            pdf_file.seek(0)

            pdf_bytes = pdf_file.read()

            document = fitz.open(
                stream=pdf_bytes,
                filetype="pdf"
            )

            pdf_text = ""

            for page_number, page in enumerate(document):

                page_text = page.get_text()

                pdf_text += (
                    f"\n--- PAGE {page_number + 1} ---\n"
                )

                pdf_text += page_text

            document.close()

            st.success(
                f"PDF read successfully. "
                f"Pages found: {len(pdf_text.split('--- PAGE ')) - 1}"
            )

            st.subheader("📄 Extracted PDF Text")

            st.text_area(
                "PDF content",
                pdf_text,
                height=500
            )

        except Exception as e:

            st.error(
                f"Could not read the PDF file: {e}"
            )

else:

    st.info(
        "Please upload both the Excel Order Form "
        "and the PDF Output."
    )
