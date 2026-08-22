import streamlit as st


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="QC Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# DARK THEME
# =========================================================

st.markdown(
    """
    <style>

    html,
    body,
    [data-testid="stAppViewContainer"],
    [data-testid="stApp"],
    .stApp,
    [data-testid="stMain"] {
        background-color: #0e1117 !important;
        color: white !important;
    }

    [data-testid="stHeader"] {
        background-color: #0e1117 !important;
    }

    .dashboard-title {
        font-size: 38px;
        font-weight: 700;
        color: white !important;
        margin-bottom: 5px;
    }

    .dashboard-subtitle {
        font-size: 16px;
        color: #aeb6c2 !important;
        margin-bottom: 35px;
    }

    .tool-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 15px;
        padding: 25px;
        min-height: 180px;
        margin-bottom: 20px;
    }

    .tool-number {
        font-size: 14px;
        color: #58a6ff !important;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .tool-name {
        font-size: 21px;
        font-weight: 700;
        color: white !important;
        margin-bottom: 10px;
    }

    .tool-description {
        font-size: 14px;
        color: #aeb6c2 !important;
        line-height: 1.5;
    }

    div.stButton > button {

        background-color: #2196F3 !important;

        color: white !important;

        border: 2px solid #000000 !important;

        border-radius: 12px !important;

        font-size: 16px !important;

        font-weight: 700 !important;

        min-height: 48px !important;

        width: 100% !important;

    }

    div.stButton > button:hover {

        background-color: #1976D2 !important;

        color: white !important;

        border: 2px solid #000000 !important;

    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SESSION STATE
# =========================================================

if "selected_tool" not in st.session_state:
    st.session_state.selected_tool = None


# =========================================================
# DASHBOARD
# =========================================================

def dashboard():

    st.markdown(
        '<div class="dashboard-title">🔍 QC Dashboard</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="dashboard-subtitle">'
        'Select a QC tool to begin.'
        '</div>',
        unsafe_allow_html=True
    )


    # -----------------------------------------------------
    # TOOL 1
    # -----------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            """
            <div class="tool-card">
                <div class="tool-number">TOOL 01</div>
                <div class="tool-name">
                    ORDER-FORM TO OUTPUT CHECK
                </div>
                <div class="tool-description">
                    Compare selected Order Form data against
                    the PDF output and identify mismatches,
                    spelling errors and missing data.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Open Order Form → Output Check",
            key="tool1"
        ):

            st.session_state.selected_tool = "order_form"


    # -----------------------------------------------------
    # TOOL 2
    # -----------------------------------------------------

    with col2:

        st.markdown(
            """
            <div class="tool-card">
                <div class="tool-number">TOOL 02</div>
                <div class="tool-name">
                    ORIGINAL SPEC TO OUTPUT CHECK
                </div>
                <div class="tool-description">
                    Compare the Original Spec against
                    the final PDF output.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Open Original Spec → Output Check",
            key="tool2"
        ):

            st.session_state.selected_tool = "spec"


    # -----------------------------------------------------
    # TOOL 3
    # -----------------------------------------------------

    col3, col4 = st.columns(2)

    with col3:

        st.markdown(
            """
            <div class="tool-card">
                <div class="tool-number">TOOL 03</div>
                <div class="tool-name">
                    SPEC + ORDER FORM + OUTPUT CHECK
                </div>
                <div class="tool-description">
                    Cross-check the Original Spec,
                    Order Form and final PDF output.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Open Spec + Order Form + Output Check",
            key="tool3"
        ):

            st.session_state.selected_tool = "spec_order"


    # -----------------------------------------------------
    # TOOL 4
    # -----------------------------------------------------

    with col4:

        st.markdown(
            """
            <div class="tool-card">
                <div class="tool-number">TOOL 04</div>
                <div class="tool-name">
                    MORE QC TOOLS
                </div>
                <div class="tool-description">
                    Additional QC utilities and validation
                    tools will be added here.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button(
            "Open More QC Tools",
            key="tool4"
        ):

            st.session_state.selected_tool = "more"


# =========================================================
# TOOL ROUTER
# =========================================================

if st.session_state.selected_tool is None:

    dashboard()

else:

    if st.button(
        "← Back to Dashboard",
        key="back"
    ):

        st.session_state.selected_tool = None
        st.rerun()


    st.divider()


    # -----------------------------------------------------
    # ORDER FORM → OUTPUT
    # -----------------------------------------------------

    if st.session_state.selected_tool == "order_form":

        from tools.order_form_output_check import main

        main()


    # -----------------------------------------------------
    # ORIGINAL SPEC → OUTPUT
    # -----------------------------------------------------

    elif st.session_state.selected_tool == "spec":

        from tools.original_spec_output_check import main

        main()


    # -----------------------------------------------------
    # SPEC + ORDER FORM + OUTPUT
    # -----------------------------------------------------

    elif st.session_state.selected_tool == "spec_order":

        from tools.spec_order_form_output_check import main

        main()


    # -----------------------------------------------------
    # MORE QC TOOLS
    # -----------------------------------------------------

    elif st.session_state.selected_tool == "more":

        from tools.more_qc_tools import main

        main()
