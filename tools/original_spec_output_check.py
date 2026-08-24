import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import base64


# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="Original Spec to Output Check",
    page_icon="🔍",
    layout="wide"
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def pdf_to_image(pdf_file, page_number, zoom=1.5):
    """
    Convert one PDF page into a PIL Image.
    """

    pdf_bytes = pdf_file.getvalue()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    if page_number >= len(doc):
        page_number = 0

    page = doc.load_page(page_number)

    matrix = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    image = Image.frombytes(
        "RGB",
        [pix.width, pix.height],
        pix.samples
    )

    doc.close()

    return image


def get_pdf_page_count(pdf_file):

    pdf_bytes = pdf_file.getvalue()

    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    page_count = len(doc)

    doc.close()

    return page_count


def create_monochrome(image, color="red"):
    """
    Convert artwork into a colored monochrome image.
    """

    gray = image.convert("L")

    width, height = gray.size

    result = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )

    pixels = gray.load()

    if color == "red":
        rgb = (255, 0, 0)

    elif color == "green":
        rgb = (0, 255, 0)

    else:
        rgb = (255, 255, 255)

    for y in range(height):
        for x in range(width):

            value = pixels[x, y]

            # Dark areas become visible
            alpha = 255 - value

            result.putpixel(
                (x, y),
                (
                    rgb[0],
                    rgb[1],
                    rgb[2],
                    alpha
                )
            )

    return result


def create_overlay(original_img, output_img, opacity=0.5):

    # Make both images same size
    width = max(
        original_img.width,
        output_img.width
    )

    height = max(
        original_img.height,
        output_img.height
    )

    original_canvas = Image.new(
        "RGBA",
        (width, height),
        "white"
    )

    output_canvas = Image.new(
        "RGBA",
        (width, height),
        "white"
    )

    original_canvas.paste(
        original_img,
        (0, 0)
    )

    output_canvas.paste(
        output_img,
        (0, 0)
    )

    # Adjust transparency
    original_alpha = original_canvas.getchannel("A")

    original_alpha = original_alpha.point(
        lambda x: int(x * opacity)
    )

    original_canvas.putalpha(original_alpha)

    output_alpha = output_canvas.getchannel("A")

    output_alpha = output_alpha.point(
        lambda x: int(x * opacity)
    )

    output_canvas.putalpha(output_alpha)

    overlay = Image.new(
        "RGBA",
        (width, height),
        "white"
    )

    overlay.alpha_composite(original_canvas)

    overlay.alpha_composite(output_canvas)

    return overlay


def image_to_base64(image):

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    return base64.b64encode(
        buffer.getvalue()
    ).decode()


# =========================================================
# MAIN APPLICATION
# =========================================================

