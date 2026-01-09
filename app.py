import streamlit as st
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import tempfile
import os
import zipfile

# ---------------- CONFIG ----------------
MAX_TOTAL_MB = 50
# ----------------------------------------

st.set_page_config(
    page_title="Herramientas PDF",
    page_icon="📄",
    layout="centered"
)

st.title("📄 Herramientas PDF")
st.caption("Unir y separar archivos PDF fácilmente (sin registro).")

# ---------- UTILIDADES ----------
def total_size_mb(files):
    return sum(f.size for f in files) / (1024 * 1024)

# ---------- TABS ----------
tab_unir, tab_separar = st.tabs(["🔗 Unir PDFs", "✂️ Separar PDF"])

# =========================================================
# 🔗 TAB UNIR PDFS
# =========================================================
with tab_unir:
    st.subheader("Unir varios PDFs en uno")

    files = st.file_uploader(
        "Selecciona los archivos PDF",
        type="pdf",
        accept_multiple_files=True,
        key="merge"
    )

    if files:
        total_mb = total_size_mb(files)
        st.info(f"📦 Tamaño total cargado: **{total_mb:.2f} MB**")

        if total_mb > MAX_TOTAL_MB:
            st.error(f"❌ El tamaño total supera el límite de {MAX_TOTAL_MB} MB.")
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
                        "⬇️ Descargar PDF unido",
                        f,
                        file_name="pdf_unido.pdf",
                        mime="application/pdf"
                    )

                st.success("✅ PDFs unidos correctamente")

            finally:
                if output_path and os.path.exists(output_path):
                    os.remove(output_path)

# =========================================================
# ✂️ TAB SEPARAR PDF
# =========================================================
with tab_separar:
    st.subheader("Separar un PDF")

    file = st.file_uploader(
        "Selecciona un archivo PDF",
        type="pdf",
        accept_multiple_files=False,
        key="split"
    )

    if file:
        reader = PdfReader(file)
        total_pages = len(reader.pages)

        st.info(f"📄 El PDF tiene **{total_pages} páginas**")

        mode = st.radio(
            "¿Cómo deseas separar el PDF?",
            ["Separar todas las páginas", "Separar un rango de páginas"]
        )

        if mode == "Separar un rango de páginas":
            col1, col2 = st.columns(2)
            start = col1.number_input(
                "Página inicial",
                min_value=1,
                max_value=total_pages,
                value=1
            )
            end = col2.number_input(
                "Página final",
                min_value=1,
                max_value=total_pages,
                value=total_pages
            )

            if start > end:
                st.error("❌ La página inicial no puede ser mayor que la final.")
                st.stop()
        else:
            start, end = 1, total_pages

        if st.button("✂️ Separar PDF"):
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "pdf_separado.zip")

                with zipfile.ZipFile(zip_path, "w") as zipf:
                    for i in range(start - 1, end):
                        writer = PdfWriter()
                        writer.add_page(reader.pages[i])

                        pdf_path = os.path.join(
                            tmpdir, f"pagina_{i+1}.pdf"
                        )
                        with open(pdf_path, "wb") as f:
                            writer.write(f)

                        zipf.write(pdf_path, arcname=f"pagina_{i+1}.pdf")

                with open(zip_path, "rb") as f:
                    st.download_button(
                        "⬇️ Descargar PDFs separados (ZIP)",
                        f,
                        file_name="pdf_separado.zip",
                        mime="application/zip"
                    )

            st.success("✅ PDF separado correctamente")
