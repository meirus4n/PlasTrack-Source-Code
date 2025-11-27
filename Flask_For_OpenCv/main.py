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
# --------------------------------------------------------- USER ROUTES ---------------------------------------------------------
def log_activity(user_id, activity_type, description):
    """Helper function to log activities"""
    try:
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activities (U_ID, activity_type, activity_description) VALUES (%s, %s, %s)",
            (user_id, activity_type, description)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error logging activity: {str(e)}")
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('LoggedIn'):
            return redirect('/')
        response = make_response(view_func(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return wrapper


@app.route('/', methods=['GET'])
def Plastrack_Start_Up_Page():
    if request.method == 'GET':
        return render_template('plastrack_startup_page.html')
    else:
        pass


@app.route('/capstone/login', methods=['GET', 'POST'])
def Plastrack_Login():
    if request.method == 'GET':
        return render_template('plastrack_login.html')

    elif request.method == 'POST':
        Form = request.form
        Username = Form['Username']
        Password = Form['Password']
        # Role = Form['U_Role']

        if Username and Password:
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute('SELECT * FROM `users` WHERE Username = %s', Username)
            results = cursor.fetchone()

            if results and results['Password'] == Password:
                session['LoggedIn'] = True
                session['Username'] = results['Username']
                session['Password'] = results['Password']
                session['U_Role'] = results['U_Role']

                role_name = "SuperAdmin" if results['U_Role'] == 2 else "Admin" if results['U_Role'] == 1 else "User"
                log_activity(results['U_ID'], 'login', f'{role_name} {results["Username"]} logged in')

                if results['U_Role'] == 1:  # Check if U_Role column is 1, if true, then login as admin
                    return redirect(f'/capstone/admin/dashboard')
                elif results['U_Role'] == 2:
                    return redirect('/capstone/superadmin/dashboard')
                else:
                    return redirect(f'/capstone/homescreen/{results["U_ID"]}')
            else:
                # Flash error message for invalid credentials
                flash('Invalid username or password. Please try again.')
                return redirect('/capstone/login')

        # If we get here, something went wrong
        flash('Please fill in all fields.')
        return redirect('/capstone/login')



#<int:ID> has to be the same in the corresponding function
# Example <int:ID> has to have a corresponding ID parameter in verbatim or else it will result in an error

@app.route('/capstone/homescreen/<int:ID>', methods=['GET'])
@login_required
def Plastrack_Homescreen(ID):
    print("You are now in the Home Page with the ID: ", ID)
    if 'LoggedIn' in session:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Show Product Table
        cursor.execute("SELECT P_Name, P_Price, P_QTY FROM `product`")
        results1 = cursor.fetchall()

        # Show Score from total_tally Table
        cursor.execute("SELECT SUM(Score) as Score FROM `total_tally` WHERE U_ID =%s", (ID,))
        results2 = cursor.fetchone()

        # Show Score from running_tally Table
        cursor.execute("""
            SELECT SUM(Score) AS Score 
            FROM running_tally 
            WHERE U_ID = %s 
            ORDER BY From_date DESC 
        """, (ID,))
        results3 = cursor.fetchone()

        # Show First and Last name form users Table
        cursor.execute("SELECT U_Fname FROM `users` WHERE U_ID =%s", ID)
        results4 = cursor.fetchone()

        # Fetch notifications from postings table
        cursor.execute("SELECT * FROM `postings` ORDER BY Post_timestamp DESC LIMIT 5")
        notifications = cursor.fetchall()

        notification_count = len(notifications)

        return render_template('plastrack_home.html',
                               products=results1, total_tally=results2, running_tally=results3,
                               user_info=results4, user_id=ID, notifications=notifications,
                               notification_count=notification_count)
    else:
        return redirect('/')


@app.route('/capstone/logout', methods=['GET'])
def Plastrack_Logout():
    if session.get('LoggedIn'):
        role_name = "SuperAdmin" if session.get('U_Role') == 2 else "Admin" if session.get('U_Role') == 1 else "User"
        log_activity(session.get('U_ID'), 'logout', f'{role_name} {session.get("Username")} logged out')

    session.clear()
    response = make_response(redirect('/capstone/login'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/capstone/registration', methods=['GET', 'POST'])
def Plastrack_Registration():
    if request.method == 'GET':
        return render_template('plastrack_registration.html')

    elif request.method == 'POST':
        Form = request.form
        First_Name = Form['U_Fname']
        Last_Name = Form['U_Lname']
        Username = Form['Username']
        Password = Form['Password']
        #Role = Form['U_Role']

        if First_Name and Last_Name and Username and Password:
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            sqlQuery = ("INSERT INTO users (`U_Fname`, `U_Lname`, `Username`, `Password`) VALUES (%s, %s, %s, %s)")
            bindData = (First_Name, Last_Name, Username, Password)
            cursor.execute(sqlQuery, bindData)
            conn.commit()

            # Get the new user's ID
            cursor.execute("SELECT U_ID FROM users WHERE Username = %s", (Username,))
            new_user = cursor.fetchone()

            # Log registration activity
            if new_user:
                log_activity(new_user['U_ID'], 'registration', f'New user {Username} registered')


            response = jsonify(Username + 'has been added')
            response.status_code = 200
            return redirect('/capstone/login')
    else:
        return redirect('/')


@app.route('/capstone/about_us/<int:ID>', methods=['GET'])
@login_required
def Plastrack_About_Us(ID):
    if 'LoggedIn' in session:
        if request.method == 'GET':
            print("You are now in the About page with the ID:", ID)
            return render_template('plastrack_about_us.html', user_id=ID)
        else:
            return redirect(f'/capstone/homescreen/{ID}')
    else:
        return redirect('/')


@app.route('/capstone/profile/<int:ID>', methods=['GET', 'POST'])
@login_required
def Plastrack_Profile(ID):
    if 'LoggedIn' in session:
        if request.method == 'GET':
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM `users` WHERE U_ID = %s", ID)
            results = cursor.fetchall()
            qr_data = str(results[0]['U_ID']) + " & " + str(results[0]['Username'])

            cursor.execute("""SELECT ph.*, p.P_Name, (p.P_Price * ph.Quantity) AS TotalPointsUsed FROM purchase_history ph JOIN product p ON ph.P_ID = p.P_ID WHERE ph.U_ID = %s ORDER BY ph.Date_Purchased DESC""", ID)
            history = cursor.fetchall()

            # Fetch notifications from postings table
            cursor.execute("SELECT * FROM `postings` ORDER BY Post_timestamp DESC LIMIT 5")
            notifications = cursor.fetchall()

            notification_count = len(notifications)

            return render_template('plastrack_profile.html', user_info=results, user_id=ID,
                                   qr_data=qr_data, purchase_history=history,
                                   notifications=notifications, notification_count=notification_count)
        elif request.method == 'POST':
            Form = request.form
            First_Name = Form['U_Fname']
            Last_Name = Form['U_Lname']
            Username = Form['Username']
            Password = Form['Password']
            if First_Name and Last_Name and Username and Password and ID:
                sqlQuery = "UPDATE users SET U_Fname=%s, U_Lname=%s, Username=%s, Password=%s WHERE U_ID=%s"
                bindData = (First_Name, Last_Name, Username, Password, ID)
                conn = mysql.connect()
                cursor = conn.cursor()
                cursor.execute(sqlQuery, bindData)
                conn.commit()

                # Log profile update activity
                log_activity(ID, 'profile_update', f'User updated profile information')

                flash('Profile updated successfully!', 'success')
                return redirect(f'/capstone/profile/{ID}')
        else:
            return redirect('/')



@login_required
@app.route('/capstone/notifications/<int:ID>', methods=['GET'])
def Plastrack_Check_Notifications(ID):
    if 'LoggedIn' in session:
        if request.method == 'GET':
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute('SELECT * FROM `postings`')
            results = cursor.fetchall()
            return render_template('plastrack_user_notifications.html', notification=results, user_id=ID)
        else:
            pass
    else:
        return redirect('/capstone/login')


# Global variables to track PIN verification state
verified_pin = None
user_id = None
conn = None
cursor = None

@app.route('/scan', methods=['POST'])
def Plastrack_Detect_and_Tally():
    global verified_pin, user_id, conn, cursor

    try:
        if request.method == 'POST':
            # Get JSON data from request
            data = request.get_json()

            if not data:
                return jsonify({"error": "No JSON data provided"}), 401

            # Extract PIN and image from JSON
            input_PIN = data.get('pin')
            base64_image = data.get('image')

            # STEP 1: PIN VERIFICATION (always check this first)
            if input_PIN:
                print(f'🔐 PIN Entered: {input_PIN}')

                # Verify PIN in database
                conn = mysql.connect()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute("SELECT U_ID, U_PIN FROM users WHERE U_PIN = %s", (input_PIN,))
                existing_user = cursor.fetchone()

                if not existing_user:
                    print('❌ Invalid PIN - not found in database')
                    return jsonify({"error": "Invalid PIN"}), 401

                print(f'✅ PIN Verified - Existing Pin in Database: {existing_user["U_PIN"]}')
                user_id = existing_user['U_ID']
                verified_pin = input_PIN

                # Close database connection for now
                cursor.close()
                conn.close()

                # If only PIN was sent (no image), return success
                if not base64_image:
                    return jsonify({
                        "status": "success",
                        "message": "PIN verified successfully. You can now send image for scanning.",
                        "user_id": user_id
                    }), 200

            # STEP 2: CHECK IF PIN WAS ALREADY VERIFIED
            if verified_pin is None:
                return jsonify({"error": "Please enter PIN first"}), 401

            # STEP 3: ONLY RUN SCANNER IF PIN IS VERIFIED AND IMAGE IS PROVIDED
            if verified_pin and base64_image:
                print(f'🔄 Running scanner for verified PIN: {verified_pin}')

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
                    return jsonify({"error": "Failed to decode image"}), 401

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

                # Reconnect to database for inserting tally
                conn = mysql.connect()
                cursor = conn.cursor()

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

                            # Insert into database
                            Score = 1
                            sqlQuery = "INSERT INTO running_tally (U_ID, Score) VALUES (%s, %s)"
                            bindData = (user_id, Score)
                            cursor.execute(sqlQuery, bindData)
                            conn.commit()

                            # ✅ ACTIVITY LOGGING ADDED - RIGHT AFTER POINTS ARE AWARDED
                            log_activity(user_id, 'bottle_scan', f'User scanned a bottle and earned 1 point')

                            # Draw bounding box on the image
                            upper_left_x = int(detected_objects[0, 0, i, 3] * width)
                            upper_left_y = int(detected_objects[0, 0, i, 4] * height)
                            lower_right_x = int(detected_objects[0, 0, i, 5] * width)
                            lower_right_y = int(detected_objects[0, 0, i, 6] * height)

                            prediction_text = f"{classes[class_index]}: {confidence:.2f}%"
                            cv2.rectangle(img, (upper_left_x, upper_left_y), (lower_right_x, lower_right_y),
                                          (0, 255, 0), 3)
                            cv2.putText(img, prediction_text, (upper_left_x,
                                                               upper_left_y - 15 if upper_left_y > 30 else upper_left_y + 15),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                            print('✅ Scan Successful - Bottle Detected')
                            print(f"📊 Confidence: {confidence:.2f}")

                            # Reset PIN after successful scan
                            verified_pin = None
                            user_id = None

                            return jsonify({
                                "status": "success",
                                "message": "Bottle Detected",
                                "confidence": float(confidence),
                                "user_id": user_id,
                                "objects_detected": detected_objects_list
                            }), 200

                if not bottle_detected:
                    print(f'❌ Scan Failed - No bottle detected')
                    print(f'📊 Highest detection: {highest_class} with {highest_confidence:.2f} confidence')
                    print(f'📋 All detected objects: {detected_objects_list}')

                    # Reset PIN even if no bottle detected
                    verified_pin = None
                    user_id = None

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
    finally:
        # Ensure database connections are closed
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()



@app.route('/capstone/redeem_product/<int:user_id>', methods=['POST'])
def Plastrack_Redeem_Product(user_id):
    if request.method == 'POST':
        print("=== FORM DATA RECEIVED ===")
        print(dict(request.form))
        print(f"User ID from URL: {user_id}")

        # Get form data
        product_name = request.form.get('P_Name', '').strip()
        quantity = request.form.get('Quantity', '').strip()

        print(f"Product Name: '{product_name}', Quantity: '{quantity}'")

        # Validate inputs
        if not product_name or not quantity:
            flash('Product name and quantity are required', 'error')
            return redirect(f'/capstone/homescreen/{user_id}')

        try:
            quantity = int(quantity)
            if quantity <= 0:
                flash('Quantity must be a positive number', 'error')
                return redirect(f'/capstone/homescreen/{user_id}')
        except ValueError:
            flash('Quantity must be a valid number', 'error')
            return redirect(f'/capstone/homescreen/{user_id}')

        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        try:
            # Step 1: Get the specific product by name
            sql_check_stock = """
                SELECT P_ID, P_QTY, P_Name, P_Price 
                FROM product 
                WHERE P_Name = %s
            """
            cursor.execute(sql_check_stock, (product_name,))
            product = cursor.fetchone()

            if not product:
                flash('Product not found', 'error')
                return redirect(f'/capstone/homescreen/{user_id}')

            if product['P_QTY'] < quantity:
                flash(f'Not enough stock for {product_name}. Only {product["P_QTY"]} available.', 'error')
                return redirect(f'/capstone/homescreen/{user_id}')

            print(f"Selected product: {product['P_Name']} | Stock: {product['P_QTY']} | Price: {product['P_Price']}")

            # Step 2: Get user's current score
            sql_check_points = """
                SELECT Score 
                FROM total_tally 
                WHERE U_ID = %s 
                ORDER BY U_ID 
            """
            cursor.execute(sql_check_points, (user_id,))
            user_points = cursor.fetchone()

            if not user_points:
                flash('User points not found', 'error')
                return redirect(f'/capstone/homescreen/{user_id}')

            current_points = user_points['Score']
            total_cost = product['P_Price'] * quantity

            print(f"User points: {current_points} | Total cost: {total_cost}")

            if current_points < total_cost:
                flash(f'Insufficient points. You have {current_points} but need {total_cost}.', 'error')
                return redirect(f'/capstone/homescreen/{user_id}')

            # Step 3: Record purchase
            sql_insert = """
                INSERT INTO purchase_history (U_ID, P_ID, Quantity) 
                VALUES (%s, %s, %s)
            """
            cursor.execute(sql_insert, (user_id, product['P_ID'], quantity))
            print("Purchase recorded in purchase_history")

            # Step 4: Update product stock
            sql_update_product = "UPDATE product SET P_QTY = P_QTY - %s WHERE P_ID = %s"
            cursor.execute(sql_update_product, (quantity, product['P_ID']))
            print("Product stock updated")

            # Step 5: Deduct user points
            new_score = current_points - total_cost
            sql_update_points = """
                UPDATE total_tally
                SET Score = %s
                WHERE U_ID = %s
                ORDER BY U_ID
            """
            cursor.execute(sql_update_points, (new_score, user_id))
            print(f"User points updated to: {new_score}")

            # Log purchase activity
            log_activity(user_id, 'purchase', f'User purchased {quantity} {product_name} for {total_cost} TOTAL points')

            conn.commit()
            cursor.close()
            conn.close()

            print("=== Redeem Process Complete ===")
            flash(f'Successfully redeemed {quantity} {product_name}(s)!', 'success')
            return redirect(f'/capstone/homescreen/{user_id}')

        except Exception as e:
            conn.rollback()
            print(f"Database error: {str(e)}")
            flash(f'Database error: {str(e)}', 'error')
            return redirect(f'/capstone/homescreen/{user_id}')

    else:
        flash('Invalid request method', 'error')
        return redirect(f'/capstone/homescreen/{user_id}')



# --------------------------------------------------------- ADMIN ROUTES ---------------------------------------------------------

@app.route('/capstone/admin/dashboard', methods=['GET'])
@login_required
def Plastrack_Admin_Dashboard():
    if 'LoggedIn' in session:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Query for user management table
        cursor.execute("""
            SELECT 
                u.U_ID,
                u.U_Fname,
                u.U_Lname,
                u.Username,
                u.U_Status,
                u.Approved,
                COALESCE(tt.Score, 0) AS Total_Score,
                COALESCE((
                    SELECT SUM(Score) AS Score 
                    FROM running_tally 
                    WHERE U_ID = u.U_ID 
                    ORDER BY U_ID DESC 
                ), 0) AS Weekly_Score
            FROM users u
            LEFT JOIN total_tally tt ON u.U_ID = tt.U_ID
            WHERE u.U_Role = 0
            ORDER BY u.U_ID ASC
        """)
        results = cursor.fetchall()

        # Query for purchase history
        cursor.execute("""
            SELECT ph.Purchase_ID, ph.U_ID, u.U_Fname, u.U_Lname, u.Username,
                   p.P_Name as Product_Name, p.P_Price, ph.Quantity, (p.P_Price * ph.Quantity) AS Points_Used,
                   ph.Date_Purchased
            FROM purchase_history ph
            JOIN users u ON ph.U_ID = u.U_ID
            JOIN product p ON ph.P_ID = p.P_ID
            ORDER BY ph.Date_Purchased DESC
        """)
        all_purchase_history = cursor.fetchall()

        return render_template('admin_dashboard.html',
                               users_table=results,
                               all_purchase_history=all_purchase_history)



@app.route('/capstone/admin/reset_score', methods=['POST', 'GET'])
def Plastack_Admin_Correct_Points():
    if 'LoggedIn' in session:
        if request.method == 'POST':
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            try:
                # ADD IT RIGHT HERE - STEP 1: Ensure all users have total_tally records
                cursor.execute("""
                INSERT INTO total_tally (U_ID, Score, Purchase_total)
                SELECT u.U_ID, 0, 1 
                FROM users u
                LEFT JOIN total_tally tt ON u.U_ID = tt.U_ID
                WHERE tt.U_ID IS NULL AND u.U_Role = 0
                """)

                # Get ALL weekly scores for each user (we'll sum them)
                cursor.execute("""
                    SELECT U_ID, SUM(Score) as total_weekly_score
                    FROM running_tally 
                    WHERE U_ID IS NOT NULL
                    GROUP BY U_ID
                """)
                weekly_scores = cursor.fetchall()
                print("TOTAL WEEKLY SCORES TO ADD:", weekly_scores)

                # Add ALL weekly scores to total scores
                for user in weekly_scores:
                    cursor.execute("""
                        UPDATE total_tally 
                        SET Score = Score + %s 
                        WHERE U_ID = %s
                    """, (user['total_weekly_score'], user['U_ID']))

                # Reset ALL weekly scores to 0 (delete all and insert fresh)
                cursor.execute("DELETE FROM running_tally WHERE U_ID IS NOT NULL")

                # Insert fresh zero records for each user
                cursor.execute("SELECT DISTINCT U_ID FROM total_tally WHERE U_ID IS NOT NULL")
                users = cursor.fetchall()

                for user in users:
                    cursor.execute("""
                        INSERT INTO running_tally (U_ID, Score, From_date, To_date)
                        VALUES (%s, 0, NOW(), NULL)
                    """, (user['U_ID'],))

                conn.commit()
                flash('Scores reset successfully!', 'success')
                return redirect('/capstone/admin/dashboard')

            except Exception as Error:
                conn.rollback()
                flash(f'Error resetting scores: {Error}', 'error')
                return redirect('/capstone/admin/dashboard')
            finally:
                cursor.close()
                conn.close()
    else:
        return redirect('/')




@app.route('/capstone/admin/update_user/<int:ID>', methods=['GET', 'POST'])
def Plastrack_Admin_Update_User(ID):
    if 'LoggedIn' in session:
        if request.method == 'GET':
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM `users` WHERE U_ID =%s", ID)
            results = cursor.fetchall()
            # return render_template()

        elif request.method == 'POST':
            try:
                Form = request.form
                U_Status = int(Form['U_Status'])
                Approved = int(Form['Approved'])
                admin_id = session.get('U_ID')

                conn = mysql.connect()
                cursor = conn.cursor(pymysql.cursors.DictCursor)

                cursor.execute("SELECT U_Role, Username FROM users WHERE U_ID = %s", (ID,))
                user = cursor.fetchone()


                cursor.execute(
                    "UPDATE users SET U_Status=%s, Approved=%s WHERE U_ID=%s",
                    (U_Status, Approved, ID)
                )
                conn.commit()

                # Log user update activity
                status_text = "Active" if U_Status == 1 else "Inactive"
                approved_text = "Approved" if Approved == 1 else "Pending"
                log_activity(admin_id, 'user_management',
                             f'Admin updated user {user["Username"]}: Status={status_text}, Approval={approved_text}')

                flash('User updated successfully!', 'success')
                return redirect('/capstone/admin/dashboard')

            except Exception as e:
                if 'conn' in locals():
                    conn.rollback()
                flash(f'Error updating user: {str(e)}', 'error')
                return redirect('/capstone/admin/dashboard')
            finally:
                if 'conn' in locals():
                    cursor.close()
                    conn.close()


@login_required
@app.route('/capstone/admin/notifications', methods=['GET'])
def Plastrack_Admin_Check_Notifications():
    if 'LoggedIn' in session:
        if request.method == 'GET':
            conn = mysql.connect()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute('SELECT * FROM `postings`')
            results = cursor.fetchall()
            return render_template('plastrack_admin_postings_dashboard.html', notification=results)
        else:
            pass
    else:
        return redirect('/capstone/login')



@app.route('/capstone/admin/create_post', methods=['POST'])
def Plastrack_Admin_Create_Post():
    if 'LoggedIn' in session:
        if request.method == 'POST':
            try:
                Form = request.form
                U_ID = session.get('U_ID')
                Post_Title = Form['Post_Title']
                Post_Content = Form['Post_Content']

                if Post_Title and Post_Content:
                    #INSERT INTO postings table
                    conn = mysql.connect()
                    cursor = conn.cursor(pymysql.cursors.DictCursor)
                    sqlQuery = ("INSERT INTO postings (`Post_Title`, `Post_Content`) VALUES (%s, %s)")
                    bindData = (Post_Title, Post_Content)
                    cursor.execute(sqlQuery, bindData)
                    conn.commit()

                    # Log announcement creation
                    log_activity(U_ID, 'announcement', f'Admin created new announcement: {Post_Title}')

                    response = jsonify(f'New Announcement: {Post_Title}')
                    response.status_code = 200
                    return redirect('/capstone/admin/notifications')

                return ""

            except Exception as Error:
                print(Error)

    else:
        return redirect('/')



@app.route('/capstone/admin/update_post/<int:Post_ID>', methods=['POST'])
def Plastrack_Admin_Update_Post(Post_ID):
    if 'LoggedIn' in session:
        if request.method == 'POST':
            try:
                Form = request.form
                Post_Title = Form['Post_Title']
                Post_Content = Form['Post_Content']
                U_ID = session.get('U_ID')

                if Post_Title and Post_Content and Post_ID:
                    sqlQuery = "UPDATE postings SET Post_Title=%s, Post_Content=%s WHERE Post_ID=%s"
                    bindData = (Post_Title, Post_Content, Post_ID)
                    conn = mysql.connect()
                    cursor = conn.cursor()
                    cursor.execute(sqlQuery, bindData)
                    conn.commit()

                    # Log announcement update
                    log_activity(U_ID, 'announcement', f'Admin updated announcement: {Post_Title}')

                    response = jsonify(f'Post: {Post_Title} Updated!')
                    response.status_code = 200
                    return redirect('/capstone/admin/notifications')

            except Exception as Error:
                print(Error)

        else:
            pass


@app.route('/capstone/admin/delete_post/<int:Post_ID>', methods=['POST'])
def Platrack_Admin_Delete_Post(Post_ID):
    if 'LoggedIn' in session:
        if request.method == 'POST':
            try:
                U_ID = session.get('U_ID')
                conn = mysql.connect()
                cursor = conn.cursor()

                # Get post title before deletion for logging
                cursor.execute("SELECT Post_Title FROM postings WHERE Post_ID = %s", (Post_ID,))
                post = cursor.fetchone()

                # Log announcement deletion
                if post:
                    log_activity(U_ID, 'announcement', f'Admin deleted announcement: {post[0]}')

                cursor.execute("DELETE FROM postings WHERE Post_ID =%s", Post_ID)
                conn.commit()
                response = jsonify(f'Post: {Post_ID} deleted!')
                response.status_code = 200
                return redirect('/capstone/admin/notifications')
            except Exception as Error:
                print(Error)
    else:
        return redirect('/')

@login_required
@app.route('/capstone/admin/products_dashboard', methods=['GET'])
def Plastrack_Admin_Products_Dashboard():
    if 'LoggedIn' in session:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT * FROM product ORDER BY P_ID')
        results = cursor.fetchall()
        return render_template('plastrack_products_dashboard.html', products=results)
    else:
        return redirect('/capstone/login')




@app.route('/capstone/admin/create_product', methods=['POST'])
def Plastrack_Admin_Create_Product():
    if 'LoggedIn' in session:
        if request.method == 'POST':
            Form = request.form
            U_ID = session.get('U_ID')
            P_Name = Form['P_Name']
            P_Quantity = Form['P_QTY']
            P_Price = Form['P_Price']
            if P_Name and P_Quantity and P_Price:
                conn = mysql.connect()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                # P_ID is auto-increment, so we don't insert it manually
                sqlQuery = ('INSERT INTO product (P_Name, P_QTY, P_Price) VALUES (%s, %s, %s)')
                bindData = (P_Name, P_Quantity, P_Price)
                cursor.execute(sqlQuery, bindData)
                conn.commit()

                # Log product creation
                log_activity(U_ID, 'product_management',
                             f'Admin created new product: {P_Name} (Qty: {P_Quantity}, Price: {P_Price})')

                flash(f'New Product: {P_Name} Added!', 'success')
                return redirect('/capstone/admin/products_dashboard')
            else:
                flash('Please fill in all fields.', 'error')
                return redirect('/capstone/admin/products_dashboard')
        else:
            return redirect('/capstone/admin/products_dashboard')
    else:
        return redirect('/capstone/login')




@app.route('/capstone/admin/update_product/<int:P_ID>', methods=['POST'])
def Plastrack_Admin_Update_Product(P_ID):
    if 'LoggedIn' in session:
        if request.method == 'POST':
            Form = request.form
            U_ID = session.get('U_ID')
            P_Name = Form['P_Name']
            P_Quantity = Form['P_QTY']
            P_Price = Form['P_Price']
            if P_Name and P_Quantity and P_Price and P_ID:
                # FIXED: Changed from 'postings' to 'product' table
                sqlQuery = "UPDATE product SET P_Name=%s, P_QTY=%s, P_Price=%s WHERE P_ID=%s"
                bindData = (P_Name, P_Quantity, P_Price, P_ID)  # FIXED: Added P_ID
                conn = mysql.connect()
                cursor = conn.cursor()
                cursor.execute(sqlQuery, bindData)
                conn.commit()
                # Log product update
                log_activity(U_ID, 'product_management',
                             f'Admin updated product: {P_Name} (Qty: {P_Quantity}, Price: {P_Price})')

                flash(f'Product: {P_Name} Updated!', 'success')
                return redirect('/capstone/admin/products_dashboard')
            else:
                flash('Please fill in all fields.', 'error')
                return redirect('/capstone/admin/products_dashboard')
    else:
        return redirect('/capstone/login')




@app.route('/capstone/admin/delete_product/<int:P_ID>', methods=['POST'])
def Plastrack_Admin_Delete_Product(P_ID):
    if 'LoggedIn' in session:
        try:
            U_ID = session.get('U_ID')
            conn = mysql.connect()
            cursor = conn.cursor()

            # Get product name before deletion for logging
            cursor.execute("SELECT P_Name FROM product WHERE P_ID = %s", (P_ID,))
            product = cursor.fetchone()

            cursor.execute("DELETE FROM product WHERE P_ID=%s", (P_ID,))
            conn.commit()

            # Log product deletion
            if product:
                log_activity(U_ID, 'product_management', f'Admin deleted product: {product[0]}')

            flash('Product deleted successfully!', 'success')
            return redirect('/capstone/admin/products_dashboard')
        except Exception as Error:
            flash(f'Error deleting product: {str(Error)}', 'error')
            return redirect('/capstone/admin/products_dashboard')
    else:
        return redirect('/capstone/login')


# --------------------------------------------------------- SUPERADMIN ROUTES ---------------------------------------------------------

@app.route('/capstone/superadmin/dashboard', methods=['GET'])
@login_required
def Plastrack_SuperAdmin_Dashboard():
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # Get ALL users including admins and superadmins - FIXED QUERY
    cursor.execute("""
        SELECT 
            u.U_ID,
            u.U_Fname,
            u.U_Lname,
            u.Username,
            u.U_Status,
            u.Approved,
            u.U_Role,
            u.U_Date_Created,
            CASE 
                WHEN u.U_Role = 2 THEN 'SuperAdmin'
                WHEN u.U_Role = 1 THEN 'Admin' 
                ELSE 'User'
            END as Role_Name,
            COALESCE(tt.Score, 0) AS Total_Score,
            COALESCE((
                SELECT SUM(Score) AS Score 
                FROM running_tally 
                WHERE U_ID = u.U_ID 
            ), 0) AS Weekly_Score
        FROM users u
        LEFT JOIN total_tally tt ON u.U_ID = tt.U_ID
        ORDER BY u.U_Role DESC, u.U_Date_Created DESC
    """)
    all_users = cursor.fetchall()

    # Get system statistics (all users)
    cursor.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total_admins FROM users WHERE U_Role = 1")
    total_admins = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total_products FROM product")
    total_products = cursor.fetchone()

    cursor.execute("SELECT SUM(Score) as total_points FROM total_tally")
    total_points = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total_purchases FROM purchase_history")
    total_purchases = cursor.fetchone()

    # Get system settings
    cursor.execute("SELECT setting_name, setting_value FROM system_settings")
    settings_data = cursor.fetchall()

    # Convert settings to dictionary for easy access
    settings = {}
    for setting in settings_data:
        settings[setting['setting_name']] = setting['setting_value']

    # Get ALL activities from activities table - NO LIMIT
    cursor.execute("""
        SELECT 
            a.activity_type,
            a.activity_description,
            a.activity_timestamp as timestamp,
            u.Username,
            u.U_Fname,
            u.U_Lname,
            u.U_Role
        FROM activities a
        LEFT JOIN users u ON a.U_ID = u.U_ID
        ORDER BY a.activity_timestamp DESC
    """)
    recent_activities = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('superadmin_dashboard.html',
                           all_users=all_users,
                           total_users=total_users['total_users'],
                           total_admins=total_admins['total_admins'],
                           total_products=total_products['total_products'],
                           total_points=total_points['total_points'] or 0,
                           total_purchases=total_purchases['total_purchases'],
                           recent_activities=recent_activities,
                           settings=settings)


@app.route('/capstone/superadmin/edit_user_points/<int:user_id>', methods=['POST'])
@login_required
def Plastrack_SuperAdmin_Edit_User_Points(user_id):
    try:
        Form = request.form
        weekly_points = int(Form['weekly_points'])
        total_points = int(Form['total_points'])
        superadmin_id = session.get('U_ID')

        conn = mysql.connect()
        cursor = conn.cursor()

        # Get user info for logging
        cursor.execute("SELECT Username FROM users WHERE U_ID = %s", (user_id,))
        user = cursor.fetchone()

        # FIX: First check if records exist and clean up duplicates
        cursor.execute("""
            DELETE r1 FROM running_tally r1
            LEFT JOIN (
                SELECT U_ID, MAX(From_date) as max_date 
                FROM running_tally 
                WHERE U_ID = %s 
                GROUP BY U_ID
            ) r2 ON r1.U_ID = r2.U_ID AND r1.From_date = r2.max_date
            WHERE r1.U_ID = %s AND r2.max_date IS NULL
        """, (user_id, user_id))

        # Now update the single remaining record
        cursor.execute("""
            UPDATE running_tally 
            SET Score = %s 
            WHERE U_ID = %s
        """, (weekly_points, user_id))

        # If no running_tally record exists after cleanup, create one
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO running_tally (U_ID, Score, From_date) 
                VALUES (%s, %s, NOW())
            """, (user_id, weekly_points))

        # For total_tally - DELETE duplicates and keep only one
        cursor.execute("DELETE FROM total_tally WHERE U_ID = %s", (user_id,))

        # Insert single record
        cursor.execute("""
            INSERT INTO total_tally (U_ID, Score) 
            VALUES (%s, %s)
        """, (user_id, total_points))

        conn.commit()

        # Log points edit activity
        log_activity(superadmin_id, 'points_edit',
                     f'SuperAdmin manually updated points for {user[0]}: Weekly={weekly_points}, Total={total_points}')

        flash(f'Points updated successfully for user ID {user_id}!', 'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Error updating points: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()


@app.route('/capstone/superadmin/get_user_points/<int:user_id>', methods=['GET'])
@login_required
def Plastrack_SuperAdmin_Get_User_Points(user_id):
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get weekly points - get the most recent record
        cursor.execute("""
            SELECT Score 
            FROM running_tally 
            WHERE U_ID = %s 
            ORDER BY From_date DESC 
            LIMIT 1
        """, (user_id,))
        weekly_result = cursor.fetchone()
        weekly_points = weekly_result['Score'] if weekly_result else 0

        # Get total points
        cursor.execute("""
            SELECT Score 
            FROM total_tally 
            WHERE U_ID = %s 
            LIMIT 1
        """, (user_id,))
        total_result = cursor.fetchone()
        total_points = total_result['Score'] if total_result else 0

        return jsonify({
            'weekly_points': weekly_points,
            'total_points': total_points
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()


@app.route('/capstone/superadmin/promote_to_admin/<int:user_id>', methods=['POST'])
@login_required
def Plastrack_SuperAdmin_Promote_To_Admin(user_id):
    try:
        superadmin_id = session.get('U_ID')
        conn = mysql.connect()
        cursor = conn.cursor()

        # Prevent changing your own role
        if user_id == session.get('U_ID'):
            flash('You cannot change your own role.', 'error')
            return redirect('/capstone/superadmin/dashboard')

        # Can only promote regular users (role 0 or NULL)
        cursor.execute("SELECT U_Role, Username FROM users WHERE U_ID = %s", (user_id,))
        user = cursor.fetchone()

        if user and user[0] not in [0, None]:
            flash('Can only promote regular users to admin.', 'error')
            return redirect('/capstone/superadmin/dashboard')

        cursor.execute("UPDATE users SET U_Role = %s WHERE U_ID = %s", (1, user_id))
        conn.commit()

        # Log promotion activity
        log_activity(superadmin_id, 'role_change', f'SuperAdmin promoted {user[1]} to Admin')

        flash('User promoted to admin successfully!', 'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Error promoting user: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()


@app.route('/capstone/superadmin/demote_to_user/<int:user_id>', methods=['POST'])
@login_required
def Plastrack_SuperAdmin_Demote_To_User(user_id):
    try:
        superadmin_id = session.get('U_ID')
        conn = mysql.connect()
        cursor = conn.cursor()

        # Prevent changing your own role
        if user_id == session.get('U_ID'):
            flash('You cannot change your own role.', 'error')
            return redirect('/capstone/superadmin/dashboard')

        # Can only demote admins (role 1) to regular users
        cursor.execute("SELECT U_Role, Username FROM users WHERE U_ID = %s", (user_id,))
        user = cursor.fetchone()

        if not user or user[0] != 1:
            flash('Can only demote admins to regular users.', 'error')
            return redirect('/capstone/superadmin/dashboard')

        cursor.execute("UPDATE users SET U_Role = %s WHERE U_ID = %s", (0, user_id))
        conn.commit()

        # Log demotion activity
        log_activity(superadmin_id, 'role_change', f'SuperAdmin demoted {user[1]} to User')

        flash('Admin demoted to user successfully!', 'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Error demoting admin: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()


@app.route('/capstone/superadmin/create_admin', methods=['POST'])
@login_required
def Plastrack_SuperAdmin_Create_Admin():
    try:
        Form = request.form
        First_Name = Form['U_Fname']
        Last_Name = Form['U_Lname']
        Username = Form['Username']
        Password = Form['Password']
        superadmin_id = session.get('U_ID')

        if not all([First_Name, Last_Name, Username, Password]):
            flash('Please fill in all fields.', 'error')
            return redirect('/capstone/superadmin/dashboard')

        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Check if username already exists
        cursor.execute('SELECT * FROM users WHERE Username = %s', (Username,))
        if cursor.fetchone():
            flash('Username already exists!', 'error')
            return redirect('/capstone/superadmin/dashboard')

        # Insert as admin (U_Role = 1)
        sqlQuery = """
            INSERT INTO users (U_Fname, U_Lname, Username, Password, U_Role, Approved, U_Status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        bindData = (First_Name, Last_Name, Username, Password, 1, 1, 1)
        cursor.execute(sqlQuery, bindData)
        conn.commit()

        # Log admin creation
        log_activity(superadmin_id, 'user_creation', f'SuperAdmin created new admin user: {Username}')

        flash(f'Admin user {Username} created successfully!', 'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Error creating admin: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()


@app.route('/capstone/superadmin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def Plastrack_SuperAdmin_Delete_User(user_id):
    try:
        superadmin_id = session.get('U_ID')
        conn = mysql.connect()
        cursor = conn.cursor()

        # Prevent deleting yourself
        if user_id == session.get('U_ID'):
            flash('You cannot delete your own account.', 'error')
            return redirect('/capstone/superadmin/dashboard')

        # Get user info for logging
        cursor.execute("SELECT Username FROM users WHERE U_ID = %s", (user_id,))
        user = cursor.fetchone()

        cursor.execute("DELETE FROM users WHERE U_ID = %s", (user_id,))
        conn.commit()

        # Log user deletion
        if user:
            log_activity(superadmin_id, 'user_management', f'SuperAdmin deleted user: {user[0]}')

        flash('User deleted successfully!', 'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()


@app.route('/capstone/superadmin/reset_system', methods=['POST'])
@login_required
def Plastrack_SuperAdmin_Reset_System():
    try:
        superadmin_id = session.get('U_ID')
        conn = mysql.connect()
        cursor = conn.cursor()

        # Get the default stock value from system settings
        cursor.execute("SELECT setting_value FROM system_settings WHERE setting_name = 'default_stock'")
        default_stock_result = cursor.fetchone()
        default_stock = default_stock_result[0] if default_stock_result else 100

        print(f"Using default stock value: {default_stock}")

        # Reset all points and purchase history
        cursor.execute("DELETE FROM running_tally")
        cursor.execute("DELETE FROM total_tally")
        cursor.execute("DELETE FROM purchase_history")
        cursor.execute("UPDATE product SET P_QTY = %s", (default_stock,))  # Use system setting

        conn.commit()

        # Log system reset
        log_activity(superadmin_id, 'system_action',
                     f'Super Admin performed full system reset. Stock reset to {default_stock}')

        flash(f'System reset successfully! All points and history cleared. Stock reset to {default_stock}.', 'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        flash(f'Error resetting system: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@app.route('/capstone/superadmin/analytics/top_contributors', methods=['GET'])
@login_required
def Plastrack_Get_Top_Contributors():
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get top contributors based on total points
        cursor.execute("""
            SELECT 
                u.U_ID,
                u.U_Fname,
                u.U_Lname,
                u.Username,
                COALESCE(tt.Score, 0) as Total_Points,
                COALESCE(tt.Score, 0) as Bottles_Recycled  -- Assuming 1 point = 1 bottle
            FROM users u
            LEFT JOIN total_tally tt ON u.U_ID = tt.U_ID
            WHERE u.U_Role = 0 OR u.U_Role IS NULL
            ORDER BY Total_Points DESC
            LIMIT 5
        """)
        top_contributors = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(top_contributors)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/capstone/superadmin/analytics/top_buyers', methods=['GET'])
@login_required
def Plastrack_Get_Top_Buyers():
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get top buyers based on purchase history
        cursor.execute("""
            SELECT 
                u.U_ID,
                u.U_Fname,
                u.U_Lname,
                u.Username,
                COUNT(ph.Purchase_ID) as Total_Purchases,
                SUM(ph.Quantity * p.P_Price) as Total_Spent
            FROM users u
            JOIN purchase_history ph ON u.U_ID = ph.U_ID
            JOIN product p ON ph.P_ID = p.P_ID
            WHERE u.U_Role = 0 OR u.U_Role IS NULL
            GROUP BY u.U_ID, u.U_Fname, u.U_Lname, u.Username
            ORDER BY Total_Spent DESC
            LIMIT 5
        """)
        top_buyers = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(top_buyers)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/capstone/superadmin/analytics/most_bought_items', methods=['GET'])
@login_required
def Plastrack_Get_Most_Bought_Items():
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get most purchased products
        cursor.execute("""
            SELECT 
                p.P_Name,
                SUM(ph.Quantity) as Total_Sold,
                SUM(ph.Quantity * p.P_Price) as Total_Revenue
            FROM product p
            JOIN purchase_history ph ON p.P_ID = ph.P_ID
            GROUP BY p.P_ID, p.P_Name
            ORDER BY Total_Sold DESC
            LIMIT 10
        """)
        most_bought = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(most_bought)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/capstone/superadmin/analytics/weekly_activity', methods=['GET'])
@login_required
def Plastrack_Get_Weekly_Activity():
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get weekly activity (last 7 days)
        cursor.execute("""
            SELECT 
                DATE(activity_timestamp) as activity_date,
                COUNT(*) as activity_count
            FROM activities 
            WHERE activity_type = 'bottle_scan'
            AND activity_timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(activity_timestamp)
            ORDER BY activity_date
        """)
        weekly_data = cursor.fetchall()

        # Create full week data
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        default_data = {day: 0 for day in days}

        for row in weekly_data:
            day_name = row['activity_date'].strftime('%a')
            default_data[day_name] = row['activity_count']

        cursor.close()
        conn.close()

        return jsonify({
            'labels': days,
            'data': [default_data[day] for day in days]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/capstone/superadmin/analytics/monthly_activity', methods=['GET'])
@login_required
def Plastrack_Get_Monthly_Activity():
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get monthly activity (last 4 weeks)
        cursor.execute("""
            SELECT 
                CONCAT('Week ', WEEK(activity_timestamp) - WEEK(DATE_SUB(NOW(), INTERVAL 1 MONTH)) + 1) as week_label,
                COUNT(*) as activity_count
            FROM activities 
            WHERE activity_type = 'bottle_scan'
            AND activity_timestamp >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
            GROUP BY WEEK(activity_timestamp)
            ORDER BY WEEK(activity_timestamp)
            LIMIT 4
        """)
        monthly_data = cursor.fetchall()

        cursor.close()
        conn.close()

        labels = [row['week_label'] for row in monthly_data]
        data = [row['activity_count'] for row in monthly_data]

        return jsonify({
            'labels': labels,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/capstone/superadmin/analytics/points_distribution', methods=['GET'])
@login_required
def Plastrack_Get_Points_Distribution():
    try:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get points distribution over last 6 months
        cursor.execute("""
            SELECT 
                DATE_FORMAT(activity_timestamp, '%Y-%m') as month,
                COUNT(*) as points_earned
            FROM activities 
            WHERE activity_type = 'bottle_scan'
            AND activity_timestamp >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(activity_timestamp, '%Y-%m')
            ORDER BY month
        """)
        points_data = cursor.fetchall()

        cursor.close()
        conn.close()

        labels = [row['month'] for row in points_data]
        data = [row['points_earned'] for row in points_data]

        return jsonify({
            'labels': labels,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500



# System Settings Routes with Database Integration
@app.route('/capstone/superadmin/update_product_settings', methods=['POST'])
@login_required
def Plastrack_Update_Product_Settings():
    try:
        superadmin_id = session.get('U_ID')
        default_stock = request.form.get('default_stock', 100)
        low_stock_threshold = request.form.get('low_stock_threshold', 10)

        print(f"Updating product settings - Default Stock: {default_stock}, Low Stock Threshold: {low_stock_threshold}")

        conn = mysql.connect()
        cursor = conn.cursor()

        # Update default stock setting
        cursor.execute("""
            INSERT INTO system_settings (setting_name, setting_value, setting_type, description) 
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE setting_value = %s, last_updated = CURRENT_TIMESTAMP
        """, ('default_stock', default_stock, 'integer', 'Default stock quantity for new products', default_stock))

        # Update low stock threshold setting
        cursor.execute("""
            INSERT INTO system_settings (setting_name, setting_value, setting_type, description) 
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE setting_value = %s, last_updated = CURRENT_TIMESTAMP
        """, (
            'low_stock_threshold', low_stock_threshold, 'integer', 'Low stock warning threshold', low_stock_threshold))

        # Verify the update worked
        cursor.execute("SELECT setting_value FROM system_settings WHERE setting_name = 'default_stock'")
        updated_value = cursor.fetchone()
        print(f"Verified default_stock in database: {updated_value[0] if updated_value else 'Not found'}")

        # Update stock of product table
        cursor.execute("UPDATE product SET P_QTY = %s", (default_stock,))

        conn.commit()
        cursor.close()
        conn.close()

        # Log settings update
        log_activity(superadmin_id, 'system_settings',
                     f'SuperAdmin updated product settings: Default stock={default_stock}, Low stock threshold={low_stock_threshold}')

        flash(
            f'Product settings updated successfully! Default stock: {default_stock}, Low stock threshold: {low_stock_threshold}',
            'success')
        return redirect('/capstone/superadmin/dashboard')

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"Error updating product settings: {str(e)}")
        flash(f'Error updating product settings: {str(e)}', 'error')
        return redirect('/capstone/superadmin/dashboard')




# Generate QR code for Mobile Testing
def generate_QR():
    url = "http://192.168.254.103:8080" #Change IP depending on the current wifi ur connected to
    qr = qrcode.QRCode(version=2, error_correction=ERROR_CORRECT_H, box_size=1, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)  # prints QR in terminal as ASCII


#RUNNER
if __name__ == "__main__":
    generate_QR()
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=8080)

