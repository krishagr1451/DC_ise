#!/usr/bin/env python3
import os
import io
import json
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import mimetypes

# --- Configuration ---
UPLOAD_FOLDER = Path('./gallery_images')
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 50 * 1024 * 1024 # 50MB

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_image_info(filepath: Path):
    """Get basic image info."""
    stat = filepath.stat()
    mime_type = mimetypes.guess_type(str(filepath))[0] or 'image/unknown'
    return {
        'filename': filepath.name,
        'size_bytes': stat.st_size,
        'upload_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'mime_type': mime_type
    }

def list_images():
    """List all images in the upload folder."""
    images = []
    if UPLOAD_FOLDER.exists():
        for file_path in UPLOAD_FOLDER.iterdir():
            if file_path.is_file() and allowed_file(file_path.name):
                images.append(get_image_info(file_path))
    # Sort by upload time, newest first
    images.sort(key=lambda x: x['upload_time'], reverse=True)
    return images

# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Image Gallery</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- SimpleLightbox CSS -->
    <link href="https://cdn.jsdelivr.net/npm/simplelightbox@2.14.2/dist/simple-lightbox.min.css" rel="stylesheet">

    <style>
        body {
            padding-top: 20px;
            background-color: #f8f9fa;
        }
        .gallery-title {
            text-align: center;
            margin-bottom: 30px;
            color: #495057;
        }
        .upload-section {
            background-color: #fff;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
            margin-bottom: 30px;
        }
        .gallery-section {
            background-color: #fff;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            padding: 0;
        }
        .gallery-item {
            border: 1px solid #dee2e6;
            border-radius: 5px;
            overflow: hidden;
            background-color: #fff;
            transition: transform 0.2s;
        }
        .gallery-item:hover {
            transform: scale(1.02);
            box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
        }
        .gallery-img-link {
             display: block;
             height: 200px; /* Fixed height for consistency */
             overflow: hidden;
             background-color: #e9ecef; /* Placeholder background */
        }
        .gallery-img {
            width: 100%;
            height: 100%;
            object-fit: cover; /* Cover the area, crop if necessary */
            transition: opacity 0.3s;
        }
        .gallery-img:hover {
            opacity: 0.9;
        }
        .gallery-caption {
            padding: 10px;
            font-size: 0.85rem;
        }
        .gallery-caption .text-muted {
            font-size: 0.75rem;
        }
        .delete-btn {
            position: absolute;
            top: 5px;
            right: 5px;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .gallery-item:hover .delete-btn {
            opacity: 1;
        }
        .status-message {
            margin-top: 15px;
        }
        footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="gallery-title my-4">My Simple Image Gallery</h1>

        <div class="upload-section mb-4">
            <h3>Upload New Image</h3>
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="mb-3">
                    <input class="form-control" type="file" id="fileInput" name="file" accept="image/*" required>
                    <div class="form-text">Supported formats: JPG, PNG, GIF, WEBP. Max size: 50MB.</div>
                </div>
                <button type="submit" class="btn btn-primary">Upload</button>
            </form>
            <div id="uploadStatus" class="status-message"></div>
        </div>

        <div class="gallery-section">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h3>Gallery</h3>
                <button id="refreshBtn" class="btn btn-outline-secondary btn-sm">Refresh</button>
            </div>
            <div id="galleryContainer">
                <!-- Gallery items will be loaded here -->
            </div>
        </div>

        <footer class="mt-5 pt-4 border-top">
            <p class="mb-0">&copy; 2023 Simple Image Gallery</p>
        </footer>
    </div>

    <!-- Bootstrap 5 JS Bundle with Popper -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <!-- SimpleLightbox JS -->
    <script src="https://cdn.jsdelivr.net/npm/simplelightbox@2.14.2/dist/simple-lightbox.min.js"></script>
    <script>
        // --- Utility Functions ---
        function formatBytes(bytes, decimals = 2) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const dm = decimals < 0 ? 0 : decimals;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        }

        function formatDate(isoString) {
            const date = new Date(isoString);
            return date.toLocaleString(); // Adjust locale as needed
        }

        // --- UI Update Functions ---
        function showStatus(message, isError = false) {
            const statusDiv = document.getElementById('uploadStatus');
            statusDiv.innerHTML = `<div class="alert alert-${isError ? 'danger' : 'success'} alert-dismissible fade show" role="alert">
                                        ${message}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                                   </div>`;
            // Auto-hide after 5 seconds
            setTimeout(() => {
                 const alert = bootstrap.Alert.getOrCreateInstance(statusDiv.querySelector('.alert'));
                 alert.close();
            }, 5000);
        }

        async function loadGallery() {
            try {
                const response = await fetch('/api/images');
                const images = await response.json();
                const container = document.getElementById('galleryContainer');
                container.innerHTML = '';

                if (images.length === 0) {
                    container.innerHTML = '<p class="text-muted text-center">No images uploaded yet.</p>';
                    return;
                }

                let html = '<div class="gallery">';
                images.forEach(img => {
                    // Use URL encoding for filenames in URLs
                    const encodedFilename = encodeURIComponent(img.filename);
                    html += `
                        <div class="gallery-item">
                            <a class="gallery-img-link" href="/images/${encodedFilename}" data-caption="${img.filename}">
                                <img class="gallery-img" src="/images/${encodedFilename}" alt="${img.filename}">
                            </a>
                            <div class="gallery-caption position-relative">
                                <strong>${img.filename}</strong><br>
                                <span class="text-muted">${formatBytes(img.size_bytes)} | ${formatDate(img.upload_time)}</span>
                                <button type="button" class="btn btn-danger btn-sm delete-btn" onclick="deleteImage('${encodedFilename}')">&times;</button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                container.innerHTML = html;

                // Initialize SimpleLightbox after adding images
                const gallery = new SimpleLightbox('.gallery a', {
                    captionsData: 'caption', // Use data-caption attribute
                    captionPosition: 'outside', // Position caption outside the image
                    // Add more options as needed
                });

            } catch (error) {
                console.error('Error loading gallery:', error);
                document.getElementById('galleryContainer').innerHTML = '<p class="text-danger">Failed to load images.</p>';
            }
        }

        // --- Event Handlers ---
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData();
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];

            if (!file) {
                showStatus('Please select a file.', true);
                return;
            }

            // Basic client-side check (server still validates)
            const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
            if (!allowedTypes.includes(file.type)) {
                 showStatus('Invalid file type. Please select an image (JPG, PNG, GIF, WEBP).', true);
                 return;
            }

            formData.append('file', file);

            try {
                showStatus('Uploading...');
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                if (response.ok) {
                    showStatus(`Image "${result.filename}" uploaded successfully!`);
                    fileInput.value = ''; // Clear input
                    loadGallery(); // Refresh gallery
                } else {
                    showStatus(`Upload failed: ${result.error}`, true);
                }
            } catch (error) {
                console.error('Upload error:', error);
                showStatus(`Upload failed: ${error.message}`, true);
            }
        });

        document.getElementById('refreshBtn').addEventListener('click', loadGallery);

        async function deleteImage(filename) {
            if (!confirm(`Are you sure you want to delete "${decodeURIComponent(filename)}"?`)) {
                return;
            }
            try {
                const response = await fetch(`/api/delete/${filename}`, {
                    method: 'DELETE'
                });
                const result = await response.json();
                if (response.ok) {
                    showStatus(`Image deleted successfully.`);
                    loadGallery(); // Refresh gallery
                } else {
                    showStatus(`Delete failed: ${result.error}`, true);
                }
            } catch (error) {
                console.error('Delete error:', error);
                showStatus(`Delete failed: ${error.message}`, true);
            }
        }

        // --- Initial Load ---
        window.addEventListener('load', () => {
            loadGallery();
        });
    </script>
</body>
</html>
"""

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Handle potential filename conflicts by appending a counter
            original_filepath = app.config['UPLOAD_FOLDER'] / filename
            counter = 1
            filepath = original_filepath
            stem = filepath.stem
            suffix = filepath.suffix
            while filepath.exists():
                new_filename = f"{stem}_{counter}{suffix}"
                filepath = app.config['UPLOAD_FOLDER'] / new_filename
                counter += 1

            file.save(filepath)
            return jsonify({'message': 'File uploaded successfully', 'filename': filepath.name}), 201
        else:
            return jsonify({'error': 'File type not allowed'}), 400
    except Exception as e:
        # Log the error for debugging server-side
        print(f"Error during upload: {e}")
        return jsonify({'error': 'An internal server error occurred'}), 500

@app.route('/images/<filename>')
def uploaded_file(filename):
    try:
        # Security: Ensure filename is secure and file exists
        filename = secure_filename(filename)
        filepath = app.config['UPLOAD_FOLDER'] / filename
        if filepath.exists() and filepath.is_file() and allowed_file(filename):
            # Guess MIME type for correct Content-Type header
            mime_type = mimetypes.guess_type(str(filepath))[0] or 'application/octet-stream'
            return send_file(filepath, mimetype=mime_type)
        else:
            # Return a placeholder or 404 if not found/allowed
            return "Image not found", 404
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return "Error retrieving image", 500

@app.route('/api/images')
def list_images_api():
    try:
        return jsonify(list_images())
    except Exception as e:
        print(f"Error listing images: {e}")
        return jsonify({'error': 'Failed to retrieve image list'}), 500

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        filename = secure_filename(filename) # Sanitize filename
        filepath = app.config['UPLOAD_FOLDER'] / filename
        if filepath.exists() and filepath.is_file():
            filepath.unlink() # Delete the file
            return jsonify({'message': 'Image deleted successfully'}), 200
        else:
            return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        print(f"Error deleting file {filename}: {e}")
        return jsonify({'error': 'An internal server error occurred'}), 500

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Simple Image Gallery...")
    print("Web interface available at: http://localhost:5000")
    print("Images will be stored in: ./gallery_images")
    app.run(debug=True, host='0.0.0.0', port=5000)
