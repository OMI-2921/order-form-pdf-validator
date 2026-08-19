import streamlit as st

st.set_page_config(
    page_title="Order Form PDF Validator",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Order Form → PDF Validator")
st.write("Upload an Order Form and PDF output to compare the required data.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Order Form")
    excel_file = st.file_uploader(
        "Upload Excel Order Form",
        type=["xlsx", "xls"]
    )

with col2:
    st.subheader("📄 PDF Output")
    pdf_file = st.file_uploader(
        "Upload PDF Output",
        type=["pdf"]
    )

if excel_file:
    st.success(f"Excel uploaded: {excel_file.name}")

if pdf_file:
    st.success(f"PDF uploaded: {pdf_file.name}")

if excel_file and pdf_file:
    st.divider()
    st.success("Both files are ready for comparison.")
    st.button("🔍 Compare Files")
