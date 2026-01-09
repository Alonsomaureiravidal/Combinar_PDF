import streamlit as st
from PyPDF2 import PdfMerger
import tempfile
import os

# ---------------- CONFIG ----------------
MAX_TOTAL_MB = 50  # límite total permitido
# ----------------------------------------

st.set_page_config(
    page_title="Unir PDFs",
    page_icon="📄",
    layout="centered"
)

st.title("📄 Unir archivos PDF")
st.write(
    f"Sube múltiples archivos PDF y únelos en uno solo. "
    f"Tamaño total máximo permitido: **{MAX_TOTAL_MB} MB**."
)

files = st.file_uploader(
    "Selecciona los archivos PDF",
    type="pdf",
    accept_multiple_files=True
)

def total_size_mb(uploaded_files):
    total_bytes = sum(f.size for f in uploaded_files)
    return total_bytes / (1024 * 1024)

if files:
    total_mb = total_size_mb(files)

    st.info(f"📦 Tamaño total cargado: **{total_mb:.2f} MB**")

    if total_mb > MAX_TOTAL_MB:
        st.error(
            f"❌ El tamaño total supera el límite de "
            f"{MAX_TOTAL_MB} MB. Reduce los archivos."
        )
        st.stop()

    if st.button("🔗 Unir PDFs"):
        merger = PdfMerger()
        output_path = None

        try:
            for pdf in files:
                merger.append(pdf)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                merger.write(tmp.name)
                output_path = tmp.name

            merger.close()

            with open(output_path, "rb") as f:
                st.download_button(
                    label="⬇️ Descargar PDF unido",
                    data=f,
                    file_name="pdf_unido.pdf",
                    mime="application/pdf"
                )

        finally:
            if output_path and os.path.exists(output_path):
                os.remove(output_path)
