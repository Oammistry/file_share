import os
import socket
import qrcode
from flask import Flask, render_template_string, request, send_file, jsonify
from werkzeug.utils import secure_filename
import mimetypes

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['UPLOAD_FOLDER'] = 'shared_files'

# Create upload folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# HTML template for the web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>File Share</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f0f0f0;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .upload-area {
            border: 2px dashed #4CAF50;
            border-radius: 5px;
            padding: 30px;
            text-align: center;
            margin: 20px 0;
            background: #f9f9f9;
        }
        .upload-area:hover {
            background: #f0f0f0;
        }
        input[type="file"] {
            display: none;
        }
        .btn {
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        .btn:hover {
            background: #45a049;
        }
        .file-list {
            margin-top: 30px;
        }
        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            margin: 5px 0;
            background: #f9f9f9;
            border-radius: 5px;
            min-height: 80px;
        }
        .file-item:hover {
            background: #f0f0f0;
        }
        .file-info {
            display: flex;
            align-items: center;
            gap: 15px;
            flex: 1;
        }
        .file-preview {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        .file-icon-large {
            width: 80px;
            height: 80px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            background: #f0f0f0;
            border-radius: 5px;
        }
        .file-name {
            flex: 1;
            word-break: break-word;
            font-size: 14px;
        }
        .qr-code {
            text-align: center;
            margin: 20px 0;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 5px;
        }
        .connection-info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        #progress {
            display: none;
            margin-top: 10px;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #f0f0f0;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: #4CAF50;
            width: 0%;
            transition: width 0.3s;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 File Share</h1>
        
        <div class="connection-info">
            <strong>Share this URL with other devices:</strong><br>
            {{ url }}
        </div>
        
        <div class="qr-code">
            <h3>Scan QR Code to Connect</h3>
            <img src="/qrcode" alt="QR Code">
        </div>
        
        <div class="upload-area" id="uploadArea">
            <p>📤 Drag and drop multiple files here or click to select</p>
            <p style="font-size: 14px; color: #666; margin-top: 10px;">
                ✨ Select multiple files at once for batch upload<br>
                🖼️ Images and documents supported
            </p>
            <input type="file" id="fileInput" multiple>
            <button class="btn" onclick="document.getElementById('fileInput').click()">
                Choose Files
            </button>
        </div>
        
        <div id="progress">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <p id="progressText">Uploading...</p>
        </div>
        
        <div class="file-list">
            <h2>Shared Files</h2>
            <div id="fileList"></div>
        </div>
    </div>

    <script>
        // Drag and drop functionality
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.background = '#e8f5e9';
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.style.background = '#f9f9f9';
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.background = '#f9f9f9';
            handleFiles(e.dataTransfer.files);
        });
        
        fileInput.addEventListener('change', (e) => {
            console.log('File input change event triggered');
            console.log('Input element multiple attribute:', e.target.multiple);
            console.log('Files selected:', e.target.files.length);
            handleFiles(e.target.files);
        });
        
        function handleFiles(files) {
            console.log(`handleFiles called with ${files.length} files:`);
            for (let i = 0; i < files.length; i++) {
                console.log(`  File ${i + 1}: ${files[i].name} (${files[i].size} bytes)`);
            }
            
            if (files.length === 0) {
                alert('No files selected');
                return;
            }
            
            // Show user which files were selected
            let fileNames = Array.from(files).map(f => f.name).join(', ');
            if (files.length > 1) {
                alert(`Selected ${files.length} files: ${fileNames}\nUploading in batch mode...`);
                uploadFilesBatch(files);
            } else {
                alert(`Selected 1 file: ${fileNames}\nUploading in single mode...`);
                uploadFile(files[0]);
            }
        }
        
        function uploadFilesBatch(files) {
            const formData = new FormData();
            
            // Append all files to the form data
            for (let file of files) {
                formData.append('files', file);
            }
            
            const progress = document.getElementById('progress');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            progress.style.display = 'block';
            progressText.textContent = `Uploading ${files.length} files...`;
            
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressFill.style.width = percentComplete + '%';
                    progressText.textContent = `Uploading ${files.length} files: ${Math.round(percentComplete)}%`;
                }
            });
            
            xhr.addEventListener('load', () => {
                progress.style.display = 'none';
                progressFill.style.width = '0%';
                
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    showUploadResults(response);
                } else {
                    alert('Upload failed!');
                }
                
                loadFiles();
            });
            
            xhr.addEventListener('error', () => {
                progress.style.display = 'none';
                progressFill.style.width = '0%';
                alert('Upload failed due to network error!');
            });
            
            xhr.open('POST', '/upload/batch');
            xhr.send(formData);
        }
        
        function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            const progress = document.getElementById('progress');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            progress.style.display = 'block';
            
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressFill.style.width = percentComplete + '%';
                    progressText.textContent = `Uploading ${file.name}: ${Math.round(percentComplete)}%`;
                }
            });
            
            xhr.addEventListener('load', () => {
                progress.style.display = 'none';
                progressFill.style.width = '0%';
                
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.uploaded_files && response.uploaded_files.length > 0) {
                        showUploadResults(response);
                    }
                } else {
                    alert('Upload failed!');
                }
                
                loadFiles();
            });
            
            xhr.addEventListener('error', () => {
                progress.style.display = 'none';
                progressFill.style.width = '0%';
                alert('Upload failed due to network error!');
            });
            
            xhr.open('POST', '/upload');
            xhr.send(formData);
        }
        
        function showUploadResults(response) {
            let message = '';
            
            if (response.total_uploaded > 0) {
                message += `✅ Successfully uploaded ${response.total_uploaded} file(s):\n`;
                response.uploaded_files.forEach(file => {
                    message += `  • ${file.original_name}\n`;
                });
            }
            
            if (response.total_errors > 0) {
                message += `\n❌ Failed to upload ${response.total_errors} file(s):\n`;
                response.errors.forEach(error => {
                    message += `  • ${error.filename}: ${error.error}\n`;
                });
            }
            
            alert(message);
        }
        
        function loadFiles() {
            fetch('/files')
                .then(response => response.json())
                .then(files => {
                    const fileList = document.getElementById('fileList');
                    fileList.innerHTML = '';
                    
                    if (files.length === 0) {
                        fileList.innerHTML = '<p>No files shared yet</p>';
                        return;
                    }
                    
                    files.forEach(file => {
                        const fileItem = document.createElement('div');
                        fileItem.className = 'file-item';
                        
                        let preview = '';
                        if (file.is_image) {
                            preview = `<img src="/preview/${file.name}" alt="${file.name}" class="file-preview" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">`;
                            preview += `<div class="file-icon-large" style="display:none;">${file.icon}</div>`;
                        } else {
                            preview = `<div class="file-icon-large">${file.icon}</div>`;
                        }
                        
                        fileItem.innerHTML = `
                            <div class="file-info">
                                ${preview}
                                <span class="file-name">${file.name}</span>
                            </div>
                            <a href="/download/${file.name}" class="btn" download>
                                Download
                            </a>
                        `;
                        fileList.appendChild(fileItem);
                    });
                });
        }
        
        // Load files on page load
        loadFiles();
        
        // Refresh file list every 5 seconds
        setInterval(loadFiles, 5000);
    </script>
