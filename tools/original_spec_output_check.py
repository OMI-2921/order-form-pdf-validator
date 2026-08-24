import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import streamlit.components.v1 as components


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Original Spec to Output Check",
    page_icon="🔍",
    layout="wide"
)


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown("""
<style>

.main-title {
    text-align: center;
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 5px;
}

.sub-title {
    text-align: center;
    color: #8a8a8a;
    margin-bottom: 25px;
}

/* Comparison Mode Buttons / Tabs */

.mode-header {
    text-align: center;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# PDF FUNCTIONS
# =========================================================

def get_pdf_page_count(uploaded_file):
    """Return total pages in uploaded PDF."""

    pdf_bytes = uploaded_file.getvalue()

    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    count = len(doc)

    doc.close()

    return count


def pdf_page_to_image(uploaded_file, page_number=0, scale=2.0):
    """Render PDF page as PIL image."""

    pdf_bytes = uploaded_file.getvalue()

    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    if page_number >= len(doc):
        page_number = 0

    page = doc.load_page(page_number)

    matrix = fitz.Matrix(scale, scale)

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


# =========================================================
# IMAGE FUNCTIONS
# =========================================================

def image_to_base64(image):
    """Convert PIL image to base64 PNG."""

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return encoded


def create_monochrome(image, rgb_color):
    """
    Convert image into monochrome artwork.

    White/light background becomes transparent.
    Dark artwork becomes selected color.
    """

    gray = image.convert("L")

    width, height = gray.size

    result = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )

    gray_pixels = gray.load()
    result_pixels = result.load()

    r, g, b = rgb_color

    for y in range(height):
        for x in range(width):

            value = gray_pixels[x, y]

            # White becomes transparent
            alpha = 255 - value

            result_pixels[x, y] = (
                r,
                g,
                b,
                alpha
            )

    return result


# =========================================================
# INTERACTIVE COMPARISON VIEWER
# =========================================================

def comparison_viewer(
    original_image,
    output_image,
    mode="overlay",
    blink_speed=0.5
):

    # -----------------------------------------------------
    # COLORS
    # -----------------------------------------------------

    # Dark professional red
    ORIGINAL_RED = (170, 45, 45)

    # Dark green (not neon)
    OUTPUT_GREEN = (35, 120, 75)


    # -----------------------------------------------------
    # CREATE MONOCHROME IMAGES
    # -----------------------------------------------------

    original_mono = create_monochrome(
        original_image,
        ORIGINAL_RED
    )

    output_mono = create_monochrome(
        output_image,
        OUTPUT_GREEN
    )


    # -----------------------------------------------------
    # CONVERT TO BASE64
    # -----------------------------------------------------

    original_b64 = image_to_base64(
        original_mono
    )

    output_b64 = image_to_base64(
        output_mono
    )


    # -----------------------------------------------------
    # HTML CANVAS VIEWER
    # -----------------------------------------------------

    html = f"""
    <!DOCTYPE html>
    <html>

    <head>

    <style>

    html,
    body {{
        margin: 0;
        padding: 0;
        background: transparent;
        overflow: hidden;
    }}

    #viewer-wrapper {{
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
    }}

    #viewer {{
        width: 900px;
        height: 650px;

        background: #000000;

        border: 1px solid #333;
        border-radius: 12px;

        overflow: hidden;

        position: relative;

        cursor: grab;

        box-shadow:
            0px 8px 30px rgba(0,0,0,0.45);
    }}

    #viewer:active {{
        cursor: grabbing;
    }}

    canvas {{
        width: 100%;
        height: 100%;

        display: block;
    }}

    .viewer-info {{
        position: absolute;

        top: 12px;
        left: 12px;

        background: rgba(25,25,25,0.85);

        color: #d5d5d5;

        padding: 7px 12px;

        border-radius: 6px;

        font-family: Arial;

        font-size: 12px;

        pointer-events: none;
    }}

    .controls {{
        position: absolute;

        bottom: 12px;
        left: 50%;

        transform: translateX(-50%);

        display: flex;

        gap: 8px;

        background: rgba(25,25,25,0.9);

        padding: 8px;

        border-radius: 8px;
    }}

    .controls button {{
        background: #252525;

        color: white;

        border: 1px solid #555;

        padding: 6px 12px;

        border-radius: 5px;

        cursor: pointer;
    }}

    .controls button:hover {{
        background: #444;
    }}

    </style>

    </head>


    <body>

    <div id="viewer-wrapper">

        <div id="viewer">

            <canvas id="canvas"></canvas>

            <div class="viewer-info" id="info">
                Loading comparison...
            </div>

            <div class="controls">

                <button onclick="zoomOut()">−</button>

                <button onclick="fitImage()">FIT</button>

                <button onclick="zoomIn()">+</button>

                <button onclick="resetView()">RESET</button>

            </div>

        </div>

    </div>


    <script>

    // =====================================================
    // SETTINGS
    // =====================================================

    const MODE = "{mode}";

    const BLINK_SPEED =
        {blink_speed} * 1000;


    // Both layers are 80% opacity
    const ORIGINAL_OPACITY = 0.80;

    const OUTPUT_OPACITY = 0.80;


    // =====================================================
    // CANVAS
    // =====================================================

    const canvas =
        document.getElementById("canvas");

    const ctx =
        canvas.getContext("2d");


    const viewer =
        document.getElementById("viewer");


    function resizeCanvas() {{

        const rect =
            viewer.getBoundingClientRect();

        canvas.width =
            rect.width;

        canvas.height =
            rect.height;

        draw();

    }}


    // =====================================================
    // IMAGES
    // =====================================================

    const original =
        new Image();

    const output =
        new Image();


    original.src =
        "data:image/png;base64,{original_b64}";


    output.src =
        "data:image/png;base64,{output_b64}";


    let loaded = 0;


    function imageLoaded() {{

        loaded++;

        if (loaded === 2) {{

            fitImage();

            if (MODE === "blink") {{

                startBlink();

            }}

        }}

    }}


    original.onload =
        imageLoaded;

    output.onload =
        imageLoaded;


    // =====================================================
    // VIEW STATE
    // =====================================================

    let scale = 1;

    let offsetX = 0;

    let offsetY = 0;


    // =====================================================
    // FIT IMAGE
    // =====================================================

    function fitImage() {{

        if (!original.width) return;

        const padding = 40;

        const scaleX =
            (canvas.width - padding) /
            original.width;

        const scaleY =
            (canvas.height - padding) /
            original.height;

        scale =
            Math.min(scaleX, scaleY);

        offsetX =
            (canvas.width -
            original.width * scale) / 2;

        offsetY =
            (canvas.height -
            original.height * scale) / 2;

        draw();

    }}


    function resetView() {{

        fitImage();

    }}


    function zoomIn() {{

        scale *= 1.25;

        draw();

    }}


    function zoomOut() {{

        scale /= 1.25;

        draw();

    }}


    // =====================================================
    // DRAW
    // =====================================================

    let blinkShowOriginal = true;


    function draw() {{

        ctx.clearRect(
            0,
            0,
            canvas.width,
            canvas.height
        );


        ctx.fillStyle =
            "#000000";

        ctx.fillRect(
            0,
            0,
            canvas.width,
            canvas.height
        );


        // -------------------------------------------------
        // OVERLAY MODE
        // -------------------------------------------------

        if (MODE === "overlay") {{

            ctx.globalAlpha =
                ORIGINAL_OPACITY;

            ctx.drawImage(
                original,
                offsetX,
                offsetY,
                original.width * scale,
                original.height * scale
            );


            ctx.globalAlpha =
                OUTPUT_OPACITY;

            ctx.drawImage(
                output,
                offsetX,
                offsetY,
                output.width * scale,
                output.height * scale
            );

        }}


        // -------------------------------------------------
        // BLINK MODE
        // -------------------------------------------------

        else if (MODE === "blink") {{

            ctx.globalAlpha = 1;

            const activeImage =
                blinkShowOriginal
                    ? original
                    : output;

            ctx.drawImage(
                activeImage,
                offsetX,
                offsetY,
                activeImage.width * scale,
                activeImage.height * scale
            );

        }}


        ctx.globalAlpha = 1;


        document.getElementById("info").innerText =

            MODE === "overlay"

                ? "🟥 Original + 🟢 Output | " +
                  Math.round(scale * 100) + "%"

                : (blinkShowOriginal
                    ? "🟥 ORIGINAL SPEC"
                    : "🟢 OUTPUT")
                  + " | "
                  + Math.round(scale * 100) + "%";

    }


    // =====================================================
    // BLINK
    // =====================================================

    function startBlink() {{

        setInterval(() => {{

            blinkShowOriginal =
                !blinkShowOriginal;

            draw();

        }}, BLINK_SPEED);

    }}


    // =====================================================
    // MOUSE WHEEL ZOOM
    // =====================================================

    viewer.addEventListener(
        "wheel",

        function(event) {{

            event.preventDefault();

            const zoomFactor =
                event.deltaY < 0
                    ? 1.12
                    : 0.88;


            const rect =
                canvas.getBoundingClientRect();


            const mouseX =
                event.clientX -
                rect.left;


            const mouseY =
                event.clientY -
                rect.top;


            // Keep mouse position stable
            offsetX =
                mouseX -
                (mouseX - offsetX) *
                zoomFactor;


            offsetY =
                mouseY -
                (mouseY - offsetY) *
                zoomFactor;


            scale *= zoomFactor;


            // Prevent extremely small zoom
            scale =
                Math.max(
                    0.05,
                    Math.min(scale, 20)
                );


            draw();

        }},
        {{ passive: false }}
    );


    // =====================================================
    // DRAG / PAN
    // =====================================================

    let dragging = false;

    let lastX = 0;

    let lastY = 0;


    viewer.addEventListener(
        "mousedown",

        function(event) {{

            dragging = true;

            lastX =
                event.clientX;

            lastY =
                event.clientY;

        }}
    );


    window.addEventListener(
        "mousemove",

        function(event) {{

            if (!dragging)
                return;


            const dx =
                event.clientX -
                lastX;


            const dy =
                event.clientY -
                lastY;


            offsetX += dx;

            offsetY += dy;


            lastX =
                event.clientX;

            lastY =
                event.clientY;


            draw();

        }}
    );


    window.addEventListener(
        "mouseup",

        function() {{

            dragging = false;

        }}
    );


    // =====================================================
    // DOUBLE CLICK = FIT
    // =====================================================

    viewer.addEventListener(
        "dblclick",

        function() {{

            fitImage();

        }}
    );


    // =====================================================
    // INITIALIZE
    // =====================================================

    window.addEventListener(
        "resize",
        resizeCanvas
    );


    setTimeout(() => {{

        resizeCanvas();

    }}, 100);


    </script>

    </body>

    </html>
    """

    components.html(
        html,
        height=680,
        scrolling=False
    )


# =========================================================
# DATA CHECK PLACEHOLDER
# =========================================================

def data_check_view():

    st.subheader("🔍 Data Check")

    st.info(
        "This section will identify text differences between "
        "the Original Spec and Output."
    )

    st.markdown("""
    ### Classification Logic

    **STATIC** → Must match exactly, including:

    - Spelling
    - Words
    - Commas
    - Periods
    - Punctuation

    **VARIABLE** → Data is allowed to change.

    **IGNORE** → Excluded from validation.
    """)

    st.selectbox(
        "Difference Type",
        [
            "Select Type",
            "STATIC",
            "VARIABLE",
            "IGNORE"
        ],
        key="data_type"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    st.markdown(
        '<div class="main-title">'
        '🔍 ORIGINAL SPEC TO OUTPUT CHECK'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sub-title">'
        'Visual and Data Comparison'
        '</div>',
        unsafe_allow_html=True
    )


    # -----------------------------------------------------
    # UPLOADS
    # -----------------------------------------------------

    col1, col2 = st.columns(2)


    with col1:

        original_spec = st.file_uploader(
            "📄 Upload Original Spec",
            type=["pdf"],
            key="original_spec_file"
        )


    with col2:

        output_file = st.file_uploader(
            "📄 Upload Output",
            type=["pdf"],
            key="output_file"
        )


    # -----------------------------------------------------
    # WAIT FOR FILES
    # -----------------------------------------------------

    if not original_spec or not output_file:

        st.info(
            "Upload both PDFs to begin comparison."
        )

        return


    # -----------------------------------------------------
    # PAGE COUNTS
    # -----------------------------------------------------

    original_pages = get_pdf_page_count(
        original_spec
    )

    output_pages = get_pdf_page_count(
        output_file
    )


    max_pages = min(
        original_pages,
        output_pages
    )


    # -----------------------------------------------------
    # PAGE SELECTOR
    # -----------------------------------------------------

    if max_pages > 1:

        page_number = st.selectbox(
            "Select Page",
            list(range(max_pages)),
            format_func=lambda x:
                f"Page {x + 1}"
        )

    else:

        page_number = 0


    # -----------------------------------------------------
    # COMPARE BUTTON
    # -----------------------------------------------------

    if st.button(
        "🔍 COMPARE",
        use_container_width=True,
        type="primary"
    ):

        st.session_state["spec_compare_started"] = True


    if not st.session_state.get(
        "spec_compare_started",
        False
    ):

        return


    # -----------------------------------------------------
    # RENDER PDF PAGES
    # -----------------------------------------------------

    with st.spinner(
        "Preparing comparison..."
    ):

        original_image = pdf_page_to_image(
            original_spec,
            page_number,
            scale=2.0
        )

        output_image = pdf_page_to_image(
            output_file,
            page_number,
            scale=2.0
        )


    # -----------------------------------------------------
    # MODES
    # -----------------------------------------------------

    overlay_tab, blink_tab, data_tab = st.tabs([

        "🟥🟢 OVERLAY",
        "👁 BLINK",
        "🔍 DATA CHECK"

    ])


    # =====================================================
    # OVERLAY
    # =====================================================

    with overlay_tab:

        st.caption(
            "Original Spec = dark red | "
            "Output = dark green | "
            "Both = 80% opacity"
        )

        comparison_viewer(
            original_image,
            output_image,
            mode="overlay"
        )


    # =====================================================
    # BLINK
    # =====================================================

    with blink_tab:

        blink_speed = st.slider(

            "⚡ Blink Speed (seconds)",

            min_value=0.25,

            max_value=2.0,

            value=0.5,

            step=0.25

        )


        st.caption(
            f"Switching Original ↔ Output every "
            f"{blink_speed} seconds"
        )


        comparison_viewer(
            original_image,
            output_image,
            mode="blink",
            blink_speed=blink_speed
        )


    # =====================================================
    # DATA CHECK
    # =====================================================

    with data_tab:

        data_check_view()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
