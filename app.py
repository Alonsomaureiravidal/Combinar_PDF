import streamlit as st
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import tempfile
import os
import zipfile
import io
import sys
import shutil
import subprocess
from pathlib import Path

from PIL import Image
from docx2pdf import convert as docx2pdf_convert

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
tab_unir, tab_separar, tab_word, tab_img = st.tabs(
    ["🔗 Unir PDFs", "✂️ Separar PDF", "📝 Word → PDF", "🖼️ JPG → PDF"]
)

def file_stem(filename: str) -> str:
    """Nombre base del archivo (sin ruta ni extensión)."""
    base = os.path.basename(filename or "archivo")
    stem, _ = os.path.splitext(base)
    return stem or "archivo"

def convert_docx_to_pdf(input_path: str, output_path: str, work_dir: str) -> None:
    """
    Convierte un .docx a .pdf.

    - En Windows intenta usar docx2pdf (requiere Microsoft Word).
    - En Linux/macOS intenta usar LibreOffice (soffice) si está disponible.
    """
    def find_soffice() -> str | None:
        # 1) PATH (Linux/macOS/Windows si está configurado)
        found = shutil.which("soffice") or shutil.which("libreoffice")
        if found:
            return found

        # 2) Ubicaciones típicas en Windows (LibreOffice)
        if sys.platform.startswith("win"):
            candidates = [
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ]
            for p in candidates:
                if os.path.exists(p):
                    return p
        return None

    # Preferimos LibreOffice siempre que exista (es lo más portable)
    soffice = find_soffice()
    if not soffice and sys.platform.startswith("win"):
        # Fallback en Windows: docx2pdf (requiere Microsoft Word)
        docx2pdf_convert(input_path, output_path)
        return

    if not soffice:
        raise RuntimeError(
            "No se encontró LibreOffice (comando `soffice`). "
            "Solución: instala LibreOffice y/o agrega `soffice` al PATH. "
            "En Streamlit Cloud puedes usar `packages.txt` con `libreoffice`."
        )

    # LibreOffice en contenedores (Streamlit Cloud) puede fallar/crashear si usa el perfil por defecto.
    # Forzamos un perfil aislado dentro del directorio temporal.
    user_profile_dir = os.path.join(work_dir, "lo_profile")
    os.makedirs(user_profile_dir, exist_ok=True)
    user_installation = Path(user_profile_dir).resolve().as_uri()  # file:///...

    # LibreOffice escribe el PDF en el outdir con el mismo nombre base del DOCX.
    before = {f for f in os.listdir(work_dir) if f.lower().endswith(".pdf")}
    try:
        env = os.environ.copy()
        env["HOME"] = work_dir
        # Locales razonables para evitar fallas raras en inicialización/config
        env.setdefault("LANG", "C.UTF-8")
        env.setdefault("LC_ALL", "C.UTF-8")
        subprocess.run(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--nolockcheck",
                "--nodefault",
                "--norestore",
                f"-env:UserInstallation={user_installation}",
                "--convert-to",
                "pdf:writer_pdf_Export",
                "--outdir",
                work_dir,
                input_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace")
        out = (e.stdout or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"LibreOffice falló.\nSTDOUT:\n{out}\nSTDERR:\n{err}") from e

    after = [f for f in os.listdir(work_dir) if f.lower().endswith(".pdf") and f not in before]
    if not after:
        # Fallback: si no detectamos el nuevo archivo, buscamos el más reciente
        pdfs = [os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.lower().endswith(".pdf")]
        if not pdfs:
            raise RuntimeError("LibreOffice no generó ningún PDF.")
        generated_path = max(pdfs, key=lambda p: os.path.getmtime(p))
    else:
        generated_path = os.path.join(work_dir, after[0])

    # Normalizamos al nombre esperado (output_path)
    if os.path.abspath(generated_path) != os.path.abspath(output_path):
        if os.path.exists(output_path):
            os.remove(output_path)
        os.replace(generated_path, output_path)

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
    st.subheader("Separar / Recortar un PDF")

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
            "¿Qué deseas hacer?",
            [
                "Recortar PDF (extraer un rango de páginas)",
                "Separar todas las páginas (una por archivo)"
            ]
        )

        # ---------------- RECORTAR PDF ----------------
        if mode == "Recortar PDF (extraer un rango de páginas)":
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

            if st.button("✂️ Recortar PDF"):
                writer = PdfWriter()

                for i in range(start - 1, end):
                    writer.add_page(reader.pages[i])

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    writer.write(tmp.name)
                    output_path = tmp.name

                with open(output_path, "rb") as f:
                    st.download_button(
                        "⬇️ Descargar PDF recortado",
                        f,
                        file_name=f"pdf_paginas_{start}_a_{end}.pdf",
                        mime="application/pdf"
                    )

                os.remove(output_path)
                st.success("✅ PDF recortado correctamente")

        # ---------------- SEPARAR EN PAGINAS ----------------
        else:
            if st.button("📄 Separar en páginas"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = os.path.join(tmpdir, "pdf_separado.zip")

                    with zipfile.ZipFile(zip_path, "w") as zipf:
                        for i in range(total_pages):
                            writer = PdfWriter()
                            writer.add_page(reader.pages[i])

                            pdf_path = os.path.join(tmpdir, f"pagina_{i+1}.pdf")
                            with open(pdf_path, "wb") as f:
                                writer.write(f)

                            zipf.write(pdf_path, arcname=f"pagina_{i+1}.pdf")

                    with open(zip_path, "rb") as f:
                        st.download_button(
                            "⬇️ Descargar páginas separadas (ZIP)",
                            f,
                            file_name="pdf_separado.zip",
                            mime="application/zip"
                        )

                st.success("✅ PDF separado en páginas correctamente")

# =========================================================
# 📝 TAB WORD -> PDF
# =========================================================
with tab_word:
    st.subheader("Convertir Word (.docx) a PDF")
    st.caption("El PDF descargable conserva el mismo nombre del Word.")

    docx_files = st.file_uploader(
        "Selecciona uno o más archivos Word",
        type=["docx"],
        accept_multiple_files=True,
        key="docx_to_pdf",
    )

    if docx_files:
        total_mb = total_size_mb(docx_files)
        st.info(f"📦 Tamaño total cargado: **{total_mb:.2f} MB**")

        if total_mb > MAX_TOTAL_MB:
            st.error(f"❌ El tamaño total supera el límite de {MAX_TOTAL_MB} MB.")
            st.stop()

        if st.button("📝 Convertir a PDF", key="btn_docx_to_pdf"):
            for doc in docx_files:
                stem = file_stem(doc.name)
                pdf_name = f"{stem}.pdf"

                with tempfile.TemporaryDirectory() as tmpdir:
                    input_path = os.path.join(tmpdir, doc.name)
                    output_path = os.path.join(tmpdir, pdf_name)

                    with open(input_path, "wb") as f:
                        f.write(doc.getbuffer())

                    try:
                        convert_docx_to_pdf(input_path, output_path, tmpdir)
                        with open(output_path, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Descargar {pdf_name}",
                                data=f,
                                file_name=pdf_name,
                                mime="application/pdf",
                                key=f"dl_docx_{doc.name}",
                            )
                    except Exception as e:
                        st.error(
                            f"❌ No se pudo convertir `{doc.name}`. "
                            f"Si estás en Linux/Streamlit Cloud, necesitas LibreOffice (soffice). "
                            f"Detalle: {e}"
                        )

# =========================================================
# 🖼️ TAB JPG -> PDF
# =========================================================
with tab_img:
    st.subheader("Convertir JPG/JPEG/PNG a PDF")
    st.caption("El PDF descargable conserva el mismo nombre de la imagen.")

    img_files = st.file_uploader(
        "Selecciona una o más imágenes",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="img_to_pdf",
    )

    if img_files:
        total_mb = total_size_mb(img_files)
        st.info(f"📦 Tamaño total cargado: **{total_mb:.2f} MB**")

        if total_mb > MAX_TOTAL_MB:
            st.error(f"❌ El tamaño total supera el límite de {MAX_TOTAL_MB} MB.")
            st.stop()

        if st.button("🖼️ Convertir a PDF", key="btn_img_to_pdf"):
            for img in img_files:
                stem = file_stem(img.name)
                pdf_name = f"{stem}.pdf"

                try:
                    image = Image.open(img).convert("RGB")
                    buf = io.BytesIO()
                    image.save(buf, format="PDF")
                    buf.seek(0)

                    st.download_button(
                        label=f"⬇️ Descargar {pdf_name}",
                        data=buf,
                        file_name=pdf_name,
                        mime="application/pdf",
                        key=f"dl_img_{img.name}",
                    )
                except Exception as e:
                    st.error(f"❌ No se pudo convertir `{img.name}`. Detalle: {e}")