</body>
</html>
'''

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def is_image_file(filename):
    """Check if file is an image based on extension"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico'}
    return ext in image_extensions

def get_file_icon(filename):
    """Get emoji icon based on file type"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    icon_map = {
        # Images
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'bmp': '🖼️', 'webp': '🖼️',
        # Videos
        'mp4': '🎥', 'avi': '🎥', 'mov': '🎥', 'wmv': '🎥', 'flv': '🎥',
        # Audio
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵', 'aac': '🎵',
        # Documents
        'pdf': '📄', 'doc': '📝', 'docx': '📝', 'txt': '📝', 'xls': '📊', 
        'xlsx': '📊', 'ppt': '📊', 'pptx': '📊',
        # Archives
        'zip': '🗜️', 'rar': '🗜️', '7z': '🗜️', 'tar': '🗜️', 'gz': '🗜️',
    }
    
    return icon_map.get(ext, '📎')

@app.route('/')
def index():
    local_ip = get_local_ip()
    port = 5000
    url = f"http://{local_ip}:{port}"
    return render_template_string(HTML_TEMPLATE, url=url)

@app.route('/qrcode')
def generate_qr():
    """Generate QR code for easy connection"""
    local_ip = get_local_ip()
    port = 5000
    url = f"http://{local_ip}:{port}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return send_file(buffer, mimetype='image/png')

@app.route('/preview/<filename>')
def preview_file(filename):
    """Serve image files for preview"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path) and is_image_file(filename):
            return send_file(file_path, mimetype=mimetypes.guess_type(filename)[0])
        else:
            return "File not found or not an image", 404
    except:
        return "Error loading image", 500

@app.route('/upload', methods=['POST'])
def upload_file():
    # Handle both single and multiple file uploads
    files = request.files.getlist('file') if 'file' in request.files else []
    
    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    uploaded_files = []
    errors = []
    
    for file in files:
        if file.filename == '':
            errors.append({'filename': 'unknown', 'error': 'No filename provided'})
            continue
            
        try:
            filename = secure_filename(file.filename)
            # Handle duplicate filenames
            base, ext = os.path.splitext(filename)
            counter = 1
            original_filename = filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
                filename = f"{base}_{counter}{ext}"
                counter += 1
            
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            uploaded_files.append({
                'original_name': original_filename,
                'saved_name': filename,
                'success': True
            })
        except Exception as e:
            errors.append({
                'filename': file.filename,
                'error': str(e)
            })
    
    # Return results
    response_data = {
        'uploaded_files': uploaded_files,
        'total_uploaded': len(uploaded_files),
        'total_errors': len(errors)
    }
    
    if errors:
        response_data['errors'] = errors
    
    # Return success if at least one file was uploaded
    if uploaded_files:
        return jsonify(response_data), 200
    else:
        return jsonify({'error': 'No files could be uploaded', 'details': errors}), 400

@app.route('/upload/batch', methods=['POST'])
def upload_batch():
    """Handle multiple file uploads in a single request"""
    files = request.files.getlist('files')  # Note: using 'files' for batch uploads
    
    if not files:
        return jsonify({'error': 'No files provided for batch upload'}), 400
    
    uploaded_files = []
    errors = []
    
    for file in files:
        if file.filename == '':
            continue
            
        try:
            # Get file size before saving
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            filename = secure_filename(file.filename)
            # Handle duplicate filenames
            base, ext = os.path.splitext(filename)
            counter = 1
            original_filename = filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
                filename = f"{base}_{counter}{ext}"
                counter += 1
            
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            uploaded_files.append({
                'original_name': original_filename,
                'saved_name': filename,
                'size': file_size,
                'success': True
            })
        except Exception as e:
            errors.append({
                'filename': file.filename,
                'error': str(e)
            })
    
    return jsonify({
        'success': True,
        'uploaded_files': uploaded_files,
        'total_uploaded': len(uploaded_files),
        'total_errors': len(errors),
        'errors': errors if errors else None
    })

@app.route('/files')
def list_files():
    """List all shared files"""
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            files.append({
                'name': filename,
                'icon': get_file_icon(filename),
                'is_image': is_image_file(filename)
            })
    return jsonify(files)

@app.route('/download/<filename>')
def download_file(filename):
    """Download a shared file"""
    try:
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            as_attachment=True,
            download_name=filename
        )
    except:
        return "File not found", 404

if __name__ == '__main__':
    local_ip = get_local_ip()
    print(f"\nFile Share Server Started!")
    print(f"Access from any device on the same network:")
    print(f"   http://{local_ip}:5000")
    print(f"   http://localhost:5000")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Run the server
    app.run(host='0.0.0.0', port=5000, debug=False)