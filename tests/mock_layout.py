import streamlit as st

st.set_page_config(page_title="Photo Tagger Mock", layout="wide")

st.markdown(
    """
    <style>
    .mock-header {
        position: sticky;
        top: 0;
        z-index: 100;
        padding: 12px 16px;
        background: rgba(250, 250, 250, 0.95);
        border-bottom: 1px solid #e0e0e0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .mock-title {
        font-size: 18px;
        font-weight: 600;
    }
    .mock-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(33, 33, 33, 0.9);
        color: white;
        padding: 6px 24px;
        font-size: 12px;
        display: flex;
        justify-content: space-between;
    }
    .mock-gallery-frame {
        margin-top: 12px;
        max-height: calc(100vh - 140px);
        overflow-y: auto;
        background: #f7f7f9;
        border-radius: 12px;
        padding: 24px;
        border: 1px dashed #d0d0d0;
    }
    .mock-card-grid {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 16px;
    }
    .mock-card {
        height: 240px;
        border-radius: 12px;
        background: white;
        border: 1px solid #e0e0e0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="mock-header">
        <div class="mock-title">Photo Tagger — Review</div>
        <div>
            <button>Process images</button>
            <button>Save approved &amp; clear</button>
            <button>Export</button>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

review_tab, config_tab = st.tabs(["Gallery", "Config"])

with review_tab:
    controls = st.columns([1, 1, 1, 1, 1])
    controls[0].toggle("Medoids only")
    controls[1].toggle("Only unapproved")
    controls[2].toggle("Hide after save")
    controls[3].toggle("Center crop")
    controls[4].button("Clear selections", use_container_width=True)

    st.markdown("#### Thumbnails")
    st.markdown(
        """
        <div class="mock-gallery-frame">
            <div class="mock-card-grid">
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
                <div class="mock-card"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with config_tab:
    st.caption("One-time setup")
    st.text_input("Root path", "/photos/library")
    st.text_input("Labels file", "labels.txt")
    st.number_input("Labels per image", min_value=1, max_value=20, value=5, step=1)
    st.number_input("Batch size", min_value=1, value=64, step=1)
    st.toggle("Include RAW files")
    st.button("Apply configuration")

st.markdown(
    """
    <div class="mock-footer">
        <span>Status: ready</span>
        <span>Last action: (placeholder)</span>
    </div>
    """,
    unsafe_allow_html=True,
)
