"""
Ultra PDF Editor - File Utilities
Helper functions for file operations
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
import hashlib
from datetime import datetime


def get_temp_dir() -> Path:
    """Get temporary directory for the application"""
    temp_dir = Path(tempfile.gettempdir()) / "ultra_pdf_editor"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def create_temp_file(suffix: str = ".pdf", prefix: str = "temp_") -> Path:
    """Create a temporary file"""
    temp_dir = get_temp_dir()
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=temp_dir)
    os.close(fd)
    return Path(path)


def get_unique_filename(directory: Path, base_name: str, extension: str) -> Path:
    """Get a unique filename by appending a number if needed"""
    filepath = directory / f"{base_name}{extension}"
    counter = 1

    while filepath.exists():
        filepath = directory / f"{base_name}_{counter}{extension}"
        counter += 1

    return filepath


def safe_delete(filepath: Path) -> bool:
    """Safely delete a file"""
    try:
        if filepath.exists():
            # Try using send2trash if available
            try:
                from send2trash import send2trash
                send2trash(str(filepath))
            except ImportError:
                filepath.unlink()
        return True
    except Exception:
        return False


def safe_copy(src: Path, dst: Path) -> bool:
    """Safely copy a file"""
    try:
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


def safe_move(src: Path, dst: Path) -> bool:
    """Safely move a file"""
    try:
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        return False


def get_file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def format_file_size(size_bytes: int) -> str:
    """Format file size for display"""
    size: float = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def get_file_info(filepath: Path) -> dict:
    """Get detailed file information"""
    stat = filepath.stat()
    return {
        "name": filepath.name,
        "path": str(filepath),
        "size": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "created": datetime.fromtimestamp(stat.st_ctime),
        "modified": datetime.fromtimestamp(stat.st_mtime),
        "accessed": datetime.fromtimestamp(stat.st_atime),
        "extension": filepath.suffix.lower(),
        "is_readonly": not os.access(filepath, os.W_OK),
    }


def validate_pdf(filepath: Path) -> Tuple[bool, str]:
    """Validate if a file is a valid PDF"""
    if not filepath.exists():
        return False, "File does not exist"

    if filepath.suffix.lower() != '.pdf':
        return False, "File is not a PDF"

    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
            if not header.startswith(b'%PDF-'):
                return False, "Invalid PDF header"
        return True, "Valid PDF"
    except Exception as e:
        return False, str(e)


def is_pdf_encrypted(filepath: Path) -> bool:
    """Check if a PDF file is encrypted"""
    try:
        import fitz
        doc = fitz.open(str(filepath))
        encrypted = doc.is_encrypted
        doc.close()
        return encrypted
    except Exception:
        return False


def get_pdf_page_count(filepath: Path) -> int:
    """Get the number of pages in a PDF"""
    try:
        import fitz
        doc = fitz.open(str(filepath))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def list_pdfs_in_directory(directory: Path, recursive: bool = False) -> List[Path]:
    """List all PDF files in a directory"""
    pdfs = []

    if recursive:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdfs.append(Path(root) / file)
    else:
        for file in directory.iterdir():
            if file.is_file() and file.suffix.lower() == '.pdf':
                pdfs.append(file)

    return sorted(pdfs)


def backup_file(filepath: Path, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """Create a backup of a file"""
    if not filepath.exists():
        return None

    if backup_dir is None:
        backup_dir = filepath.parent / "backups"

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filepath.stem}_{timestamp}{filepath.suffix}"
    backup_path = backup_dir / backup_name

    if safe_copy(filepath, backup_path):
        return backup_path
    return None


def clean_temp_files(max_age_hours: int = 24):
    """Clean old temporary files"""
    temp_dir = get_temp_dir()
    now = datetime.now()

    for filepath in temp_dir.iterdir():
        try:
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            age = (now - mtime).total_seconds() / 3600

            if age > max_age_hours:
                if filepath.is_file():
                    filepath.unlink()
                elif filepath.is_dir():
                    shutil.rmtree(filepath)
        except Exception:
            pass


def ensure_extension(filepath: Path, extension: str) -> Path:
    """Ensure a file has the specified extension"""
    if not extension.startswith('.'):
        extension = '.' + extension

    if filepath.suffix.lower() != extension.lower():
        return filepath.with_suffix(extension)
    return filepath


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing invalid characters"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')

    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')

    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext

    return filename
