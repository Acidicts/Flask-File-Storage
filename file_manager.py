import fernet
import os
from werkzeug.utils import secure_filename
try:
    from PIL import Image
except ImportError:
    Image = None

class FileManager:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        self.files = {}

        self.files = self.get_all_files()
        print(f"Initialized FileManager with files: {self.files}")
    
    def get_all_files(self):
        try:
            files = []
            for item in os.listdir(self.upload_folder):
                item_path = os.path.join(self.upload_folder, item)
                extension = os.path.splitext(item)[1].lower() if os.path.isfile(item_path) else None
                files.append({
                    'name': item,
                    'is_dir': os.path.isdir(item_path),
                    'size': os.path.getsize(item_path) if os.path.isfile(item_path) else None,
                    'extension': extension,
                    'file_type': self._get_file_type(extension)
                })
            return files
        except Exception as e:
            print(f"Error getting files: {e}")
            return []
    
    def _get_file_type(self, extension):
        if not extension:
            return 'folder'
        
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        if extension in image_exts:
            return 'image'
        
        file_type_map = {
            '.py': 'python',
            '.html': 'html',
            '.css': 'css',
            '.js': 'javascript',
            '.json': 'json',
            '.xml': 'xml',
            '.txt': 'text',
            '.md': 'markdown',
            '.pdf': 'pdf',
            '.zip': 'archive',
            '.rar': 'archive',
            '.7z': 'archive',
            '.tar': 'archive',
            '.gz': 'archive',
            '.doc': 'word',
            '.docx': 'word',
            '.xls': 'excel',
            '.xlsx': 'excel',
            '.ppt': 'powerpoint',
            '.pptx': 'powerpoint',
            '.mp4': 'video',
            '.avi': 'video',
            '.mov': 'video',
            '.mp3': 'audio',
            '.wav': 'audio',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.ts': 'typescript',
            '.jsx': 'react',
            '.tsx': 'react',
            '.vue': 'vue',
            '.sql': 'database',
        }
        
        return file_type_map.get(extension, 'file')
    
    def get_file_details(self, filename):
        file_path = os.path.join(self.upload_folder, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {filename} not found")
        
        stats = os.stat(file_path)
        extension = os.path.splitext(filename)[1].lower()
        file_type = self._get_file_type(extension)
        
        # Get detailed size information
        size_bytes = stats.st_size
        size_bits = size_bytes * 8
        
        details = {
            'name': filename,
            'size_bytes': size_bytes,
            'size_bits': size_bits,
            'size_bytes_formatted': self._format_size(size_bytes, 'B'),
            'size_bits_formatted': self._format_size(size_bits, 'b'),
            'extension': extension,
            'file_type': file_type,
            'modified': stats.st_mtime,
            'created': stats.st_ctime,
            'is_text': self._is_text_file(extension),
            'is_editable': self._is_editable(extension),
        }
        
        # Add image metadata if it's an image
        if file_type == 'image':
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    details['image_metadata'] = {
                        'width': img.width,
                        'height': img.height,
                        'format': img.format,
                        'mode': img.mode,
                    }
                    if hasattr(img, '_getexif') and img._getexif():
                        details['image_metadata']['exif'] = str(img._getexif())
            except Exception as e:
                details['image_metadata'] = {'error': str(e)}
        
        return details
    
    def _format_size(self, size, unit):
        if unit == 'B':
            units = ['B', 'kB', 'MB', 'GB', 'TB']
        else:
            units = ['b', 'kb', 'Mb', 'Gb', 'Tb']
        
        for i, u in enumerate(units):
            if size < 1024 or i == len(units) - 1:
                return f"{size:.2f} {u}"
            size /= 1024
        
        return f"{size:.2f} {units[-1]}"
    
    def _is_text_file(self, extension):
        text_exts = ['.txt', '.py', '.html', '.css', '.js', '.json', '.xml', 
                     '.md', '.csv', '.log', '.yaml', '.yml', '.ini', '.cfg',
                     '.java', '.cpp', '.c', '.h', '.php', '.rb', '.go', '.rs',
                     '.ts', '.jsx', '.tsx', '.vue', '.sql', '.sh', '.bat']
        return extension in text_exts
    
    def _is_editable(self, extension):
        return self._is_text_file(extension)
    
    def get_file_content(self, filename):
        file_path = os.path.join(self.upload_folder, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {filename} not found")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            return "[Binary file - cannot display as text]"
    
    def save_file_content(self, filename, content):
        file_path = os.path.join(self.upload_folder, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def upload_file(self, file):
        filename = secure_filename(file.filename)
        if not filename:
            raise ValueError("Invalid filename")
        
        file_path = os.path.join(self.upload_folder, filename)
        
        # Check if file already exists
        if os.path.exists(file_path):
            # Add number to filename
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_path):
                filename = f"{name}_{counter}{ext}"
                file_path = os.path.join(self.upload_folder, filename)
                counter += 1
        
        file.save(file_path)
        return filename
    
    def delete_file(self, filename):
        file_path = os.path.join(self.upload_folder, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File or folder {filename} not found")
        
        if os.path.isdir(file_path):
            import shutil
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
    
    def create_folder(self, folder_name):
        folder_name = secure_filename(folder_name)
        if not folder_name:
            raise ValueError("Invalid folder name")
        
        folder_path = os.path.join(self.upload_folder, folder_name)
        
        if os.path.exists(folder_path):
            raise FileExistsError(f"Folder {folder_name} already exists")
        
        os.makedirs(folder_path)

    def save_file(self, file, target_folder=''):
        safe_filename = secure_filename(fernet.Fernet.generate_key().decode() + "_" + file.filename)
        
        # Sanitize and validate target folder
        if target_folder:
            safe_folder = secure_filename(target_folder)
            target_path = os.path.join(self.upload_folder, safe_folder)
            
            # Ensure the target folder exists
            if not os.path.exists(target_path):
                raise ValueError(f"Target folder '{target_folder}' does not exist")
            
            if not os.path.isdir(target_path):
                raise ValueError(f"'{target_folder}' is not a folder")
            
            file_path = os.path.join(target_path, safe_filename)
        else:
            file_path = os.path.join(self.upload_folder, safe_filename)
        
        file.save(file_path)
        return {"message": "Item added successfully!", "filename": safe_filename, "folder": target_folder}, 200

    def get_file_path(self, filename):
        safe_filename = secure_filename(filename)
        return os.path.join(self.upload_folder, safe_filename)