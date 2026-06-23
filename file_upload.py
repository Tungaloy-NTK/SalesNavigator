import streamlit as st
import os

def page_file_upload():
    """Simple file upload page for database files"""
    st.title("📤 Upload Database Files")

    st.write("Upload the insert_converter_db.xlsx file here:")

    uploaded_file = st.file_uploader(
        "Choose file",
        type=["xlsx"],
        key="db_upload"
    )

    if uploaded_file is not None:
        # Define the save path
        save_path = "/var/www/salesnavigator/insert_converter_db.xlsx"

        try:
            # Save the uploaded file
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.success(f"✅ File uploaded successfully to {save_path}")
            st.info(f"File size: {uploaded_file.size} bytes")

        except Exception as e:
            st.error(f"❌ Error uploading file: {str(e)}")