def main():

    st.title("🔍 ORIGINAL SPEC TO OUTPUT CHECK")

    st.caption(
        "Compare Original Specification artwork against Final Output."
    )

    st.divider()


    # =====================================================
    # UPLOAD SECTION
    # =====================================================

    col1, col2 = st.columns(2)

    with col1:

        original_spec = st.file_uploader(
            "📄 Upload Original Spec",
            type=["pdf"],
            key="original_spec_upload"
        )

    with col2:

        output_file = st.file_uploader(
            "📄 Upload Output PDF",
            type=["pdf"],
            key="output_upload"
        )


    # =====================================================
    # WAIT FOR FILES
    # =====================================================

    if not original_spec or not output_file:

        st.info(
            "Upload both the Original Spec and Output PDF to begin comparison."
        )

        return


    # =====================================================
    # PAGE INFORMATION
    # =====================================================

    original_pages = get_pdf_page_count(original_spec)

    output_pages = get_pdf_page_count(output_file)

    max_pages = min(
        original_pages,
        output_pages
    )

    st.success(
        f"Original Spec: {original_pages} page(s) | "
        f"Output: {output_pages} page(s)"
    )


    # =====================================================
    # PAGE SELECTOR
    # =====================================================

    if max_pages > 1:

        page_number = st.selectbox(
            "Select Page for Comparison",
            options=list(range(max_pages)),
            format_func=lambda x: f"Page {x + 1}"
        )

    else:

        page_number = 0


    # =====================================================
    # COMPARISON BUTTON
    # =====================================================

    st.divider()

    if st.button(
        "🔍 COMPARE ARTWORK",
        use_container_width=True
    ):

        st.session_state["comparison_started"] = True


    if not st.session_state.get(
        "comparison_started",
        False
    ):

        return


    # =====================================================
    # RENDER SETTINGS
    # =====================================================

    render_zoom = 1.5

    original_image = pdf_to_image(
        original_spec,
        page_number,
        render_zoom
    )

    output_image = pdf_to_image(
        output_file,
        page_number,
        render_zoom
    )


    # =====================================================
    # COMPARISON MODES
    # =====================================================

    st.divider()

    tab_overlay, tab_blink, tab_data = st.tabs([
        "🟥🟩 OVERLAY",
        "👁 BLINK",
        "🔍 DATA CHECK"
    ])


    # =====================================================
    # OVERLAY MODE
    # =====================================================

    with tab_overlay:

        st.subheader("🟥🟩 Overlay Comparison")

        st.write(
            "Original Spec is shown in red and Output is shown in green."
        )

        opacity = st.slider(
            "Overlay Opacity",
            min_value=0.1,
            max_value=1.0,
            value=0.55,
            step=0.05
        )

        original_red = create_monochrome(
            original_image,
            "red"
        )

        output_green = create_monochrome(
            output_image,
            "green"
        )

        overlay_image = create_overlay(
            original_red,
            output_green,
            opacity
        )

        zoom_percent = st.slider(
            "🔍 Zoom",
            min_value=25,
            max_value=300,
            value=100,
            step=25
        )

        display_width = int(
            overlay_image.width * (zoom_percent / 100)
        )

        st.image(
            overlay_image,
            width=display_width
        )


    # =====================================================
    # BLINK MODE
    # =====================================================

    with tab_blink:

        st.subheader("👁 Blink Comparison")

        st.write(
            "The Original Spec and Output alternate continuously."
        )

        blink_speed = st.slider(
            "Blink Interval (seconds)",
            min_value=0.25,
            max_value=2.0,
            value=0.5,
            step=0.25
        )

        st.info(
            f"Current blink speed: {blink_speed} seconds"
        )

        st.write(
            "### Original Spec"
        )

        st.image(
            original_image,
            use_container_width=True
        )

        st.write(
            "### Output"
        )

        st.image(
            output_image,
            use_container_width=True
        )

        st.warning(
            "Blink animation will be added in the next update using "
            "a synchronized HTML/JavaScript comparison viewer."
        )


    # =====================================================
    # DATA CHECK MODE
    # =====================================================

    with tab_data:

        st.subheader("🔍 Data Check")

        st.write(
            "Detected differences between Original Spec and Output "
            "will be reviewed here."
        )

        st.divider()

        st.info(
            "Data comparison logic will identify corresponding text "
            "and allow each detected difference to be classified."
        )

        st.write("### Difference Classification")

        classification = st.selectbox(
            "Select Data Type",
            [
                "Select Type",
                "STATIC",
                "VARIABLE",
                "IGNORE"
            ]
        )

        if classification == "STATIC":

            st.error(
                "STATIC data requires an exact match. "
                "Spelling, punctuation, commas, periods, and wording "
                "must match exactly."
            )

        elif classification == "VARIABLE":

            st.success(
                "VARIABLE data is allowed to differ between the "
                "Original Spec and Output."
            )

        elif classification == "IGNORE":

            st.warning(
                "This data will be excluded from validation."
            )


    # =====================================================
    # FOOTER
    # =====================================================

    st.divider()

    st.caption(
        "Original Spec → Output Visual & Data Comparison Tool"
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    main()
