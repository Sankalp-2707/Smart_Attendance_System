# Smart_Attendance_System
Smart Attendance System developed with Flask that utilizes dynamic QR codes, time-based tokens, and IP validation for secure and proxy-less attendance. It has a teacher dashboard, student portal, live QR refresh, duplicate IP check, and Excel download of attendance records.

# Smart Attendance System

Web application implemented using Flask that facilitates secure and proxy-free attendance through **dynamic QR codes**, **time-sensitive tokens**, and **IP verification**.

---

##  Features
- **Dynamic QR Code Generation** – Produces a new QR every 15 seconds.  
- ⏳ **Token Validation with Grace Period** – Present and past token accepted to prevent scan delay.
- **IP Address Verification** – Avoids duplicate entries from the same IP.
- **Teacher Dashboard** – Create/manage attendance sessions and download logs.
- **Student Portal** – Easy interface for scanning QR and marking attendance.
- **Excel Export** – Attendance logs downloadable in `.xlsx` format.

---

## Tech Stack
- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **Database:** SQLite
- **Libraries:** `qrcode`, `flask`, `openpyxl`, `secrets`, `datetime`
