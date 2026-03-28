from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredExcelLoader
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging

logger = logging.getLogger(__name__)

def load_and_split(
        file_path: str
):
    extension = os.path.splitext(file_path)[1].lower()
    logger.info(f"Extension of file: {extension}")
    if extension == '.pdf':
        loader = PyPDFLoader(file_path=file_path)
    elif extension == '.txt':
        logger.info(f"Loading file .txt in TextLoader")
        loader = TextLoader(file_path=file_path)
        logger.info(f"File loaded with TextLoader")
    elif extension == '.docx':
        loader = Docx2txtLoader(file_path=file_path)
    elif extension in ['.xlsx','.xls']:
        loader = UnstructuredExcelLoader(file_path=file_path)
    else:
        raise ValueError(F"Unsupported file {extension} type")
    
    logger.info(f"Checking if file exists: {file_path}")
    logger.info(f"Current working directory {os.getcwd()}")
    logger.info(f"File exists? {os.path.exists(file_path)}")
    documents = loader.load()
    logger.info(f"Trying to split chunks")
    splitter = RecursiveCharacterTextSplitter(        
        chunk_size = 300,
        chunk_overlap = 100,
    )
    logger.info(f"Splitter: {splitter}")
    chunks = splitter.split_documents(documents=documents)
    logger.info(f"Chunks splitted successufully")

    return chunks