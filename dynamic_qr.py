import datetime
import os
import io
import pandas as pd
import qrcode
import secrets
import time
from flask import Flask, request, render_template_string, redirect, send_file, session, url_for

# --- Flask App Configuration ---
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# --- General Configuration ---
TEACHER_PASSWORD = '123'
ATTENDANCE_FILE = 'attendance.csv'

# --- QR Configuration ---
QR_REFRESH_INTERVAL = 15  # seconds

# --- Token Management (with grace period) ---
current_qr_token = secrets.token_urlsafe(8)
previous_qr_token = None
last_qr_refresh = int(time.time())

def get_current_qr_token():
    """Generate or reuse QR token that refreshes every QR_REFRESH_INTERVAL seconds."""
    global current_qr_token, previous_qr_token, last_qr_refresh
    now = int(time.time())
    if now - last_qr_refresh >= QR_REFRESH_INTERVAL:
        previous_qr_token = current_qr_token
        current_qr_token = secrets.token_urlsafe(8)
        last_qr_refresh = now
    return current_qr_token

def is_token_valid(token_from_user):
    """Checks if the provided token is either the current or previous one."""
    get_current_qr_token()
    return token_from_user is not None and (token_from_user == current_qr_token or token_from_user == previous_qr_token)

# --- ADDED: Function to check for duplicate IP addresses for the current day ---
def has_ip_already_attended_today(ip_address):
    """Checks if an IP address has already been logged in the attendance file for today."""
    if not os.path.exists(ATTENDANCE_FILE):
        return False
    
    try:
        df = pd.read_csv(ATTENDANCE_FILE)
        if df.empty:
            return False
            
        # Convert timestamp strings to datetime objects and filter for today's records
        today = datetime.date.today()
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        today_df = df[df['Timestamp'].dt.date == today]
        
        # Check if the IP address is in today's records
        return ip_address in today_df['IP Address'].values

    except (FileNotFoundError, pd.errors.EmptyDataError):
        # If file doesn't exist or is empty, no one has attended yet
        return False
# --- END ADDITION ---


# --- HTML Templates (No changes needed here) ---
STUDENT_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mark Attendance</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; } </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-8 rounded-xl shadow-lg text-center max-w-md w-full">
        <h1 class="text-3xl font-bold text-gray-800">Mark Your Attendance</h1>
        <p class="mt-2 text-gray-600">Enter your full name and MIS number.</p>
        {% if message %}
            <div class="mt-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative" role="alert">
                <span class="block sm:inline">{{ message }}</span>
            </div>
        {% endif %}
        <form method="post" action="/submit_attendance" class="mt-6 text-left">
            <div class="mb-4">
                <label for="student_name" class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input type="text" id="student_name" name="student_name" placeholder="e.g., John Doe" class="w-full p-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500" required>
            </div>
            <div class="mb-6">
                 <label for="student_mis" class="block text-sm font-medium text-gray-700 mb-1">MIS Number</label>
                <input type="text" id="student_mis" name="student_mis" placeholder="e.g., 11223344" class="w-full p-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500" required>
            </div>
            <input type="hidden" name="token" value="{{ token }}">
            <button type="submit" class="w-full bg-indigo-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-indigo-700 transition duration-300 ease-in-out">
                Submit Attendance
            </button>
        </form>
    </div>
</body>
</html>
"""

STUDENT_SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance Marked</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; } </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-8 rounded-xl shadow-lg text-center max-w-md w-full">
        <div class="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100">
            <svg class="h-10 w-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
        </div>
        <h1 class="text-3xl font-bold mt-5 text-gray-800">Attendance Marked!</h1>
        <p class="mt-2 text-gray-600">Your attendance has been recorded successfully.</p>
        <div class="mt-6 text-left bg-gray-50 p-4 rounded-lg border">
            <p class="text-sm text-gray-500">Name: <span class="font-bold text-gray-800">{{ student_name }}</span></p>
            <p class="text-sm text-gray-500 mt-2">MIS: <span class="font-bold text-gray-800">{{ student_mis }}</span></p>
            <p class="text-sm text-gray-500 mt-2">Timestamp: <span class="font-bold text-gray-800">{{ current_time }}</span></p>
        </div>
    </div>
</body>
</html>
"""

