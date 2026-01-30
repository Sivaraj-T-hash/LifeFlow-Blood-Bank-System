# LifeFlow - Blood Bank Management System 🩸

**LifeFlow** is a comprehensive web-based platform designed to bridge the gap between blood donors, hospitals, and blood donation camps. It facilitates real-time communication, donor management, appointment scheduling, and blood stock tracking.

---

## 🚀 Key Modules

### 👤 Donor (User) Module
* **Secure Access**: Registration and login with secure password hashing.
* **Smart Booking**: Schedule slots at hospitals or register for upcoming blood donation camps.
* **Eligibility Engine**: Automated system prevents booking if the last donation was within 90 days.
* **Digital Certificates**: Auto-generated PDF certificates available after donation verification.
* **History Tracking**: View comprehensive logs of all past donations and their status.

### 🏥 Hospital Module
* **Verification System**: Approve or reject manual "Past Donation" logs and verify scheduled appointments.
* **Data Export**: Download donation history and appointment logs in CSV or PDF formats.
* **Inventory Management**: Real-time stock updates based on approved donations.

### ⛺ Camp Host Module
* **Event Scheduling**: Organize and schedule new camps with date, time, and capacity management.
* **Donor Lists**: View and export lists of registered donors for specific camps.
* **Gallery Integration**: Upload photos from completed camps to the public gallery.

### 🛡️ Admin Module (Super Admin)
* **Global Management**: Full control over Donors, Hospitals, and Camp Host accounts.
* **Advanced Reporting**: Generate performance reports and history logs in landscape PDF format.
* **Content Moderation**: Manage the homepage gallery and site-wide statistics.

---

## 🌐 Public Features
* **Interactive Map**: View hospitals (Red) and camps (Orange) with live stock and registration data using Leaflet.js.
* **Live Stats**: Real-time tracking of Total Donors, Lives Saved, and Blood Units Collected.
* **Dynamic Gallery**: A carousel showcasing recent successful blood donation camps.

---

## 🛠️ Technology Stack
* **Backend**: Python (Flask)
* **Database**: SQLite (Relational)
* **Frontend**: HTML5, CSS3 (Bootstrap), JavaScript
* **Mapping**: Leaflet.js (OpenStreetMap)
* **PDF Engine**: FPDF
* **Security**: Werkzeug Security (Password Hashing)

---

## 📋 Installation & Setup
1. **Clone the repository**:
   ```bash
   git clone [https://github.com/Sivaraj-T-hash/LifeFlow-Blood-Bank-System.git](https://github.com/Sivaraj-T-hash/LifeFlow-Blood-Bank-System.git)
