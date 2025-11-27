import pymysql
from app import app
from config import mysql
from flask import jsonify, render_template, redirect, session, make_response
from flask import flash, request, json, send_file
from flask_cors import cross_origin
from PIL import Image
import base64
import numpy as np
import cv2
from functools import wraps
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from pyzbar.pyzbar import decode
import os

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def home():
    return "Hello, Flask Server is running!"


@app.route('/scan', methods=['POST'])
def receive_pin():
    data = request.get_json()
    pin = data.get('pin')

    # Simply print to terminal
    print(f"PIN Entered: {pin}")

    return "PIN Received!"


@app.route('/scan2', methods=['POST'])
def Plastrack_Detect_and_Tally():
    try:
        if request.method == 'POST':
            # Get JSON data from request
            data = request.get_json()

            if not data:
                return jsonify({"error": "No JSON data provided"}), 400

            # Extract image from JSON
            base64_image = data.get('image')

            if not base64_image:
                return jsonify({"error": "Image is required"}), 400

            # Process base64 image
            if ',' in base64_image:
                base64_image = base64_image.split(',')[1]

            # Decode base64 to image bytes (this is your hardware data)
            image_bytes = base64.b64decode(base64_image)

            print(f"✅ Image bytes received: {len(image_bytes)} bytes")

            # Convert image_bytes directly to OpenCV image
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                return jsonify({"error": "Failed to decode image"}), 400

            print(f"✅ Image decoded successfully")
            print(f"📏 Image dimensions: {img.shape}")

            # Load the model and process the image
            proto_txt_path = "Models/MobileNetSSD_deploy.prototxt"
            model_path = "Models/MobileNetSSD_deploy.caffemodel"
            min_confidence = 0.75

            classes = ["background", "aeroplane", "bicycle", "bird", "boat",
                       "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
                       "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
                       "sofa", "train", "tvmonitor"]

            net = cv2.dnn.readNetFromCaffe(proto_txt_path, model_path)

            height, width = img.shape[0], img.shape[1]
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007, (300, 300), 130)

            net.setInput(blob)
            detected_objects = net.forward()

            bottle_detected = False
            highest_confidence = 0
            detected_objects_list = []
            highest_class = "none"  # Initialize with default value

            for i in range(detected_objects.shape[2]):
                confidence = detected_objects[0][0][i][2]
                class_index = int(detected_objects[0, 0, i, 1])

                # Track all detected objects for debugging
                if confidence > min_confidence:
                    detected_objects_list.append({
                        "class": classes[class_index],
                        "confidence": float(confidence)
                    })

                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        highest_class = classes[class_index]

                    # Check if the detected object is a bottle (class index 5)
                    if classes[class_index] == "bottle":
                        bottle_detected = True

                        # Draw bounding box on the image
                        upper_left_x = int(detected_objects[0, 0, i, 3] * width)
                        upper_left_y = int(detected_objects[0, 0, i, 4] * height)
                        lower_right_x = int(detected_objects[0, 0, i, 5] * width)
                        lower_right_y = int(detected_objects[0, 0, i, 6] * height)

                        prediction_text = f"{classes[class_index]}: {confidence:.2f}%"
                        cv2.rectangle(img, (upper_left_x, upper_left_y), (lower_right_x, lower_right_y), (0, 255, 0), 3)
                        cv2.putText(img, prediction_text, (upper_left_x,
                                                           upper_left_y - 15 if upper_left_y > 30 else upper_left_y + 15),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                        print('✅ Scan Successful - Bottle Detected')
                        print(f"📊 Confidence: {confidence:.2f}")

                        return jsonify({
                            "status": "success",
                            "message": "Bottle Detected",
                            "confidence": float(confidence),
                            "objects_detected": detected_objects_list
                        }), 200

            if not bottle_detected:
                print(f'❌ Scan Failed - No bottle detected')
                print(f'📊 Highest detection: {highest_class} with {highest_confidence:.2f} confidence')
                print(f'📋 All detected objects: {detected_objects_list}')

                return jsonify({
                    "status": "error",
                    "message": "Unable to detect bottle",
                    "highest_detection": highest_class,
                    "highest_confidence": float(highest_confidence),
                    "all_detections": detected_objects_list
                }), 400

    except Exception as e:
        print(f"❌ Error processing request: {str(e)}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# Optional: Route to view latest images
@app.route('/images', methods=['GET'])
def list_images():
    """List all saved ESP32-CAM images"""
    try:
        images = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith('esp32_cam_') and filename.lower().endswith(('.jpg', '.jpeg')):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                images.append({
                    "filename": filename,
                    "size": os.path.getsize(filepath),
                })

        # Sort by newest first
        images.sort(key=lambda x: x['created'], reverse=True)
        return jsonify({"esp32_cam_images": images})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("🚀 Flask Server Running - Ready for ESP32-CAM")
    print("📍 PIN endpoint: POST http://192.168.1.7:8080/pin")
    print("🖼️  Image endpoint: POST http://192.168.1.7:8080/image")
    print("📁 Upload folder:", os.path.abspath(UPLOAD_FOLDER))
    print("-" * 50)

    app.run(debug=True, host='0.0.0.0', port=8080)