TEACHER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Teacher Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; } </style>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto max-w-6xl my-8 px-4">
        {% if not logged_in %}
            <div class="flex items-center justify-center pt-10">
                <div class="bg-white p-8 rounded-xl shadow-lg text-center max-w-sm w-full">
                    <h1 class="text-3xl font-bold text-gray-800">Teacher Login</h1>
                    <form method="post" action="/teacher" class="mt-6 text-left">
                        <label for="password" class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                        <input type="password" id="password" name="password" class="w-full p-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4" required>
                        <button type="submit" class="w-full bg-indigo-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-indigo-700 transition duration-300">Login</button>
                        {% if error %}
                            <p class="text-red-500 mt-3 text-sm text-center">{{ error }}</p>
                        {% endif %}
                    </form>
                </div>
            </div>
        {% else %}
            <header class="flex flex-col md:flex-row justify-between items-center mb-6">
                <h1 class="text-4xl font-bold text-gray-800 mb-4 md:mb-0">Attendance Dashboard</h1>
                <a href="/logout" class="bg-red-500 text-white font-bold py-2 px-4 rounded-lg hover:bg-red-600 transition duration-300">Logout</a>
            </header>
            <main class="space-y-8">
                <div class="bg-blue-100 border-l-4 border-blue-500 text-blue-700 p-4 rounded-lg mb-6" role="alert">
                    <p class="font-bold">Live Update Active</p>
                    <p>This page automatically refreshes the QR every 15 seconds.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="md:col-span-1 bg-white p-6 rounded-xl shadow-md text-center">
                        <h3 class="text-xl font-semibold text-gray-700">Scan to Mark Attendance</h3>
                        <p class="text-gray-500 text-sm mt-1">Share this QR code with students.</p>
                        <img id="qrImage" src="/qr_code" alt="Attendance QR Code" class="mt-4 mx-auto border-4 border-gray-200 shadow-sm rounded-lg">
                    </div>
                    <div class="md:col-span-2 bg-white p-6 rounded-xl shadow-md">
                         <h3 class="text-xl font-semibold text-gray-700">Download Records</h3>
                         <p class="text-gray-500 text-sm mt-1">Get the complete attendance data as a formatted Excel file.</p>
                         <a href="/download_excel" class="inline-block mt-4 bg-green-500 text-white font-bold py-2 px-5 rounded-lg hover:bg-green-600 transition duration-300">
                             Download Excel File
                         </a>
                    </div>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-md">
                    <h3 class="text-2xl font-bold mb-4 text-gray-800">Attendance Log</h3>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">MIS</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">
                                {% for row in attendance_data %}
                                <tr>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ row.get('Name', '') }}</td>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800">{{ row.get('MIS', '') }}</td>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ row.get('Timestamp', '') }}</td>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ row.get('IP Address', '') }}</td>
                                </tr>
                                {% else %}
                                <tr>
                                    <td colspan="4" class="text-center py-10 text-gray-500">No attendance records yet.</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
            
            <script>
                setInterval(function(){
                    document.getElementById("qrImage").src = "/qr_code?ts=" + new Date().getTime();
                }, 15000); // 15 seconds
            </script>

        {% endif %}
    </div>
</body>
</html>
"""

def setup_attendance_file():
    """Checks for the attendance file and creates it with the correct headers if it doesn't exist."""
    if not os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, 'w') as f:
            f.write("Name,MIS,Timestamp,IP Address\n")

@app.route('/qr_code')
def generate_qr():
    token = get_current_qr_token()
    data_to_encode = url_for('student_login', token=token, _external=True)
    img_bytes = io.BytesIO()
    qrcode.make(data_to_encode).save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')

@app.route('/')
@app.route('/student_login')
def student_login():
    token = request.args.get("token")
    if not is_token_valid(token):
        return "QR code expired. Please rescan.", 403
    return render_template_string(STUDENT_LOGIN_TEMPLATE, token=token)

# --- MODIFIED: Added IP address check to this route ---
@app.route('/submit_attendance', methods=['POST'])
def submit_attendance():
    student_name = request.form.get('student_name')
    student_mis = request.form.get('student_mis')
    token = request.form.get('token')

    # 1. Check if token is valid
    if not is_token_valid(token):
        return "Submission time expired. Please rescan the QR code.", 403

    # 2. Check for required fields
    if not student_name or not student_mis:
        return render_template_string(STUDENT_LOGIN_TEMPLATE, message="Both Name and MIS are required.", token=token)

    # 3. Check if IP has already attended today
    client_ip = request.remote_addr
    if has_ip_already_attended_today(client_ip):
        message = "Attendance has already been marked from this device/network for today."
        return render_template_string(STUDENT_LOGIN_TEMPLATE, message=message, token=token)

    # If all checks pass, record the attendance
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(ATTENDANCE_FILE, 'a') as f:
        f.write(f'"{student_name}","{student_mis}",{timestamp},{client_ip}\n')

    return render_template_string(STUDENT_SUCCESS_TEMPLATE, 
                                  student_name=student_name, 
                                  student_mis=student_mis, 
                                  current_time=timestamp)
# --- END MODIFICATION ---

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == TEACHER_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('teacher_dashboard'))
        else:
            error = "Invalid password. Please try again."
    
    if not session.get('logged_in'):
        return render_template_string(TEACHER_TEMPLATE, logged_in=False, error=error)
    
    attendance_data = []
    if os.path.exists(ATTENDANCE_FILE):
        try:
            df = pd.read_csv(ATTENDANCE_FILE)
            df = df.iloc[::-1]
            attendance_data = df.to_dict('records')
        except pd.errors.EmptyDataError:
            attendance_data = []
            
    return render_template_string(TEACHER_TEMPLATE, logged_in=True, attendance_data=attendance_data)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('teacher_dashboard'))

@app.route('/download_excel')
def download_excel():
    if not session.get('logged_in'):
        return "Unauthorized Access", 401
    
    if not os.path.exists(ATTENDANCE_FILE):
        return "No attendance data available to download.", 404
    
    try:
        df = pd.read_csv(ATTENDANCE_FILE)
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, sheet_name='Attendance')
        excel_buffer.seek(0)
        return send_file(
            excel_buffer, 
            as_attachment=True, 
            download_name='attendance_records.xlsx', 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except pd.errors.EmptyDataError:
        return "No attendance data available to download.", 404

if __name__ == '__main__':
    setup_attendance_file()
    app.run(host='0.0.0.0', port=5000, debug=True)